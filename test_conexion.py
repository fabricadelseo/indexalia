"""Diagnóstico de conexión con Google — ejecútalo tras pegar las credenciales.

    python test_conexion.py

Comprueba, en orden:
  1. Que se cargan las credenciales (service_account.json o env/secrets).
  2. Que las APIs responden y lista las propiedades de Search Console
     a las que la cuenta de servicio tiene acceso.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("== Indexalia · diagnóstico de conexión ==\n")

    # 1) Credenciales
    try:
        from core import auth

        identidad = auth.identity_label()
        if not identidad:
            print("❌ No hay sesión iniciada.")
            print("   Inicia sesión con OAuth desde la app (client_secret.json),")
            print("   o coloca service_account.json en esta carpeta.")
            return 1
        print(f"✅ {identidad}\n")
    except Exception as e:  # noqa: BLE001
        print(f"❌ Error cargando credenciales: {e}")
        return 1

    # 2) Acceso a Search Console
    try:
        from core import gsc

        sites = gsc.list_sites()
    except Exception as e:  # noqa: BLE001
        print(f"❌ Error llamando a Search Console: {e}")
        print("   ¿Has habilitado la 'Google Search Console API' en Google Cloud?")
        return 1

    if not sites:
        print("⚠️  Conexión OK, pero la cuenta no tiene acceso a ninguna propiedad.")
        print("   Añade el email de arriba como USUARIO en la Search Console de tus")
        print("   clientes (y como PROPIETARIO si vas a reindexar).")
        return 0

    print(f"✅ Acceso a {len(sites)} propiedad(es) de Search Console:\n")
    for s in sites:
        print(f"   • {s['siteUrl']:45s} permiso: {s.get('permissionLevel', '?')}")
    print("\n🎉 Todo listo. Ya puedes usar Indexalia con estos clientes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
