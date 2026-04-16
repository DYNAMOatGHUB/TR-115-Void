"""
AI interpretation layer for live carbon stream.
Combines rule-based insights with optional Groq LLM for premium commentary.
"""

import os
from typing import Optional


def _format_event_label(label: str | None) -> str:
    if not label or label == "unknown":
        return "Mixed operational events"
    return label.replace("_", " ").strip().title()


def rule_based_insight(insights_state: dict) -> str:
    """
    Generate deterministic, fast rule-based commentary on emissions patterns.
    Guaranteed to work without external APIs.
    """
    emissions = insights_state.get("emissions", {})
    activity = insights_state.get("activity", {})
    dominant_scope = insights_state.get("ai_insights", {}).get("dominant_scope")

    total_co2 = emissions.get("total_kg_session", 0)
    events_count = insights_state.get("pipeline", {}).get("events_processed_total", 0)

    if events_count == 0:
        return "Awaiting first event data."

    scope_dist = emissions.get("scope_distribution", {})
    event_types = activity.get("event_types_seen", {})

    if event_types:
        top_activity_raw = max(event_types, key=event_types.get)
        top_count = event_types[top_activity_raw]
        top_activity = _format_event_label(top_activity_raw)
        top_activity_pct = (top_count / events_count * 100)
    else:
        top_activity = "Insufficient activity data"
        top_activity_pct = 0

    dominant_scope_label = {
        "scope1": "Scope 1 (Direct)",
        "scope2": "Scope 2 (Energy)",
        "scope3": "Scope 3 (Supply Chain)",
    }.get(dominant_scope, "Not available")

    dominant_scope_pct = scope_dist.get(dominant_scope, 0) if dominant_scope else 0
    avg_per_event = (total_co2 / events_count) if events_count else 0

    suppliers_seen = activity.get("suppliers_seen", [])
    supplier_count = activity.get("supplier_count", len(suppliers_seen))
    confidence = activity.get("confidence_avg", 0.9)

    if dominant_scope == "scope3":
        recommendation = "Prioritize supplier procurement and logistics optimization."
    elif dominant_scope == "scope2":
        recommendation = "Prioritize renewable electricity sourcing and energy efficiency."
    elif dominant_scope == "scope1":
        recommendation = "Prioritize fuel switching and fleet efficiency measures."
    else:
        recommendation = "Continue collecting events to improve signal quality."

    confidence_note = ""
    if confidence < 0.85:
        confidence_note = "\n- Data confidence is below target; source validation is recommended."

    return (
        "**What Happened**\n"
        f"- Dominant scope: {dominant_scope_label} at {dominant_scope_pct:.1f}% of session emissions.\n"
        f"- Leading activity: {top_activity} at {top_activity_pct:.0f}% of processed events.\n"
        "\n"
        "**Why It Matters**\n"
        f"- Session total is {total_co2:,.0f} kg CO₂e across {events_count} events "
        f"(average {avg_per_event:.1f} kg per event).\n"
        f"- Active suppliers in stream: {supplier_count}.{confidence_note}\n"
        "\n"
        "**Recommended Action**\n"
        f"- {recommendation}"
    )


def groq_enhanced_insight(
    insights_state: dict,
    ai_comment: str = "",
) -> Optional[str]:
    """
    Optional: Call Groq LLM for premium, sophisticated AI commentary.
    Falls back gracefully if GROQ_API_KEY not set or API call fails.
    """
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return None

    try:
        from groq import Groq

        client = Groq(api_key=groq_key)
        
        emissions = insights_state.get("emissions", {})
        total_co2 = emissions.get("total_kg_session", 0)
        scope_dist = emissions.get("scope_distribution", {})
        event_types = insights_state.get("activity", {}).get("event_types_seen", {})

        prompt = f"""You are a carbon accounting AI analyst. Based on this live emissions data stream, provide a 2-sentence executive insight.

Session Summary:
- Total CO₂e: {total_co2:,.0f} kg
- Scope Distribution: {scope_dist}
- Top Activities: {dict(sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:3])}

Provide a brief, actionable insight focused on immediate reduction strategy. Keep it under 50 words.
"""

        response = client.messages.create(
            model="llama-3-8b-instant",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
    except Exception as e:
        # Silent fallback if Groq fails
        return None


def get_live_interpretation(insights_state: dict) -> dict:
    """
    Generate full interpretation: rule-based + optional Groq.
    Returns dict ready for dashboard consumption.
    """
    rule_insight = rule_based_insight(insights_state)
    groq_insight = groq_enhanced_insight(insights_state)

    return {
        "rule_based": rule_insight,
        "ai_enhanced": groq_insight,
        "primary": groq_insight or rule_insight,
        "timestamp": insights_state.get("timestamp"),
    }
