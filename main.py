"""
main.py – Einstiegspunkt der openHAB Google Bridge.

Startet zwei Hintergrund-Threads:
  1. Gmail-Polling        (alle POLL_INTERVAL_SECONDS Sekunden)
  2. Kalender-Prüfung     (alle CALENDAR_POLL_INTERVAL_SECONDS Sekunden)

Ausführung:
    python main.py
"""

import time
import threading
from datetime import datetime

from config.settings import settings
from modules.gmail_handler import process_unread_emails
from modules.calendar_handler import process_due_calendar_events


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def email_loop():
    print(f"[MAIN] Gmail-Loop gestartet (Intervall: {settings.POLL_INTERVAL_SECONDS}s)")
    while True:
        try:
            print(f"[{_now()}] Prüfe Gmail-Posteingang...")
            process_unread_emails()
        except Exception as e:
            print(f"[{_now()}] Gmail-Loop Fehler: {e}")
        time.sleep(settings.POLL_INTERVAL_SECONDS)


def calendar_loop():
    print(f"[MAIN] Kalender-Loop gestartet (Intervall: {settings.CALENDAR_POLL_INTERVAL_SECONDS}s)")
    while True:
        try:
            print(f"[{_now()}] Prüfe Google Calendar...")
            process_due_calendar_events()
        except Exception as e:
            print(f"[{_now()}] Kalender-Loop Fehler: {e}")
        time.sleep(settings.CALENDAR_POLL_INTERVAL_SECONDS)


def main():
    print()
    print("=" * 60)
    print("  openHAB Google Bridge")
    print("=" * 60)
    print(f"  openHAB URL:   {settings.OPENHAB_URL}")
    print(f"  Secret Key:    {'✅ gesetzt' if settings.BRIDGE_SECRET_KEY else '❌ NICHT GESETZT!'}")
    print(f"  Gmail-Poll:    alle {settings.POLL_INTERVAL_SECONDS}s")
    print(f"  Kalender:      alle {settings.CALENDAR_POLL_INTERVAL_SECONDS}s")
    print(f"  SSE-Timeout:   {settings.SSE_TIMEOUT_SECONDS}s")
    print("=" * 60)
    print()

    if not settings.BRIDGE_SECRET_KEY:
        print("⚠️  WARNUNG: BRIDGE_SECRET_KEY ist leer!")
        print("   Alle E-Mails und Kalendertermine werden abgelehnt.")
        print("   Bitte .env konfigurieren und Bridge neu starten.")
        print()

    t_mail = threading.Thread(target=email_loop, daemon=True, name="GmailLoop")
    t_cal = threading.Thread(target=calendar_loop, daemon=True, name="CalendarLoop")

    t_mail.start()
    t_cal.start()

    print("[MAIN] Bridge läuft. Zum Beenden: Strg+C")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[MAIN] Bridge beendet.")


if __name__ == "__main__":
    main()
