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

from datetime import datetime, timezone

from googleapiclient.discovery import build

from .auth import get_credentials
from . import settings

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


def _ensure_header(svc) -> None:
    """Crea la cabecera si la hoja está vacía."""
    rng = f"{_TAB}!A1:F1"
    resp = svc.spreadsheets().values().get(spreadsheetId=_sheet_id(), range=rng).execute()
    if not resp.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=_sheet_id(),
            range=rng,
            valueInputOption="RAW",
            body={"values": [_HEADER]},
        ).execute()


def _rows() -> list[list[str]]:
    svc = _svc()
    _ensure_header(svc)
    resp = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:F")
        .execute()
    )
    return resp.get("values", [])


def _to_dict(row: list[str]) -> dict:
    row = (row + [""] * 6)[:6]
    return dict(zip(_HEADER, row))


def all_items() -> list[dict]:
    return [_to_dict(r) for r in _rows()]


def add_urls(urls: list[str], site_url: str) -> int:
    svc = _svc()
    _ensure_header(svc)
    existing = {it["url"] for it in all_items() if it["status"] == "pending"}
    new_rows = []
    for url in urls:
        if url in existing:
            continue
        new_rows.append([url, site_url, "pending", _now(), "", ""])
    if new_rows:
        svc.spreadsheets().values().append(
            spreadsheetId=_sheet_id(),
            range=f"{_TAB}!A2:F",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": new_rows},
        ).execute()
    return len(new_rows)


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
    for i, row in enumerate(rows):
        d = _to_dict(row)
        if d["url"] == url and d["status"] == "pending":
            row_num = i + 2  # +2: fila 1 cabecera, índice base 0
            svc.spreadsheets().values().update(
                spreadsheetId=_sheet_id(),
                range=f"{_TAB}!C{row_num}:F{row_num}",
                valueInputOption="RAW",
                body={"values": [[status, d["added_at"], _now(), detail]]},
            ).execute()
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
            ).execute()
            return
