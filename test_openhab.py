"""
test_openhab.py – Testet openhab_client.py direkt (nicht an ihr vorbei).

Ausführung:
    python test_openhab.py                                          # Verbindung + alle Items
    python test_openhab.py --item iSmartHome_Hue_Lampen_Schalter   # Item-Details
    python test_openhab.py --item iSmartHome_Hue_Lampen_Schalter --command ON
    python test_openhab.py --sse iSmartHome_Hue_Lampen_Schalter    # SSE warten
    python test_openhab.py --list rules
    python test_openhab.py --list things
    python test_openhab.py --list sitemaps
    python test_openhab.py --security                               # security.py testen
"""

import sys
import os
import json
import argparse
import logging

# Projektverzeichnis in den Pfad
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Logging aktivieren – so sieht man auch alle log.error/log.warning aus openhab_client.py
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(name)s: %(message)s",
)

from config.settings import settings
import modules.openhab_client as oh  # <-- der echte Client, nicht drumherum


def sep(title=""):
    print()
    print("=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_connection():
    sep("Verbindungstest")
    print(f"  URL:      {settings.OPENHAB_URL}")
    print(f"  Token:    {'gesetzt' if settings.OPENHAB_TOKEN else '(leer)'}")
    print(f"  User:     {settings.OPENHAB_USER or '(leer)'}")

    # Direkt über openhab_client testen
    items = oh.list_items()
    if items:
        print(f"\n✅ Verbindung OK – {len(items)} Items geladen.")
    else:
        print("\n❌ Keine Items geladen – Verbindung prüfen oder Logging oben beachten.")
    return items


def test_get_item(item_name: str):
    sep(f"oh.get_item('{item_name}')")
    result = oh.get_item(item_name)
    if result is not None:
        print(f"✅ Gefunden:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"❌ None – Item nicht gefunden oder Fehler (siehe Logging oben).")


def test_get_state(item_name: str):
    sep(f"oh.get_item_state('{item_name}')")
    state = oh.get_item_state(item_name)
    if state is not None:
        print(f"✅ State: {state}")
    else:
        print(f"❌ None – State nicht abrufbar.")


def test_send_command(item_name: str, command: str):
    sep(f"oh.send_command('{item_name}', '{command}')")
    success, err = oh.send_command(item_name, command)
    if success:
        print(f"✅ Command gesendet.")
    else:
        print(f"❌ Fehler: {err}")


def test_sse(item_name: str):
    sep(f"oh.wait_for_state_change('{item_name}', timeout={settings.SSE_TIMEOUT_SECONDS}s)")
    print("  Nutzt ItemStateChangedEvent(itemName) direkt.")
    print("  Bitte jetzt den State des Items in openHAB ändern...")
    print()
    changed, new_state = oh.wait_for_state_change(item_name, timeout=settings.SSE_TIMEOUT_SECONDS)
    if changed:
        print(f"\n✅ State-Änderung empfangen: {new_state}")
    else:
        print(f"\n⏰ Timeout – kein Event empfangen.")


def test_list(resource: str):
    sep(f"oh.list_{resource}()")
    fn = {
        "items":    oh.list_items,
        "rules":    oh.list_rules,
        "things":   oh.list_things,
        "sitemaps": oh.list_sitemaps,
    }.get(resource.lower())

    if not fn:
        print(f"❌ Unbekannte Ressource. Gültig: items, rules, things, sitemaps")
        return

    data = fn()
    print(f"✅ {len(data)} Einträge:")
    print(json.dumps(data[:10], indent=2, ensure_ascii=False))
    if len(data) > 10:
        print(f"  ... und {len(data) - 10} weitere")


def test_all_items(items: list):
    sep(f"Alle Items ({len(items)} Stück)")
    for entry in sorted(items, key=lambda x: x.get("name", "")):
        name  = entry.get("name", "?")
        typ   = entry.get("type", "?")
        state = entry.get("state", "?")
        label = entry.get("label", "")
        label_str = f" [{label}]" if label else ""
        print(f"  {name}{label_str}  |  {typ}  |  {state}")


def test_security():
    sep("security.py – validate_key")
    from modules.security import validate_key

    tests = [
        ("Leer + Key (Abfrage-Fall)",  f"\n{settings.BRIDGE_SECRET_KEY}",   True),
        ("Command + Key",              f"ON\n{settings.BRIDGE_SECRET_KEY}",  True),
        ("Nur Key (1 Zeile)",          settings.BRIDGE_SECRET_KEY,           False),
        ("Falscher Key",               f"ON\nFalschesPasswort",              False),
        ("Leerer Body",                "",                                    False),
    ]

    for desc, body, expected in tests:
        valid, command, err = validate_key(body)
        ok = valid == expected
        icon = "✅" if ok else "❌ UNERWARTET"
        print(f"  {icon} '{desc}'")
        print(f"       valid={valid}  command='{command}'  err='{err}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="openHAB Client Tester")
    parser.add_argument("--item",     help="Item-Name testen (get_item + get_item_state)")
    parser.add_argument("--command",  help="Command an --item senden (send_command)")
    parser.add_argument("--sse",      help="SSE auf Item warten (wait_for_state_change)")
    parser.add_argument("--list",     help="items / rules / things / sitemaps")
    parser.add_argument("--security", action="store_true", help="security.py testen")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        openHAB Google Bridge – Terminal-Tester          ║")
    print("╚══════════════════════════════════════════════════════════╝")

    if args.security:
        test_security()
        return

    if args.sse:
        test_sse(args.sse)
        return

    if args.item and args.command:
        test_send_command(args.item, args.command)
        return

    if args.item:
        test_get_item(args.item)
        test_get_state(args.item)
        return

    if args.list:
        test_list(args.list)
        return

    # Standard: Verbindung + alle Items
    items = test_connection()
    if items:
        test_all_items(items)


if __name__ == "__main__":
    main()
