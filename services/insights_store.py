"""
Insights store: shared state for live metrics derived from streaming events.
Acts as the single source of truth for dashboard updates.
Persisted to JSON for durability and cross-process access.
"""

import json
import os
import threading
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path


INSIGHTS_FILE = "runtime/insights_state.json"
LOCK = threading.RLock()


def _ensure_dir():
    Path("runtime").mkdir(exist_ok=True)


def _default_state():
    """Returns fresh insights state template."""
    return {
        "timestamp": datetime.now().isoformat(),
        "pipeline": {
            "status": "connected",
            "last_event_received": None,
            "events_processed_total": 0,
            "kafka_throughput_per_min": 0,
            "consumer_latency_ms": 0,
            "processing_queue_depth": 0,
            "event_timestamps": [],
        },
        "emissions": {
            "total_kg_session": 0.0,
            "scope1_kg": 0.0,
            "scope2_kg": 0.0,
            "scope3_kg": 0.0,
            "scope_distribution": {"scope1": 0, "scope2": 0, "scope3": 0},
        },
        "activity": {
            "event_types_seen": defaultdict(int),
            "suppliers_seen": set(),
            "regions_seen": set(),
            "confidence_avg": 0.0,
        },
        "live_events": [],  # last 30 events for display
        "ai_insights": {
            "dominant_scope": None,
            "dominant_activity": None,
            "recent_alert": None,
            "trend_summary": None,
            "interpretation": {
                "rule_based": "Awaiting first event...",
                "ai_enhanced": None,
                "primary": "Awaiting first event...",
                "timestamp": None,
            },
        },
    }


