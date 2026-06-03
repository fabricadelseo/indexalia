"""Ajustes simples persistidos en data/settings.json.

Guarda cosas no secretas o de conveniencia: la key de IndexNow, el ID
de la hoja de Google Sheets, etc. Para valores sensibles en cloud,
prioriza variables de entorno / st.secrets (ver core.sheets_backend).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"


def _load() -> dict:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def get(key: str, default=None):
    # Prioridad: variable de entorno > st.secrets > settings.json > default
    env = os.environ.get(key.upper())
    if env:
        return env
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return _load().get(key, default)


def set_(key: str, value) -> None:
    data = _load()
    data[key] = value
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
