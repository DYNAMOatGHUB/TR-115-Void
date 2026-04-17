"""
Agent 2: Validator Agent
Responsibility: Check extracted data for errors, missing fields, unit mismatches, outliers
Uses: Rule engine first, LLM for ambiguous cases only (saves rate limit)
"""

import json
import re
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


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _percent_diff(system_value: float | None, reference_value: float | None) -> float | None:
    if reference_value in [None, 0] or system_value is None:
        return None
    return round(abs(system_value - reference_value) / abs(reference_value) * 100, 2)


def _confidence_band(diff_pct: float | None) -> str:
    if diff_pct is None:
        return "UNKNOWN"
    if diff_pct <= 5:
        return "HIGH"
    if diff_pct <= 10:
        return "MEDIUM"
    return "LOW"


def _approval_status(diff_pct: float | None) -> str:
    if diff_pct is None:
        return "REVIEW"
    if diff_pct <= 10:
        return "APPROVED"
    if diff_pct <= 20:
        return "REVIEW"
    return "REJECTED"


def _method_b_item_co2e(item: dict, result: dict, region: str = "us") -> float | None:
    """
    Internal cross-check Method B (independent from direct factor method):
    - Fuel: quantity × heat_content(mmBtu/unit) × kgCO2/mmBtu
    - Electricity: quantity(kWh) × region factor
    - Transport: ton-mile × factor
    """
    qty = _safe_float(result.get("input_quantity_normalized"))
    if qty is None:
        return None

    activity_type = (item.get("activity_type") or "").lower()
    subtype = (item.get("activity_subtype") or "").lower()
    desc = (item.get("description") or "").lower()
    factor_key = (result.get("factor_key") or "").lower()

    text = " ".join([
        item.get("description") or "",
        item.get("origin") or "",
        item.get("destination") or "",
    ]).lower()

    item_region = region
    if re.search(r"\bindia\b", text):
        item_region = "in"
    elif re.search(r"\b(united\s+kingdom|great\s+britain|england|uk|gb)\b", text):
        item_region = "uk"
    elif re.search(r"\b(united\s+states|usa|u\.s\.?a?\.)\b", text):
        item_region = "us"

    if activity_type == "fuel":
        fuel_mmbtu_per_unit = {
            "diesel": 0.138,
            "gasoline": 0.125,
            "petrol": 0.125,
            "natural_gas": 0.001026,
            "cng": 0.001026,
            "lng": 0.075,
            "lpg": 0.092,
            "propane": 0.092,
            "fuel_oil": 0.149,
            "coal": 0.021,
        }
        kgco2_per_mmbtu = {
            "diesel": 74.0,
            "gasoline": 70.2,
            "petrol": 70.2,
            "natural_gas": 53.06,
            "cng": 53.06,
            "lng": 60.0,
            "lpg": 61.71,
            "propane": 61.71,
            "fuel_oil": 76.0,
            "coal": 95.35,
        }

        fuel_name = subtype
        for candidate in ["diesel", "gasoline", "petrol", "natural_gas", "cng", "lng", "lpg", "propane", "fuel_oil", "coal"]:
            if candidate in subtype or candidate in desc or candidate in factor_key:
                fuel_name = candidate
                break

        h = fuel_mmbtu_per_unit.get(fuel_name)
        k = kgco2_per_mmbtu.get(fuel_name)
        if h is None or k is None:
            return None
        return round(qty * h * k, 6)

    if activity_type == "electricity":
        region_factor = {"us": 0.35, "uk": 0.233, "gb": 0.233, "in": 0.728}.get(item_region, 0.35)
        if any(k in desc for k in ["solar", "wind", "renewable", "green energy"]):
            region_factor = 0.021
        return round(qty * region_factor, 6)

    if activity_type == "transport":
        if any(k in subtype or k in desc or k in factor_key for k in ["air"]):
            factor = 1.086
        elif any(k in subtype or k in desc or k in factor_key for k in ["rail"]):
            factor = 0.021
        elif any(k in subtype or k in desc or k in factor_key for k in ["sea", "ship", "ocean"]):
            factor = 0.048
        elif any(k in subtype or k in desc or k in factor_key for k in ["van"]):
            factor = 0.246
        else:
            factor = 0.186
        return round(qty * factor, 6)

    if activity_type == "material":
        factor = {
            "steel": 1.9,
            "aluminum": 8.14,
            "aluminium": 8.14,
            "cement": 0.83,
            "plastic": 2.53,
            "paper": 0.92,
            "glass": 0.85,
            "copper": 2.71,
            "electronics": 20.0,
        }.get(subtype)
        if factor is None:
            return None
        return round(qty * factor, 6)

    if activity_type == "waste":
        factor = 0.021 if any(k in subtype or k in desc for k in ["recycl"]) else 0.53
        return round(qty * factor, 6)

    return None


