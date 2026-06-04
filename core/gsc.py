"""Cliente de la URL Inspection API de Google Search Console.

Permite saber, para cada URL, si Google la tiene indexada o no.
Requiere que la service account esté añadida como usuario en la
propiedad de Search Console del cliente.

Límites de Google: ~2.000 inspecciones/día y ~600/minuto por propiedad.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import get_credentials


@dataclass
class InspectionResult:
    url: str
    indexed: bool
    coverage_state: str  # texto humano de Google
    verdict: str         # PASS / NEUTRAL / FAIL
    error: str | None = None


def _build_service(creds=None):
    creds = creds or get_credentials()
    # cache_discovery=False evita warnings/escrituras en disco en entornos cloud.
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def make_service(creds=None):
    """Servicio reutilizable (para analizar por tandas sin reconstruirlo)."""
    return _build_service(creds)


def list_sites(creds=None) -> list[dict]:
    """Propiedades accesibles por UNA cuenta (creds). Por defecto, la principal.

    Cada elemento: {"siteUrl": "...", "permissionLevel": "siteOwner"|...}.
    """
    svc = _build_service(creds)
    resp = svc.sites().list().execute()
    return resp.get("siteEntry", [])


def list_sites_all_accounts(accs=None) -> list[dict]:
    """Junta las propiedades de TODAS las cuentas OAuth conectadas.

    Cada elemento añade "account" (email de la cuenta dueña del acceso).
    Si un dominio aparece en varias cuentas, se queda con el de mayor permiso.
    """
    from .auth import accounts

    if accs is None:
        accs = accounts()
    orden = {"siteOwner": 3, "siteFullUser": 2, "siteRestrictedUser": 1, "siteUnverifiedUser": 0}
    mejor: dict[str, dict] = {}
    for acc in accs:
        try:
            sites = list_sites(acc["creds"])
        except Exception:
            continue
        for s in sites:
            su = s["siteUrl"]
            cand = {
                "siteUrl": su,
                "permissionLevel": s.get("permissionLevel", "?"),
                "account": acc["name"],
            }
            prev = mejor.get(su)
            if prev is None or orden.get(cand["permissionLevel"], -1) > orden.get(
                prev["permissionLevel"], -1
            ):
                mejor[su] = cand
    return sorted(mejor.values(), key=lambda x: x["siteUrl"])


def _is_indexed(coverage_state: str, verdict: str) -> bool:
    cs = (coverage_state or "").lower()
    if "not indexed" in cs:
        return False
    if "indexed" in cs:
        return True
    # Respaldo por veredicto si el texto no es concluyente.
    return verdict == "PASS"


def inspect_url(site_url: str, url: str, service=None) -> InspectionResult:
    """Inspecciona una sola URL. `site_url` es la propiedad de GSC.

    Formatos válidos de site_url:
      - "https://cliente.com/"      (prefijo de URL)
      - "sc-domain:cliente.com"     (propiedad de dominio)
    """
    svc = service or _build_service()
    body = {"inspectionUrl": url, "siteUrl": site_url}
    try:
        resp = svc.urlInspection().index().inspect(body=body).execute()
        res = resp.get("inspectionResult", {}).get("indexStatusResult", {})
        coverage = res.get("coverageState", "Desconocido")
        verdict = res.get("verdict", "NEUTRAL")
        return InspectionResult(
            url=url,
            indexed=_is_indexed(coverage, verdict),
            coverage_state=coverage,
            verdict=verdict,
        )
    except HttpError as e:
        return InspectionResult(url, False, "Error", "FAIL", error=str(e))


def inspect_many(site_url: str, urls: list[str], pause: float = 0.5, progress=None, creds=None):
    """Inspecciona varias URLs respetando un pequeño retardo entre llamadas.

    `creds` = credenciales de la cuenta dueña de la propiedad (multi-cuenta).
    `progress` es un callback opcional progress(i, total) para la barra.
    """
    svc = _build_service(creds)
    results: list[InspectionResult] = []
    total = len(urls)
    for i, url in enumerate(urls, start=1):
        results.append(inspect_url(site_url, url, service=svc))
        if progress:
            progress(i, total)
        if i < total:
            time.sleep(pause)
    return results
