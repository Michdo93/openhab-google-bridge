"""
auth_setup.py – Einmalige OAuth2-Authentifizierung mit Google.

Dieses Skript muss einmalig ausgeführt werden. Es öffnet den Browser,
du meldest dich mit dem Google-Konto an und erteilst die Berechtigungen.
Das Token wird in google_token.json gespeichert und danach automatisch
von der Bridge verwendet und bei Bedarf erneuert.

Ausführung:
    python auth_setup.py
"""

import os
from modules.google_auth import get_credentials
from config.settings import settings


def main():
    print("=" * 60)
    print("  openHAB Google Bridge – OAuth2 Ersteinrichtung")
    print("=" * 60)
    print()

    if not os.path.exists(settings.CREDENTIALS_FILE):
        print(f"❌ '{settings.CREDENTIALS_FILE}' nicht gefunden!")
        print()
        print("Bitte zuerst die credentials.json aus der Google Cloud Console")
        print("herunterladen und ins Projektverzeichnis kopieren.")
        print()
        print("Anleitung:")
        print("  1. https://console.cloud.google.com/ öffnen")
        print("  2. Dein Projekt auswählen")
        print("  3. APIs & Services → Anmeldedaten")
        print("  4. OAuth 2.0-Client-ID herunterladen (JSON)")
        print("  5. Als 'credentials.json' hier ablegen")
        return

    if os.path.exists(settings.TOKEN_FILE):
        print(f"✅ Token-Datei '{settings.TOKEN_FILE}' bereits vorhanden.")
        print("   Zum Neu-Authentifizieren bitte google_token.json löschen.")
        print()
        print("Du kannst die Bridge jetzt starten:")
        print("    python main.py")
        return

    print("Starte Browser für Google-Authentifizierung...")
    print()
    print("➡  Ein Browser-Fenster öffnet sich.")
    print("   Melde dich mit dem Google-Konto an, das du für die Bridge")
    print("   verwenden möchtest, und erteile alle Berechtigungen.")
    print()
    print("⚠️  Hinweis: Google zeigt möglicherweise eine Warnung")
    print("   'Diese App wurde nicht verifiziert'. Das ist normal,")
    print("   da wir die App im Testing-Modus betreiben.")
    print("   Klicke auf 'Erweitert' → 'Zu [Projektname] (unsicher)'")
    print("   um fortzufahren.")
    print()

    try:
        creds = get_credentials()
        if creds and creds.valid:
            print("✅ Authentifizierung erfolgreich!")
            print(f"   Token gespeichert in: {settings.TOKEN_FILE}")
            print()
            print("Du kannst die Bridge jetzt starten:")
            print("    python main.py")
        else:
            print("❌ Authentifizierung fehlgeschlagen.")
    except Exception as e:
        print(f"❌ Fehler: {e}")


if __name__ == "__main__":
    main()
