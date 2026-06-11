"""Descarga y parseo de sitemaps (incluye índices de sitemaps anidados)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import requests

# Cabeceras de navegador: algunos servidores/WAF devuelven 403/415 si el
# User-Agent no es de navegador o falta la cabecera Accept.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml,text/xml,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}
_TIMEOUT = 20


def _normalize_domain(domain: str) -> str:
    """Acepta 'cliente.com', 'https://cliente.com/' etc. y devuelve la base."""
    domain = domain.strip()
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain
    parsed = urlparse(domain)
    return f"{parsed.scheme}://{parsed.netloc}"


def candidate_sitemaps(domain: str) -> list[str]:
    """URLs típicas donde suele estar el sitemap, más lo que diga robots.txt."""
    base = _normalize_domain(domain)
    found: list[str] = []

    # 1) Leer robots.txt en busca de líneas "Sitemap:"
    try:
        r = requests.get(urljoin(base + "/", "robots.txt"), headers=_HEADERS, timeout=_TIMEOUT)
        if r.ok:
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    found.append(line.split(":", 1)[1].strip())
    except requests.RequestException:
        pass

    # 2) Rutas habituales como respaldo
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        url = base + path
        if url not in found:
            found.append(url)

    return found


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_xml(content: bytes) -> tuple[list[str], list[str]]:
    """Devuelve (urls, sub_sitemaps) a partir del XML de un sitemap."""
    urls: list[str] = []
    subs: list[str] = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return urls, subs

    root_tag = _strip_ns(root.tag)
    for child in root:
        for el in child:
            if _strip_ns(el.tag) == "loc" and el.text:
                loc = el.text.strip()
                if root_tag == "sitemapindex":
                    subs.append(loc)
                else:
                    urls.append(loc)
    return urls, subs


def fetch_urls(domain: str, max_urls: int = 5000) -> tuple[list[str], list[str]]:
    """Devuelve (urls, mensajes_log) recorriendo el/los sitemap(s) del dominio.

    Sigue índices de sitemaps de forma recursiva (con tope de seguridad).
    """
    log: list[str] = []
    seen_urls: set[str] = set()
    pending = candidate_sitemaps(domain)
    visited: set[str] = set()

    while pending and len(seen_urls) < max_urls:
        sm = pending.pop(0)
        if sm in visited:
            continue
        visited.add(sm)
        try:
            r = requests.get(sm, headers=_HEADERS, timeout=_TIMEOUT)
        except requests.RequestException as e:
            log.append(f"⚠️ No se pudo leer {sm}: {e}")
            continue
        if not r.ok:
            log.append(f"⚠️ {sm} devolvió {r.status_code}")
            continue

        urls, subs = _parse_xml(r.content)
        if urls or subs:
            log.append(f"✅ {sm}: {len(urls)} URLs, {len(subs)} sub-sitemaps")
        for u in urls:
            seen_urls.add(u)
        pending.extend(subs)

    if not seen_urls:
        log.append("❌ No se encontraron URLs en ningún sitemap.")

    return sorted(seen_urls)[:max_urls], log
