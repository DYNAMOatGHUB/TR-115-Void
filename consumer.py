"""
Kafka consumer: ingests events and processes through the carbon pipeline.
Updates insights/metrics in real-time for dashboard consumption.
"""

from confluent_kafka import Consumer
import json
import sys
from datetime import datetime, timezone
from services.processor import process_event


def normalize_event(raw_event: dict) -> dict:
    """Normalize legacy and current Kafka payloads into enterprise event schema."""
    if "supplier_name" in raw_event and "event_type" in raw_event and "co2e_kg" in raw_event:
        return raw_event

    supplier_name = raw_event.get("supplier", "Unknown Supplier")
    event_type = raw_event.get("event", "operational_event")
    co2e_kg = float(raw_event.get("co2e", 0))

    inferred_scope = "scope3"
    if "electricity" in event_type:
        inferred_scope = "scope2"
    elif "diesel" in event_type or "fuel" in event_type:
        inferred_scope = "scope1"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_system": "legacy_producer",
        "supplier_id": supplier_name.lower().replace(" ", "_"),
        "supplier_name": supplier_name,
        "event_type": event_type,
        "event_subtype": "legacy_mapped",
        "activity_category": inferred_scope,
        "quantity": co2e_kg,
        "unit": "kg",
        "region": "unknown",
        "co2e_kg": co2e_kg,
        "confidence_score": 0.8,
        "metadata": {"migration": "legacy_schema_mapping"},
    }


def main():
    consumer = Consumer(
        {
            "bootstrap.servers": "localhost:9092",
            "group.id": "carbon-processor-group",
            "auto.offset.reset": "latest",
        }
    )

    consumer.subscribe(["carbon-events"])

    print("🔄 Carbon Event Consumer starting...")
    print("   Topic: carbon-events")
    print("   Group: carbon-processor-group")
    print("   Processing synthetic enterprise streams...\n")

    event_count = 0
    try:
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():
                print(f"❌ Consumer error: {msg.error()}")
                continue

            # Deserialize event from Kafka
            try:
                raw_event = json.loads(msg.value().decode("utf-8"))
                event = normalize_event(raw_event)
            except json.JSONDecodeError:
                print("❌ Failed to parse event JSON")
                continue

            # Process through pipeline
            try:
                result = process_event(event)
                event_count += 1

                # Display metrics
                metrics = result.get("pipeline", {})
                emissions = result.get("emissions", {})
                
                print(
                    f"[{event_count}] {event['supplier_name']:20} | "
                    f"{event['event_type']:20} | "
                    f"CO₂: {event['co2e_kg']:7.2f} kg | "
                    f"Session Total: {emissions.get('total_kg_session', 0):10,.0f} kg"
                )

            except Exception as e:
                print(f"❌ Processing error: {e}")
                continue

    except KeyboardInterrupt:
        print(f"\n\n✅ Consumer stopped after {event_count} events processed.")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()