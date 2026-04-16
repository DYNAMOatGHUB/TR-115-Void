"""
Agent 3: Carbon Analyst Agent
Responsibility: Map validated items → emission factors → calculate CO₂e
Uses: JSON factor DB + unit conversion. LLM only for factor matching when alias fails.
"""

import json
import os
from pipeline.groq_client import get_groq_client

# Load factor databases
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(BASE_DIR, "data/epa_factors.json")) as f:
    EPA_FACTORS = json.load(f)

with open(os.path.join(BASE_DIR, "data/defra_factors.json")) as f:
    DEFRA_FACTORS = json.load(f)

SCOPE_LABELS = {1: "Scope 1 (Direct)", 2: "Scope 2 (Energy)", 3: "Scope 3 (Supply Chain)"}

ANALYST_SYSTEM_PROMPT = """You are a carbon emission factor specialist.
Given an activity description and subtype, return the best matching emission factor key from EPA database.

Available keys:
fuel_combustion: diesel, gasoline, natural_gas, lpg, fuel_oil, coal
electricity: us_average, india_average, uk_average, renewable
transport: truck_freight, rail_freight, air_freight, sea_freight, van_freight
materials: steel, aluminum, cement, plastic, paper, glass, copper, electronics
waste: landfill, recycling

Return ONLY a JSON object:
{
  "category": "<fuel_combustion|electricity|transport|materials|waste>",
  "key": "<key from list above>",
  "confidence": "<high|medium|low>",
  "reason": "<one line explanation>"
}
No markdown. No extra text."""


def build_alias_map(db: dict) -> dict:
    """Build flat alias → (category, key) lookup"""
    alias_map = {}
    for category, items in db.items():
        for key, data in items.items():
            # Add key itself
            alias_map[key.lower()] = (category, key)
            # Add all aliases
            for alias in data.get("aliases", []):
                alias_map[alias.lower()] = (category, key)
    return alias_map


EPA_ALIAS_MAP = build_alias_map(EPA_FACTORS)
DEFRA_ALIAS_MAP = build_alias_map(DEFRA_FACTORS)


def unit_convert_to_base(quantity: float, unit: str, factor_unit: str) -> float:
    """
    Convert extracted quantity to match factor unit
    Returns converted quantity or original if no conversion needed
    """
    # Normalize
    unit = (unit or "").lower().strip()
    factor_unit = (factor_unit or "").lower()

    # Extract base unit from factor string like "kg_co2_per_gallon"
    factor_base = factor_unit.split("per_")[-1] if "per_" in factor_unit else factor_unit

    conversions = {
        # Volume
        ("litre", "gallon"): 0.264172,
        ("liter", "gallon"): 0.264172,
        ("gallon", "litre"): 3.78541,
        ("m3", "scf"): 35.3147,
        ("cubic_metre", "scf"): 35.3147,
        # Weight
        ("tonne", "kg"): 1000,
        ("ton", "kg"): 907.185,   # short ton
        ("lb", "kg"): 0.453592,
        ("pound", "kg"): 0.453592,
        # Energy
        ("mwh", "kwh"): 1000,
        # Distance
        ("km", "mile"): 0.621371,
        ("mile", "km"): 1.60934,
    }

    key = (unit, factor_base)
    if key in conversions:
        return quantity * conversions[key]

    # Same unit - no conversion needed
    return quantity


def lookup_factor_by_alias(description: str, activity_subtype: str, db: str = "epa") -> tuple:
    """
    Try to find emission factor by alias matching.
    Returns (category, key, factor_data) or None
    """
    alias_map = EPA_ALIAS_MAP if db == "epa" else DEFRA_ALIAS_MAP
    factors = EPA_FACTORS if db == "epa" else DEFRA_FACTORS

    search_terms = []
    if activity_subtype:
        search_terms.append(activity_subtype.lower())
        search_terms.extend(activity_subtype.lower().split("_"))
    if description:
        search_terms.extend(description.lower().split())

    for term in search_terms:
        if term in alias_map:
            category, key = alias_map[term]
            return category, key, factors[category][key]

    return None, None, None


