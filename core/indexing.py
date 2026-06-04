"""Cliente de la Indexing API de Google (solicitar indexación de una URL).

IMPORTANTE:
- La service account debe estar añadida como PROPIETARIO ("Owner") en la
  propiedad de Search Console del cliente para que esto funcione.
- Oficialmente la Indexing API solo soporta JobPosting y BroadcastEvent.
  Para páginas normales funciona en la práctica, pero no es uso soportado:
  por eso enviamos pocas URLs/día (drip-feed) en lugar de en masa.
"""

from __future__ import annotations

from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import get_credentials


@dataclass
class PublishResult:
    url: str
    ok: bool
    detail: str


def _build_service(creds=None):
    creds = creds or get_credentials()
    return build("indexing", "v3", credentials=creds, cache_discovery=False)


def make_service(creds=None):
    return _build_service(creds)


def publish_url(url: str, service=None, action: str = "URL_UPDATED") -> PublishResult:
    """Notifica a Google que una URL fue creada/actualizada.

    action: "URL_UPDATED" (crear/actualizar) o "URL_DELETED" (eliminada).
    """
    svc = service or _build_service()
    body = {"url": url, "type": action}
    try:
        resp = svc.urlNotifications().publish(body=body).execute()
        ts = resp.get("urlNotificationMetadata", {}).get("latestUpdate", {}).get("notifyTime", "")
        return PublishResult(url, True, f"Enviada a Google ({ts})")
    except HttpError as e:
        return PublishResult(url, False, f"Error: {e}")


def publish_many(urls: list[str], service=None) -> list[PublishResult]:
    svc = service or _build_service()
    return [publish_url(u, service=svc) for u in urls]
