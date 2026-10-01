"""
google_auth.py – Zentrales OAuth2-Modul für Gmail und Google Calendar.

Lädt und erneuert das Token automatisch aus google_token.json.
Beim ersten Start (kein Token vorhanden) wird der Browser-Flow gestartet.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config.settings import settings


def get_credentials() -> Credentials:
    """
    Gibt gültige OAuth2-Credentials zurück.
    Erneuert das Token automatisch wenn abgelaufen.
    Startet den Browser-Flow wenn noch kein Token existiert.
    """
    creds = None

    if os.path.exists(settings.TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            settings.TOKEN_FILE, settings.GOOGLE_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(settings.CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{settings.CREDENTIALS_FILE}' nicht gefunden!\n"
                    "Bitte credentials.json aus der Google Cloud Console "
                    "herunterladen und ins Projektverzeichnis kopieren.\n"
                    "Siehe README.md → Schritt 3."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.CREDENTIALS_FILE, settings.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Token speichern
        with open(settings.TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())

    return creds
