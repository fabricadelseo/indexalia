"""Recarga automática de los módulos de core/ cuando cambian en disco.

En Streamlit Cloud, tras un `git pull` se re-ejecuta app.py pero los módulos
`core/*` ya importados quedan cacheados en sys.modules (con la versión vieja),
lo que obligaba a un Reboot manual. Este módulo detecta si algún fichero de
core/ cambió (por mtime) y hace importlib.reload solo entonces.

Este módulo NO se recarga a sí mismo, así su estado (última mtime vista)
persiste entre reruns.
"""

from __future__ import annotations

import glob
import importlib
import os
import sys

_CORE_DIR = os.path.dirname(__file__)
_state = {"mtime": 0.0}

# Orden de recarga: dependencias "hoja" primero, dependientes después.
_MODS = [
    "core.settings", "core.clients", "core.indexnow", "core.sitemap",
    "core.history", "core.access", "core.auth", "core.json_backend",
    "core.sheets_backend", "core.accounts_store", "core.gsc",
    "core.indexing", "core.storage",
]


def reload_if_changed() -> None:
    files = glob.glob(os.path.join(_CORE_DIR, "*.py"))
    latest = max((os.path.getmtime(f) for f in files), default=0.0)

    # Recarga si algún fichero es más nuevo que la última marca vista.
    # (mtime empieza en 0, así la primera llamada del proceso también recarga,
    #  aplicando cambios traídos por un git pull sin necesidad de reboot.)
    if latest <= _state["mtime"]:
        return

    _state["mtime"] = latest
    for name in _MODS:
        mod = sys.modules.get(name)
        if mod is not None:
            try:
                importlib.reload(mod)
            except Exception:
                pass
