"""
Carbon event schemas for Kafka topic ingestion.
Follows enterprise event-driven architecture patterns.
"""

from typing import TypedDict, Literal


class CarbonEventPayload(TypedDict):
    """
    Standard schema for carbon emissions events entering the Kafka topic.
    Represents real enterprise data sources: ERP, IoT sensors, billing systems, logistics platforms.
    """
    timestamp: str  # ISO 8601
    source_system: str  # e.g. "erp", "iot_gateway", "utility_bill_processor", "logistics_api"
    supplier_id: str  # vendor/supplier identifier
    supplier_name: str  # human readable
    event_type: str  # truck_shipment, electricity_bill, diesel_purchase, rail_shipment, material_purchase
    event_subtype: str  # refinement of event_type
    activity_category: Literal["scope1", "scope2", "scope3"]
    quantity: float  # amount of activity
    unit: str  # kwh, gallon, ton_mile, kg, etc
    region: str  # geographic location
    co2e_kg: float  # calculated CO2 equivalent in kg
    confidence_score: float  # 0-1, extraction/calculation confidence
    metadata: dict  # flexible extension point


# Example event for reference during demo
EXAMPLE_TRUCK_SHIPMENT_EVENT = {
    "timestamp": "2026-04-17T14:32:45Z",
    "source_system": "logistics_api",
    "supplier_id": "abc_logistics_001",
    "supplier_name": "ABC Logistics",
    "event_type": "truck_shipment",
    "event_subtype": "interstate_freight",
    "activity_category": "scope3",
    "quantity": 240.5,
    "unit": "ton_mile",
    "region": "US-TX",
    "co2e_kg": 445.72,
    "confidence_score": 0.92,
    "metadata": {
        "distance_km": 387,
        "origin": "Houston",
        "destination": "Dallas",
        "truck_type": "standard_semi",
    },
}

EXAMPLE_ELECTRICITY_EVENT = {
    "timestamp": "2026-04-17T14:35:12Z",
    "source_system": "utility_bill_processor",
    "supplier_id": "sun_energy_001",
    "supplier_name": "Sun Energy",
    "event_type": "electricity_bill",
    "event_subtype": "purchased_grid_electricity",
    "activity_category": "scope2",
    "quantity": 1850.0,
    "unit": "kwh",
    "region": "US-CA",
    "co2e_kg": 713.5,
    "confidence_score": 0.98,
    "metadata": {
        "billing_period": "2026-03-01_to_2026-03-31",
        "facility": "Plant A",
        "grid_intensity_factor": 0.386,
    },
}

ACTUAL_SCOPE_WEIGHTS = {
    "scope1": 0.15,  # 15% of typical emissions
    "scope2": 0.20,  # 20%
    "scope3": 0.65,  # 65% (supply chain dominates)
}
