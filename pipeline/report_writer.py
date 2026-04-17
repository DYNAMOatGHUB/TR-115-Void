"""
Agent 5: Report Writer Agent
Responsibility: Compile all pipeline outputs → ESG-ready report (Markdown + CSV)
Uses: LLM for executive summary paragraph only. Rest is deterministic.
"""

import json
import csv
import io
from datetime import datetime
from pipeline.groq_client import get_groq_client

REPORT_SUMMARY_PROMPT = """You are a corporate sustainability report writer.
Write a professional 3-paragraph executive summary for a carbon emissions audit report.
Use the data provided. Be specific with numbers. Use formal ESG report tone.
Do NOT use markdown formatting. Plain text only. No headers."""


def _ascii_co2(text: str) -> str:
    """Normalize CO2 text so PDF rendering stays compatible."""
    return text.replace("CO₂e", "CO2e").replace("CO₂", "CO2").replace("₂", "2")


def generate_executive_summary(totals: dict, by_type: dict, supplier: str = None) -> str:
    """Generate LLM executive summary"""
    context = f"""
Total emissions: {totals.get('total_kg', 0):.2f} kg CO2e ({totals.get('total_tonnes', 0):.4f} tonnes CO2e)
Scope 1 (direct): {totals.get('scope1_kg', 0):.2f} kg CO2e
Scope 2 (energy): {totals.get('scope2_kg', 0):.2f} kg CO2e
Scope 3 (supply chain): {totals.get('scope3_kg', 0):.2f} kg CO2e
Activity breakdown: {json.dumps(by_type)}
Supplier/Company: {supplier or 'Not specified'}
Report Date: {datetime.now().strftime('%B %d, %Y')}
"""
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": REPORT_SUMMARY_PROMPT},
                {"role": "user", "content": context}
            ],
            temperature=0.4,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception:
        total_kg = totals.get('total_kg', 0)
        return _ascii_co2(
            f"This carbon emissions audit report covers supply chain activities with total estimated "
            f"emissions of {total_kg:.2f} kg CO2e. "
            f"Scope 1 direct emissions account for {totals.get('scope1_kg', 0):.2f} kg CO2e, "
            f"Scope 2 energy-related emissions for {totals.get('scope2_kg', 0):.2f} kg CO2e, "
            f"and Scope 3 supply chain emissions for {totals.get('scope3_kg', 0):.2f} kg CO2e. "
            f"This assessment was generated using EPA GHG Emission Factors Hub (2025) "
            f"and DEFRA conversion factors as applicable."
        )


