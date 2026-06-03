"""Elimina filas duplicadas de la hoja (deja 1 por URL). Ejecuta:

    python limpiar_hoja.py

Conserva, para cada URL, la fila con el estado más avanzado:
sent (enviada) > pending (en proceso) > error.
"""

from googleapiclient.discovery import build

from core import sheets_backend as sb
from core.auth import get_credentials

PRIO = {"sent": 3, "pending": 2, "error": 1, "removed": 0}


def main() -> int:
    if not sb.is_enabled():
        print("No hay sheet_id configurado (data/settings.json).")
        return 1

    svc = build("sheets", "v4", credentials=get_credentials(), cache_discovery=False)
    sid = sb._sheet_id()
    rows = sb._rows()

    best, order = {}, []
    for r in rows:
        r = (r + [""] * 6)[:6]
        url = r[0]
        if not url:
            continue
        if url not in best:
            best[url] = r
            order.append(url)
        elif PRIO.get(r[2], 0) > PRIO.get(best[url][2], 0):
            best[url] = r

    deduped = [best[u] for u in order]
    quitadas = len(rows) - len(deduped)

    svc.spreadsheets().values().clear(
        spreadsheetId=sid, range="queue!A2:F"
    ).execute()
    if deduped:
        svc.spreadsheets().values().update(
            spreadsheetId=sid,
            range="queue!A2:F",
            valueInputOption="RAW",
            body={"values": deduped},
        ).execute()

    print(f"OK: {len(rows)} filas -> {len(deduped)} (eliminadas {quitadas} duplicadas).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
