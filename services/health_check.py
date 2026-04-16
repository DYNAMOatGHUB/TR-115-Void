"""
Health check for Kafka pipeline and services.
Detects if Kafka is actually running and responding.
"""

import socket
import os
from datetime import datetime, timezone, timedelta


def is_kafka_reachable(host: str = "localhost", port: int = 9092, timeout: int = 2) -> bool:
    """
    Check if Kafka broker is accessible.
    
    Args:
        host: Kafka broker hostname (default: localhost)
        port: Kafka broker port (default: 9092)
        timeout: Connection timeout in seconds
    
    Returns:
        True if broker is reachable, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def is_pipeline_stale(last_event_timestamp: str, stale_threshold_seconds: int = 30) -> bool:
    """
    Check if the pipeline hasn't received events recently.
    
    Args:
        last_event_timestamp: ISO format timestamp of last event
        stale_threshold_seconds: Max age of last event before considered stale
    
    Returns:
        True if last event is older than threshold, False otherwise
    """
    if not last_event_timestamp:
        return True
    
    try:
        last_event = datetime.fromisoformat(last_event_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age = (now - last_event).total_seconds()
        return age > stale_threshold_seconds
    except Exception:
        return True


def update_pipeline_health(insights_state: dict) -> dict:
    """
    Update the health status of the pipeline based on actual checks.
    
    Args:
        insights_state: Current insights state dict
    
    Returns:
        Updated insights_state with correct health status
    """
    pipeline = insights_state.get("pipeline", {})
    
    # Check if Kafka is reachable
    kafka_reachable = is_kafka_reachable()
    
    # Check if pipeline is stale (no recent events)
    last_event = pipeline.get("last_event_received")
    is_stale = is_pipeline_stale(last_event, stale_threshold_seconds=45)
    
    # Determine status
    if not kafka_reachable:
        pipeline["status"] = "offline"
        pipeline["status_reason"] = "Kafka broker unreachable"
    elif is_stale:
        pipeline["status"] = "stale"
        pipeline["status_reason"] = "No events received in 45+ seconds"
    else:
        pipeline["status"] = "connected"
        pipeline["status_reason"] = "Receiving events normally"
    
    insights_state["pipeline"] = pipeline
    return insights_state


def get_status_color_and_icon(status: str) -> tuple:
    """
    Get color and icon for status display.
    
    Returns:
        (color_hex, icon_text, status_label)
    """
    status_map = {
        "connected": ("#10b981", "●", "Connected"),
        "stale": ("#f59e0b", "◐", "Stale"),
        "offline": ("#ef4444", "●", "Offline"),
    }
    
    return status_map.get(status, ("#9ca3af", "○", "Unknown"))
