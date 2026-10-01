"""
calendar_handler.py – Google Calendar-basierte openHAB-Automatisierung.

Termin-Format:
  Titel:       CMD: <ItemName>   (oder cmd: / Command: / command:)
  Beschreibung:
    Zeile 1: Command
    Zeile 2: BRIDGE_SECRET_KEY

Ablauf:
  1. Termin wird zum Startzeitpunkt erkannt (±2 Min. Fenster)
  2. Key geprüft, Command an openHAB gesendet
  3. Erfolg  → Termin-Farbkennung auf Grün (SAGE) gesetzt = "Zusage"
  4. Fehler   → Termin-Farbkennung auf Rot (TOMATO) gesetzt = "Absage"
  5. Bereits verarbeitete und gelöschte Termine werden übersprungen

Kalenderabfragen:
  today, tomorrow, next_hour, week, accepted (grün), declined (rot), all

Kalenderabfragen per E-Mail:
  Betreff: GET CALENDAR: today  (usw.)
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from googleapiclient.discovery import build

from modules.google_auth import get_credentials
from modules.security import validate_key
from modules import openhab_client as oh
from config.settings import settings


CMD_TITLE_PATTERN = re.compile(
    r"^(CMD|cmd|Command|command)\s*:\s*(.+)$", re.IGNORECASE
)

# Google Calendar Farb-IDs als "Status"-Ersatz
# (Google Calendar hat keine accept/decline-API für eigene Termine)
COLOR_ACCEPTED = "2"   # SAGE (Grün) = Zusage / erfolgreich ausgeführt
COLOR_DECLINED = "11"  # TOMATO (Rot) = Absage / Fehler
COLOR_PENDING  = None  # Standardfarbe = noch nicht verarbeitet

# Marker im Extended-Property, um doppelte Ausführung zu verhindern
PROCESSED_MARKER = "openhab_bridge_processed"


# ---------------------------------------------------------------------------
# Fällige Termine verarbeiten
# ---------------------------------------------------------------------------

def process_due_calendar_events():
    """
    Wird regelmäßig aufgerufen.
    Verarbeitet Termine, deren Startzeit jetzt ±2 Min. liegt und
    die noch nicht als verarbeitet markiert sind.
    """
    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(minutes=2)).isoformat()
        time_max = (now + timedelta(minutes=2)).isoformat()

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])

        for event in events:
            _process_event(service, event)

    except Exception as e:
        print(f"[CALENDAR] Fehler bei der Verarbeitung: {e}")


def _process_event(service, event: dict):
    title = event.get("summary", "").strip()
    description = event.get("description", "").strip()
    event_id = event.get("id", "")

    # Nur CMD-Termine
    m = CMD_TITLE_PATTERN.match(title)
    if not m:
        return

    item_name = m.group(2).strip()

    # Abgesagt / gelöscht?
    if event.get("status") == "cancelled":
        print(f"[CALENDAR] Termin '{title}' ist abgesagt – überspringe.")
        return

    # Bereits verarbeitet?
    ext_props = event.get("extendedProperties", {}).get("private", {})
    if ext_props.get(PROCESSED_MARKER):
        print(f"[CALENDAR] Termin '{title}' bereits verarbeitet – überspringe.")
        return

    print(f"[CALENDAR] Verarbeite: '{title}' → Item: '{item_name}'")

    # Key validieren
    valid, command, err = validate_key(description)
    if not valid:
        print(f"[CALENDAR] Sicherheitsfehler: {err}")
        _mark_event(service, event_id, success=False, reason=err)
        return

    if not command:
        _mark_event(service, event_id, success=False, reason="Kein Command in Zeile 1")
        return

    # Item prüfen
    item_data = oh.get_item(item_name)
    if item_data is None:
        _mark_event(service, event_id, success=False,
                    reason=f"Item '{item_name}' nicht gefunden")
        return

    item_type = item_data.get("type", "Unbekannt")

    # SSE-Listener ZUERST starten, dann Command senden
    cmd_ok, changed, new_state, err = oh.send_command_and_wait(
        item_name, command, timeout=settings.SSE_TIMEOUT_SECONDS
    )

    if not cmd_ok:
        print(f"[CALENDAR] '{title}' – Command-Fehler: {err}")
        _mark_event(service, event_id, success=False, reason=err)
        return

    if changed:
        print(f"[CALENDAR] '{title}' erfolgreich – neuer State: {new_state}")
        _mark_event(service, event_id, success=True,
                    reason=f"Ausgeführt. Neuer State: {new_state}")
    else:
        reason = (
            f"Command gesendet, aber kein SSE-Event nach "
            f"{settings.SSE_TIMEOUT_SECONDS}s. "
            f"Gültige Commands für '{item_type}': "
            f"{oh.get_valid_commands_hint(item_type)}"
        )
        print(f"[CALENDAR] '{title}' – Timeout bei SSE-Warten.")
        _mark_event(service, event_id, success=False, reason=reason)


def _mark_event(service, event_id: str, success: bool, reason: str = ""):
    """
    Markiert einen Termin als verarbeitet:
    - Farbkennung: Grün (Zusage) oder Rot (Absage)
    - Extended Property als Duplikatsschutz
    - Statustext in die Beschreibung anhängen
    """
    try:
        event = service.events().get(
            calendarId="primary", eventId=event_id
        ).execute()

        # Farbe setzen
        event["colorId"] = COLOR_ACCEPTED if success else COLOR_DECLINED

        # Verarbeitungs-Marker
        if "extendedProperties" not in event:
            event["extendedProperties"] = {}
        if "private" not in event["extendedProperties"]:
            event["extendedProperties"]["private"] = {}
        event["extendedProperties"]["private"][PROCESSED_MARKER] = (
            "accepted" if success else "declined"
        )

        # Statusinfo in Beschreibung anhängen
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        status_icon = "✅" if success else "❌"
        status_line = f"\n\n--- Bridge-Status ({timestamp}) ---\n{status_icon} {reason}"
        event["description"] = (event.get("description", "") + status_line)

        service.events().update(
            calendarId="primary", eventId=event_id, body=event
        ).execute()

    except Exception as e:
        print(f"[CALENDAR] Fehler beim Markieren von Termin {event_id}: {e}")


# ---------------------------------------------------------------------------
# Kalenderabfragen
# ---------------------------------------------------------------------------

def query_calendar_by_filter(filter_str: str) -> str:
    """
    Gibt eine formatierte Terminübersicht zurück.

    Gültige Filter:
      today, tomorrow, next_hour, week, accepted, declined, all
    """
    f = filter_str.strip().lower()

    try:
        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        now = datetime.now(timezone.utc)

        if f == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            label = "heute"
        elif f == "tomorrow":
            tmrw = now + timedelta(days=1)
            start = tmrw.replace(hour=0, minute=0, second=0, microsecond=0)
            end = tmrw.replace(hour=23, minute=59, second=59, microsecond=0)
            label = "morgen"
        elif f == "next_hour":
            start = now
            end = now + timedelta(hours=1)
            label = "in der nächsten Stunde"
        elif f == "week":
            start = now
            end = now + timedelta(days=7)
            label = "in den nächsten 7 Tagen"
        elif f in ("accepted", "declined", "all"):
            start = now
            end = now + timedelta(days=365)
            label = f"(Filter: {f})"
        else:
            return (
                f"❌ Unbekannter Filter: '{filter_str}'.\n\n"
                "Gültige Filter:\n"
                "  today, tomorrow, next_hour, week, accepted, declined, all"
            )

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=100,
        ).execute()

        events = events_result.get("items", [])

        # Status-Filter über Farbe
        if f == "accepted":
            events = [e for e in events if e.get("colorId") == COLOR_ACCEPTED]
        elif f == "declined":
            events = [e for e in events if e.get("colorId") == COLOR_DECLINED]

        # Abgesagte/gelöschte raus
        events = [e for e in events if e.get("status") != "cancelled"]

        if not events:
            return f"📅 Keine Termine {label} gefunden."

        lines = [f"📅 Termine {label} ({len(events)} Stück):\n"]
        for event in events:
            start_val = event.get("start", {})
            start_str = (
                start_val.get("dateTime", start_val.get("date", "?"))
            )
            # Formatieren
            try:
                dt = datetime.fromisoformat(start_str)
                start_str = dt.astimezone().strftime("%d.%m.%Y %H:%M")
            except Exception:
                pass

            color_id = event.get("colorId")
            if color_id == COLOR_ACCEPTED:
                status_icon = "✅"
            elif color_id == COLOR_DECLINED:
                status_icon = "❌"
            else:
                status_icon = "⏳"

            title = event.get("summary", "(kein Titel)")
            lines.append(f"{status_icon} {start_str}  |  {title}")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Fehler beim Abrufen des Kalenders: {e}"
