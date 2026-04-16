import json
import os
from datetime import datetime


STORE_DIR = "company_data"
os.makedirs(STORE_DIR, exist_ok=True)


def _company_path(company_id: str) -> str:
    return os.path.join(STORE_DIR, f"{company_id}.json")


def load_history(company_id: str) -> list:
    path = _company_path(company_id)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


def save_run(company_id: str, summary: dict, analyst: dict, report_md: str):
    history = load_history(company_id)
    totals = analyst.get("totals", {}) if isinstance(analyst, dict) else {}

    history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "scope1": totals.get("scope1_kg", 0),
            "scope2": totals.get("scope2_kg", 0),
            "scope3": totals.get("scope3_kg", 0),
            "total": totals.get("total_kg", 0),
            "report_md": report_md,
        }
    )

    with open(_company_path(company_id), "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2)


def get_trend(company_id: str) -> dict:
    history = load_history(company_id)
    if len(history) < 2:
        return {"trend": "insufficient_data", "runs": len(history)}

    latest = history[-1].get("total", 0)
    previous = history[-2].get("total", 0)
    delta = latest - previous
    pct = (delta / previous * 100) if previous else 0

    return {
        "runs": len(history),
        "latest_kg": latest,
        "previous_kg": previous,
        "delta_kg": round(delta, 2),
        "delta_pct": round(pct, 1),
        "trend": "up" if delta > 0 else "down",
    }
