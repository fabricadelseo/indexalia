"""Primer inicio de sesión OAuth con Google. Ejecuta:  python login.py

Abre el navegador para autorizar Indexalia y guarda token.json (se renueva
solo a partir de entonces). Solo hay que hacerlo una vez.
"""

from core import auth


def main() -> None:
    print("Abriendo el navegador para autorizar Indexalia con tu cuenta de Google...")
    print("(Si sale 'App no verificada': Configuracion avanzada -> Ir a Indexalia -> Permitir)\n")
    auth.oauth_login()
    print("\nOK: sesion iniciada. Se ha creado token.json.")
    print("Ahora ejecuta:  python test_conexion.py")


if __name__ == "__main__":
    main()
