# 🔎 Indexalia

> **by La Fábrica del SEO** · [indexalia.es](https://indexalia.es)

Herramienta visual (Streamlit) para clientes de agencia: dado un dominio,
saca las URLs de su sitemap, detecta **cuáles no están indexadas** en Google
y solicita su indexación de forma **escalonada (2-3 URLs/día)**.

> Funciona solo con **dominios que controlas** y que tengas verificados en
> Google Search Console. Esto es lo que hace la herramienta 100% legítima.

---

## ¿Qué hace cada parte?

| Componente | Función |
|---|---|
| `app.py` | Panel visual: analizar dominio, ver indexación, gestionar la cola |
| `core/sitemap.py` | Descarga y parsea sitemaps (incluye índices anidados y robots.txt) |
| `core/clients.py` | Nombres amigables de clientes (`data/clients.json`) |
| `core/gsc.py` | Lista de propiedades + URL Inspection API (¿indexada?) |
| `core/indexing.py` | Indexing API de Google → solicita la indexación |
| `core/indexnow.py` | IndexNow → avisa a Bing/Yandex (gratis, sin tope diario) |
| `core/storage.py` | Cola de URLs (despachador de backend) |
| `core/json_backend.py` | Backend de cola en JSON local (`data/queue.json`) |
| `core/sheets_backend.py` | Backend de cola en Google Sheets (app + cron comparten) |
| `core/settings.py` | Ajustes (key de IndexNow, `sheet_id`) |
| `core/history.py` | Histórico de indexación (`data/history.json`) |
| `daily_batch.py` | Envía el lote diario (2-3 URLs). Lo ejecuta el cron |
| `.github/workflows/daily-index.yml` | Cron diario en GitHub Actions |

---

## Puesta en marcha (paso a paso)

Hay dos formas de autenticarse. **OAuth es la recomendada para agencias con
muchos clientes**: inicias sesión una vez con tu cuenta y ves TODAS las
propiedades a las que ya tienes acceso, sin tocar la Search Console de cada
cliente.

### Opción 1 — OAuth (recomendado, login con tu cuenta) ⭐
1. En [Google Cloud Console](https://console.cloud.google.com/) → crea un proyecto.
2. **APIs y servicios → Biblioteca**, habilita:
   - *Google Search Console API*
   - *Web Search Indexing API*
3. **APIs y servicios → Pantalla de consentimiento de OAuth**:
   - Tipo **Externo** → rellena lo básico (nombre de app, tu email).
   - En **Usuarios de prueba**, añade tu cuenta de Google.
   - Para que la sesión **no caduque cada 7 días**, pon el estado de
     publicación en **"En producción"** (saldrá un aviso de "app no
     verificada" que puedes saltar con *Configuración avanzada → Continuar*;
     para uso interno propio no necesitas verificación de Google).
4. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de
   OAuth → Tipo: Aplicación de escritorio**. Descarga el JSON.
5. Renómbralo a **`client_secret.json`** y déjalo en la raíz del proyecto.
6. Arranca la app, barra lateral → **🔐 Iniciar sesión con Google**. Se abre el
   navegador, autorizas, y se guarda `token.json` (se renueva solo).

### Opción 2 — Cuenta de servicio (acceso aislado por propiedad)
1. Mismos pasos 1–2 de arriba (proyecto + APIs).
2. **Credenciales → Crear credencial → Cuenta de servicio** → pestaña
   **Claves → Añadir clave → JSON**.
3. Guárdalo como `service_account.json` en la raíz.
4. Añade su email (`...iam.gserviceaccount.com`) como usuario/propietario en la
   Search Console de **cada** cliente. (Manual; mejor OAuth si tienes muchos.)

### Permisos necesarios
- **Comprobar indexación** → cualquier nivel de acceso a la propiedad.
- **Solicitar indexación (Indexing API)** → debes ser **Propietario** de esa
  propiedad. Donde no lo seas, refuerza con **IndexNow** (Bing/Yandex).

### Ejecutar y comprobar
```bash
pip install -r requirements.txt
python test_conexion.py     # diagnóstico: lista tus propiedades
streamlit run app.py
```

---

## Despliegue en Streamlit Community Cloud (multiusuario) ⭐
Para que la use **todo el equipo** desde una URL, con login propio:

1. **Prepara en local** (una vez):
   - Inicia sesión OAuth en la app (botón 🔐) → genera `token.json`.
   - `python exportar_token.py` → copia el token.
   - Crea la hoja de Google Sheets y apunta su `sheet_id` (ver sección Sheets).
2. **Sube el repo a GitHub** (los `*.json` de credenciales no se suben, están en
   `.gitignore`).
3. En [share.streamlit.io](https://share.streamlit.io) conecta el repo y elige
   `app.py`.
4. En **Settings → Secrets** pega (ver `.streamlit/secrets.toml.example`):
   ```toml
   app_password = "clave-del-equipo"

   google_oauth_token = '''<contenido de token.json>'''
   sheet_id = "ID_DE_TU_HOJA"
   # indexnow_key = "..."   # opcional
   ```
5. Todo el equipo entra con la **misma contraseña**. **Comparten** la misma
   cuenta de Google (acceso a los clientes) y la misma hoja de Sheets (lista
   "en proceso"), así que veis lo mismo en tiempo real.

> 🔒 El login protege la URL pública. Sin `app_password` (ni `[passwords]`) la
> app queda **abierta** (úsalo solo en local).
>
> ⚠️ En Streamlit Cloud el disco es efímero: por eso la lista "en proceso" va en
> **Google Sheets** (no en `queue.json`). El cron de GitHub Actions usa esa misma
> hoja, así que ambos están siempre sincronizados.

---

## Envío automático diario (2-3 URLs/día)
`daily_batch.py` coge el lote del día, lo envía a Google (drip-feed) y, si hay
key de IndexNow, avisa también a Bing/Yandex de esas mismas URLs.

### Opción A — GitHub Actions (recomendado, sin tu PC encendido) ⭐
En modo online, la app (Streamlit Cloud) y el cron (GitHub Actions) comparten la
lista "en proceso" mediante **Google Sheets**. Pasos, una sola vez:

1. **Cola en Google Sheets** (ver sección más abajo): crea la hoja, compártela y
   apunta su `sheet_id`.
2. **Inicia sesión OAuth en local** una vez (botón 🔐 de la app) para generar
   `token.json`. Luego ejecuta `python exportar_token.py` y copia lo que imprime.
3. Sube el repo a GitHub.
4. **Settings → Secrets and variables → Actions → New repository secret** y crea:
   - `GOOGLE_OAUTH_TOKEN` → el contenido de `token.json` (del paso 2). **Obligatorio.**
   - `SHEET_ID` → ID de tu hoja de Google Sheets. **Obligatorio en modo online.**
   - `INDEXNOW_KEY` → tu key de IndexNow (opcional, para avisar a Bing/Yandex).
   - *(alternativa a OAuth)* `GCP_SA_JSON` → JSON de cuenta de servicio.
5. El workflow `daily-index.yml` corre a las 08:00 UTC y envía el lote del día
   (Google + IndexNow). Cambia el `cron` o `DAILY_LIMIT` a tu gusto.
6. Para probarlo sin esperar: pestaña **Actions → "Envío diario a indexar" →
   Run workflow**. Revisa el log: debe listar las URLs enviadas.

> 💡 El token OAuth caduca si dejaste la pantalla de consentimiento en "Testing".
> Ponla **En producción** (sin verificar) para que el refresh token dure.

### Opción B — Programador de tareas de Windows (local)
Si prefieres no usar GitHub, programa el script en tu PC:
```powershell
# Crea una tarea diaria a las 09:00 que ejecuta el script
$accion  = New-ScheduledTaskAction -Execute "python" `
  -Argument "daily_batch.py" -WorkingDirectory "C:\Users\car87\.claude\indexador-seo"
$disparo = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -TaskName "IndexadorSEO" -Action $accion -Trigger $disparo
```
Requiere tener `service_account.json` en la carpeta (y el PC encendido a esa hora).

---

## IndexNow (Bing / Yandex) — opcional, gratis
A diferencia de Google, IndexNow **sí** soporta oficialmente cualquier URL y no
tiene tope diario. Para activarlo:
1. En la **barra lateral** de la app, pulsa "🎲 Generar" para crear una key
   (o pega la tuya) y "💾 Guardar key".
2. Sube un fichero `<key>.txt` con la key dentro a la **raíz de cada dominio**
   de cliente (la app te muestra la URL exacta donde debe quedar).
3. Usa el botón "📡 Enviar … por IndexNow" en la sección de la cola.

El cron no usa IndexNow por defecto (no hace falta racionarlo), pero puedes
añadirlo si quieres.

---

## Cola en Google Sheets — opcional, recomendado para producción
Hace que la app (Streamlit) y el cron (GitHub Actions) compartan la MISMA cola,
sin depender del disco efímero ni de commits.
1. Crea una hoja de cálculo en Google Sheets.
2. Compártela con el email de la cuenta de servicio, permiso **Editor**.
3. Copia el ID de la hoja (lo que va entre `/d/` y `/edit` en la URL).
4. Configúralo como ajuste `sheet_id`:
   - **Local:** se guarda en `data/settings.json` (o variable `SHEET_ID`).
   - **Streamlit Cloud:** añade `sheet_id = "..."` en *Secrets*.
   - **GitHub Actions:** añade un Secret `SHEET_ID` y pásalo al workflow.

Cuando hay `sheet_id`, la app conmuta sola al backend de Sheets (lo verás
indicado en la barra lateral: *Cola: Google Sheets*).

---

## Notas importantes / límites
- **URL Inspection API:** ~2.000 inspecciones/día y ~600/min por propiedad.
- **Indexing API:** oficialmente solo soporta `JobPosting`/`BroadcastEvent`.
  Para páginas normales funciona en la práctica, pero al no ser uso soportado
  enviamos pocas URLs/día (drip-feed) para minimizar riesgos.
- Indexar **no** está garantizado: Google decide. La herramienta solicita y
  acelera el rastreo, no obliga a indexar.
