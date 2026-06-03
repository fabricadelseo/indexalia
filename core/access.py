"""Control de acceso a la app (login de equipo) para el despliegue en la nube.

Como Streamlit Cloud expone una URL pública, protegemos la app con usuario y
contraseña. Los usuarios se definen en los *secrets*:

    # .streamlit/secrets.toml  (o Settings ▸ Secrets en Streamlit Cloud)
    [passwords]
    ana   = "clave-de-ana"
    pedro = "clave-de-pedro"

Alternativa de una sola clave compartida:

    app_password = "clave-del-equipo"

Si no hay nada configurado (desarrollo local), la app queda abierta.
"""

from __future__ import annotations

import hmac

import streamlit as st


def _shared_password() -> str | None:
    """Clave única compartida por todo el equipo (app_password)."""
    try:
        if "app_password" in st.secrets:
            return str(st.secrets["app_password"])
    except Exception:
        pass
    return None


def _user_table() -> dict | None:
    """Usuarios individuales (tabla [passwords]), si se prefiere."""
    try:
        if "passwords" in st.secrets:
            return dict(st.secrets["passwords"])
    except Exception:
        pass
    return None


def require_login() -> str:
    """Bloquea la app hasta autenticarse. Devuelve el usuario (o 'equipo').

    - Si hay `app_password` -> pide solo la contraseña (clave única del equipo).
    - Si hay tabla `[passwords]` -> pide usuario + contraseña.
    - Si no hay nada (local) -> devuelve 'local' sin pedir nada.
    """
    if st.session_state.get("_user"):
        return st.session_state["_user"]

    shared = _shared_password()
    users = _user_table()

    if not shared and not users:
        return "local"

    st.markdown("## 🔒 Indexalia")
    st.caption("Acceso restringido al equipo.")

    with st.form("login"):
        if shared:
            usuario = "equipo"
            clave = st.text_input("Contraseña", type="password")
        else:
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Entrar", type="primary")

    if entrar:
        if shared:
            ok = hmac.compare_digest(str(clave), shared)
        else:
            ok = usuario in users and hmac.compare_digest(str(clave), str(users[usuario]))
        if ok:
            st.session_state["_user"] = usuario
            st.rerun()
        else:
            st.error("Contraseña incorrecta." if shared else "Usuario o contraseña incorrectos.")
    st.stop()


def logout_button() -> None:
    if st.session_state.get("_user"):
        if st.button("🔒 Salir de Indexalia", use_container_width=True):
            del st.session_state["_user"]
            st.rerun()
