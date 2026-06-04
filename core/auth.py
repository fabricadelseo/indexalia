"""Credenciales de Google — OAuth multi-cuenta (+ cuenta de servicio).

Soporta VARIAS cuentas de Google a la vez: cada una se guarda en su propio
token y la app junta los dominios de todas. Para cada dominio se usan las
credenciales de la cuenta que tiene acceso a él.

Tokens:
  - token.json                -> cuenta principal (login.py / botón inicial)
  - tokens/<email>.json       -> cuentas adicionales (botón "Añadir cuenta")
  - env GOOGLE_OAUTH_TOKEN[_N] -> tokens en la nube (Streamlit/GitHub)
  - st.secrets google_oauth_token[_N]

Alternativa: cuenta de servicio (GCP_SA_JSON / service_account.json).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2 import service_account

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",  # listar + inspeccionar
    "https://www.googleapis.com/auth/indexing",             # solicitar indexación
    "https://www.googleapis.com/auth/spreadsheets",         # cola en Sheets
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",       # nombre de la cuenta
]

_BASE = Path(__file__).resolve().parent.parent
_SA_FILE = _BASE / "service_account.json"
_CLIENT_SECRET = _BASE / "client_secret.json"
_TOKEN = _BASE / "token.json"
_TOKENS_DIR = _BASE / "tokens"


# ----------------------------------------------------------- helpers OAuth ---
def has_client_secret() -> bool:
    return _CLIENT_SECRET.exists()


def _streamlit_oauth_tokens() -> list[tuple[str, str]]:
    """[(label, raw_json)] desde st.secrets (claves que empiezan por google_oauth_token)."""
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return []
    out = []
    try:
        for key in st.secrets:
            if key == "google_oauth_token" or key.startswith("google_oauth_token_"):
                out.append((key, st.secrets[key]))
    except Exception:
        return []
    return out


def _env_oauth_tokens() -> list[tuple[str, str]]:
    out = []
    for key, val in os.environ.items():
        if key == "GOOGLE_OAUTH_TOKEN" or key.startswith("GOOGLE_OAUTH_TOKEN_"):
            if val:
                out.append((key.lower(), val))
    return out


def has_oauth_token() -> bool:
    if _TOKEN.exists():
        return True
    if _TOKENS_DIR.exists() and any(_TOKENS_DIR.glob("*.json")):
        return True
    return bool(_env_oauth_tokens() or _streamlit_oauth_tokens())


def _refresh(creds, save_path: Path | None):
    from google.auth.transport.requests import Request

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if save_path is not None:
            save_path.write_text(creds.to_json(), encoding="utf-8")
        return creds
    return creds if creds and creds.valid else None


def _creds_from_file(path: Path):
    # OJO: no forzamos SCOPES al cargar; usamos los que ya tiene el token
    # (si no, el refresco falla con invalid_scope para tokens antiguos).
    from google.oauth2.credentials import Credentials

    try:
        creds = Credentials.from_authorized_user_file(str(path))
    except Exception:
        return None
    return _refresh(creds, save_path=path)


def _creds_from_raw(raw: str):
    from google.oauth2.credentials import Credentials

    try:
        creds = Credentials.from_authorized_user_info(json.loads(raw))
    except Exception:
        return None
    return _refresh(creds, save_path=None)


def _email_of(creds) -> str | None:
    try:
        from googleapiclient.discovery import build

        svc = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        return svc.userinfo().get().execute().get("email")
    except Exception:
        return None


# ------------------------------------------------------- cuentas (público) ---
def accounts() -> list[dict]:
    """Lista de cuentas conectadas: [{'name': email, 'creds': Credentials}]."""
    out: list[dict] = []
    seen: set[str] = set()

    fuentes: list[tuple[str, str, object]] = []
    # Ficheros locales
    if _TOKEN.exists():
        fuentes.append(("principal", "file", _TOKEN))
    if _TOKENS_DIR.exists():
        for p in sorted(_TOKENS_DIR.glob("*.json")):
            fuentes.append((p.stem, "file", p))
    # Nube
    for label, raw in _env_oauth_tokens() + _streamlit_oauth_tokens():
        fuentes.append((label, "raw", raw))

    for label, kind, val in fuentes:
        creds = _creds_from_file(val) if kind == "file" else _creds_from_raw(val)
        if not creds:
            continue
        # Si el nombre ya es un email (fichero tokens/<email>.json) lo usamos;
        # si es genérico (principal/env/secret) intentamos resolver el email.
        name = label
        if "@" not in label:
            name = _email_of(creds) or label
        if name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "creds": creds})
    return out


def creds_map() -> dict:
    """{nombre_cuenta: Credentials} para enrutar por cuenta."""
    return {a["name"]: a["creds"] for a in accounts()}


# ------------------------------------------------------------- login OAuth ---
def _run_flow():
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not _CLIENT_SECRET.exists():
        raise RuntimeError("Falta client_secret.json (OAuth client de Google Cloud).")
    flow = InstalledAppFlow.from_client_secrets_file(str(_CLIENT_SECRET), SCOPES)
    return flow.run_local_server(port=0, prompt="consent")


def oauth_login():
    """Login de la cuenta principal -> guarda token.json (lo usa login.py)."""
    creds = _run_flow()
    _TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def add_account() -> str:
    """Login de una cuenta ADICIONAL -> guarda tokens/<email>.json. Devuelve el email."""
    creds = _run_flow()
    email = _email_of(creds) or f"cuenta-{len(accounts()) + 1}"
    _TOKENS_DIR.mkdir(exist_ok=True)
    (_TOKENS_DIR / f"{email}.json").write_text(creds.to_json(), encoding="utf-8")
    return email


def remove_account(name: str) -> None:
    """Quita una cuenta. 'principal' borra token.json; el resto su fichero."""
    if name == "principal" and _TOKEN.exists():
        _TOKEN.unlink()
        return
    f = _TOKENS_DIR / f"{name}.json"
    if f.exists():
        f.unlink()


def oauth_logout() -> None:
    """Cierra todas las sesiones OAuth locales."""
    if _TOKEN.exists():
        _TOKEN.unlink()
    if _TOKENS_DIR.exists():
        for p in _TOKENS_DIR.glob("*.json"):
            p.unlink()


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
        import streamlit as st
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
    """Credenciales 'por defecto' (1ª cuenta OAuth o cuenta de servicio).

    Lo usan Sheets y procesos que no enrutan por cuenta. Para inspección/
    indexación por dominio se usan las credenciales de cada cuenta (creds_map).
    """
    accs = accounts()
    if accs:
        return accs[0]["creds"]
    sa = _service_account_creds()
    if sa:
        return sa
    raise RuntimeError(
        "No hay credenciales. Inicia sesión con OAuth (client_secret.json) "
        "o configura una cuenta de servicio (service_account.json / GCP_SA_JSON)."
    )


def identity_label() -> str | None:
    """Resumen de cuentas conectadas para la UI."""
    try:
        accs = accounts()
    except Exception:
        accs = []
    if accs:
        if len(accs) == 1:
            return accs[0]["name"]
        return f"{len(accs)} cuentas conectadas"
    sa = None
    try:
        sa = getattr(_service_account_creds(), "service_account_email", None)
    except Exception:
        sa = None
    return f"Cuenta de servicio: {sa}" if sa else None


def service_account_email() -> str | None:
    try:
        return getattr(get_credentials(), "service_account_email", None)
    except Exception:
        return None
