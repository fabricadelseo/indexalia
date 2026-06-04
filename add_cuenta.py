"""Conecta una cuenta de Google ADICIONAL. Ejecuta:  python add_cuenta.py

Abre el navegador para autorizar OTRA cuenta (elige la cuenta nueva en el
selector de Google). Guarda su token en tokens/<email>.json. Repite para
cada cuenta extra que quieras añadir.
"""

from core import auth


def main() -> None:
    print("Abriendo el navegador para autorizar OTRA cuenta de Google...")
    print("(Elige la cuenta NUEVA; si sale 'App no verificada' -> Avanzada -> Continuar)\n")
    email = auth.add_account()
    print(f"\nOK: cuenta añadida -> {email}")
    print("Ya aparece junto a las demás al pulsar 'Cargar clientes'.")
    print("Para la app online, vuelve a generar los secrets: python generar_secrets.py \"clave\"")


if __name__ == "__main__":
    main()
