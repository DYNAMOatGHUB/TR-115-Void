import json
import random
import threading
import time
from datetime import datetime
from pathlib import Path


SUPPLIERS = [
    "ABC Logistics",
    "Vertex Steel",
    "BlueDart",
    "Sun Energy",
    "Coastal Shipping",
]

DEFAULT_EVENTS = [
    {"type": "truck_shipment", "scope": 3, "co2e_min": 150.0, "co2e_max": 950.0},
    {"type": "electricity_bill", "scope": 2, "co2e_min": 180.0, "co2e_max": 1700.0},
    {"type": "diesel_purchase", "scope": 1, "co2e_min": 220.0, "co2e_max": 3000.0},
    {"type": "rail_shipment", "scope": 3, "co2e_min": 90.0, "co2e_max": 780.0},
    {"type": "material_purchase", "scope": 3, "co2e_min": 250.0, "co2e_max": 3800.0},
]

_stream_log = []
_running = False
_lock = threading.Lock()


def _load_event_templates() -> list[dict]:
    template_path = Path("data/stream_templates/stream_events.json")
    if not template_path.exists():
        return DEFAULT_EVENTS
    try:
        with template_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, list) and payload:
            return payload
    except (OSError, json.JSONDecodeError):
        pass
    return DEFAULT_EVENTS


def get_stream_log():
    with _lock:
        return list(_stream_log[-20:])


def start_stream():
    global _running
    if _running:
        return

    _running = True
    events = _load_event_templates()

    def _loop():
        while _running:
            event = random.choice(events)
            min_v = float(event.get("co2e_min", 100.0))
            max_v = float(event.get("co2e_max", 1000.0))
            co2e = round(random.uniform(min_v, max_v), 2)

            entry = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "supplier": random.choice(event.get("suppliers", SUPPLIERS)),
                "event_type": event.get("type", "operational_event"),
                "co2e_kg": co2e,
                "scope": f"Scope {event.get('scope', 3)}",
            }
            with _lock:
                _stream_log.append(entry)
            time.sleep(random.uniform(3, 8))

    threading.Thread(target=_loop, daemon=True).start()


def stop_stream():
    global _running
    _running = False
