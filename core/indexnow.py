"""Cliente de IndexNow (Bing, Yandex, Seznam, Naver — gratis y soportado).

IndexNow es un protocolo abierto: notificas una URL y la comparten todos
los buscadores adheridos. Es la forma 100% legítima de avisar a Bing/Yandex.

Requisito: alojar un fichero de verificación  {key}.txt  en la raíz del
dominio del cliente, cuyo contenido sea exactamente la key. Así el
buscador comprueba que controlas el dominio.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests

_ENDPOINT = "https://api.indexnow.org/indexnow"
_TIMEOUT = 20


@dataclass
class IndexNowResult:
    ok: bool
    status: int
    detail: str


def _host(domain_or_url: str) -> str:
    s = domain_or_url.strip()
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    return urlparse(s).netloc


def key_file_url(domain_or_url: str, key: str) -> str:
    """URL donde debes alojar el fichero de verificación de la key."""
    return f"https://{_host(domain_or_url)}/{key}.txt"


def submit_urls(domain_or_url: str, urls: list[str], key: str) -> IndexNowResult:
    """Envía un lote de URLs a IndexNow (hasta 10.000 por petición)."""
    host = _host(domain_or_url)
    payload = {
        "host": host,
        "key": key,
        "keyLocation": key_file_url(domain_or_url, key),
        "urlList": urls,
    }
    try:
        r = requests.post(_ENDPOINT, json=payload, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return IndexNowResult(False, 0, f"Error de red: {e}")

    # 200 y 202 = aceptado. 422 = URLs no coinciden con el host. 403 = key inválida.
    ok = r.status_code in (200, 202)
    notas = {
        200: "Aceptado",
        202: "Aceptado (pendiente de validar la key)",
        400: "Petición inválida",
        403: "Key inválida o fichero .txt no encontrado",
        422: "Las URLs no pertenecen al host indicado",
        429: "Demasiadas peticiones",
    }
    detail = notas.get(r.status_code, r.text[:200] or "Sin detalle")
    return IndexNowResult(ok, r.status_code, f"{r.status_code} — {detail}")
