"""
gmail_sender.py – Versendet Antwort-E-Mails über die Gmail API.
"""

import base64
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from modules.google_auth import get_credentials


def send_reply(to_address: str, subject: str, body: str) -> bool:
    """
    Sendet eine E-Mail.

    Returns:
        True bei Erfolg, False bei Fehler.
    """
    try:
        creds = get_credentials()
        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(body, "plain", "utf-8")
        message["To"] = to_address
        message["Subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        print(f"[GMAIL_SENDER] E-Mail an {to_address} gesendet: {subject}")
        return True

    except Exception as e:
        print(f"[GMAIL_SENDER] Fehler beim Senden: {e}")
        return False
