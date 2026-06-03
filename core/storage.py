"""Cola de URLs — despachador de backend.

Elige automáticamente el backend según la configuración:
  - Si hay `sheet_id` configurado -> Google Sheets (compartido app + cron).
  - Si no -> fichero JSON local (data/queue.json).

Ambos backends exponen la misma interfaz, así que el resto de la app
(app.py, daily_batch.py) no cambia.
"""

from __future__ import annotations

from . import json_backend, sheets_backend


def _backend():
    if sheets_backend.is_enabled():
        return sheets_backend
    return json_backend


def backend_name() -> str:
    return "Google Sheets" if sheets_backend.is_enabled() else "JSON local"


def all_items():
    return _backend().all_items()


def add_urls(urls, site_url):
    return _backend().add_urls(urls, site_url)


def pending(site_url=None):
    return _backend().pending(site_url)


def count_sent_today():
    return _backend().count_sent_today()


def mark(url, status, detail=""):
    return _backend().mark(url, status, detail)


def take_batch(n, site_url=None):
    return _backend().take_batch(n, site_url)


def remove(url):
    return _backend().remove(url)
