"""
Agent 1: Extractor Agent
Responsibility: Parse raw document text → structured activity JSON
Uses: PyMuPDF for PDF text, LLM for intelligent entity extraction
"""

import fitz  # PyMuPDF
import csv
import json
import re
from pipeline.groq_client import get_groq_client

EXTRACTOR_SYSTEM_PROMPT = """You are a carbon accounting data extraction specialist.
Your job is to extract supply chain activity data from business documents like invoices, shipping manifests, energy bills, and purchase orders.

Extract ALL activities that can be linked to carbon emissions:
- Fuel purchases (diesel, petrol, natural gas, LPG)
- Electricity consumption
- Transport/shipping (truck, rail, air, sea)
- Material purchases (steel, aluminum, plastic, paper, cement, etc.)
- Waste disposal

Return ONLY a valid JSON object. No explanation. No markdown. No preamble.

Schema:
{
  "document_type": "invoice|manifest|energy_bill|purchase_order|unknown",
  "supplier": "<company name or null>",
  "date": "<date string or null>",
  "currency": "<INR|USD|GBP|EUR or null>",
  "items": [
    {
      "description": "<exact text from document>",
      "activity_type": "<fuel|electricity|transport|material|waste>",
      "activity_subtype": "<diesel|gasoline|natural_gas|lpg|truck_freight|rail_freight|air_freight|sea_freight|steel|aluminum|plastic|paper|cement|coal|electronics|other>",
      "quantity": <number or null>,
      "unit": "<gallon|litre|kwh|mwh|kg|tonne|ton|mile|km|scf|cubic_metre or null>",
      "transport_mode": "<truck|rail|air|sea|van or null>",
      "origin": "<location or null>",
      "destination": "<location or null>",
      "distance": <number or null>,
      "distance_unit": "<mile|km or null>",
      "confidence": "<high|medium|low>"
    }
  ]
}

Rules:
- If quantity is ambiguous, set confidence to low
- If unit is missing, try to infer from context
- For transport, extract origin/destination/distance if present
- Always include the raw description text
- If nothing extractable, return items as empty array"""


KEYWORD_SUBTYPE_MAP = {
    "diesel": ("fuel", "diesel"),
    "petrol": ("fuel", "gasoline"),
    "gasoline": ("fuel", "gasoline"),
    "natural gas": ("fuel", "natural_gas"),
    "lpg": ("fuel", "lpg"),
    "electricity": ("electricity", "other"),
    "power": ("electricity", "other"),
    "truck": ("transport", "truck_freight"),
    "rail": ("transport", "rail_freight"),
    "air": ("transport", "air_freight"),
    "sea": ("transport", "sea_freight"),
    "steel": ("material", "steel"),
    "aluminum": ("material", "aluminum"),
    "plastic": ("material", "plastic"),
    "paper": ("material", "paper"),
    "cement": ("material", "cement"),
    "waste": ("waste", "other"),
}


def _infer_activity(description: str) -> tuple[str, str]:
    text = (description or "").lower()
    for keyword, mapped in KEYWORD_SUBTYPE_MAP.items():
        if keyword in text:
            return mapped
    return "material", "other"


def _extract_qty_unit(text: str) -> tuple[float | None, str | None]:
    if not text:
        return None, None

    pattern = r"(\d+(?:\.\d+)?)\s*(gallon|litre|liter|kwh|mwh|kg|tonne|ton|mile|km|scf|cubic_metre|m3)\b"
    match = re.search(pattern, text.lower())
    if not match:
        return None, None

    qty = float(match.group(1))
    unit = match.group(2)
    if unit == "liter":
        unit = "litre"
    if unit == "m3":
        unit = "cubic_metre"
    return qty, unit


