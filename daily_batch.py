"""Envío diario escalonado (drip-feed) — Google Indexing API + IndexNow.

Pensado para ejecutarse SOLO una vez al día desde GitHub Actions (cron).
1. Coge hasta DAILY_LIMIT URLs pendientes de la cola y las envía a Google,
   respetando el cupo de las ya enviadas hoy (drip-feed).
2. Si hay key de IndexNow configurada, además avisa a Bing/Yandex de esas
   mismas URLs (gratis y sin límite, por eso se hace siempre que haya key).

Uso local:
    python daily_batch.py [limite]
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

from core import clients, indexing, indexnow, settings, storage

DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "3"))


def _notify_indexnow(enviadas: list[dict]) -> None:
    """Avisa a IndexNow de las URLs enviadas, agrupadas por dominio."""
    key = settings.get("indexnow_key")
    if not key or not enviadas:
        return
    por_dominio: dict[str, list[str]] = defaultdict(list)
    for it in enviadas:
        dominio = clients.domain_from_site_url(it["site_url"])
        por_dominio[dominio].append(it["url"])

    for dominio, urls in por_dominio.items():
        res = indexnow.submit_urls(dominio, urls, key)
        estado = "OK " if res.ok else "ERR"
        print(f"  [IndexNow {estado}] {dominio} ({len(urls)} URLs) -> {res.detail}")


def run(limit: int = DAILY_LIMIT) -> None:
    sent_today = storage.count_sent_today()
    restante = max(0, limit - sent_today)
    if restante == 0:
        print(f"Cupo diario de Google agotado ({sent_today}/{limit}). Nada que hacer.")
        return

    lote = storage.take_batch(restante)
    if not lote:
        print("No hay URLs pendientes en la cola.")
        return

    print(f"Enviando {len(lote)} URL(s) a Google (cupo restante {restante}/{limit})…")
    enviadas = []
    for it in lote:
        res = indexing.publish_url(it["url"])
        ok = res.ok
        storage.mark(it["url"], "sent" if ok else "error", res.detail)
        print(f"  [Google {'OK ' if ok else 'ERR'}] {it['url']} -> {res.detail}")
        if ok:
            enviadas.append(it)

    # IndexNow es gratis y sin tope: avisamos de las mismas URLs si hay key.
    _notify_indexnow(enviadas)


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else DAILY_LIMIT
    run(lim)
