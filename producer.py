"""
Kafka producer: generates enterprise-grade synthetic carbon events.
Simulates real operational data from ERP, IoT, billing, and logistics systems.
"""

from confluent_kafka import Producer
import json
import time
import random
from datetime import datetime, timezone
from kafka.schemas import CarbonEventPayload

# Real-world domain data
SUPPLIERS = {
    "ABC Logistics": {"id": "abc_log_001", "region": "US-TX"},
    "Vertex Steel": {"id": "vertex_steel_001", "region": "US-PA"},
    "Sun Energy": {"id": "sun_energy_001", "region": "US-CA"},
    "Coastal Shipping": {"id": "coastal_ship_001", "region": "US-FL"},
    "National Rail": {"id": "national_rail_001", "region": "US-IL"},
}

EVENT_TEMPLATES = [
    {
        "event_type": "truck_shipment",
        "event_subtype": "interstate_freight",
        "activity_category": "scope3",
        "unit": "ton_mile",
        "source_system": "logistics_api",
        "supplier_pool": ["ABC Logistics", "Coastal Shipping"],
        "co2e_range": (150, 500),
        "regions": ["US-TX", "US-CA", "US-FL"],
    },
    {
        "event_type": "electricity_bill",
        "event_subtype": "purchased_grid_electricity",
        "activity_category": "scope2",
        "unit": "kwh",
        "source_system": "utility_bill_processor",
        "supplier_pool": ["Sun Energy"],
        "co2e_range": (200, 800),
        "regions": ["US-CA", "US-TX"],
    },
    {
        "event_type": "diesel_purchase",
        "event_subtype": "fleet_fuel",
        "activity_category": "scope1",
        "unit": "gallon",
        "source_system": "fuel_management_system",
        "supplier_pool": ["ABC Logistics"],
        "co2e_range": (100, 350),
        "regions": ["US-TX", "US-PA"],
    },
    {
        "event_type": "rail_shipment",
        "event_subtype": "freight_rail",
        "activity_category": "scope3",
        "unit": "ton_mile",
        "source_system": "logistics_api",
        "supplier_pool": ["National Rail"],
        "co2e_range": (80, 400),
        "regions": ["US-IL", "US-TX"],
    },
    {
        "event_type": "material_purchase",
        "event_subtype": "raw_materials_sourcing",
        "activity_category": "scope3",
        "unit": "kg",
        "source_system": "procurement_system",
        "supplier_pool": ["Vertex Steel"],
        "co2e_range": (250, 1000),
        "regions": ["US-PA"],
    },
]

producer = Producer({"bootstrap.servers": "localhost:9092"})


def generate_event() -> dict:
    """Generate a realistic Kafka event matching enterprise schema."""
    template = random.choice(EVENT_TEMPLATES)
    supplier_name = random.choice(template["supplier_pool"])
    supplier_info = SUPPLIERS[supplier_name]

    co2e_min, co2e_max = template["co2e_range"]
    co2e = round(random.uniform(co2e_min, co2e_max), 2)

    event: CarbonEventPayload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_system": template["source_system"],
        "supplier_id": supplier_info["id"],
        "supplier_name": supplier_name,
        "event_type": template["event_type"],
        "event_subtype": template["event_subtype"],
        "activity_category": template["activity_category"],
        "quantity": round(random.uniform(50, 500), 2),
        "unit": template["unit"],
        "region": random.choice(template["regions"]),
        "co2e_kg": co2e,
        "confidence_score": round(random.uniform(0.85, 0.99), 3),
        "metadata": {
            "batch_id": f"batch_{int(time.time())}",
            "data_source": template["source_system"],
        },
    }

    return event


def publish_event(event: dict):
    """Publish event to Kafka topic."""
    producer.produce(
        "carbon-events",
        key=event["supplier_id"],
        value=json.dumps(event),
    )
    producer.flush()
    return event


if __name__ == "__main__":
    print("🚀 Carbon Event Producer starting...")
    print("   Topic: carbon-events")
    print("   Broker: localhost:9092")
    print("   Generating synthetic enterprise operational streams...\n")

    event_count = 0
    try:
        while True:
            event = generate_event()
            publish_event(event)
            event_count += 1

            print(
                f"[{event_count}] {event['timestamp']} | "
                f"{event['supplier_name']:20} | "
                f"{event['event_type']:20} | "
                f"{event['co2e_kg']:7.2f} kg CO₂e"
            )

            time.sleep(random.uniform(1.5, 3.5))  # Realistic event spacing

    except KeyboardInterrupt:
        print(f"\n\n✅ Producer stopped after {event_count} events.")