"""Backend de la cola sobre Google Sheets (misma interfaz que core.storage).

Ventaja frente a queue.json: la app (Streamlit) y el cron (GitHub Actions)
comparten EXACTAMENTE la misma cola en tiempo real, sin problemas de disco
efímero ni de commits.

Estructura de la hoja (pestaña "queue"), fila 1 = cabecera:
    A:url  B:site_url  C:status  D:added_at  E:sent_at  F:detail

Configuración:
    - Crea una hoja de cálculo en Google Sheets.
    - Compártela con el email de la cuenta de servicio (permiso Editor).
    - Guarda su ID (el trozo de la URL entre /d/ y /edit) como ajuste
      `sheet_id` (env SHEET_ID, st.secrets, o data/settings.json).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from googleapiclient.discovery import build

from .auth import get_credentials
from . import settings


def _age_days(ts: str | None) -> float:
    if not ts:
        return 10**9
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return 10**9
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400

_TAB = "queue"
_HEADER = ["url", "site_url", "status", "added_at", "sent_at", "detail"]


def is_enabled() -> bool:
    return bool(settings.get("sheet_id"))


def _svc():
    creds = get_credentials()
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _sheet_id() -> str:
    sid = settings.get("sheet_id")
    if not sid:
        raise RuntimeError("No hay 'sheet_id' configurado para el backend de Sheets.")
    return sid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Caché corta para no exceder la cuota de lecturas de Sheets (~60/min).
_CACHE = {"rows": None, "ts": 0.0}
_TTL = 30.0


def _invalidate() -> None:
    _CACHE["rows"] = None


def _ensure_header(svc) -> None:
    """Crea la cabecera si la hoja está vacía."""
    rng = f"{_TAB}!A1:F1"
    resp = svc.spreadsheets().values().get(spreadsheetId=_sheet_id(), range=rng).execute(num_retries=5)
    if not resp.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=_sheet_id(),
            range=rng,
            valueInputOption="RAW",
            body={"values": [_HEADER]},
        ).execute(num_retries=5)


def _rows(force: bool = False) -> list[list[str]]:
    now = time.monotonic()
    if not force and _CACHE["rows"] is not None and (now - _CACHE["ts"]) < _TTL:
        return _CACHE["rows"]
    svc = _svc()
    _ensure_header(svc)
    resp = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:F")
        .execute(num_retries=5)
    )
    data = resp.get("values", [])
    _CACHE["rows"] = data
    _CACHE["ts"] = now
    return data


def _to_dict(row: list[str]) -> dict:
    row = (row + [""] * 6)[:6]
    return dict(zip(_HEADER, row))


def all_items() -> list[dict]:
    return [_to_dict(r) for r in _rows()]


def add_urls(urls: list[str], site_url: str, retry_days: int | None = None) -> int:
    """Encola URLs no indexadas (nuevas + reintentos tras retry_days sin indexar).

    - 'pending' -> se ignora.
    - 'sent'/'error' con antigüedad >= retry_days -> se reintenta (su fila vuelve
      a 'pending', sin duplicar).
    - 'sent'/'error' reciente -> se ignora.
    """
    if retry_days is None:
        retry_days = int(settings.get("retry_days", 15))

    svc = _svc()
    _ensure_header(svc)
    rows = _rows()
    index = {}
    for i, r in enumerate(rows):
        d = _to_dict(r)
        index[d["url"]] = (i + 2, d)  # fila real (cabecera = 1)

    new_rows = []
    added = 0
    for url in urls:
        if url in index:
            row_num, d = index[url]
            if d["status"] == "pending":
                continue
            if _age_days(d.get("sent_at")) >= retry_days:
                svc.spreadsheets().values().update(
                    spreadsheetId=_sheet_id(),
                    range=f"{_TAB}!A{row_num}:F{row_num}",
                    valueInputOption="RAW",
                    body={"values": [[
                        url, d["site_url"] or site_url, "pending", _now(), "",
                        "reintento (seguía sin indexar)",
                    ]]},
                ).execute(num_retries=5)
                added += 1
        else:
            new_rows.append([url, site_url, "pending", _now(), "", ""])
            added += 1

    if new_rows:
        svc.spreadsheets().values().append(
            spreadsheetId=_sheet_id(),
            range=f"{_TAB}!A2:F",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": new_rows},
        ).execute(num_retries=5)
    _invalidate()
    return added


def pending(site_url: str | None = None) -> list[dict]:
    return [
        it for it in all_items()
        if it["status"] == "pending" and (site_url is None or it["site_url"] == site_url)
    ]


def count_sent_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(
        1 for it in all_items()
        if it["status"] == "sent" and (it.get("sent_at") or "").startswith(today)
    )


def take_batch(n: int, site_url: str | None = None) -> list[dict]:
    return pending(site_url)[:n]


def mark(url: str, status: str, detail: str = "") -> None:
    svc = _svc()
    rows = _rows()
    ahora = _now()
    for i, row in enumerate(rows):
        d = _to_dict(row)
        if d["url"] == url and d["status"] == "pending":
            row_num = i + 2  # +2: fila 1 cabecera, índice base 0
            svc.spreadsheets().values().update(
                spreadsheetId=_sheet_id(),
                range=f"{_TAB}!C{row_num}:F{row_num}",
                valueInputOption="RAW",
                body={"values": [[status, d["added_at"], ahora, detail]]},
            ).execute(num_retries=5)
            # Actualiza la caché en memoria (rows es el objeto cacheado).
            rows[i] = [d["url"], d["site_url"], status, d["added_at"], ahora, detail]
            return


def due_for_recheck(retry_days: int, limit: int) -> list[dict]:
    """URLs 'sent' con antigüedad >= retry_days (candidatas a re-verificar)."""
    out = []
    for it in all_items():
        if it["status"] == "sent" and _age_days(it.get("sent_at")) >= retry_days:
            out.append(it)
            if len(out) >= limit:
                break
    return out


def update_status(url: str, status: str, detail: str = "") -> None:
    """Actualiza el estado de una URL cualquiera (no solo 'pending')."""
    svc = _svc()
    rows = _rows()
    ahora = _now()
    for i, row in enumerate(rows):
        d = _to_dict(row)
        if d["url"] == url:
            row_num = i + 2
            svc.spreadsheets().values().update(
                spreadsheetId=_sheet_id(),
                range=f"{_TAB}!C{row_num}:F{row_num}",
                valueInputOption="RAW",
                body={"values": [[status, d["added_at"], ahora, detail]]},
            ).execute(num_retries=5)
            rows[i] = [d["url"], d["site_url"], status, d["added_at"], ahora, detail]
            return


def remove(url: str) -> None:
    """Marca como 'removed' (no borra la fila, para mantener el histórico simple)."""
    svc = _svc()
    rows = _rows()
    for i, row in enumerate(rows):
        d = _to_dict(row)
        if d["url"] == url:
            row_num = i + 2
            svc.spreadsheets().values().update(
                spreadsheetId=_sheet_id(),
                range=f"{_TAB}!C{row_num}",
                valueInputOption="RAW",
                body={"values": [["removed"]]},
            ).execute(num_retries=5)
            _invalidate()
            return
