"""Gestión de clientes: nombres amigables para las propiedades de GSC.

Las propiedades reales se obtienen de la API (core.gsc.list_sites), pero
sus identificadores son feos (p. ej. "sc-domain:zapatos.com"). Aquí
guardamos un mapa  site_url -> nombre amigable  en data/clients.json,
para que en el desplegable veas "Zapatería Pepe" en lugar del id.
"""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "clients.json"


def load_names() -> dict[str, str]:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(names: dict[str, str]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")


def set_name(site_url: str, name: str) -> None:
    names = load_names()
    if name.strip():
        names[site_url] = name.strip()
    else:
        names.pop(site_url, None)
    _save(names)


def label_for(site_url: str) -> str:
    """Etiqueta a mostrar: 'Nombre amigable — site_url' o solo el site_url."""
    name = load_names().get(site_url)
    return f"{name} — {site_url}" if name else site_url


def domain_from_site_url(site_url: str) -> str:
    """Extrae el dominio plano de un site_url de GSC (para leer el sitemap)."""
    if site_url.startswith("sc-domain:"):
        return site_url.split(":", 1)[1]
    return site_url  # los de prefijo de URL ya sirven tal cual para el sitemap
