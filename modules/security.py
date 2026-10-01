"""
security.py – Validiert den Sicherheitsschlüssel in eingehenden Nachrichten.

Format (E-Mail-Body ODER Kalender-Beschreibung):
    Zeile 1: Command (kann leer sein bei reinen Abfragen)
    Zeile 2: BRIDGE_SECRET_KEY

Robustheit:
    - Führende/nachfolgende Leerzeichen pro Zeile werden entfernt
    - Leere Zeilen zwischen Command und Key werden übersprungen
    - HTML-Tags werden entfernt (Google Calendar fügt manchmal welche ein)
    - Der Key wird in allen nicht-leeren Zeilen gesucht, nicht nur in Zeile 2
    - BOM und unsichtbare Unicode-Zeichen werden entfernt
"""

import re
from config.settings import settings

# HTML-Tags entfernen (Google Calendar wandelt manchmal Beschreibungen in HTML um)
_HTML_TAG = re.compile(r"<[^>]+>")
# HTML-Entities wie &nbsp; &amp; etc.
_HTML_ENTITY = re.compile(r"&[a-z]+;|&#\d+;")
# Unsichtbare Unicode-Zeichen (Zero-Width Space, BOM etc.)
_INVISIBLE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00a0]")


def _clean_body(body: str) -> str:
    """Bereinigt den Body von HTML, unsichtbaren Zeichen und normalisiert Zeilenumbrüche."""
    # HTML-Tags entfernen
    body = _HTML_TAG.sub("", body)
    # HTML-Entities entfernen
    body = _HTML_ENTITY.sub(" ", body)
    # Unsichtbare Zeichen entfernen
    body = _INVISIBLE.sub("", body)
    # Windows-Zeilenumbrüche normalisieren
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    return body


def _clean_line(line: str) -> str:
    """Bereinigt eine einzelne Zeile."""
    return line.strip()


def validate_key(body: str) -> tuple[bool, str, str]:
    """
    Parst Body und prüft den Schlüssel.

    Logik:
    - Body wird bereinigt (HTML, unsichtbare Zeichen, Whitespace)
    - Alle Zeilen werden einzeln getrimmt
    - Zeile 1 (auch leer) = Command
    - Der Key wird in allen folgenden nicht-leeren Zeilen gesucht
      → funktioniert auch wenn der Key versehentlich in Zeile 3 landet

    Returns:
        (is_valid, command, error_message)
    """
    if not settings.BRIDGE_SECRET_KEY:
        return False, "", "Kein BRIDGE_SECRET_KEY konfiguriert."

    if not body or not body.strip():
        return False, "", "Leerer Body – Zeile 1: Command, Zeile 2: Schlüssel."

    # Bereinigen
    body = _clean_body(body)

    # Zeilen aufteilen und trimmen
    raw_lines = body.split("\n")
    cleaned_lines = [_clean_line(l) for l in raw_lines]

    # Erste Zeile = Command (auch wenn leer)
    command = cleaned_lines[0] if cleaned_lines else ""

    # In allen weiteren Zeilen nach dem Key suchen (auch wenn Leerzeilen dazwischen)
    remaining = [l for l in cleaned_lines[1:] if l]  # leere Zeilen überspringen

    if not remaining:
        return (
            False,
            "",
            "Kein Schlüssel gefunden.\n"
            "Zeile 1: Command (oder leer)\n"
            "Zeile 2: Sicherheitsschlüssel",
        )

    # Key in einer der verbleibenden Zeilen suchen
    key_found = any(line == settings.BRIDGE_SECRET_KEY for line in remaining)

    if not key_found:
        return False, "", "Falscher Sicherheitsschlüssel. Zugriff verweigert."

    return True, command, ""
