"""
Agent 4: Recommendation Agent
Responsibility: Analyze emission results → generate ranked reduction opportunities
Uses: LLM for contextual recommendations based on actual data
"""

import json
from pipeline.groq_client import get_groq_client

RECOMMENDER_SYSTEM_PROMPT = """You are a corporate sustainability consultant specializing in supply chain decarbonization.
Given a carbon emissions breakdown from a company's supply chain documents, generate actionable reduction recommendations.

Return ONLY a JSON array of recommendations. No markdown. No preamble.

Schema:
[
  {
    "title": "<short action title>",
    "description": "<2-3 sentence explanation>",
    "target_activity": "<which activity type this addresses>",
    "estimated_reduction_pct": <10-80 number>,
    "implementation_effort": "<low|medium|high>",
    "timeframe": "<immediate|3_months|6_months|1_year>",
    "co2e_savings_kg": <estimated kg savings based on current emissions>,
    "priority_score": <1-10>,
    "category": "<fuel|transport|energy|materials|procurement>"
  }
]

Rules:
- Generate 5-8 recommendations sorted by priority_score descending
- Base estimates on actual numbers from the emissions data provided
- Be specific and actionable, not generic
- Consider Indian supply chain context if location hints suggest it
- Focus on highest-emission activities first"""


def get_rule_based_recommendations(analyst_results: dict) -> list:
    """
    Fast rule-based recommendations as baseline
    (Used as fallback if LLM fails or to supplement)
    """
    totals = analyst_results.get("totals", {})
    by_type = analyst_results.get("by_activity_type", {})
    recommendations = []

    # Transport recommendations
    transport_emission = by_type.get("transport", 0)
    if transport_emission > 0:
        recommendations.append({
            "title": "Switch Road Freight to Rail",
            "description": "Rail freight emits ~89% less CO₂ than road transport per ton-mile. Consolidate shipments and negotiate rail freight contracts for long-distance routes.",
            "target_activity": "transport",
            "estimated_reduction_pct": 60,
            "implementation_effort": "medium",
            "timeframe": "6_months",
            "co2e_savings_kg": round(transport_emission * 0.6, 2),
            "priority_score": 9,
            "category": "transport"
        })
        recommendations.append({
            "title": "Consolidate Shipments / Reduce Frequency",
            "description": "Reduce shipment frequency by batching orders. Full truckloads emit less per unit than partial loads. Target 80%+ truck utilization.",
            "target_activity": "transport",
            "estimated_reduction_pct": 25,
            "implementation_effort": "low",
            "timeframe": "immediate",
            "co2e_savings_kg": round(transport_emission * 0.25, 2),
            "priority_score": 8,
            "category": "transport"
        })

    # Electricity recommendations
    electricity_emission = by_type.get("electricity", 0)
    if electricity_emission > 0:
        recommendations.append({
            "title": "Transition to Renewable Energy Sources",
            "description": "Solar/wind electricity has ~95% lower emissions than grid average. Install rooftop solar or purchase Renewable Energy Certificates (RECs) to reduce Scope 2 emissions.",
            "target_activity": "electricity",
            "estimated_reduction_pct": 80,
            "implementation_effort": "high",
            "timeframe": "1_year",
            "co2e_savings_kg": round(electricity_emission * 0.8, 2),
            "priority_score": 7,
            "category": "energy"
        })

    # Fuel recommendations
    fuel_emission = by_type.get("fuel", 0)
    if fuel_emission > 0:
        recommendations.append({
            "title": "Fleet Electrification or CNG Conversion",
            "description": "Replace diesel vehicles with EVs or CNG-powered alternatives. EVs reduce operational emissions by 60-70%, CNG by 25-30% vs diesel.",
            "target_activity": "fuel",
            "estimated_reduction_pct": 50,
            "implementation_effort": "high",
            "timeframe": "1_year",
            "co2e_savings_kg": round(fuel_emission * 0.5, 2),
            "priority_score": 7,
            "category": "fuel"
        })

    # Material recommendations
    material_emission = by_type.get("material", 0)
    if material_emission > 0:
        recommendations.append({
            "title": "Prioritize Recycled/Low-Carbon Materials",
            "description": "Recycled steel emits 58% less CO₂ than primary steel. Specify recycled content requirements in procurement contracts. Target suppliers with green certifications.",
            "target_activity": "material",
            "estimated_reduction_pct": 35,
            "implementation_effort": "medium",
            "timeframe": "3_months",
            "co2e_savings_kg": round(material_emission * 0.35, 2),
            "priority_score": 6,
            "category": "procurement"
        })
        recommendations.append({
            "title": "Local Sourcing to Reduce Transport Emissions",
            "description": "Source materials from local/regional suppliers to reduce transportation distances. Every 100km reduction in average shipping saves significant logistics emissions.",
            "target_activity": "material",
            "estimated_reduction_pct": 20,
            "implementation_effort": "medium",
            "timeframe": "3_months",
            "co2e_savings_kg": round(material_emission * 0.2, 2),
            "priority_score": 5,
            "category": "procurement"
        })

    # Sort by priority
    return sorted(recommendations, key=lambda x: x["priority_score"], reverse=True)


def run_recommender_agent(analyst_results: dict) -> dict:
    """
    Agent 4: Generate ranked reduction recommendations
    """
    totals = analyst_results.get("totals", {})
    by_type = analyst_results.get("by_activity_type", {})
    results = analyst_results.get("results", [])

    # Build context for LLM
    context = {
        "total_co2e_kg": totals.get("total_kg", 0),
        "total_co2e_tonnes": totals.get("total_tonnes", 0),
        "scope_breakdown": {
            "scope1_direct": totals.get("scope1_kg", 0),
            "scope2_energy": totals.get("scope2_kg", 0),
            "scope3_supply_chain": totals.get("scope3_kg", 0)
        },
        "by_activity": by_type,
        "top_emitting_items": sorted(
            [r for r in results if r.get("co2e_kg")],
            key=lambda x: x["co2e_kg"],
            reverse=True
        )[:5]
    }

    # Get rule-based recommendations as baseline
    rule_recs = get_rule_based_recommendations(analyst_results)

    # Try LLM for more contextual recommendations
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # 8b sufficient for recommendations
            messages=[
                {"role": "system", "content": RECOMMENDER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate reduction recommendations for this supply chain emissions data:\n{json.dumps(context, indent=2)}"}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        llm_recs = json.loads(raw.strip())

        # Use LLM recs if valid, fallback to rule-based
        if isinstance(llm_recs, list) and len(llm_recs) > 0:
            recommendations = sorted(llm_recs, key=lambda x: x.get("priority_score", 0), reverse=True)
            source = "llm"
        else:
            recommendations = rule_recs
            source = "rule_based"

    except Exception:
        recommendations = rule_recs
        source = "rule_based_fallback"

    return {
        "success": True,
        "recommendations": recommendations,
        "source": source,
        "total_potential_savings_kg": sum(
            r.get("co2e_savings_kg", 0) for r in recommendations
        )
    }
