"""
gmail_handler.py – Empfängt und verarbeitet eingehende E-Mails via Gmail API.

Unterstützte Betreff-Präfixe (Großschreibung egal):
  CMD / cmd / Command / command   → openHAB Command senden
  State / STATE / state           → State eines Items abfragen
  ITEM / Item / item              → Vollständiger JSON-Response eines Items
  GET / Get / get                 → Rules, Items, Things, Sitemaps, Bindings
  GET CALENDAR / ...              → Kalender abfragen
"""

import base64
import json
import re
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from modules.google_auth import get_credentials
from modules.security import validate_key
from modules.gmail_sender import send_reply
from modules import openhab_client as oh
from modules.calendar_handler import query_calendar_by_filter


# ---------------------------------------------------------------------------
# Betreff-Pattern
# ---------------------------------------------------------------------------

CMD_PATTERN = re.compile(r"^(CMD|cmd|Command|command)\s*:\s*(.+)$", re.IGNORECASE)
STATE_PATTERN = re.compile(r"^(State|STATE|state)\s*:\s*(.+)$", re.IGNORECASE)
ITEM_PATTERN = re.compile(r"^(ITEM|Item|item)\s*:\s*(.+)$", re.IGNORECASE)
GET_CAL_PATTERN = re.compile(r"^(GET\s+CALENDAR|Get\s+Calendar|get\s+calendar)\s*:\s*(.+)$", re.IGNORECASE)
GET_PATTERN = re.compile(r"^(GET|Get|get)\s*:\s*(.+)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Gmail-Service
# ---------------------------------------------------------------------------

def _get_service():
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Hauptfunktion: Ungelesene E-Mails holen und verarbeiten
# ---------------------------------------------------------------------------

def process_unread_emails():
    """Ruft ungelesene E-Mails ab und verarbeitet sie."""
    try:
        service = _get_service()

        results = service.users().messages().list(
            userId="me", q="is:unread in:inbox", maxResults=20
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()

            _handle_message(service, msg)

            # Als gelesen markieren
            service.users().messages().modify(
                userId="me",
                id=msg_ref["id"],
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

    except Exception as e:
        print(f"[GMAIL_HANDLER] Fehler beim Abrufen: {e}")


# ---------------------------------------------------------------------------
# Einzelne E-Mail verarbeiten
# ---------------------------------------------------------------------------

def _handle_message(service, msg: dict):
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    subject = headers.get("Subject", "").strip()
    sender = _extract_email_address(headers.get("From", ""))
    body = _extract_body(msg)

    if not sender:
        return

    print(f"[GMAIL_HANDLER] Von: {sender} | Betreff: '{subject}'")

    # GET CALENDAR (vor GET prüfen!)
    m = GET_CAL_PATTERN.match(subject)
    if m:
        _handle_get_calendar(sender, subject, body, m.group(2).strip())
        return

    # CMD
    m = CMD_PATTERN.match(subject)
    if m:
        _handle_command(sender, subject, body, m.group(2).strip())
        return

    # STATE
    m = STATE_PATTERN.match(subject)
    if m:
        _handle_state(sender, subject, body, m.group(2).strip())
        return

    # ITEM
    m = ITEM_PATTERN.match(subject)
    if m:
        _handle_item(sender, subject, body, m.group(2).strip())
        return

    # GET
    m = GET_PATTERN.match(subject)
    if m:
        _handle_get(sender, subject, body, m.group(2).strip())
        return

    print(f"[GMAIL_HANDLER] Betreff '{subject}' passt zu keinem Muster – ignoriere.")


# ---------------------------------------------------------------------------
# Handler: CMD
# ---------------------------------------------------------------------------

def _handle_command(sender: str, subject: str, body: str, item_name: str):
    from config.settings import settings

    valid, command, err = validate_key(body)
    if not valid:
        send_reply(sender, f"RE: {subject}", f"❌ Fehler: {err}")
        return

    if not command:
        send_reply(sender, f"RE: {subject}",
                   "❌ Kein Command in Zeile 1 des Bodys angegeben.")
        return

    item_data = oh.get_item(item_name)
    if item_data is None:
        send_reply(sender, f"RE: {subject}",
                   f"❌ Item '{item_name}' wurde in openHAB nicht gefunden.")
        return

    item_type = item_data.get("type", "Unbekannt")

    # SSE-Listener wird ZUERST gestartet, dann Command gesendet
    cmd_ok, changed, new_state, err = oh.send_command_and_wait(
        item_name, command, timeout=settings.SSE_TIMEOUT_SECONDS
    )

    if not cmd_ok:
        send_reply(sender, f"RE: {subject}",
                   f"❌ Command konnte nicht gesendet werden.\n\n"
                   f"Fehler:     {err}\n"
                   f"Item:       {item_name}\n"
                   f"Item-Typ:   {item_type}\n"
                   f"Command:    {command}")
        return

    if changed:
        reply = (
            f"✅ Command erfolgreich ausgeführt.\n\n"
            f"Item:        {item_name}\n"
            f"Item-Typ:    {item_type}\n"
            f"Command:     {command}\n"
            f"Neuer State: {new_state}"
        )
    else:
        reply = (
            f"⚠️ Command gesendet, aber keine State-Änderung innerhalb von "
            f"{settings.SSE_TIMEOUT_SECONDS}s empfangen.\n\n"
            f"Item:      {item_name}\n"
            f"Item-Typ:  {item_type}\n"
            f"Command:   {command}\n\n"
            f"Gültige Commands für Typ '{item_type}':\n"
            f"{oh.get_valid_commands_hint(item_type)}"
        )

    send_reply(sender, f"RE: {subject}", reply)


# ---------------------------------------------------------------------------
# Handler: STATE
# ---------------------------------------------------------------------------

def _handle_state(sender: str, subject: str, body: str, item_name: str):
    valid, _, err = validate_key(body)
    if not valid:
        send_reply(sender, f"RE: {subject}", f"❌ Fehler: {err}")
        return

    state = oh.get_item_state(item_name)
    if state is None:
        send_reply(sender, f"RE: {subject}",
                   f"❌ Item '{item_name}' nicht gefunden.")
        return

    send_reply(sender, f"RE: {subject}",
               f"📊 State von '{item_name}': {state}")


# ---------------------------------------------------------------------------
# Handler: ITEM
# ---------------------------------------------------------------------------

def _handle_item(sender: str, subject: str, body: str, item_name: str):
    valid, _, err = validate_key(body)
    if not valid:
        send_reply(sender, f"RE: {subject}", f"❌ Fehler: {err}")
        return

    item_data = oh.get_item(item_name)
    if item_data is None:
        send_reply(sender, f"RE: {subject}",
                   f"❌ Item '{item_name}' nicht gefunden.")
        return

    pretty = json.dumps(item_data, indent=2, ensure_ascii=False)
    send_reply(sender, f"RE: {subject}",
               f"📦 Item-Details für '{item_name}':\n\n{pretty}")


# ---------------------------------------------------------------------------
# Handler: GET
# ---------------------------------------------------------------------------

def _handle_get(sender: str, subject: str, body: str, resource: str):
    valid, _, err = validate_key(body)
    if not valid:
        send_reply(sender, f"RE: {subject}", f"❌ Fehler: {err}")
        return

    rl = resource.strip().lower()

    if rl == "items":
        data = oh.list_items()
        text = _format_list("Items", data, ["name", "type", "state", "label"])
    elif rl == "rules":
        data = oh.list_rules()
        text = _format_list("Rules", data, ["uid", "name", "status"])
    elif rl == "things":
        data = oh.list_things()
        text = _format_list("Things", data, ["UID", "label", "statusInfo"])
    elif rl == "sitemaps":
        data = oh.list_sitemaps()
        text = _format_list("Sitemaps", data, ["name", "label"])
    else:
        send_reply(sender, f"RE: {subject}",
                   f"❌ Unbekannte Ressource: '{resource}'.\n\n"
                   "Gültige Werte: Items, Rules, Things, Sitemaps")
        return

    send_reply(sender, f"RE: {subject}", text)


# ---------------------------------------------------------------------------
# Handler: GET CALENDAR
# ---------------------------------------------------------------------------

def _handle_get_calendar(sender: str, subject: str, body: str, filter_str: str):
    valid, _, err = validate_key(body)
    if not valid:
        send_reply(sender, f"RE: {subject}", f"❌ Fehler: {err}")
        return

    result = query_calendar_by_filter(filter_str)
    send_reply(sender, f"RE: {subject}", result)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _extract_email_address(from_header: str) -> str:
    """Extrahiert die E-Mail-Adresse aus einem From-Header."""
    m = re.search(r"<([^>]+)>", from_header)
    if m:
        return m.group(1).strip()
    return from_header.strip()


def _extract_body(msg: dict) -> str:
    """Extrahiert den Plaintext-Body einer Gmail-Nachricht."""
    payload = msg.get("payload", {})
    return _decode_part(payload)


def _decode_part(part: dict) -> str:
    mime_type = part.get("mimeType", "")
    body_data = part.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    # Multipart: Teile rekursiv durchsuchen, text/plain bevorzugen
    parts = part.get("parts", [])
    plain = ""
    for p in parts:
        result = _decode_part(p)
        if result:
            if p.get("mimeType", "") == "text/plain":
                return result  # sofort zurück bei text/plain
            plain = plain or result  # Fallback: erster gefundener Text

    return plain


def _format_list(title: str, data: list, keys: list) -> str:
    if not data:
        return f"📋 {title}: Keine Einträge gefunden."

    lines = [f"📋 {title} ({len(data)} Einträge):\n"]
    for i, entry in enumerate(data, 1):
        if isinstance(entry, dict):
            parts = [f"{k}: {entry[k]}" for k in keys if entry.get(k)]
            lines.append(f"{i}. {' | '.join(parts)}")
        else:
            lines.append(f"{i}. {entry}")

    return "\n".join(lines)
