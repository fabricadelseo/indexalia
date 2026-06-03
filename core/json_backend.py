"""Backend de la cola en fichero JSON local (data/queue.json).

Implementación por defecto cuando NO hay Google Sheets configurado.
Misma interfaz que core.sheets_backend.

NOTA: el disco de Streamlit Community Cloud es efímero (se borra al
redeplegar). Para algo persistente y compartido con el cron, usa el
backend de Google Sheets (configura `sheet_id`).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_QUEUE_PATH = Path(__file__).resolve().parent.parent / "data" / "queue.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> list[dict]:
    if not _QUEUE_PATH.exists():
        return []
    try:
        return json.loads(_QUEUE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: list[dict]) -> None:
    _QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _QUEUE_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def all_items() -> list[dict]:
    return _load()


def add_urls(urls: list[str], site_url: str) -> int:
    """Añade URLs a la cola evitando duplicados aún pendientes. Devuelve cuántas se añadieron."""
    items = _load()
    # Evita duplicar URLs ya en proceso o ya enviadas (no re-encolar lo enviado).
    existing = {it["url"] for it in items if it["status"] in ("pending", "sent")}
    added = 0
    for url in urls:
        if url in existing:
            continue
        items.append(
            {
                "url": url,
                "site_url": site_url,
                "status": "pending",
                "added_at": _now(),
                "sent_at": None,
                "detail": "",
            }
        )
        added += 1
    _save(items)
    return added


def pending(site_url: str | None = None) -> list[dict]:
    items = _load()
    return [
        it for it in items
        if it["status"] == "pending" and (site_url is None or it["site_url"] == site_url)
    ]


def count_sent_today() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(
        1 for it in _load()
        if it["status"] == "sent" and (it.get("sent_at") or "").startswith(today)
    )


def mark(url: str, status: str, detail: str = "") -> None:
    items = _load()
    for it in items:
        if it["url"] == url and it["status"] == "pending":
            it["status"] = status
            it["sent_at"] = _now()
            it["detail"] = detail
            break
    _save(items)


def take_batch(n: int, site_url: str | None = None) -> list[dict]:
    """Devuelve las primeras n URLs pendientes (sin marcarlas todavía)."""
    return pending(site_url)[:n]


def remove(url: str) -> None:
    items = [it for it in _load() if it["url"] != url]
    _save(items)
