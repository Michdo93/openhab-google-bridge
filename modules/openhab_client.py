"""
openhab_client.py – Wrapper für python-openhab-rest-client.
"""

import json
import logging
import queue
import threading
from typing import Optional

from openhab import OpenHABClient, Items, ItemEvents, Rules, Things, Sitemaps
from config.settings import settings

log = logging.getLogger(__name__)


def _build_client() -> OpenHABClient:
    if settings.OPENHAB_TOKEN:
        return OpenHABClient(url=settings.OPENHAB_URL, token=settings.OPENHAB_TOKEN)
    return OpenHABClient(
        url=settings.OPENHAB_URL,
        username=settings.OPENHAB_USER,
        password=settings.OPENHAB_PASS,
    )


# ---------------------------------------------------------------------------
# Item-Operationen
# ---------------------------------------------------------------------------

def get_item(item_name: str) -> Optional[dict]:
    """Gibt den vollständigen JSON-Response eines einzelnen Items zurück."""
    try:
        client = _build_client()
        itemsAPI = Items(client)
        result = itemsAPI.getItem(item_name)
        log.debug(f"get_item('{item_name}'): {result}")

        if isinstance(result, dict) and "error" in result:
            log.warning(f"get_item('{item_name}'): {result['error']}")
            return None

        return result
    except Exception as e:
        log.error(f"get_item('{item_name}'): {type(e).__name__}: {e}")
        return None


def get_item_state(item_name: str) -> Optional[str]:
    """Gibt den aktuellen State eines Items zurück."""
    try:
        client = _build_client()
        itemsAPI = Items(client)
        result = itemsAPI.getItemState(item_name)
        log.debug(f"get_item_state('{item_name}'): {result}")

        if isinstance(result, dict) and "error" in result:
            log.warning(f"get_item_state('{item_name}'): {result['error']}")
            return None

        return str(result)
    except Exception as e:
        log.error(f"get_item_state('{item_name}'): {type(e).__name__}: {e}")
        return None


def get_item_type(item_name: str) -> Optional[str]:
    """Gibt den Typ eines Items zurück (z. B. Switch, Dimmer)."""
    data = get_item(item_name)
    if data and isinstance(data, dict):
        return data.get("type")
    return None


def send_command(item_name: str, command: str) -> tuple[bool, str]:
    """Sendet einen Command an ein openHAB-Item."""
    try:
        client = _build_client()
        itemsAPI = Items(client)
        result = itemsAPI.sendCommand(item_name, command)
        log.debug(f"send_command('{item_name}', '{command}'): {result}")

        if isinstance(result, dict) and "error" in result:
            log.warning(f"send_command('{item_name}'): {result['error']}")
            return False, result["error"]

        return True, ""
    except Exception as e:
        log.error(f"send_command('{item_name}', '{command}'): {type(e).__name__}: {e}")
        return False, str(e)


def send_command_and_wait(
    item_name: str, command: str, timeout: int = 15
) -> tuple[bool, bool, Optional[str], str]:
    """
    Startet den SSE-Listener ZUERST, sendet dann den Command,
    und wartet anschließend auf die State-Änderung.

    Reihenfolge:
        1. SSE-Listener-Thread starten
        2. Warten bis Listener bereit ist (ready_event)
        3. Command senden
        4. Auf State-Änderung warten (Timeout)

    Returns:
        (command_success, state_changed, new_state, error_message)
    """
    result_queue: queue.Queue = queue.Queue()
    ready_event = threading.Event()  # signalisiert: SSE-Verbindung steht

    def _listener():
        try:
            client = _build_client()
            itemEventsAPI = ItemEvents(client)
            response = itemEventsAPI.ItemStateChangedEvent(item_name)
            log.debug(f"SSE-Listener bereit für '{item_name}'")

            # SSE-Verbindung steht – jetzt darf der Command gesendet werden
            ready_event.set()

            with response as events:
                for line in events.iter_lines():
                    line = line.decode()

                    if "data" not in line:
                        continue

                    line = line.replace("data: ", "")

                    try:
                        data = json.loads(line)
                    except json.decoder.JSONDecodeError:
                        continue

                    log.debug(f"SSE-Event: {data}")

                    new_state = None
                    payload_raw = data.get("payload")
                    if payload_raw:
                        try:
                            payload = json.loads(payload_raw)
                            new_state = payload.get("value")
                        except Exception:
                            new_state = str(payload_raw)

                    result_queue.put(("changed", new_state))
                    return

        except Exception as exc:
            log.error(f"SSE-Listener für '{item_name}': {type(exc).__name__}: {exc}")
            ready_event.set()  # im Fehlerfall trotzdem freigeben
            result_queue.put(("error", str(exc)))

    # 1. Listener starten
    t = threading.Thread(target=_listener, daemon=True)
    t.start()

    # 2. Warten bis SSE-Verbindung steht (max. 5s)
    if not ready_event.wait(timeout=5):
        log.error(f"SSE-Listener für '{item_name}' nicht rechtzeitig bereit.")
        return False, False, None, "SSE-Listener konnte nicht gestartet werden."

    # 3. Command senden
    command_success, send_err = send_command(item_name, command)
    if not command_success:
        return False, False, None, send_err

    # 4. Auf State-Änderung warten
    try:
        event_type, value = result_queue.get(timeout=timeout)
        if event_type == "changed":
            return True, True, value, ""
        return True, False, None, value  # value = Fehlermeldung
    except queue.Empty:
        log.warning(f"Timeout nach {timeout}s – kein SSE-Event für '{item_name}'")
        return True, False, None, ""


