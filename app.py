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

DAILY_LIMIT = 3  # máximo de URLs a enviar por día (drip-feed)

# Paleta de marca (La Fábrica del SEO)
NARANJA = "#F26C21"   # naranja del logo
NARANJA2 = "#FF8A3D"  # naranja claro (degradado)
GRIS = "#37373A"      # gris oscuro del logo
VERDE = "#16a34a"     # semántico: indexada / OK
ROJO = "#dc2626"      # semántico: no indexada / error

# ---------------------------------------------------------------- estilos ----
st.markdown(
    """
    <style>
      #MainMenu, footer {visibility: hidden;}
      .block-container {padding-top: 1.4rem; max-width: 1150px;}
      h1, h2, h3 {color: #37373A;}

      /* Cabecera minimalista */
      .appbar {display: flex; align-items: baseline; gap: .7rem;
        padding-bottom: .5rem; border-bottom: 1px solid #ECEAE7; margin-bottom: .2rem;}
      .appbar .logo {font-size: 1.55rem; font-weight: 800; color: #37373A; letter-spacing: -.02em;}
      .appbar .logo .dot {color: #F26C21;}
      .appbar .tag {font-size: .72rem; color: #A6A6AB; text-transform: uppercase;
        letter-spacing: .1em; margin-left: auto;}

      /* Tarjetas de métricas sobrias */
      div[data-testid="stMetric"] {
        background: #fff; border: 1px solid #EDECEA; border-radius: 12px;
        padding: .85rem 1.05rem;
      }
      div[data-testid="stMetricLabel"] p {font-weight: 600; color: #8a8a8f; font-size: .82rem;}

      /* --- Botones --- */
      .stButton > button, .stFormSubmitButton > button {
        border-radius: 9px; font-weight: 600; padding: .5rem 1.1rem;
        transition: all .15s ease; border: 1px solid #E2E0DD;
      }
      /* Primario: naranja sólido */
      .stButton > button[kind="primary"],
      .stFormSubmitButton > button[kind="primaryFormSubmit"] {
        background: #F26C21; border-color: #F26C21; color: #fff;
        box-shadow: 0 2px 6px rgba(242,108,33,.25);
      }
      .stButton > button[kind="primary"]:hover,
      .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover {
        background: #D9531A; border-color: #D9531A; color: #fff;
        box-shadow: 0 4px 12px rgba(242,108,33,.35);
      }
      /* Secundario: contorno sobrio que se ilumina en naranja */
      .stButton > button[kind="secondary"],
      .stFormSubmitButton > button[kind="secondaryFormSubmit"] {
        background: #fff; color: #37373A;
      }
      .stButton > button[kind="secondary"]:hover,
      .stFormSubmitButton > button[kind="secondaryFormSubmit"]:hover {
        border-color: #F26C21; color: #D9531A; background: #fff;
      }
      /* Deshabilitado */
      .stButton > button:disabled, .stButton > button:disabled:hover {
        background: #F3F2F0; border-color: #ECEAE7; color: #BBB9B6;
        box-shadow: none; cursor: not-allowed;
      }

      button[data-baseweb="tab"] {font-size: .98rem; font-weight: 600;}
      a, a:visited {color: #D9531A;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Control de acceso (login de equipo en la nube). En local, sin secrets, pasa directo.
usuario_actual = access.require_login()

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


def enviar_a_indexar(limite_restante: int):
    """Envía hasta `limite_restante` URLs en proceso a Google (Indexing API).

    Devuelve (enviadas_ok, errores). Respeta el goteo: solo manda las que
    caben en el cupo de hoy; el resto se quedan en proceso para el cron.
    """
    if limite_restante <= 0:
        return 0, 0
    lote = storage.take_batch(limite_restante)
    ok = err = 0
    for it in lote:
        res = indexing.publish_url(it["url"])
        storage.mark(it["url"], "sent" if res.ok else "error", res.detail)
        if res.ok:
            ok += 1
        else:
            err += 1
    return ok, err


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
    st.markdown("**Acceso a Google**")
    if autenticado:
        st.success(identidad)
        if auth.has_oauth_token():
            if st.button("🚪 Cerrar sesión", use_container_width=True):
                auth.oauth_logout()
                st.session_state.sites = None
                st.rerun()
    else:
        st.error("Sin sesión iniciada.")

    # Login OAuth (recomendado para muchos clientes).
    if auth.has_client_secret() and not auth.has_oauth_token():
        st.caption("Inicia sesión con tu cuenta de agencia para ver todos tus clientes.")
        if st.button("🔐 Iniciar sesión con Google", type="primary", use_container_width=True):
            with st.spinner("Abriendo el navegador para autorizar…"):
                try:
                    auth.oauth_login()
                    st.session_state.sites = None
                    st.success("¡Sesión iniciada!")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"No se pudo iniciar sesión: {e}")
    elif not auth.has_client_secret() and not autenticado:
        st.caption(
            "Para OAuth, coloca `client_secret.json` en la carpeta del proyecto "
            "(o usa una cuenta de servicio). Ver README."
        )

    st.divider()
    daily_limit = st.number_input(
        "URLs a enviar por día (Google)", min_value=1, max_value=20, value=DAILY_LIMIT
    )
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
            st.session_state.sites = gsc.list_sites()
        except Exception as e:  # noqa: BLE001
            st.session_state.sites = []
            st.error(f"No se pudieron cargar las propiedades: {e}")

site_url = None
domain = None
perms = {}

with sel_cols[0]:
    if st.session_state.sites is None:
        st.caption("Pulsa **Cargar clientes** para traer tus propiedades de Search Console.")
    elif not st.session_state.sites:
        st.warning(
            "No hay propiedades accesibles. Añade el email de la cuenta de "
            "servicio como usuario en la Search Console de tus clientes."
        )
    else:
        site_urls = [s["siteUrl"] for s in st.session_state.sites]
        perms = {s["siteUrl"]: s.get("permissionLevel", "?") for s in st.session_state.sites}
        site_url = st.selectbox(
            "👤 Cliente", options=site_urls, format_func=clients.label_for
        )
        domain = clients.domain_from_site_url(site_url)

if site_url:
    chips = st.columns([2, 2, 3])
    chips[0].caption(f"Propiedad: `{site_url}`")
    chips[1].caption(f"Permiso: `{perms.get(site_url, '?')}`")
    with chips[2]:
        current = clients.load_names().get(site_url, "")
        new_name = st.text_input(
            "Nombre amigable", value=current, key=f"name_{site_url}",
            label_visibility="collapsed", placeholder="Nombre amigable del cliente",
        )
        if st.button("💾 Guardar nombre"):
            clients.set_name(site_url, new_name)
            st.rerun()
    if perms.get(site_url) not in ("siteOwner", "siteFullUser"):
        st.warning(
            "Con este permiso podrás comprobar indexación, pero para **solicitar "
            "indexación** la cuenta debe ser **Propietario** de la propiedad."
        )

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
        "las que caben hoy y el resto quedan en proceso (el cron las envía a "
        "2-3/día).",
    )

    BATCH = 10  # URLs por tanda (entre tandas se puede pulsar Parar)

    # --- Arranque del análisis: lee el sitemap y prepara el estado por tandas ---
    if analizar:
        with st.spinner("Leyendo sitemap…"):
            urls, log = sitemap.fetch_urls(domain, max_urls=max_urls)
        if urls:
            st.session_state.results = None
            st.session_state.an = {
                "running": True,
                "site_url": site_url,
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

        # Procesa una tanda y vuelve a ejecutar (deja hueco para pulsar Parar).
        svc = gsc.make_service()
        for url in an["urls"][an["i"]:an["i"] + BATCH]:
            r = gsc.inspect_url(an["site_url"], url, service=svc)
            an["rows"].append({
                "URL": r.url,
                "Indexada": "✅" if r.indexed else "❌",
                "Estado Google": r.coverage_state,
                "_indexed": r.indexed,
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
        st.session_state.cambios = history.add_snapshot(
            an["site_url"], [{"url": r["URL"], "indexed": r["_indexed"]} for r in rows]
        )
        if an["auto"] and rows:
            no_idx = [r["URL"] for r in rows if not r["_indexed"]]
            registradas = storage.add_urls(no_idx, an["site_url"], retry_days=retry_days)
            restante = max(0, daily_limit - storage.count_sent_today())
            enviadas, errores = enviar_a_indexar(restante)
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
        total = len(df)
        indexadas = int(df["_indexed"].sum())
        no_indexadas = total - indexadas

        left, right = st.columns([1, 1.4])
        with left:
            st.plotly_chart(donut(indexadas, no_indexadas), use_container_width=True)
        with right:
            mm1, mm2, mm3 = st.columns(3)
            mm1.metric("Total URLs", total)
            mm2.metric("Indexadas", indexadas)
            mm3.metric("No indexadas", no_indexadas)

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
        view = df[~df["_indexed"]] if solo_no else df
        st.dataframe(
            view[["URL", "Indexada", "Estado Google"]],
            use_container_width=True,
            hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("URL", width="large")},
        )

        no_index_urls = df[~df["_indexed"]]["URL"].tolist()

        resumen = st.session_state.get("envio_resumen")
        if resumen is not None:
            if resumen["registradas"] == 0 and resumen["enviadas"] == 0:
                st.caption("No había URLs nuevas que enviar (ya estaban en proceso).")
            else:
                msg = f"📤 {resumen['enviadas']} URLs enviadas a indexar a Google hoy."
                if resumen["en_proceso"]:
                    msg += (
                        f" Quedan **{resumen['en_proceso']}** en proceso "
                        "(se enviarán los próximos días, 2-3/día)."
                    )
                st.success(msg)
            if resumen["errores"]:
                st.warning(
                    f"{resumen['errores']} no se pudieron enviar a Google "
                    "(¿la cuenta es Propietario de la propiedad?). Puedes reforzar "
                    "con IndexNow en la pestaña *Indexaciones*."
                )

        # Botón manual (por si desactivaste el envío automático o quieres reintentar).
        if no_index_urls and st.button(
            f"📤 Enviar a indexar {len(no_index_urls)} no indexadas"
        ):
            registradas = storage.add_urls(no_index_urls, site_url, retry_days=retry_days)
            restante = max(0, daily_limit - storage.count_sent_today())
            enviadas, errores = enviar_a_indexar(restante)
            en_proceso = len(storage.pending())
            st.success(
                f"📤 {enviadas} enviadas a indexar hoy · {en_proceso} en proceso "
                "para los próximos días."
            )
            st.rerun()
    elif not analizando:
        st.caption("Selecciona un cliente y pulsa **Analizar** para empezar.")

# ======================================================== TAB INDEXACIONES ===
with tab_cola:
    items = storage.all_items()
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

    restante = max(0, daily_limit - sent_today)
    st.progress(
        min(1.0, sent_today / daily_limit) if daily_limit else 0.0,
        text=f"Cupo de envío a Google de hoy: {sent_today}/{daily_limit} (quedan {restante})",
    )
    st.caption(
        "Las URLs **en proceso** se envían a Google poco a poco (2-3/día) "
        "automáticamente con el cron. Aquí puedes forzar el envío de hoy."
    )

    if st.button(
        f"📤 Enviar a indexar ahora ({restante} de hoy)",
        type="primary",
        disabled=restante == 0 or not pend or not autenticado,
    ):
        enviadas, errores = enviar_a_indexar(restante)
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
            "Las URLs en proceso se envían a Google a 2-3/día con el cron de "
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
