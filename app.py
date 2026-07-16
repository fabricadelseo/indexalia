"""Indexalia — panel visual en Streamlit (by La Fábrica del SEO).

Dashboard para detectar URLs no indexadas de clientes y solicitar su
indexación de forma escalonada (Google drip-feed + IndexNow).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

from core import (
    access, auth, clients, gsc, history, indexing, indexnow, settings, sitemap, storage,
)

st.set_page_config(
    page_title="Indexalia · La Fábrica del SEO",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Logo de marca (si existe assets/logo.png se muestra arriba de la barra lateral).
_LOGO = Path(__file__).resolve().parent / "assets" / "logo.png"
if _LOGO.exists():
    try:
        st.logo(str(_LOGO))
    except Exception:
        pass

PER_DOMAIN_DEFAULT = 10   # máximo de URLs/día a Google POR cada dominio
GLOBAL_CAP = 200          # tope global diario (límite de la Indexing API de Google)

# Paleta de marca (La Fábrica del SEO)
NARANJA = "#FF6A00"   # naranja intenso de marca
NARANJA2 = "#FF8A3D"  # naranja claro
GRIS = "#37373A"      # gris oscuro del logo
VERDE = "#16a34a"     # semántico: indexada / OK
ROJO = "#dc2626"      # semántico: no indexada / error

# ---------------------------------------------------------------- estilos ----
st.markdown(
    """
    <style>
      #MainMenu, footer {visibility: hidden;}
      .block-container {padding-top: 3.4rem; max-width: 1150px;}
      h1, h2, h3 {color: #2B2B2D;}

      /* Cabecera */
      .appbar {display: flex; align-items: baseline; gap: .7rem;
        padding-bottom: .55rem; border-bottom: 2px solid #FF6A00; margin-bottom: .35rem;}
      .appbar .logo {font-size: 2.05rem; font-weight: 800; color: #2B2B2D; letter-spacing: -.02em;}
      .appbar .logo .dot {color: #FF6A00;}
      .appbar .tag {font-size: .72rem; color: #A6A6AB; text-transform: uppercase;
        letter-spacing: .1em; margin-left: auto;}

      /* Tarjetas de métricas sobrias */
      div[data-testid="stMetric"] {
        background: #fff; border: 1px solid #EDECEA; border-radius: 12px;
        padding: .85rem 1.05rem;
      }
      div[data-testid="stMetricLabel"] p {font-weight: 600; color: #8a8a8f; font-size: .82rem;}

      /* --- Botones (base) --- */
      .stButton > button, .stFormSubmitButton > button {
        border-radius: 9px !important; font-weight: 600 !important;
        padding: .55rem 1.15rem !important; transition: all .15s ease !important;
      }
      /* Primario: naranja intenso */
      button[kind="primary"], button[kind="primaryFormSubmit"],
      button[data-testid="stBaseButton-primary"],
      button[data-testid="baseButton-primary"],
      button[data-testid="stBaseButton-primaryFormSubmit"],
      a[data-testid="stBaseLinkButton-primary"],
      a[data-testid="baseLinkButton-primary"],
      a[kind="primary"] {
        background: #FF6A00 !important; border: 1px solid #FF6A00 !important;
        color: #fff !important; box-shadow: 0 2px 8px rgba(255,106,0,.32) !important;
      }
      a[data-testid="stBaseLinkButton-primary"]:hover,
      a[data-testid="baseLinkButton-primary"]:hover {
        background: #E85F00 !important; border-color: #E85F00 !important;
        color: #fff !important;
      }
      button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover,
      button[data-testid="stBaseButton-primary"]:hover,
      button[data-testid="baseButton-primary"]:hover {
        background: #E85F00 !important; border-color: #E85F00 !important;
        box-shadow: 0 5px 14px rgba(255,106,0,.45) !important;
      }
      /* Secundario: contorno y texto naranja ya en reposo */
      button[kind="secondary"], button[kind="secondaryFormSubmit"],
      button[data-testid="stBaseButton-secondary"],
      button[data-testid="baseButton-secondary"],
      button[data-testid="stBaseButton-secondaryFormSubmit"] {
        background: #fff !important; border: 1.5px solid #FFC299 !important;
        color: #E85F00 !important;
      }
      button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover,
      button[data-testid="stBaseButton-secondary"]:hover,
      button[data-testid="baseButton-secondary"]:hover {
        background: #FFF3EA !important; border-color: #FF6A00 !important;
        color: #E85F00 !important;
      }
      /* Deshabilitado (gana al resto) */
      .stButton > button:disabled, .stButton > button:disabled:hover {
        background: #F3F2F0 !important; border: 1px solid #ECEAE7 !important;
        color: #BBB9B6 !important; box-shadow: none !important; cursor: not-allowed;
      }

      /* --- Tour por pasos --- */
      .tour {display: flex; align-items: center; gap: .5rem; flex-wrap: wrap;
        margin: .2rem 0 .15rem;}
      .tour .step {display: flex; align-items: center; gap: .45rem;
        font-size: .9rem; font-weight: 600; color: #A6A6AB;}
      .tour .step .num {display: inline-flex; align-items: center; justify-content: center;
        width: 1.5rem; height: 1.5rem; border-radius: 50%; background: #ECEAE7;
        color: #8a8a8f; font-size: .8rem;}
      .tour .step.active {color: #2B2B2D;}
      .tour .step.active .num {background: #FF6A00; color: #fff;}
      .tour .step.done {color: #2B2B2D;}
      .tour .step.done .num {background: #FFE0CC; color: #E85F00;}
      .tour .sep {flex: 0 0 26px; height: 2px; background: #ECEAE7; border-radius: 2px;}
      .tourhint {font-size: .92rem; color: #E85F00; font-weight: 600; margin: .15rem 0 .7rem;}

      /* Caja discreta (prioridad) */
      div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #ECEAE7 !important;
        border-radius: 12px;
      }

      button[data-baseweb="tab"] {font-size: .98rem; font-weight: 600;}
      a, a:visited {color: #E85F00;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Control de acceso (login de equipo en la nube). En local, sin secrets, pasa directo.
usuario_actual = access.require_login()

# Conexión de cuenta nueva vía OAuth web: Google redirige aquí con ?code=...
if "code" in st.query_params and auth.web_oauth_available():
    try:
        _email = auth.web_exchange(st.query_params["code"])
        st.session_state["_added_ok"] = _email
        st.session_state.sites = None
    except Exception as e:  # noqa: BLE001
        st.session_state["_added_err"] = str(e)
    st.query_params.clear()
    st.rerun()

st.markdown(
    """
    <div class="appbar">
      <span class="logo">Indexalia<span class="dot">.</span></span>
      <span class="tag">La Fábrica del SEO</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Detecta URLs no indexadas de tus clientes y envíalas a indexar "
    "(Google + Bing/Yandex)."
)
st.write("")


def donut(indexadas: int, no_indexadas: int) -> go.Figure:
    """Gráfico de dona con el % de indexación."""
    total = indexadas + no_indexadas
    pct = (indexadas / total * 100) if total else 0
    fig = go.Figure(
        go.Pie(
            values=[indexadas, no_indexadas],
            labels=["Indexadas", "No indexadas"],
            hole=0.68,
            sort=False,
            marker_colors=[VERDE, ROJO],
            textinfo="none",
            hovertemplate="%{label}: %{value}<extra></extra>",
        )
    )
    fig.update_layout(
        height=260,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(orientation="h", y=-0.1),
        annotations=[
            dict(text=f"<b>{pct:.0f}%</b><br>indexado", x=0.5, y=0.5,
                 font_size=22, showarrow=False)
        ],
    )
    return fig


def donut_estados(en_proceso: int, enviadas: int, errores: int) -> go.Figure:
    """Gráfico circular del reparto por estado (con %)."""
    valores = [en_proceso, enviadas, errores]
    etiquetas = ["En proceso", "Enviadas", "Error"]
    colores = ["#f59e0b", VERDE, ROJO]
    fig = go.Figure(
        go.Pie(
            values=valores,
            labels=etiquetas,
            hole=0.62,
            sort=False,
            marker_colors=colores,
            textinfo="percent",
            texttemplate="%{percent:.0%}",
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        )
    )
    total = sum(valores)
    fig.update_layout(
        height=280,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(orientation="h", y=-0.1),
        annotations=[
            dict(text=f"<b>{total}</b><br>URLs", x=0.5, y=0.5,
                 font_size=20, showarrow=False)
        ],
    )
    return fig


def render_tour(paso: int) -> None:
    """Indicador de pasos guiado (1 Cargar · 2 Elegir · 3 Analizar)."""
    pasos = ["Cargar clientes", "Elegir cliente", "Analizar y enviar"]
    pistas = {
        1: "👉 Pulsa <b>Cargar clientes</b> (arriba a la derecha) para traer tus "
           "propiedades de Search Console.",
        2: "👉 Elige un cliente en el desplegable.",
        3: "👉 Pulsa <b>Analizar y enviar a indexar</b>.",
    }
    bloques = []
    for i, nombre in enumerate(pasos, start=1):
        estado = "done" if i < paso else ("active" if i == paso else "todo")
        num = "✓" if i < paso else str(i)
        bloques.append(
            f'<div class="step {estado}"><span class="num">{num}</span> {nombre}</div>'
        )
        if i < len(pasos):
            bloques.append('<div class="sep"></div>')
    st.markdown(f'<div class="tour">{"".join(bloques)}</div>', unsafe_allow_html=True)
    if paso in pistas:
        st.markdown(f'<div class="tourhint">{pistas[paso]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="tourhint">✅ Análisis hecho. Revisa los resultados abajo.</div>',
            unsafe_allow_html=True,
        )


def _enviar_lote(lote):
    """Envía un lote de URLs a Google enrutando por cuenta. Devuelve (ok, err)."""
    cmap = st.session_state.get("acc_creds") or auth.creds_map()
    site_acc_map = settings.get("site_accounts", {}) or {}
    svc_cache: dict = {}
    ok = err = 0
    for it in lote:
        acc = site_acc_map.get(it["site_url"])
        if acc not in svc_cache:
            svc_cache[acc] = indexing.make_service(cmap.get(acc))
        res = indexing.publish_url(it["url"], service=svc_cache[acc])
        try:
            storage.mark(it["url"], "sent" if res.ok else "error", res.detail)
        except Exception:  # noqa: BLE001  (pico de Sheets: no romper la app)
            pass
        if res.ok:
            ok += 1
        else:
            err += 1
    return ok, err


def enviar_prioritario(site_url: str, cuantas: int, global_cap: int = GLOBAL_CAP):
    """Envía YA las URLs en proceso de UN cliente, saltándose el tope por dominio.

    Solo respeta el tope global del día (límite de Google).
    """
    restante_global = max(0, global_cap - storage.count_sent_today())
    lote = storage.pending(site_url)[: min(cuantas, restante_global)]
    if not lote:
        return 0, 0
    return _enviar_lote(lote)


def enviar_a_indexar(per_domain: int, global_cap: int = GLOBAL_CAP):
    """Envía a Google las URLs en proceso respetando el límite por dominio y el
    tope global del día. Devuelve (enviadas_ok, errores).
    """
    lote = storage.select_to_send(per_domain, global_cap)
    if not lote:
        return 0, 0
    return _enviar_lote(lote)


# --------------------------------------------------------------- sidebar ----
identidad = auth.identity_label()
autenticado = identidad is not None
with st.sidebar:
    if usuario_actual != "local":
        if usuario_actual == "equipo":
            st.caption("👤 Sesión iniciada")
        else:
            st.caption(f"👤 Conectado como **{usuario_actual}**")
        access.logout_button()
        st.divider()

    st.header("⚙️ Configuración")
    st.markdown("**Cuentas de Google**")

    # Avisos de la conexión web recién hecha.
    if _ok := st.session_state.pop("_added_ok", None):
        st.success(f"✅ Cuenta conectada: {_ok}")
    if _err := st.session_state.pop("_added_err", None):
        st.error(f"No se pudo conectar: {_err}")

    cuentas = []
    if autenticado:
        try:
            cuentas = auth.accounts()
        except Exception:
            cuentas = []
        if cuentas:
            for c in cuentas:
                st.success(f"✅ {c['name']}")
        else:
            st.success(identidad)
    else:
        st.error("Sin cuentas conectadas.")

    # Añadir cuenta:
    #  - En la NUBE (OAuth web configurado) -> enlace de autorización de Google.
    #  - En LOCAL (client_secret.json) -> abre el navegador (run_local_server).
    if auth.web_oauth_available():
        try:
            st.link_button(
                "➕ Añadir cuenta de Google", auth.web_auth_url(),
                type="primary", use_container_width=True,
            )
            st.caption("Te lleva a Google; al volver, la cuenta queda conectada.")
        except Exception as e:  # noqa: BLE001
            st.caption(f"OAuth web mal configurado: {e}")
    elif auth.has_client_secret():
        etiqueta = "🔐 Iniciar sesión con Google" if not auth.has_oauth_token() else "➕ Añadir otra cuenta de Google"
        if st.button(etiqueta, type="primary", use_container_width=True):
            with st.spinner("Abriendo el navegador para autorizar…"):
                try:
                    auth.oauth_login() if not auth.has_oauth_token() else auth.add_account()
                    st.session_state.sites = None
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"No se pudo conectar la cuenta: {e}")
    elif not autenticado:
        st.caption(
            "Para conectar cuentas desde la nube, configura `oauth_web` en los "
            "Secrets (ver README)."
        )

    # Solo se pueden quitar las cuentas añadidas (con email); la principal no.
    quitables = [c for c in cuentas if "@" in c["name"]]
    if quitables:
        with st.expander("Gestionar cuentas añadidas"):
            for c in quitables:
                st.caption(c["name"])
                if st.button(f"🗑️ Quitar {c['name']}", key=f"rm_{c['name']}",
                             use_container_width=True):
                    auth.remove_account(c["name"])
                    st.session_state.sites = None
                    st.rerun()

    st.divider()
    _sid = settings.get("sheet_id")
    if _sid:
        st.link_button(
            "📄 Abrir hoja de Sheets",
            f"https://docs.google.com/spreadsheets/d/{_sid}",
            use_container_width=True,
            type="primary",
        )
    per_domain = st.number_input(
        "URLs por día y dominio (Google)", min_value=1, max_value=200,
        value=PER_DOMAIN_DEFAULT,
        help="Máximo de URLs que se envían a Google al día por CADA dominio. "
        f"Hay además un tope global de {GLOBAL_CAP}/día (límite de Google).",
    )
    st.caption(f"Tope global de seguridad: **{GLOBAL_CAP}/día**.")
    retry_days = st.number_input(
        "Reintentar tras (días sin indexar)", min_value=0, max_value=90,
        value=int(settings.get("retry_days", 15)),
        help="Si una URL se envió hace estos días y sigue sin indexar, se vuelve "
        "a enviar. 0 = reintentar siempre.",
    )
    st.caption(f"Backend de la cola: **{storage.backend_name()}**")

    st.divider()
    st.subheader("IndexNow (Bing/Yandex)")
    indexnow_key = settings.get("indexnow_key", "")
    key_input = st.text_input("Key de IndexNow", value=indexnow_key or "")
    c_gen, c_save = st.columns(2)
    with c_gen:
        if st.button("🎲 Generar", use_container_width=True):
            import secrets as _secrets

            settings.set_("indexnow_key", _secrets.token_hex(16))
            st.rerun()
    with c_save:
        if st.button("💾 Guardar", use_container_width=True):
            settings.set_("indexnow_key", key_input.strip())
            st.success("Key guardada.")
            st.rerun()
    if indexnow_key:
        st.caption(
            "Sube un fichero `<key>.txt` (con la key dentro) a la raíz de cada "
            "dominio para que IndexNow lo valide."
        )

# ------------------------------------------------------- selector cliente ----
if "sites" not in st.session_state:
    st.session_state.sites = None
if "results" not in st.session_state:
    st.session_state.results = None

sel_cols = st.columns([3, 1])
with sel_cols[1]:
    st.write("")
    if st.button("🔄 Cargar clientes", disabled=not autenticado, use_container_width=True):
        try:
            accs = auth.accounts()
            st.session_state.acc_creds = {a["name"]: a["creds"] for a in accs}
            st.session_state.sites = gsc.list_sites_all_accounts(accs)
            settings.set_(
                "site_accounts",
                {s["siteUrl"]: s.get("account") for s in st.session_state.sites},
            )
        except Exception as e:  # noqa: BLE001
            st.session_state.sites = []
            st.error(f"No se pudieron cargar las propiedades: {e}")

site_url = None
domain = None
perms = {}
site_acc = {}

with sel_cols[0]:
    if st.session_state.sites is None:
        st.empty()
    elif not st.session_state.sites:
        st.warning(
            "No hay propiedades accesibles. Añade el email de tu cuenta como "
            "usuario en la Search Console de tus clientes."
        )
    else:
        site_urls = [s["siteUrl"] for s in st.session_state.sites]
        perms = {s["siteUrl"]: s.get("permissionLevel", "?") for s in st.session_state.sites}
        site_acc = {s["siteUrl"]: s.get("account") for s in st.session_state.sites}
        site_url = st.selectbox(
            "👤 Cliente", options=site_urls, format_func=clients.label_for
        )
        domain = clients.domain_from_site_url(site_url)

if site_url:
    chips = st.columns([2, 2, 3])
    chips[0].caption(f"Propiedad: `{site_url}`")
    chips[1].caption(f"Permiso: `{perms.get(site_url, '?')}` · cuenta: `{site_acc.get(site_url, '?')}`")
    with chips[2]:
        current = clients.load_names().get(site_url, "")
        new_name = st.text_input(
            "Nombre amigable", value=current, key=f"name_{site_url}",
            label_visibility="collapsed", placeholder="Nombre amigable del cliente",
        )
        if st.button("💾 Guardar nombre"):
            clients.set_name(site_url, new_name)
            st.rerun()
    # La Indexing API de Google exige ser PROPIETARIO (siteOwner) de la propiedad.
    if perms.get(site_url) != "siteOwner":
        st.warning(
            f"Tu acceso aquí es `{perms.get(site_url, '?')}`, no **Propietario**. "
            "Podrás **analizar** la indexación, pero Google **no permite solicitar "
            "indexación** (dará *Permission denied*). Para poder indexar, pide que "
            "te añadan como **Propietario** en esa Search Console."
        )

# --- Tour guiado: marca el paso actual según el estado ---
if st.session_state.sites is None:
    _paso = 1
elif not site_url:
    _paso = 2
elif not st.session_state.results:
    _paso = 3
else:
    _paso = 4
render_tour(_paso)

st.write("")
tab_analisis, tab_cola, tab_hist = st.tabs(
    ["🔍 Análisis", "📤 Indexaciones", "📈 Histórico"]
)

# ============================================================ TAB ANÁLISIS ===
with tab_analisis:
    c_opts = st.columns([3, 1])
    with c_opts[0]:
        max_urls = st.slider("Máximo de URLs a analizar", 10, 1000, 100, step=10)
    with c_opts[1]:
        st.write("")
        st.write("")
        analizar = st.button(
            "🚀 Analizar y enviar a indexar", type="primary", use_container_width=True,
            disabled=not (domain and autenticado),
        )
    auto_enviar = st.checkbox(
        "Enviar a indexar automáticamente las no indexadas",
        value=True,
        help="Al analizar, las URLs no indexadas se envían a indexar: se mandan "
        "las que caben en el cupo de hoy y el resto quedan en proceso (el cron "
        "las envía cada día).",
    )

    BATCH = 10  # URLs por tanda (entre tandas se puede pulsar Parar)

    # --- Arranque del análisis: lee el sitemap y prepara el estado por tandas ---
    if analizar:
        with st.spinner("Leyendo sitemap…"):
            # Preguntamos a Search Console qué sitemaps tiene la propiedad
            # (fiable: nombres no estándar, subdominio www, etc.).
            _c = (st.session_state.get("acc_creds") or {}).get(site_acc.get(site_url))
            sm_gsc = gsc.list_sitemaps(site_url, _c)
            urls, log = sitemap.fetch_urls(domain, max_urls=max_urls, extra=sm_gsc)
        if urls:
            st.session_state.results = None
            st.session_state.an = {
                "running": True,
                "site_url": site_url,
                "account": site_acc.get(site_url),
                "perm": perms.get(site_url),
                "urls": urls,
                "i": 0,
                "rows": [],
                "auto": auto_enviar,
                "finalized": False,
            }
            st.rerun()
        else:
            st.warning("No se encontraron URLs en el sitemap de este cliente.")
            for line in log:
                st.caption(line)

    an = st.session_state.get("an")

    # --- Análisis en curso: barra de progreso + botón Parar + tanda ---
    if an and an["running"]:
        total = len(an["urls"])
        st.progress(an["i"] / total, text=f"Analizando… {an['i']}/{total}")
        if st.button("⏹️ Parar análisis", type="secondary"):
            an["running"] = False
            st.rerun()

        # Procesa una tanda con las credenciales de la cuenta dueña del dominio.
        _creds = (st.session_state.get("acc_creds") or {}).get(an.get("account"))
        svc = gsc.make_service(_creds)
        for url in an["urls"][an["i"]:an["i"] + BATCH]:
            r = gsc.inspect_url(an["site_url"], url, service=svc)
            es_error = bool(r.error)
            an["rows"].append({
                "URL": r.url,
                "Indexada": "⚠️" if es_error else ("✅" if r.indexed else "❌"),
                "Estado Google": "Sin acceso / error" if es_error else r.coverage_state,
                "_indexed": r.indexed,
                "_error": es_error,
            })
            an["i"] += 1
        if an["i"] >= total:
            an["running"] = False
        st.rerun()

    # --- Fin (terminado o parado): vuelca resultados, guarda histórico y envía ---
    if an and not an["running"] and not an["finalized"]:
        an["finalized"] = True
        rows = an["rows"]
        st.session_state.results = rows
        # El histórico ignora las URLs con error (no se pudieron comprobar).
        st.session_state.cambios = history.add_snapshot(
            an["site_url"],
            [{"url": r["URL"], "indexed": r["_indexed"]}
             for r in rows if not r.get("_error")],
        )
        if an["auto"] and rows and an.get("perm") != "siteOwner":
            # Sin ser Propietario, Google rechaza la indexación (403): no encolamos.
            st.session_state.envio_resumen = None
            st.session_state.sin_permiso = an.get("perm")
        elif an["auto"] and rows:
            st.session_state.sin_permiso = None
            # Solo se encolan las realmente NO indexadas (las de error se omiten).
            no_idx = [r["URL"] for r in rows if not r["_indexed"] and not r.get("_error")]
            registradas = storage.add_urls(no_idx, an["site_url"], retry_days=retry_days)
            enviadas, errores = enviar_a_indexar(per_domain)
            st.session_state.envio_resumen = {
                "registradas": registradas,
                "enviadas": enviadas,
                "errores": errores,
                "en_proceso": len(storage.pending()),
            }
        else:
            st.session_state.envio_resumen = None
        if an["i"] < len(an["urls"]):
            st.caption(f"⏹️ Análisis detenido en {an['i']}/{len(an['urls'])} URLs.")

    analizando = bool(an and an["running"])

    if st.session_state.results and not analizando:
        df = pd.DataFrame(st.session_state.results)
        if "_error" not in df.columns:
            df["_error"] = False
        df["_error"] = df["_error"].fillna(False)
        total = len(df)
        errores = int(df["_error"].sum())
        indexadas = int(df["_indexed"].sum())
        no_indexadas = total - indexadas - errores

        left, right = st.columns([1, 1.4])
        with left:
            st.plotly_chart(donut(indexadas, no_indexadas), use_container_width=True)
        with right:
            mm1, mm2, mm3 = st.columns(3)
            mm1.metric("Total URLs", total)
            mm2.metric("Indexadas", indexadas)
            mm3.metric("No indexadas", no_indexadas)
            if errores:
                st.warning(
                    f"⚠️ {errores} URLs no se pudieron comprobar (Google devolvió "
                    "error). Suele ser **falta de acceso verificado** a esta "
                    "propiedad en Search Console. No se envían a indexar."
                )

            cambios = st.session_state.get("cambios")
            if cambios and (cambios["nuevas_indexadas"] or cambios["perdidas"]):
                if cambios["nuevas_indexadas"]:
                    st.success(
                        f"🟢 {len(cambios['nuevas_indexadas'])} URLs nuevas indexadas "
                        "desde el último análisis"
                    )
                if cambios["perdidas"]:
                    st.error(
                        f"🔴 {len(cambios['perdidas'])} URLs perdieron indexación"
                    )

        st.divider()
        solo_no = st.checkbox("Mostrar solo no indexadas", value=True)
        view = df[(~df["_indexed"]) & (~df["_error"])] if solo_no else df
        st.dataframe(
            view[["URL", "Indexada", "Estado Google"]],
            use_container_width=True,
            hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("URL", width="large")},
        )

        # No indexadas reales (excluye las de error): son las que se envían.
        no_index_urls = df[(~df["_indexed"]) & (~df["_error"])]["URL"].tolist()

        _sin_perm = st.session_state.get("sin_permiso")
        if _sin_perm:
            st.warning(
                f"🔒 No se enviaron a indexar: tu acceso es `{_sin_perm}` y Google "
                "exige ser **Propietario** para solicitar indexación. Pide acceso "
                "de Propietario en esa Search Console (o usa IndexNow para Bing)."
            )

        resumen = st.session_state.get("envio_resumen")
        if resumen is not None:
            if resumen["registradas"] == 0 and resumen["enviadas"] == 0:
                st.caption("No había URLs nuevas que enviar (ya estaban en proceso).")
            else:
                msg = f"📤 {resumen['enviadas']} URLs enviadas a indexar a Google hoy."
                if resumen["en_proceso"]:
                    msg += (
                        f" Quedan **{resumen['en_proceso']}** en proceso "
                        "(se enviarán los próximos días según el cupo)."
                    )
                st.success(msg)
            if resumen["errores"]:
                st.warning(
                    f"{resumen['errores']} no se pudieron enviar a Google "
                    "(¿la cuenta es Propietario de la propiedad?). Puedes reforzar "
                    "con IndexNow en la pestaña *Indexaciones*."
                )

        # Botón manual (por si desactivaste el envío automático o quieres reintentar).
        _es_owner = perms.get(site_url) == "siteOwner"
        if no_index_urls and st.button(
            f"📤 Enviar a indexar {len(no_index_urls)} no indexadas",
            disabled=not _es_owner,
            help=None if _es_owner else "Necesitas ser Propietario de la propiedad.",
        ):
            registradas = storage.add_urls(no_index_urls, site_url, retry_days=retry_days)
            enviadas, errores = enviar_a_indexar(per_domain)
            en_proceso = len(storage.pending())
            st.success(
                f"📤 {enviadas} enviadas a indexar hoy · {en_proceso} en proceso "
                "para los próximos días."
            )
            st.rerun()
    elif not analizando:
        st.empty()

    # --- Prioridad: adelantar este cliente saltándose el tope por dominio ---
    if site_url and not analizando:
        st.write("")
        with st.container(border=True):
            st.markdown("##### ⚡ Priorizar este cliente")
            try:
                _pend_cli = storage.pending(site_url)
                _global_rest = max(0, GLOBAL_CAP - storage.count_sent_today())
            except Exception:  # noqa: BLE001
                _pend_cli, _global_rest = [], 0

            _max_env = min(len(_pend_cli), _global_rest)
            if _max_env > 0:
                st.caption(
                    f"{len(_pend_cli)} URLs en proceso · cupo global libre hoy: "
                    f"{_global_rest}/{GLOBAL_CAP}. Se salta el límite por dominio."
                )
                pcol1, pcol2 = st.columns([1, 2])
                with pcol1:
                    n_prio = st.number_input(
                        "Cuántas enviar ahora",
                        min_value=1, max_value=_max_env, value=min(_max_env, 25),
                        key="prio_n",
                    )
                if st.button(
                    f"⚡ Enviar ya {n_prio} de este cliente (prioridad)",
                    type="primary", key="prio_btn", disabled=not autenticado,
                ):
                    ok_p, err_p = enviar_prioritario(site_url, int(n_prio))
                    st.success(f"⚡ {ok_p} enviadas a indexar con prioridad.")
                    if err_p:
                        st.warning(f"{err_p} con error.")
                    st.rerun()
            else:
                st.caption(
                    "Sin URLs en proceso para este cliente, o el cupo global de hoy "
                    "está agotado."
                )

# ======================================================== TAB INDEXACIONES ===
with tab_cola:
    try:
        items = storage.all_items()
    except Exception as e:  # noqa: BLE001  (p. ej. cuota de Sheets puntual)
        st.warning(
            "No se pudo leer la cola ahora mismo (puede ser un pico de la API de "
            "Google Sheets). Espera unos segundos y recarga."
        )
        st.caption(f"Detalle: {e}")
        st.stop()
    sent_today = storage.count_sent_today()
    pend = [it for it in items if it["status"] == "pending"]
    enviadas_total = sum(1 for it in items if it["status"] == "sent")
    errores_total = sum(1 for it in items if it["status"] == "error")

    izq, der = st.columns([1.4, 1])
    with izq:
        c1, c2, c3 = st.columns(3)
        c1.metric("⏳ En proceso", len(pend))
        c2.metric("📨 Enviadas hoy", sent_today)
        c3.metric("✅ Enviadas (total)", enviadas_total)
        if errores_total:
            st.metric("⚠️ Con error", errores_total)
    with der:
        if items:
            st.plotly_chart(
                donut_estados(len(pend), enviadas_total, errores_total),
                use_container_width=True,
            )

    global_rest = max(0, GLOBAL_CAP - sent_today)
    st.progress(
        min(1.0, sent_today / GLOBAL_CAP) if GLOBAL_CAP else 0.0,
        text=f"Cupo global de hoy: {sent_today}/{GLOBAL_CAP} · {per_domain}/día por dominio",
    )
    st.caption(
        "Las URLs **en proceso** se envían a Google poco a poco "
        f"(máx. {per_domain}/día por dominio) automáticamente con el cron. "
        "Aquí puedes forzar el envío de hoy."
    )

    # ¿Cuántas se enviarían ahora respetando los límites?
    enviables = len(storage.select_to_send(per_domain, GLOBAL_CAP))
    if st.button(
        f"📤 Enviar a indexar ahora ({enviables} disponibles)",
        type="primary",
        disabled=enviables == 0 or not autenticado,
    ):
        enviadas, errores = enviar_a_indexar(per_domain)
        st.success(f"📤 {enviadas} enviadas a indexar a Google.")
        if errores:
            st.warning(f"{errores} con error (revisa permisos de Propietario).")
        st.rerun()

    st.markdown("##### 📡 IndexNow (Bing / Yandex) — gratis, sin tope diario")
    in_key = settings.get("indexnow_key", "")
    if not in_key:
        st.caption("Configura una key de IndexNow en la barra lateral para activarlo.")
    elif site_url:
        pend_cliente = [it["url"] for it in pend if it["site_url"] == site_url]
        st.caption(f"Fichero a alojar en el dominio: `{indexnow.key_file_url(domain, in_key)}`")
        if st.button(
            f"📡 Enviar {len(pend_cliente)} en proceso de este cliente por IndexNow",
            disabled=not pend_cliente,
        ):
            res = indexnow.submit_urls(domain, pend_cliente, in_key)
            (st.success if res.ok else st.error)(f"IndexNow: {res.detail}")
    else:
        st.caption("Selecciona un cliente para enviar por IndexNow.")

    st.divider()
    if items:
        estados = {"pending": "⏳ En proceso", "sent": "✅ Enviada", "error": "⚠️ Error"}
        idf = pd.DataFrame(items)
        idf["Estado"] = idf["status"].map(estados).fillna(idf["status"])
        idf = idf[["url", "site_url", "Estado", "added_at", "sent_at", "detail"]].rename(
            columns={
                "url": "URL", "site_url": "Cliente",
                "added_at": "Añadida", "sent_at": "Enviada", "detail": "Detalle",
            }
        )
        st.dataframe(idf, use_container_width=True, hide_index=True)
    else:
        st.caption("Nada en proceso todavía. Envía no indexadas desde la pestaña Análisis.")

    with st.expander("ℹ️ ¿Cómo se envían solas cada día?"):
        st.markdown(
            "Las URLs en proceso se envían a Google según el cupo diario con el cron de "
            "**GitHub Actions** (`daily-index.yml` → `daily_batch.py`). Así no "
            "tienes que volver a entrar. Consulta el README para activarlo."
        )

# ============================================================ TAB HISTÓRICO ==
with tab_hist:
    if not site_url:
        st.caption("Selecciona un cliente para ver su evolución.")
    else:
        snaps = history.snapshots(site_url)
        if not snaps:
            st.caption("Aún no hay análisis guardados de este cliente. Analízalo primero.")
        else:
            hdf = pd.DataFrame(snaps)
            hdf["Fecha"] = pd.to_datetime(hdf["ts"]).dt.strftime("%Y-%m-%d %H:%M")
            ultimo = snaps[-1]
            primero = snaps[0]
            pct = (ultimo["indexed"] / ultimo["total"] * 100) if ultimo["total"] else 0
            delta = ultimo["indexed"] - primero["indexed"]

            k1, k2, k3 = st.columns(3)
            k1.metric("% indexado (actual)", f"{pct:.0f}%")
            k2.metric("Indexadas (actual)", ultimo["indexed"],
                      delta=f"{delta:+d} vs 1er análisis")
            k3.metric("Análisis guardados", len(snaps))

            chart = hdf.set_index("Fecha")[["indexed", "not_indexed"]].rename(
                columns={"indexed": "Indexadas", "not_indexed": "No indexadas"}
            )
            st.line_chart(chart, color=[VERDE, ROJO])

            with st.expander("Ver tabla del histórico"):
                st.dataframe(
                    hdf[["Fecha", "total", "indexed", "not_indexed"]].rename(
                        columns={
                            "total": "Total",
                            "indexed": "Indexadas",
                            "not_indexed": "No indexadas",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
