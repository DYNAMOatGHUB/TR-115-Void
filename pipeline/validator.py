"""
Agent 2: Validator Agent
Responsibility: Check extracted data for errors, missing fields, unit mismatches, outliers
Uses: Rule engine first, LLM for ambiguous cases only (saves rate limit)
"""

import json
from pipeline.groq_client import get_groq_client

# Known valid units per activity type
VALID_UNITS = {
    "fuel": ["gallon", "litre", "liter", "kg", "tonne", "ton", "scf", "cubic_metre", "m3", "mmbtu"],
    "electricity": ["kwh", "mwh", "kwh/month", "units"],
    "transport": ["km", "mile", "ton_mile", "tonne_km", "ton-mile", "tonne-km"],
    "material": ["kg", "tonne", "ton", "g", "lb", "pound", "piece", "unit"],
    "waste": ["kg", "tonne", "ton", "cubic_metre"]
}

# Reasonable quantity bounds (to detect outliers)
QUANTITY_BOUNDS = {
    "fuel": (0.1, 1_000_000),
    "electricity": (1, 10_000_000),
    "transport": (0.01, 100_000),
    "material": (0.01, 1_000_000),
    "waste": (0.01, 100_000)
}

VALIDATOR_SYSTEM_PROMPT = """You are a carbon accounting data quality validator.
Given a list of extracted supply chain items, fix any issues you find.

For each item, check:
1. Is the activity_subtype correctly identified? (e.g. "HSD" should be "diesel")
2. Is the unit correct for the activity type?
3. Can you infer missing quantity or unit from context?
4. Should confidence be adjusted?

Return ONLY a JSON array of the corrected items. No explanation. No markdown.
Keep the exact same structure, only fix what's wrong.
If an item is unfixable, add "validation_note": "<reason>" to it."""


def normalize_unit(unit: str) -> str:
    """Normalize common unit variations"""
    if not unit:
        return None
    unit = unit.lower().strip()
    mappings = {
        "liter": "litre",
        "liters": "litre",
        "litres": "litre",
        "gallons": "gallon",
        "kilo": "kg",
        "kilos": "kg",
        "kilograms": "kg",
        "kilogram": "kg",
        "tonnes": "tonne",
        "tons": "tonne",
        "mwh": "mwh",
        "kwh": "kwh",
        "units": "kwh",  # electricity "units" = kwh in India
        "km": "km",
        "kilometers": "km",
        "kilometres": "km",
        "miles": "mile",
        "m3": "cubic_metre",
        "cubic meter": "cubic_metre",
        "cubic meters": "cubic_metre"
    }
    return mappings.get(unit, unit)


def rule_based_validation(items: list) -> tuple[list, list]:
    """
    Fast rule-based checks. Returns (validated_items, issues_list)
    """
    validated = []
    issues = []

    for i, item in enumerate(items):
        item_issues = []
        item = item.copy()

        activity_type = item.get("activity_type", "")
        quantity = item.get("quantity")
        unit = item.get("unit", "")
        confidence = item.get("confidence", "medium")

        # 1. Normalize unit
        if unit:
            item["unit"] = normalize_unit(unit)

        # 2. Check missing quantity
        if quantity is None:
            item_issues.append("Missing quantity")
            item["confidence"] = "low"

        # 3. Check quantity bounds
        elif activity_type in QUANTITY_BOUNDS:
            lo, hi = QUANTITY_BOUNDS[activity_type]
            if not (lo <= quantity <= hi):
                item_issues.append(f"Quantity {quantity} outside expected range [{lo}, {hi}]")
                item["confidence"] = "low"

        # 4. Transport missing distance/mode
        if activity_type == "transport":
            if not item.get("transport_mode"):
                item_issues.append("Transport mode missing - defaulting to truck")
                item["transport_mode"] = "truck"
                item["confidence"] = "medium"
            if not item.get("distance") and not quantity:
                item_issues.append("Transport distance missing")
                item["confidence"] = "low"

        # 5. Missing activity_subtype
        if not item.get("activity_subtype") or item.get("activity_subtype") == "other":
            item_issues.append("Activity subtype unclear - needs LLM review")

        if item_issues:
            item["validation_issues"] = item_issues
            issues.append({"item_index": i, "description": item.get("description"), "issues": item_issues})

        validated.append(item)

    return validated, issues


def llm_fix_ambiguous(items_with_issues: list) -> list:
    """
    Send only ambiguous items to LLM for fixing (save rate limit)
    """
    if not items_with_issues:
        return items_with_issues

    # Only send items that need LLM help (unclear subtype or unit issues)
    needs_llm = [item for item in items_with_issues
                 if "Activity subtype unclear" in str(item.get("validation_issues", []))]

    if not needs_llm:
        return items_with_issues

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"Fix these extracted items:\n{json.dumps(needs_llm, indent=2)}"}
            ],
            temperature=0.1,
            max_tokens=1500
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        fixed = json.loads(raw.strip())

        # Merge fixed items back
        fixed_map = {item.get("description"): item for item in fixed}
        result = []
        for item in items_with_issues:
            desc = item.get("description")
            if desc in fixed_map:
                result.append(fixed_map[desc])
            else:
                result.append(item)
        return result

    except Exception as e:
        # If LLM fails, return as-is
        for item in items_with_issues:
            item.setdefault("validation_note", f"LLM validator unavailable: {str(e)}")
        return items_with_issues


def run_validator_agent(extracted_data: dict) -> dict:
    """
    Agent 2: Validate and clean extracted items
    Returns validated data with issues flagged
    """
    items = extracted_data.get("items", [])
    if not items:
        return {
            "success": True,
            "validated_items": [],
            "issues": [],
            "validation_summary": "No items to validate"
        }

    # Step 1: Rule-based fast validation
    validated_items, issues = rule_based_validation(items)

    # Step 2: LLM fixes for ambiguous ones only
    if any(item.get("validation_issues") for item in validated_items):
        validated_items = llm_fix_ambiguous(validated_items)

    # Summary
    total = len(validated_items)
    high_conf = sum(1 for i in validated_items if i.get("confidence") == "high")
    med_conf = sum(1 for i in validated_items if i.get("confidence") == "medium")
    low_conf = sum(1 for i in validated_items if i.get("confidence") == "low")

    return {
        "success": True,
        "validated_items": validated_items,
        "issues": issues,
        "validation_summary": {
            "total_items": total,
            "high_confidence": high_conf,
            "medium_confidence": med_conf,
            "low_confidence": low_conf,
            "issues_found": len(issues)
        }
    }
