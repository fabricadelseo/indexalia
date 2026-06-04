"""Genera el bloque de SECRETS para Streamlit Cloud. Ejecuta:

    python generar_secrets.py "clave-del-equipo"

Incluye TODAS las cuentas de Google conectadas (token.json + tokens/*.json).
Pega lo que imprime en Streamlit Cloud -> Settings -> Secrets.
No lo subas a ningún sitio: contiene tus tokens.
"""

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_TOKEN = _BASE / "token.json"
_TOKENS_DIR = _BASE / "tokens"


def _tokens() -> list[str]:
    out = []
    if _TOKEN.exists():
        out.append(_TOKEN.read_text(encoding="utf-8").strip())
    if _TOKENS_DIR.exists():
        for p in sorted(_TOKENS_DIR.glob("*.json")):
            out.append(p.read_text(encoding="utf-8").strip())
    return out


def main() -> int:
    toks = _tokens()
    if not toks:
        print("ERROR: no hay tokens. Ejecuta antes: python login.py (y python add_cuenta.py)")
        return 1

    pwd = sys.argv[1] if len(sys.argv) > 1 else "CAMBIA-ESTA-CLAVE"

    print("\n================ COPIA DESDE AQUÍ ================\n")
    print(f'app_password = "{pwd}"')
    print()
    for i, tok in enumerate(toks):
        clave = "google_oauth_token" if i == 0 else f"google_oauth_token_{i + 1}"
        print(f"{clave} = '''")
        print(tok)
        print("'''")
        print()
    print('# sheet_id = "PEGA_AQUI_EL_ID_DE_TU_HOJA"')
    print('# indexnow_key = "tu-key"   # opcional')
    print(f"\n# ({len(toks)} cuenta(s) de Google incluida(s))")
    print("\n================ HASTA AQUÍ ================\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