def wait_for_state_change(
    item_name: str, timeout: int = 15
) -> tuple[bool, Optional[str]]:
    """
    Wartet via SSE auf ein ItemStateChangedEvent (ohne Command zu senden).
    Für direkten SSE-Test via test_openhab.py --sse.
    """
    result_queue: queue.Queue = queue.Queue()

    def _listener():
        try:
            client = _build_client()
            itemEventsAPI = ItemEvents(client)
            response = itemEventsAPI.ItemStateChangedEvent(item_name)
            log.debug(f"SSE-Response für '{item_name}': {response}")

            with response as events:
                for line in events.iter_lines():
                    line = line.decode()

                    if "data" not in line:
                        continue

                    line = line.replace("data: ", "")

                    try:
                        data = json.loads(line)
                    except json.decoder.JSONDecodeError:
                        continue

                    log.debug(f"SSE-Event: {data}")

                    new_state = None
                    payload_raw = data.get("payload")
                    if payload_raw:
                        try:
                            payload = json.loads(payload_raw)
                            new_state = payload.get("value")
                        except Exception:
                            new_state = str(payload_raw)

                    result_queue.put(("changed", new_state))
                    return

        except Exception as exc:
            log.error(f"SSE-Listener für '{item_name}': {type(exc).__name__}: {exc}")
            result_queue.put(("error", str(exc)))

    t = threading.Thread(target=_listener, daemon=True)
    t.start()

    try:
        event_type, value = result_queue.get(timeout=timeout)
        if event_type == "changed":
            return True, value
        return False, None
    except queue.Empty:
        log.warning(f"wait_for_state_change: Timeout nach {timeout}s für '{item_name}'")
        return False, None


# ---------------------------------------------------------------------------
# Listen-Operationen
# ---------------------------------------------------------------------------

def list_items() -> list[dict]:
    try:
        client = _build_client()
        itemsAPI = Items(client)
        result = itemsAPI.getItems()
        if isinstance(result, list):
            return [
                {
                    "name":  e.get("name", ""),
                    "type":  e.get("type", ""),
                    "state": e.get("state", ""),
                    "label": e.get("label", ""),
                }
                for e in result if isinstance(e, dict)
            ]
        log.error(f"list_items: Unerwarteter Typ: {type(result)}")
        return []
    except Exception as e:
        log.error(f"list_items: {type(e).__name__}: {e}")
        return []


def list_rules() -> list[dict]:
    try:
        client = _build_client()
        rulesAPI = Rules(client)
        result = rulesAPI.getRules()
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return list(result.values())
        return []
    except Exception as e:
        log.error(f"list_rules: {type(e).__name__}: {e}")
        return []


def list_things() -> list[dict]:
    try:
        client = _build_client()
        thingsAPI = Things(client)
        result = thingsAPI.getThings()
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return list(result.values())
        return []
    except Exception as e:
        log.error(f"list_things: {type(e).__name__}: {e}")
        return []


def list_sitemaps() -> list[dict]:
    try:
        client = _build_client()
        sitemapsAPI = Sitemaps(client)
        result = sitemapsAPI.getSitemaps()
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return list(result.values())
        return []
    except Exception as e:
        log.error(f"list_sitemaps: {type(e).__name__}: {e}")
        return []


# ---------------------------------------------------------------------------
# Hinweise zu gültigen Commands je Item-Typ
# ---------------------------------------------------------------------------

def get_valid_commands_hint(item_type: str) -> str:
    hints = {
        "Switch":        "ON, OFF",
        "Dimmer":        "ON, OFF, 0–100 (Prozent), INCREASE, DECREASE",
        "Color":         "ON, OFF, HSB-Wert (z. B. 240,100,100)",
        "Rollershutter": "UP, DOWN, STOP, 0–100 (Prozent)",
        "Number":        "Numerischer Wert (z. B. 21.5)",
        "String":        "Beliebiger Text",
        "Contact":       "(read-only – kein Command möglich)",
        "Player":        "PLAY, PAUSE, STOP, NEXT, PREVIOUS, REWIND, FASTFORWARD",
    }
    return hints.get(item_type, f"Keine Hinweise für Typ '{item_type}' hinterlegt.")
