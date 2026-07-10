"""Trabajo diario del cron (GitHub Actions):

1. RE-VERIFICA las URLs ya enviadas hace >= RECHECK_AFTER_DAYS: si Google ya
   las indexó las marca 'indexed'; si siguen sin indexar las reencola (pending)
   para reenviarlas. Limitado a RECHECK_LIMIT/día para no gastar cuota.
2. ENVÍA las URLs en proceso a Google respetando el límite por dominio
   (PER_DOMAIN_LIMIT) y el tope global del día (GLOBAL_LIMIT).
3. Si hay key de IndexNow, avisa también a Bing/Yandex.

Uso local:
    python daily_batch.py
"""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict

from core import auth, clients, gsc, indexing, indexnow, settings, storage

PER_DOMAIN = int(os.environ.get("PER_DOMAIN_LIMIT", "10"))       # por dominio/día
GLOBAL_CAP = int(os.environ.get("GLOBAL_LIMIT", "200"))          # tope global/día
RECHECK_AFTER = int(os.environ.get("RECHECK_AFTER_DAYS", "15"))  # re-verificar tras N días
RECHECK_LIMIT = int(os.environ.get("RECHECK_LIMIT", "150"))      # máx re-verificaciones/día


def _routing():
    """Reconstruye el enrutado por cuenta y devuelve (indexing_for, gsc_for).

    El cron tiene todas las cuentas (tokens en secrets), así que sabe qué
    cuenta tiene acceso a cada propiedad para usar las credenciales correctas.
    """
    accs = auth.accounts()
    cmap = {a["name"]: a["creds"] for a in accs}
    site_acc = {}
    try:
        for s in gsc.list_sites_all_accounts(accs):
            site_acc[s["siteUrl"]] = s.get("account")
    except Exception:
        pass
    idx_cache, gsc_cache = {}, {}

    def indexing_for(site_url):
        acc = site_acc.get(site_url)
        if acc not in idx_cache:
            idx_cache[acc] = indexing.make_service(cmap.get(acc))
        return idx_cache[acc]

    def gsc_for(site_url):
        acc = site_acc.get(site_url)
        if acc not in gsc_cache:
            gsc_cache[acc] = gsc.make_service(cmap.get(acc))
        return gsc_cache[acc]

    return indexing_for, gsc_for


def reverificar(gsc_for, retry_days: int, limit: int) -> None:
    """Re-comprueba en Google las URLs enviadas hace >= retry_days.

    Indexadas -> 'indexed'.  Sin indexar -> 'pending' (se reenviarán).
    """
    due = storage.due_for_recheck(retry_days, limit)
    if not due:
        print("Re-verificación: nada pendiente de revisar hoy.")
        return

    print(f"Re-verificando {len(due)} URL(s) enviadas hace >= {retry_days} días…")
    ya_idx = reencoladas = 0
    for it in due:
        r = gsc.inspect_url(it["site_url"], it["url"], service=gsc_for(it["site_url"]))
        if r.error:
            continue  # sin acceso verificado: no tocar
        if r.indexed:
            storage.update_status(it["url"], "indexed", "Indexada (verificada)")
            ya_idx += 1
        else:
            storage.update_status(it["url"], "pending", "reintento (seguía sin indexar)")
            reencoladas += 1
        time.sleep(0.3)
    print(f"  -> {ya_idx} ya indexadas · {reencoladas} reencoladas para reenviar.")


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
    indexing_for, gsc_for = _routing()

    # 1) Re-verificar lo enviado hace tiempo (reencola lo que siga sin indexar).
    reverificar(gsc_for, RECHECK_AFTER, RECHECK_LIMIT)

    # 2) Enviar el lote del día (incluye lo recién reencolado).
    lote = storage.select_to_send(per_domain, global_cap)
    if not lote:
        print("No hay URLs que enviar hoy (cupos cubiertos o cola vacía).")
        return

    print(f"Enviando {len(lote)} URL(s) a Google "
          f"(máx {per_domain}/dominio, tope global {global_cap})…")
    enviadas = []
    for it in lote:
        res = indexing.publish_url(it["url"], service=indexing_for(it["site_url"]))
        ok = res.ok
        storage.mark(it["url"], "sent" if ok else "error", res.detail)
        print(f"  [Google {'OK ' if ok else 'ERR'}] {it['url']} -> {res.detail}")
        if ok:
            enviadas.append(it)

    # 3) IndexNow (gratis, sin tope) para las mismas URLs si hay key.
    _notify_indexnow(enviadas)


if __name__ == "__main__":
    pd = int(sys.argv[1]) if len(sys.argv) > 1 else PER_DOMAIN
    run(pd, GLOBAL_CAP)
