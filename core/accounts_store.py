"""Persistencia de cuentas OAuth adicionales en la hoja de Google Sheets.

En la nube el disco es efímero, así que las cuentas que conectes desde la app
se guardan en una pestaña 'accounts' de la misma hoja (sheet_id):
    A = email   B = token_json

Se usa la credencial principal (la dueña de la hoja) para leer/escribir.
"""

from __future__ import annotations

import time

from googleapiclient.discovery import build

from . import settings

_TAB = "accounts"
_HEADER = ["email", "token_json"]

_CACHE = {"data": None, "ts": 0.0}
_TTL = 30.0


def _invalidate() -> None:
    _CACHE["data"] = None


def is_enabled() -> bool:
    return bool(settings.get("sheet_id"))


def _svc(creds):
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _sheet_id() -> str:
    return settings.get("sheet_id")


def _ensure_tab(svc) -> None:
    sid = _sheet_id()
    meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
    tabs = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if _TAB not in tabs:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sid,
            body={"requests": [{"addSheet": {"properties": {"title": _TAB}}}]},
        ).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=sid, range=f"{_TAB}!A1:B1",
            valueInputOption="RAW", body={"values": [_HEADER]},
        ).execute()


def list_tokens(creds) -> list[tuple[str, str]]:
    """Devuelve [(email, token_json)] guardados en la hoja (cacheado)."""
    if not is_enabled():
        return []
    now = time.monotonic()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < _TTL:
        return _CACHE["data"]
    try:
        svc = _svc(creds)
        _ensure_tab(svc)
        resp = svc.spreadsheets().values().get(
            spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:B"
        ).execute()
        out = []
        for row in resp.get("values", []):
            if len(row) >= 2 and row[0] and row[1]:
                out.append((row[0], row[1]))
        _CACHE["data"] = out
        _CACHE["ts"] = now
        return out
    except Exception:
        return _CACHE["data"] or []


def save_token(creds, email: str, token_json: str) -> None:
    svc = _svc(creds)
    _ensure_tab(svc)
    rows = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:B"
    ).execute().get("values", [])
    # ¿Existe ya? -> actualiza esa fila; si no, añade.
    for i, row in enumerate(rows):
        if row and row[0] == email:
            svc.spreadsheets().values().update(
                spreadsheetId=_sheet_id(), range=f"{_TAB}!A{i + 2}:B{i + 2}",
                valueInputOption="RAW", body={"values": [[email, token_json]]},
            ).execute()
            _invalidate()
            return
    svc.spreadsheets().values().append(
        spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:B",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": [[email, token_json]]},
    ).execute()
    _invalidate()


def delete(creds, email: str) -> None:
    svc = _svc(creds)
    rows = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:B"
    ).execute().get("values", [])
    keep = [r for r in rows if not (r and r[0] == email)]
    svc.spreadsheets().values().clear(
        spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:B"
    ).execute()
    if keep:
        svc.spreadsheets().values().update(
            spreadsheetId=_sheet_id(), range=f"{_TAB}!A2:B",
            valueInputOption="RAW", body={"values": keep},
        ).execute()
    _invalidate()
