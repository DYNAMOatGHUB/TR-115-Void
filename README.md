---
title: Supply Chain Carbon Emission Analyzer
emoji: 🌿
colorFrom: emerald
colorTo: slate
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
license: mit
---

# 🌿 Supply Chain Carbon Emission Analyzer

AI-powered pipeline that ingests supply chain documents and calculates **Scope 1, 2 & 3 CO₂e emissions** using EPA/DEFRA emission factor databases.

## Architecture

```
Document Upload (PDF/CSV)
        ↓
[Agent 1] Extractor     — PyMuPDF + LLaMA-3 70B (Groq)
        ↓
[Agent 2] Validator     — Rule engine + LLaMA-3 70B
        ↓
[Agent 3] Analyst       — EPA/DEFRA factor lookup + CO₂e calculation
        ↓
[Agent 4] Recommender   — LLaMA-3 8B + rule-based ranking
        ↓
[Agent 5] Report Writer — LLaMA-3 8B executive summary + full ESG report
```

## Emission Factor Sources

- **Primary:** [EPA GHG Emission Factors Hub (2024)](https://www.epa.gov/climateleadership/ghg-emission-factors-hub)
- **Fallback:** [DEFRA/DESNZ UK Conversion Factors (2023)](https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting)

## Supported Inputs

- Invoices (PDF, CSV)
- Shipping manifests (PDF, CSV)
- Energy bills (PDF, CSV)
- Purchase orders (PDF, CSV)

## Outputs

- Scope 1/2/3 CO₂e breakdown
- Activity-wise emission visualization
- Ranked reduction recommendations
- Full ESG-ready audit report (Markdown)
- CSV export of line-item calculations

## Setup (Local)

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your key
python app.py
```

Or set the key directly in your shell:

```bash
export GROQ_API_KEY=your_key_here
python app.py
```

## Environment Variables (HF Secrets)

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key (free tier works) |

## Methodology

```
CO₂e = Activity Data × Emission Factor
```

GHG Protocol Corporate Standard — Scopes 1, 2, 3.
