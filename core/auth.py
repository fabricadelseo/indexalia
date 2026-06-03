"""Credenciales de Google — soporta OAuth (login de usuario) y cuenta de servicio.

Orden de preferencia en get_credentials():
  1. OAuth de usuario (token.json o env GOOGLE_OAUTH_TOKEN) -> RECOMENDADO
     para agencias con muchos clientes: inicias sesión una vez con tu cuenta
     y ves TODAS las propiedades a las que ya tienes acceso, sin tocar la
     Search Console de cada cliente.
  2. Cuenta de servicio (GCP_SA_JSON / st.secrets / service_account.json)
     -> útil cuando quieres acceso aislado por propiedad.

Para OAuth necesitas un "client_secret.json" (OAuth client tipo Desktop)
descargado de Google Cloud. La primera vez se abre el navegador para
autorizar; el token (con refresh_token) se guarda en token.json y se
reutiliza/renueva solo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2 import service_account

# Permisos que pedimos a Google:
#   - webmasters.readonly -> listar propiedades + URL Inspection API
#   - indexing            -> Indexing API (solicitar indexación)
#   - spreadsheets        -> cola en Google Sheets (opcional)
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/indexing",
    "https://www.googleapis.com/auth/spreadsheets",
]

_BASE = Path(__file__).resolve().parent.parent
_SA_FILE = _BASE / "service_account.json"
_CLIENT_SECRET = _BASE / "client_secret.json"
_TOKEN = _BASE / "token.json"


# --------------------------------------------------------------- OAuth -------
def has_client_secret() -> bool:
    return _CLIENT_SECRET.exists()


def has_oauth_token() -> bool:
    return _TOKEN.exists() or bool(os.environ.get("GOOGLE_OAUTH_TOKEN"))


def _save_token(creds) -> None:
    _TOKEN.write_text(creds.to_json(), encoding="utf-8")


def _oauth_token_from_streamlit() -> str | None:
    """Lee el token OAuth desde st.secrets['google_oauth_token'] (app en la nube)."""
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return None
    try:
        if "google_oauth_token" in st.secrets:
            return st.secrets["google_oauth_token"]
    except Exception:
        return None
    return None


def _load_oauth_creds():
    """Devuelve credenciales de usuario válidas (renovándolas) o None."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    raw = os.environ.get("GOOGLE_OAUTH_TOKEN") or _oauth_token_from_streamlit()
    if raw:
        creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    elif _TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN), SCOPES)

    if not creds:
        return None
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if not raw:  # solo persistimos si trabajamos con fichero local
            _save_token(creds)
        return creds
    return None


def oauth_login():
    """Lanza el flujo de autorización en el navegador y guarda token.json.

    Solo funciona en local (abre un servidor temporal en localhost).
    Requiere client_secret.json en la raíz del proyecto.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not _CLIENT_SECRET.exists():
        raise RuntimeError("Falta client_secret.json (OAuth client de Google Cloud).")
    flow = InstalledAppFlow.from_client_secrets_file(str(_CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    _save_token(creds)
    return creds


def oauth_logout() -> None:
    if _TOKEN.exists():
        _TOKEN.unlink()


# ----------------------------------------------------- cuenta de servicio ----
def _service_account_creds():
    raw = os.environ.get("GCP_SA_JSON")
    if raw:
        return service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=SCOPES
        )
    info = _info_from_streamlit()
    if info:
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    if _SA_FILE.exists():
        return service_account.Credentials.from_service_account_file(
            str(_SA_FILE), scopes=SCOPES
        )
    return None


def _info_from_streamlit() -> dict | None:
    try:
        import streamlit as st  # import perezoso: el cron no tiene streamlit
    except ModuleNotFoundError:
        return None
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        return None
    return None


# -------------------------------------------------------------- público ------
def get_credentials():
    """Devuelve credenciales válidas (OAuth primero, luego cuenta de servicio)."""
    oauth = _load_oauth_creds()
    if oauth:
        return oauth

    sa = _service_account_creds()
    if sa:
        return sa

    raise RuntimeError(
        "No hay credenciales. Inicia sesión con OAuth (client_secret.json) "
        "o configura una cuenta de servicio (service_account.json / GCP_SA_JSON)."
    )


def identity_label() -> str | None:
    """Texto descriptivo de la identidad actual, para mostrar en la UI."""
    try:
        creds = get_credentials()
    except Exception:
        return None
    sa_email = getattr(creds, "service_account_email", None)
    if sa_email:
        return f"Cuenta de servicio: {sa_email}"
    return "Sesión OAuth iniciada (tu cuenta de Google)"


def service_account_email() -> str | None:
    """Compatibilidad: email de la cuenta de servicio, o None si usas OAuth."""
    try:
        return getattr(get_credentials(), "service_account_email", None)
    except Exception:
        return None