def run_emission_validation(
    validated: dict,
    analyst: dict,
    region: str = "us",
    manual_validation: dict | None = None,
) -> dict:
    """
    Carbon Validation Engine
    - Auto mode: system vs internal Method B
    - Validation mode: system vs optional manual scope/total input
    """
    manual_validation = manual_validation or {}

    items = validated.get("validated_items", [])
    results = analyst.get("results", [])
    totals = analyst.get("totals", {})

    system_scope = {
        "scope1": _safe_float(totals.get("scope1_kg")) or 0.0,
        "scope2": _safe_float(totals.get("scope2_kg")) or 0.0,
        "scope3": _safe_float(totals.get("scope3_kg")) or 0.0,
    }
    system_total = _safe_float(totals.get("total_kg")) or sum(system_scope.values())

    total_items = len(items)
    mapped_items = len([r for r in results if r.get("co2e_kg") is not None])
    coverage_pct = round((mapped_items / total_items * 100), 1) if total_items else 0.0

    method_b_scope = {"scope1": 0.0, "scope2": 0.0, "scope3": 0.0}
    reasons = []

    for idx, item in enumerate(items):
        if idx >= len(results):
            break
        r = results[idx]
        alt = _method_b_item_co2e(item, r, region=region)
        scope_num = r.get("scope")
        if alt is not None and scope_num in [1, 2, 3]:
            method_b_scope[f"scope{scope_num}"] += alt

        if r.get("factor_match_method") == "llm_lookup":
            reasons.append("LLM factor mapping used for at least one line item")
        if r.get("factor_source") == "DEFRA":
            reasons.append("DEFRA fallback factors were used for some items")
        if (r.get("calculation_note") or "").startswith("Transport:"):
            reasons.append("Transport quantities were normalized to ton-mile")

    method_b_scope = {k: round(v, 2) for k, v in method_b_scope.items()}
    method_b_total = round(sum(method_b_scope.values()), 2)

    manual_scope = {
        "scope1": _safe_float(manual_validation.get("manual_scope1")),
        "scope2": _safe_float(manual_validation.get("manual_scope2")),
        "scope3": _safe_float(manual_validation.get("manual_scope3")),
    }
    manual_total = _safe_float(manual_validation.get("manual_total"))
    if manual_total is None:
        provided_scopes = [v for v in manual_scope.values() if v is not None]
        if provided_scopes:
            manual_total = round(sum(provided_scopes), 2)

    mode = "auto"
    if any(v is not None for v in manual_scope.values()) or manual_total is not None:
        mode = "manual_validation"

    breakdown = {}
    scope_diffs = []
    for s in ["scope1", "scope2", "scope3"]:
        system_value = system_scope[s]
        reference_value = manual_scope[s] if manual_scope[s] is not None else method_b_scope[s]
        diff = _percent_diff(system_value, reference_value)
        if diff is not None:
            scope_diffs.append(diff)

        breakdown[s] = {
            "system": round(system_value, 2),
            "reference": round(reference_value, 2) if reference_value is not None else None,
            "deviation_percent": diff,
            "confidence": _confidence_band(diff),
            "status": _approval_status(diff),
            "reference_source": "manual" if manual_scope[s] is not None else "internal_method_b",
        }

    reference_total = manual_total if manual_total is not None else method_b_total
    deviation_percent = _percent_diff(system_total, reference_total)
    confidence = _confidence_band(deviation_percent)
    status = _approval_status(deviation_percent)
    confidence_score_pct = round(max(0.0, 100 - (deviation_percent or 0.0)), 1) if deviation_percent is not None else 0.0

    if deviation_percent is None:
        reasons.append("Reference value unavailable for total comparison")
    elif deviation_percent <= 1:
        reasons.append("Minor variance likely due to rounding")
    elif deviation_percent > 10:
        reasons.extend([
            "Deviation likely influenced by electricity factor assumptions",
            "Unit normalization differences may contribute",
            "Missing or ambiguous activity subtype mapping may affect totals",
        ])

    # Scope with most deviation (bonus)
    max_scope = None
    max_scope_diff = -1.0
    for s, b in breakdown.items():
        d = b.get("deviation_percent")
        if d is not None and d > max_scope_diff:
            max_scope_diff = d
            max_scope = s
    if max_scope:
        reasons.append(f"Largest scope deviation observed in {max_scope}")

    explanation = "; ".join(sorted(set(reasons))[:5]) if reasons else "System and reference are aligned."

    # Backward-compatible structure for existing UI/report consumers
    comparison_source = "manual" if mode == "manual_validation" else "benchmark"
    legacy_confidence_band = "high" if confidence == "HIGH" else "medium" if confidence == "MEDIUM" else "low"
    legacy_status = "verified" if status == "APPROVED" else "acceptable" if status == "REVIEW" else "review_required"

    return {
        "mode": mode,
        "system_total": round(system_total, 2),
        "reference_total": round(reference_total, 2) if reference_total is not None else None,
        "deviation_percent": deviation_percent,
        "confidence": confidence,
        "confidence_score_pct": confidence_score_pct,
        "status": status,
        "breakdown": breakdown,
        "explanation": explanation,
        "internal_method_b": {
            "scope1": method_b_scope["scope1"],
            "scope2": method_b_scope["scope2"],
            "scope3": method_b_scope["scope3"],
            "total": method_b_total,
        },

        # Existing consumers still expect these keys
        "coverage": {
            "mapped_items": mapped_items,
            "total_items": total_items,
            "coverage_pct": coverage_pct,
        },
        "comparison": {
            "source": comparison_source,
            "manual_pairs_count": 0,
            "benchmark_pairs_count": mapped_items,
            "manual_diff_pct": deviation_percent if mode == "manual_validation" else None,
            "benchmark_diff_pct": deviation_percent if mode == "auto" else None,
            "effective_diff_pct": deviation_percent,
        },
        "why_difference": sorted(set(reasons))[:5],
        "legacy_confidence": {
            "score_pct": confidence_score_pct,
            "band": legacy_confidence_band,
        },
        "legacy_status": legacy_status,
    }