def load_insights():
    """Load current insights state from disk."""
    _ensure_dir()
    with LOCK:
        if not os.path.exists(INSIGHTS_FILE):
            state = _default_state()
            _save_insights_unsafe(state)
            return state
        try:
            with open(INSIGHTS_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                # Convert defaultdicts back
                if isinstance(state.get("activity", {}).get("event_types_seen"), dict):
                    state["activity"]["event_types_seen"] = defaultdict(int, state["activity"]["event_types_seen"])
                if isinstance(state.get("activity", {}).get("suppliers_seen"), list):
                    state["activity"]["suppliers_seen"] = set(state["activity"]["suppliers_seen"])
                if isinstance(state.get("activity", {}).get("regions_seen"), list):
                    state["activity"]["regions_seen"] = set(state["activity"]["regions_seen"])
                return state
        except (json.JSONDecodeError, OSError):
            return _default_state()


def _save_insights_unsafe(state):
    """Internal: save without locking (assumes caller has lock)."""
    _ensure_dir()
    # Convert sets to lists for JSON serialization
    state_copy = dict(state)
    activity_copy = dict(state_copy.get("activity", {}))
    activity_copy["event_types_seen"] = dict(activity_copy.get("event_types_seen", {}))
    activity_copy["suppliers_seen"] = list(activity_copy.get("suppliers_seen", set()))
    activity_copy["regions_seen"] = list(activity_copy.get("regions_seen", set()))
    state_copy["activity"] = activity_copy
    
    with open(INSIGHTS_FILE, "w", encoding="utf-8") as f:
        json.dump(state_copy, f, indent=2)


def save_insights(state):
    """Save insights state to disk (thread-safe)."""
    with LOCK:
        state["timestamp"] = datetime.now().isoformat()
        _save_insights_unsafe(state)


def update_from_event(event: dict):
    """
    Process a single Kafka event and update insights.
    Called by consumer after each event ingestion.
    """
    with LOCK:
        state = load_insights()
        
        # Update pipeline metrics
        state["pipeline"]["last_event_received"] = event.get("timestamp")
        state["pipeline"]["events_processed_total"] += 1
        now = datetime.now(timezone.utc)

        event_timestamps = state["pipeline"].get("event_timestamps", [])
        event_timestamps.append(now.isoformat())
        cutoff = now.timestamp() - 60
        event_timestamps = [
            ts for ts in event_timestamps
            if datetime.fromisoformat(ts).timestamp() >= cutoff
        ]
        state["pipeline"]["event_timestamps"] = event_timestamps
        state["pipeline"]["kafka_throughput_per_min"] = len(event_timestamps)

        event_ts = event.get("timestamp")
        if event_ts:
            try:
                parsed_event_ts = datetime.fromisoformat(event_ts.replace("Z", "+00:00"))
                latency_ms = max((now - parsed_event_ts).total_seconds() * 1000, 0)
                state["pipeline"]["consumer_latency_ms"] = round(latency_ms, 2)
            except ValueError:
                pass
        
        # Update emissions totals
        co2e = event.get("co2e_kg", 0)
        scope = event.get("activity_category", "scope3")
        
        state["emissions"]["total_kg_session"] += co2e
        state["emissions"][f"{scope}_kg"] = state["emissions"].get(f"{scope}_kg", 0) + co2e
        
        # Update scope distribution percentages
        total = state["emissions"]["total_kg_session"]
        if total > 0:
            state["emissions"]["scope_distribution"] = {
                "scope1": round(state["emissions"]["scope1_kg"] / total * 100, 1),
                "scope2": round(state["emissions"]["scope2_kg"] / total * 100, 1),
                "scope3": round(state["emissions"]["scope3_kg"] / total * 100, 1),
            }
        
        # Update activity insights
        event_type = event.get("event_type", "unknown")
        supplier = event.get("supplier_name", "unknown")
        region = event.get("region", "unknown")
        
        state["activity"]["event_types_seen"][event_type] = state["activity"]["event_types_seen"].get(event_type, 0) + 1
        state["activity"]["suppliers_seen"].add(supplier)
        state["activity"]["regions_seen"].add(region)
        
        # Rolling average confidence
        old_total = state["pipeline"]["events_processed_total"] - 1
        old_avg = state["activity"]["confidence_avg"]
        new_confidence = event.get("confidence_score", 0.9)
        state["activity"]["confidence_avg"] = (old_avg * old_total + new_confidence) / state["pipeline"]["events_processed_total"]
        
        # Keep last 30 events for live feed
        event_display = {
            "timestamp": event.get("timestamp"),
            "supplier": supplier,
            "event_type": event_type,
            "co2e_kg": co2e,
            "scope": scope,
        }
        state["live_events"].insert(0, event_display)
        state["live_events"] = state["live_events"][:30]
        
        # Detect dominant scope
        scopes = state["emissions"]["scope_distribution"]
        if scopes:
            dominant = max(scopes, key=scopes.get)
            state["ai_insights"]["dominant_scope"] = dominant
        
        # Detect dominant activity
        activities = state["activity"]["event_types_seen"]
        if activities:
            dominant_activity = max(activities, key=activities.get)
            state["ai_insights"]["dominant_activity"] = dominant_activity
        
        _save_insights_unsafe(state)
        return state


def update_interpretation(interpretation: dict):
    """Persist latest AI interpretation for dashboard consumption."""
    with LOCK:
        state = load_insights()
        state.setdefault("ai_insights", {})["interpretation"] = interpretation
        _save_insights_unsafe(state)
        return state


def get_dashboard_snapshot():
    """Get a clean snapshot for dashboard display (thread-safe)."""
    with LOCK:
        state = load_insights()
    
    # Convert for JSON serialization
    return {
        "timestamp": state["timestamp"],
        "pipeline": {
            "status": state["pipeline"]["status"],
            "last_event_received": state["pipeline"]["last_event_received"],
            "events_processed_total": state["pipeline"]["events_processed_total"],
            "kafka_throughput_per_min": state["pipeline"]["kafka_throughput_per_min"],
            "consumer_latency_ms": state["pipeline"]["consumer_latency_ms"],
            "processing_queue_depth": state["pipeline"]["processing_queue_depth"],
        },
        "emissions": {
            "total_kg_session": round(state["emissions"]["total_kg_session"], 2),
            "scope1_kg": round(state["emissions"]["scope1_kg"], 2),
            "scope2_kg": round(state["emissions"]["scope2_kg"], 2),
            "scope3_kg": round(state["emissions"]["scope3_kg"], 2),
            "scope_distribution": state["emissions"]["scope_distribution"],
        },
        "activity": {
            "event_types_seen": dict(state["activity"]["event_types_seen"]),
            "supplier_count": len(state["activity"]["suppliers_seen"]),
            "region_count": len(state["activity"]["regions_seen"]),
            "confidence_avg": round(state["activity"]["confidence_avg"], 3),
        },
        "live_events": state["live_events"],
        "ai_insights": state["ai_insights"],
    }