def llm_factor_lookup(description: str, activity_subtype: str) -> tuple:
    """
    Fallback: Ask LLM to identify the correct factor key
    """
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Use 8b for simple lookup - saves 70b quota
            messages=[
                {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                {"role": "user", "content": f"Activity: {activity_subtype}\nDescription: {description}"}
            ],
            temperature=0.1,
            max_tokens=200
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        category = result.get("category")
        key = result.get("key")

        if category and key and category in EPA_FACTORS and key in EPA_FACTORS[category]:
            return category, key, EPA_FACTORS[category][key]

    except Exception:
        pass

    return None, None, None


def calculate_item_emission(item: dict, region: str = "us") -> dict:
    """
    Calculate CO₂e for a single validated item
    """
    description = item.get("description", "")
    activity_subtype = item.get("activity_subtype", "")
    quantity = item.get("quantity")
    unit = item.get("unit", "")
    transport_mode = item.get("transport_mode")
    distance = item.get("distance")
    distance_unit = item.get("distance_unit", "km")

    result = {
        "description": description,
        "activity_type": item.get("activity_type"),
        "activity_subtype": activity_subtype,
        "quantity": quantity,
        "unit": unit,
        "co2e_kg": None,
        "scope": None,
        "scope_label": None,
        "emission_factor": None,
        "factor_unit": None,
        "factor_source": None,
        "confidence": item.get("confidence", "medium"),
        "calculation_note": None
    }

    if quantity is None:
        result["calculation_note"] = "Skipped: missing quantity"
        return result

    # Special handling for transport: qty = weight * distance
    if item.get("activity_type") == "transport" and distance:
        # Convert to ton-miles (EPA) or tonne-km (DEFRA)
        weight_kg = quantity
        weight_tonne = weight_kg / 1000 if unit == "kg" else quantity
        dist_miles = distance * 0.621371 if distance_unit == "km" else distance
        effective_quantity = weight_tonne * dist_miles
        unit = "ton_mile"
        quantity = effective_quantity
        result["calculation_note"] = f"Transport: {weight_tonne:.2f} tons × {dist_miles:.1f} miles"

        # Use transport_mode for lookup
        if transport_mode:
            activity_subtype = f"{transport_mode}_freight"

    # Try alias lookup (EPA first)
    category, key, factor_data = lookup_factor_by_alias(description, activity_subtype, "epa")

    # DEFRA fallback for UK
    if not factor_data and region in ["uk", "gb"]:
        category, key, factor_data = lookup_factor_by_alias(description, activity_subtype, "defra")
        if factor_data:
            result["factor_source"] = "DEFRA"

    # LLM fallback
    if not factor_data:
        category, key, factor_data = llm_factor_lookup(description, activity_subtype)
        if factor_data:
            result["calculation_note"] = (result.get("calculation_note") or "") + " [LLM factor match]"

    if not factor_data:
        result["calculation_note"] = "No emission factor found - manual review needed"
        result["confidence"] = "low"
        return result

    factor = factor_data["factor"]
    factor_unit = factor_data["unit"]
    scope = factor_data.get("scope", 3)

    if not result.get("factor_source"):
        result["factor_source"] = "EPA GHG Hub 2024"

    # Unit conversion
    converted_qty = unit_convert_to_base(quantity, unit, factor_unit)

    # Calculate
    co2e = converted_qty * factor

    result.update({
        "co2e_kg": round(co2e, 3),
        "scope": scope,
        "scope_label": SCOPE_LABELS.get(scope, "Scope 3"),
        "emission_factor": factor,
        "factor_unit": factor_unit,
        "factor_key": f"{category}.{key}"
    })

    return result


def run_analyst_agent(validated_data: dict, region: str = "us") -> dict:
    """
    Agent 3: Calculate emissions for all validated items
    """
    items = validated_data.get("validated_items", [])

    if not items:
        return {
            "success": True,
            "results": [],
            "totals": {"scope1": 0, "scope2": 0, "scope3": 0, "total": 0}
        }

    results = [calculate_item_emission(item, region) for item in items]

    # Aggregate by scope
    scope1 = sum(r["co2e_kg"] for r in results if r.get("scope") == 1 and r["co2e_kg"])
    scope2 = sum(r["co2e_kg"] for r in results if r.get("scope") == 2 and r["co2e_kg"])
    scope3 = sum(r["co2e_kg"] for r in results if r.get("scope") == 3 and r["co2e_kg"])
    total = scope1 + scope2 + scope3

    # By activity type
    by_type = {}
    for r in results:
        if r["co2e_kg"]:
            atype = r.get("activity_type", "unknown")
            by_type[atype] = by_type.get(atype, 0) + r["co2e_kg"]

    # Items needing review
    review_needed = [r for r in results if not r["co2e_kg"]]

    return {
        "success": True,
        "results": results,
        "totals": {
            "scope1_kg": round(scope1, 2),
            "scope2_kg": round(scope2, 2),
            "scope3_kg": round(scope3, 2),
            "total_kg": round(total, 2),
            "total_tonnes": round(total / 1000, 4)
        },
        "by_activity_type": {k: round(v, 2) for k, v in by_type.items()},
        "items_calculated": len([r for r in results if r["co2e_kg"]]),
        "items_skipped": len(review_needed),
        "review_needed": review_needed
    }