def fallback_extract_structured(raw_text: str) -> dict:
    """Deterministic fallback extraction when LLM is unavailable."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    items = []

    # Try CSV first
    try:
        reader = csv.DictReader(raw_text.splitlines())
        if reader.fieldnames:
            for row in reader:
                description = " ".join(str(v) for v in row.values() if v).strip()
                if not description:
                    continue
                activity_type, activity_subtype = _infer_activity(description)
                qty = None
                unit = None

                for key in ["quantity", "qty", "amount", "value"]:
                    if key in row and row.get(key):
                        try:
                            qty = float(str(row.get(key)).replace(",", ""))
                            break
                        except Exception:
                            pass

                if not qty:
                    qty, unit = _extract_qty_unit(description)

                if not unit:
                    for key in ["unit", "uom"]:
                        if key in row and row.get(key):
                            unit = str(row.get(key)).lower().strip()

                items.append({
                    "description": description,
                    "activity_type": activity_type,
                    "activity_subtype": activity_subtype,
                    "quantity": qty,
                    "unit": unit,
                    "transport_mode": None,
                    "origin": row.get("origin") if isinstance(row, dict) else None,
                    "destination": row.get("destination") if isinstance(row, dict) else None,
                    "distance": None,
                    "distance_unit": None,
                    "confidence": "low"
                })
    except Exception:
        pass

    if not items:
        for line in lines[:100]:
            qty, unit = _extract_qty_unit(line)
            if qty is None and len(line) < 12:
                continue
            activity_type, activity_subtype = _infer_activity(line)
            items.append({
                "description": line,
                "activity_type": activity_type,
                "activity_subtype": activity_subtype,
                "quantity": qty,
                "unit": unit,
                "transport_mode": None,
                "origin": None,
                "destination": None,
                "distance": None,
                "distance_unit": None,
                "confidence": "low"
            })

    return {
        "document_type": "unknown",
        "supplier": None,
        "date": None,
        "currency": None,
        "items": items
    }


def extract_text_from_pdf(file_path: str) -> str:
    """Extract raw text from PDF using PyMuPDF"""
    text = ""
    try:
        doc = fitz.open(file_path)
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")
            # Also try to extract tables as text
            blocks = page.get_text("blocks")
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page_text
        doc.close()
    except Exception as e:
        text = f"PDF extraction error: {str(e)}"
    return text.strip()


def extract_text_from_csv(file_path: str) -> str:
    """Read CSV file as raw text"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"CSV read error: {str(e)}"


def extract_text_from_file(file_path: str) -> str:
    """Route to correct extractor based on file type"""
    ext = file_path.lower().split(".")[-1]
    if ext == "pdf":
        return extract_text_from_pdf(file_path)
    elif ext in ["csv", "txt"]:
        return extract_text_from_csv(file_path)
    else:
        # Try as text
        return extract_text_from_csv(file_path)


def run_extractor_agent(raw_text: str) -> dict:
    """
    Agent 1: Send raw document text to LLM for structured extraction
    Returns parsed dict with items array
    """
    # Truncate if too long (keep under 3000 tokens to stay within rate limits)
    if len(raw_text) > 6000:
        raw_text = raw_text[:6000] + "\n[... document truncated ...]"

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract all carbon-relevant activity data from this document:\n\n{raw_text}"}
            ],
            temperature=0.1,  # Low temp for deterministic extraction
            max_tokens=2000
        )

        raw_response = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
        raw_response = raw_response.strip()

        parsed = json.loads(raw_response)
        return {"success": True, "data": parsed}

    except RuntimeError as e:
        # API key not configured: continue with deterministic fallback extraction
        fallback_data = fallback_extract_structured(raw_text)
        return {
            "success": True,
            "data": fallback_data,
            "fallback_mode": True,
            "warning": str(e)
        }
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse error: {str(e)}", "raw": raw_response}
    except Exception as e:
        fallback_data = fallback_extract_structured(raw_text)
        return {
            "success": True,
            "data": fallback_data,
            "fallback_mode": True,
            "warning": f"LLM extraction unavailable, used fallback parser: {str(e)}"
        }


def extract_from_file(file_path: str) -> dict:
    """Full pipeline: file → text → structured extraction"""
    raw_text = extract_text_from_file(file_path)
    if not raw_text or len(raw_text) < 10:
        return {"success": False, "error": "Could not extract text from file"}
    result = run_extractor_agent(raw_text)
    result["raw_text_preview"] = raw_text[:500]
    return result
