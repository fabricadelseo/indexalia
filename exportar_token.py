"""Muestra el contenido de token.json para pegarlo en los secrets.

Tras iniciar sesión OAuth en la app (se crea token.json), ejecuta:

    python exportar_token.py

Copia TODO lo que imprime y pégalo en:
  - GitHub  -> Settings ▸ Secrets ▸ Actions ▸ GOOGLE_OAUTH_TOKEN
  - Streamlit Cloud -> Settings ▸ Secrets, como:
        google_oauth_token = '''<lo que imprime>'''
"""

from pathlib import Path

_TOKEN = Path(__file__).resolve().parent / "token.json"


def main() -> int:
    if not _TOKEN.exists():
        print("❌ No existe token.json. Inicia sesión con Google en la app primero.")
        return 1
    print("----- COPIA DESDE AQUÍ -----")
    print(_TOKEN.read_text(encoding="utf-8").strip())
    print("----- HASTA AQUÍ -----")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
