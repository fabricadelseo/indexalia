"""Crea la hoja de Google Sheets para la cola compartida. Ejecuta:

    python crear_hoja.py

Crea una hoja nueva en tu Google Drive con la pestaña 'queue' y guarda su ID
en data/settings.json (para que la app local ya use Sheets). Imprime el ID
para los secrets de Streamlit y GitHub.
"""

from googleapiclient.discovery import build

from core import settings
from core.auth import get_credentials

HEADER = ["url", "site_url", "status", "added_at", "sent_at", "detail"]


def main() -> int:
    svc = build("sheets", "v4", credentials=get_credentials(), cache_discovery=False)
    body = {
        "properties": {"title": "Indexalia - cola de indexacion"},
        "sheets": [{"properties": {"title": "queue"}}],
    }
    res = svc.spreadsheets().create(body=body, fields="spreadsheetId").execute()
    sid = res["spreadsheetId"]

    svc.spreadsheets().values().update(
        spreadsheetId=sid,
        range="queue!A1:F1",
        valueInputOption="RAW",
        body={"values": [HEADER]},
    ).execute()

    settings.set_("sheet_id", sid)

    print("OK: hoja creada.")
    print("sheet_id:", sid)
    print("URL: https://docs.google.com/spreadsheets/d/" + sid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
