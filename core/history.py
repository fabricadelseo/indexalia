"""Histórico de indexación, persistido en data/history.json.

Cada vez que analizas un cliente se guarda:
  - una instantánea resumen (fecha, totales) -> para la gráfica de evolución.
  - el estado por URL -> para detectar cambios respecto al análisis anterior
    (URLs que pasaron a estar indexadas, o que perdieron la indexación).

Estructura:
{
  "snapshots": [
    {"ts": "...", "site_url": "...", "total": 120, "indexed": 90, "not_indexed": 30}
  ],
  "url_state": {
    "sc-domain:cliente.com": {
      "https://cliente.com/x": {"indexed": true, "last_checked": "..."}
    }
  }
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "history.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> dict:
    if not _PATH.exists():
        return {"snapshots": [], "url_state": {}}
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        data.setdefault("snapshots", [])
        data.setdefault("url_state", {})
        return data
    except (json.JSONDecodeError, OSError):
        return {"snapshots": [], "url_state": {}}


def _save(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_snapshot(site_url: str, results: list[dict]) -> dict:
    """Guarda una instantánea y devuelve los cambios respecto al análisis previo.

    `results`: lista de {"url": str, "indexed": bool}.
    Devuelve {"nuevas_indexadas": [...], "perdidas": [...]}.
    """
    data = _load()
    site_state = data["url_state"].setdefault(site_url, {})

    cambios = {"nuevas_indexadas": [], "perdidas": []}
    ts = _now()
    indexed = 0
    for r in results:
        url, is_idx = r["url"], bool(r["indexed"])
        if is_idx:
            indexed += 1
        prev = site_state.get(url)
        if prev is not None:
            if not prev["indexed"] and is_idx:
                cambios["nuevas_indexadas"].append(url)
            elif prev["indexed"] and not is_idx:
                cambios["perdidas"].append(url)
        site_state[url] = {"indexed": is_idx, "last_checked": ts}

    total = len(results)
    data["snapshots"].append(
        {
            "ts": ts,
            "site_url": site_url,
            "total": total,
            "indexed": indexed,
            "not_indexed": total - indexed,
        }
    )
    _save(data)
    return cambios


def snapshots(site_url: str | None = None) -> list[dict]:
    snaps = _load()["snapshots"]
    if site_url is None:
        return snaps
    return [s for s in snaps if s["site_url"] == site_url]
