"""Envío diario escalonado (drip-feed) — Google Indexing API + IndexNow.

Pensado para ejecutarse SOLO una vez al día desde GitHub Actions (cron).
1. Envía las URLs en proceso a Google respetando el límite por dominio
   (PER_DOMAIN_LIMIT) y el tope global del día (GLOBAL_LIMIT).
2. Si hay key de IndexNow configurada, además avisa a Bing/Yandex de esas
   mismas URLs (gratis y sin límite, por eso se hace siempre que haya key).

Uso local:
    python daily_batch.py [limite]
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

from core import auth, clients, gsc, indexing, indexnow, settings, storage

PER_DOMAIN = int(os.environ.get("PER_DOMAIN_LIMIT", "10"))  # por dominio/día
GLOBAL_CAP = int(os.environ.get("GLOBAL_LIMIT", "200"))     # tope global/día


def _routing():
    """Devuelve (mapa site_url->cuenta, mapa cuenta->servicio_indexing).

    El cron tiene todas las cuentas (tokens en secrets), así que reconstruye
    qué cuenta tiene acceso a cada propiedad para enviar con las credenciales
    correctas.
    """
    accs = auth.accounts()
    cmap = {a["name"]: a["creds"] for a in accs}
    site_acc = {}
    try:
        for s in gsc.list_sites_all_accounts(accs):
            site_acc[s["siteUrl"]] = s.get("account")
    except Exception:
        pass
    svc_cache = {}

    def service_for(site_url):
        acc = site_acc.get(site_url)
        if acc not in svc_cache:
            svc_cache[acc] = indexing.make_service(cmap.get(acc))
        return svc_cache[acc]

    return service_for


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


def run(per_domain: int = PER_DOMAIN, global_cap: int = GLOBAL_CAP) -> None:
    lote = storage.select_to_send(per_domain, global_cap)
    if not lote:
        print("No hay URLs que enviar hoy (cupos cubiertos o cola vacía).")
        return

    print(f"Enviando {len(lote)} URL(s) a Google "
          f"(máx {per_domain}/dominio, tope global {global_cap})…")
    service_for = _routing()
    enviadas = []
    for it in lote:
        res = indexing.publish_url(it["url"], service=service_for(it["site_url"]))
        ok = res.ok
        storage.mark(it["url"], "sent" if ok else "error", res.detail)
        print(f"  [Google {'OK ' if ok else 'ERR'}] {it['url']} -> {res.detail}")
        if ok:
            enviadas.append(it)

    # IndexNow es gratis y sin tope: avisamos de las mismas URLs si hay key.
    _notify_indexnow(enviadas)


if __name__ == "__main__":
    pd = int(sys.argv[1]) if len(sys.argv) > 1 else PER_DOMAIN
    run(pd, GLOBAL_CAP)
