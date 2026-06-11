"""Descarga y parseo de sitemaps (incluye índices de sitemaps anidados)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import requests

# Excluye espacios, comillas y caracteres de Markdown ()[]<> para no pegar URLs.
_URL_RE = re.compile(r'https?://[^\s<>"\'\)\(\]\[]+', re.I)

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
    data, mode, _status, _via = _fetch(urljoin(base + "/", "robots.txt"))
    if data:
        text = data.decode("utf-8", "ignore") if mode == "xml" else data
        for line in text.splitlines():
            if line.lower().startswith("sitemap:"):
                found.append(line.split(":", 1)[1].strip())

    # 2) Rutas habituales como respaldo
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        url = base + path
        if url not in found:
            found.append(url)

    return found


def _jina(url: str) -> str | None:
    """Lee una URL a través del proxy de lectura Jina (otra IP, evita WAF)."""
    try:
        r = requests.get("https://r.jina.ai/" + url, timeout=35)
        if r.ok and r.text:
            return r.text
    except requests.RequestException:
        return None
    return None


def _fetch(url: str):
    """Descarga una URL. Devuelve (datos, modo, status, via).

    Intenta directo; si el servidor bloquea (WAF/datacenter: 403/415/429/503…),
    reintenta vía proxy de lectura. modo: 'xml' (bytes) | 'text' (str) | None.
    """
    status = None
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if r.ok:
            return r.content, "xml", r.status_code, "directo"
        status = r.status_code
    except requests.RequestException:
        status = None
    txt = _jina(url)
    if txt:
        return txt, "text", status, "proxy"
    return None, None, status, None


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_text(text: str, host: str) -> tuple[list[str], list[str]]:
    """Extrae URLs de texto plano (cuando el proxy quita las etiquetas XML).

    Clasifica como sub-sitemap las que acaban en .xml o contienen 'sitemap'.
    Solo conserva URLs del mismo host (evita ruido del proxy).
    """
    urls: list[str] = []
    subs: list[str] = []
    for raw in _URL_RE.findall(text):
        u = raw.rstrip('.,);]')
        if host and urlparse(u).netloc != host:
            continue
        if u.lower().endswith(".xml") or "sitemap" in u.lower():
            subs.append(u)
        else:
            urls.append(u)
    return urls, subs


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
    host = urlparse(_normalize_domain(domain)).netloc
    pending = candidate_sitemaps(domain)
    visited: set[str] = set()

    while pending and len(seen_urls) < max_urls:
        sm = pending.pop(0)
        if sm in visited:
            continue
        visited.add(sm)

        data, mode, status, via = _fetch(sm)
        if not data:
            log.append(f"⚠️ {sm} no accesible (status {status}).")
            continue

        if mode == "xml":
            urls, subs = _parse_xml(data)
            if not urls and not subs:  # por si vino como texto
                urls, subs = _parse_text(data.decode("utf-8", "ignore"), host)
        else:
            urls, subs = _parse_text(data, host)

        if urls or subs:
            via_txt = "" if via == "directo" else f" [{via}]"
            log.append(f"✅ {sm}{via_txt}: {len(urls)} URLs, {len(subs)} sub-sitemaps")
        for u in urls:
            seen_urls.add(u)
        for s in subs:
            if s not in visited:
                pending.append(s)

    if not seen_urls:
        log.append("❌ No se encontraron URLs en ningún sitemap.")

    return sorted(seen_urls)[:max_urls], log
