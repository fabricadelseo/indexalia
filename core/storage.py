"""Cola de URLs — despachador de backend.

Elige automáticamente el backend según la configuración:
  - Si hay `sheet_id` configurado -> Google Sheets (compartido app + cron).
  - Si no -> fichero JSON local (data/queue.json).

Ambos backends exponen la misma interfaz, así que el resto de la app
(app.py, daily_batch.py) no cambia.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import json_backend, sheets_backend


def _backend():
    if sheets_backend.is_enabled():
        return sheets_backend
    return json_backend


def backend_name() -> str:
    return "Google Sheets" if sheets_backend.is_enabled() else "JSON local"


def all_items():
    return _backend().all_items()


def add_urls(urls, site_url, retry_days=None):
    return _backend().add_urls(urls, site_url, retry_days)


def pending(site_url=None):
    return _backend().pending(site_url)


def count_sent_today():
    return _backend().count_sent_today()


def mark(url, status, detail=""):
    return _backend().mark(url, status, detail)


def take_batch(n, site_url=None):
    return _backend().take_batch(n, site_url)


def due_for_recheck(retry_days, limit):
    return _backend().due_for_recheck(retry_days, limit)


def update_status(url, status, detail=""):
    return _backend().update_status(url, status, detail)


def remove(url):
    return _backend().remove(url)


def sent_today_by_site() -> dict:
    """{site_url: nº enviadas hoy} (para respetar el límite por dominio)."""
    today = datetime.now(timezone.utc).date().isoformat()
    out: dict = {}
    for it in all_items():
        if it["status"] == "sent" and (it.get("sent_at") or "").startswith(today):
            out[it["site_url"]] = out.get(it["site_url"], 0) + 1
    return out


def select_to_send(per_domain: int, global_cap: int) -> list[dict]:
    """Elige las URLs en proceso a enviar hoy respetando:
       - como máximo `per_domain` por cada dominio (contando lo ya enviado hoy),
       - y un tope global diario `global_cap` (límite de Google).
    """
    items = all_items()
    today = datetime.now(timezone.utc).date().isoformat()

    enviadas_hoy_total = sum(
        1 for it in items
        if it["status"] == "sent" and (it.get("sent_at") or "").startswith(today)
    )
    por_dominio = sent_today_by_site()
    global_rest = max(0, global_cap - enviadas_hoy_total)

    seleccion: list[dict] = []
    contador = dict(por_dominio)
    for it in items:
        if len(seleccion) >= global_rest:
            break
        if it["status"] != "pending":
            continue
        s = it["site_url"]
        if contador.get(s, 0) >= per_domain:
            continue
        seleccion.append(it)
        contador[s] = contador.get(s, 0) + 1
    return seleccion
