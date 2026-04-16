"""
Pipeline Orchestrator
Chains all 5 agents in sequence with error handling
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.extractor import extract_from_file
from pipeline.validator import run_validator_agent
from pipeline.analyst import run_analyst_agent
from pipeline.recommender import run_recommender_agent
from pipeline.report_writer import run_report_writer_agent


def run_full_pipeline(file_path: str, region: str = "us") -> dict:
    """
    Full 5-agent pipeline:
    File → Extract → Validate → Analyse → Recommend → Report
    
    Returns complete pipeline output dict
    """
    pipeline_output = {}
    errors = []

    print(f"[1/5] Extractor Agent: Processing {os.path.basename(file_path)}...")
    extracted = extract_from_file(file_path)
    pipeline_output["extracted"] = extracted

    if not extracted.get("success"):
        return {
            "success": False,
            "error": f"Extraction failed: {extracted.get('error')}",
            "pipeline_output": pipeline_output
        }

    print(f"      → Extracted {len(extracted.get('data', {}).get('items', []))} items")

    print("[2/5] Validator Agent: Checking data quality...")
    validated = run_validator_agent(extracted.get("data", {}))
    pipeline_output["validated"] = validated
    summary = validated.get("validation_summary", {})
    print(f"      → {summary.get('total_items', 0)} items | {summary.get('issues_found', 0)} issues found")

    print("[3/5] Carbon Analyst Agent: Calculating emissions...")
    analyst = run_analyst_agent(validated, region=region)
    pipeline_output["analyst"] = analyst
    totals = analyst.get("totals", {})
    print(f"      → Total: {totals.get('total_kg', 0):.2f} kg CO₂e")
    print(f"      → Scope 1: {totals.get('scope1_kg', 0):.2f} | Scope 2: {totals.get('scope2_kg', 0):.2f} | Scope 3: {totals.get('scope3_kg', 0):.2f}")

    print("[4/5] Recommendation Agent: Generating reduction strategies...")
    recommender = run_recommender_agent(analyst)
    pipeline_output["recommender"] = recommender
    print(f"      → {len(recommender.get('recommendations', []))} recommendations generated")
    print(f"      → Potential savings: {recommender.get('total_potential_savings_kg', 0):.2f} kg CO₂e")

    print("[5/5] Report Writer Agent: Generating ESG report...")
    report = run_report_writer_agent(pipeline_output)
    pipeline_output["report"] = report
    print(f"      → Report generated ({len(report.get('markdown_report', ''))} chars)")

    print("\n✅ Pipeline complete!")

    return {
        "success": True,
        "pipeline_output": pipeline_output,
        "summary": {
            "file": os.path.basename(file_path),
            "items_extracted": len(extracted.get("data", {}).get("items", [])),
            "items_calculated": analyst.get("items_calculated", 0),
            "total_co2e_kg": totals.get("total_kg", 0),
            "total_co2e_tonnes": totals.get("total_tonnes", 0),
            "scope1_kg": totals.get("scope1_kg", 0),
            "scope2_kg": totals.get("scope2_kg", 0),
            "scope3_kg": totals.get("scope3_kg", 0),
            "recommendations_count": len(recommender.get("recommendations", [])),
            "potential_savings_kg": recommender.get("total_potential_savings_kg", 0)
        }
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <file_path> [region: us|uk|in]")
        sys.exit(1)

    file_path = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "us"

    result = run_full_pipeline(file_path, region)
    print(json.dumps(result["summary"], indent=2))
