"""
Event processor: transforms raw Kafka events into insights.
Acts as the processing layer between consumer and insights store.
"""

from services.insights_store import update_from_event, update_interpretation, get_dashboard_snapshot
from services.ai_interpreter import get_live_interpretation


def process_event(event: dict) -> dict:
    """
    Process a single Kafka carbon event:
    1. Update insights store
    2. Generate AI interpretation
    3. Return processed state for dashboard
    """
    # Update the insights state with this event
    updated_state = update_from_event(event)

    # Generate AI insights based on current state
    interpretation = get_live_interpretation(updated_state)
    update_interpretation(interpretation)

    # Return dashboard-ready snapshot
    snapshot = get_dashboard_snapshot()
    snapshot["ai_insights"]["interpretation"] = interpretation

    return snapshot


def batch_process_events(events: list) -> dict:
    """
    Process multiple events (useful for catch-up or replay).
    """
    final_state = None
    for event in events:
        final_state = process_event(event)
    return final_state or get_dashboard_snapshot()
