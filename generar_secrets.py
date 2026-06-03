"""Genera el bloque de SECRETS para Streamlit Cloud. Ejecuta:

    python generar_secrets.py "clave-del-equipo"

Imprime el texto listo para pegar en Streamlit Cloud -> Settings -> Secrets.
No subas esto a ningún sitio: contiene tu token de Google.
"""

import sys
from pathlib import Path

_TOKEN = Path(__file__).resolve().parent / "token.json"


def main() -> int:
    if not _TOKEN.exists():
        print("ERROR: no existe token.json. Ejecuta antes: python login.py")
        return 1

    pwd = sys.argv[1] if len(sys.argv) > 1 else "CAMBIA-ESTA-CLAVE"
    token = _TOKEN.read_text(encoding="utf-8").strip()

    print("\n================ COPIA DESDE AQUÍ ================\n")
    print(f'app_password = "{pwd}"')
    print()
    print("google_oauth_token = '''")
    print(token)
    print("'''")
    print()
    print('# sheet_id = "PEGA_AQUI_EL_ID_DE_TU_HOJA"   # para la cola compartida')
    print('# indexnow_key = "tu-key"                    # opcional (Bing/Yandex)')
    print("\n================ HASTA AQUÍ ================\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