def generate_markdown_report(pipeline_output: dict) -> str:
    """Generate full Markdown ESG report"""
    extracted = pipeline_output.get("extracted", {})
    validated = pipeline_output.get("validated", {})
    analyst = pipeline_output.get("analyst", {})
    recommender = pipeline_output.get("recommender", {})
    emission_validation = pipeline_output.get("emission_validation", {})

    totals = analyst.get("totals", {})
    by_type = analyst.get("by_activity_type", {})
    results = analyst.get("results", [])
    recommendations = recommender.get("recommendations", [])
    supplier = extracted.get("data", {}).get("supplier", "Unknown")

    exec_summary = generate_executive_summary(totals, by_type, supplier)
    now = datetime.now().strftime("%B %d, %Y %H:%M")

    lines = []
    lines.append("# Carbon Emissions Audit Report")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Methodology:** EPA GHG Emission Factors Hub (2025) + DEFRA  ")
    lines.append(f"**Supplier/Entity:** {supplier}  ")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(exec_summary)
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Emissions Overview")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| **Total CO2e** | **{totals.get('total_kg', 0):.2f} kg** |")
    lines.append(f"| Total CO2e (tonnes) | {totals.get('total_tonnes', 0):.4f} t |")
    lines.append(f"| Scope 1 – Direct | {totals.get('scope1_kg', 0):.2f} kg |")
    lines.append(f"| Scope 2 – Energy | {totals.get('scope2_kg', 0):.2f} kg |")
    lines.append(f"| Scope 3 – Supply Chain | {totals.get('scope3_kg', 0):.2f} kg |")
    lines.append(f"| Items Calculated | {analyst.get('items_calculated', 0)} |")
    lines.append(f"| Items Needing Review | {analyst.get('items_skipped', 0)} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Emissions by Activity Category")
    lines.append("")
    lines.append("| Activity | CO2e (kg) | % of Total |")
    lines.append("|----------|-----------|------------|")
    total_kg = totals.get("total_kg", 1)
    for activity, kg in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        pct = (kg / total_kg * 100) if total_kg > 0 else 0
        lines.append(f"| {activity.replace('_', ' ').title()} | {kg:.2f} | {pct:.1f}% |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Line-Item Breakdown")
    lines.append("")
    lines.append("| Description | Scope | CO2e (kg) | Factor Source | Confidence |")
    lines.append("|-------------|-------|-----------|---------------|------------|")
    for r in results:
        co2e = f"{r['co2e_kg']:.3f}" if r.get("co2e_kg") else "N/A"
        scope = r.get("scope_label", "Unknown")
        source = r.get("factor_source", "N/A")
        conf = r.get("confidence", "N/A")
        desc = (r.get("description") or "")[:60]
        lines.append(f"| {desc} | {scope} | {co2e} | {source} | {conf} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Validation & Audit Trail")
    lines.append("")
    coverage = emission_validation.get("coverage", {})
    comparison = emission_validation.get("comparison", {})
    confidence_label = emission_validation.get("confidence", "UNKNOWN")
    confidence_score = emission_validation.get("confidence_score_pct", 0)
    lines.append(f"- **Status:** {emission_validation.get('status', 'N/A')}")
    lines.append(f"- **Coverage:** {coverage.get('mapped_items', 0)}/{coverage.get('total_items', 0)} ({coverage.get('coverage_pct', 0)}%)")
    lines.append(f"- **Comparison Source:** {comparison.get('source', 'none')}")
    lines.append(f"- **Effective Diff:** {emission_validation.get('deviation_percent', comparison.get('effective_diff_pct', 'N/A'))}%")
    lines.append(f"- **Confidence:** {confidence_score}% ({confidence_label})")

    why_diff = emission_validation.get("why_difference", [])
    if why_diff:
        lines.append("")
        lines.append("**Why differences may occur:**")
        for reason in why_diff:
            lines.append(f"- {reason}")

    lines.append("")
    lines.append("**Sample calculation traces:**")
    for r in [x for x in results if x.get("co2e_kg")][:5]:
        lines.append(
            f"- {r.get('description', 'Unknown')[:70]} | "
            f"{r.get('factor_source', 'N/A')} | "
            f"{r.get('factor_match_method', 'N/A')} | "
            f"{r.get('calculation_formula', 'N/A')}"
        )
    lines.append("")

    if analyst.get("items_skipped", 0) > 0:
        lines.append("---")
        lines.append("")
        lines.append("## Items Requiring Manual Review")
        lines.append("")
        for r in analyst.get("review_needed", []):
            lines.append(_ascii_co2(f"- **{r.get('description', 'Unknown')}**: {r.get('calculation_note', 'No factor found')}"))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Reduction Recommendations")
    lines.append("")
    lines.append(f"**Estimated total potential savings: {recommender.get('total_potential_savings_kg', 0):.2f} kg CO2e**")
    lines.append("")

    for i, rec in enumerate(recommendations, 1):
        savings = rec.get('co2e_savings_kg', 0)
        pct = rec.get('estimated_reduction_pct', 0)
        effort = rec.get('implementation_effort', 'medium')
        timeframe = rec.get('timeframe', '').replace('_', ' ')
        lines.append(f"### {i}. {rec.get('title', 'Recommendation')}")
        lines.append(_ascii_co2(f"**Priority Score:** {rec.get('priority_score', 0)}/10 | **Effort:** {effort.title()} | **Timeframe:** {timeframe.title()}"))
        lines.append("")
        lines.append(_ascii_co2(rec.get('description', '')))
        lines.append("")
        lines.append(_ascii_co2(f"- Estimated reduction: **{pct}%** of {rec.get('target_activity', 'related')} emissions"))
        lines.append(_ascii_co2(f"- Potential savings: **{savings:.2f} kg CO2e**"))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Methodology & Data Sources")
    lines.append("")
    lines.append("- **Emission Factors:** EPA Emission Factors for Greenhouse Gas Inventories (2025)")
    lines.append("- **Fallback:** DEFRA/DESNZ UK Government GHG Conversion Factors (2023)")
    lines.append("- **Formula:** CO2e = Activity Data × Emission Factor")
    lines.append("- **Extraction:** PyMuPDF + Groq LLaMA-3 70B")
    lines.append("- **Scopes:** GHG Protocol Corporate Standard (Scopes 1, 2, 3)")
    lines.append("")
    lines.append("*This report was generated automatically. Values marked as low confidence should be verified manually.*")

    return _ascii_co2("\n".join(lines))


def generate_csv_export(analyst_results: dict) -> str:
    """Generate CSV string for download"""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Description", "Activity Type", "Activity Subtype",
        "Quantity", "Unit", "CO2e (kg)", "Scope", "Emission Factor",
        "Factor Unit", "Factor Source", "Factor Match Method", "Factor Confidence",
        "Normalized Quantity", "Calculation Formula", "Confidence", "Notes"
    ])

    for r in analyst_results.get("results", []):
        writer.writerow([
            r.get("description", ""),
            r.get("activity_type", ""),
            r.get("activity_subtype", ""),
            r.get("quantity", ""),
            r.get("unit", ""),
            r.get("co2e_kg", ""),
            r.get("scope_label", ""),
            r.get("emission_factor", ""),
            r.get("factor_unit", ""),
            r.get("factor_source", ""),
            r.get("factor_match_method", ""),
            r.get("factor_confidence", ""),
            r.get("input_quantity_normalized", ""),
            r.get("calculation_formula", ""),
            r.get("confidence", ""),
            r.get("calculation_note", "")
        ])

    return output.getvalue()


def run_report_writer_agent(pipeline_output: dict) -> dict:
    """
    Agent 5: Generate final ESG report in multiple formats
    """
    markdown = generate_markdown_report(pipeline_output)
    csv_data = generate_csv_export(pipeline_output.get("analyst", {}))

    return {
        "success": True,
        "markdown_report": markdown,
        "csv_export": csv_data,
        "generated_at": datetime.now().isoformat()
    }
