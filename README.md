---
title: Supply Chain Carbon Emission Analyzer
emoji: chart_with_upwards_trend
colorFrom: emerald
colorTo: slate
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
license: mit
---

# Supply Chain Carbon Emission Analyzer

Carbon accounting platform for documents and live event streams. It calculates Scope 1, 2, and 3 emissions from invoices, manifests, utility bills, and Kafka-fed operational events.

## What it does

- Extracts activity data from PDF and CSV documents
- Calculates emissions using EPA and DEFRA factors
- Generates ranked reduction recommendations
- Produces a full ESG-ready report in Markdown and PDF
- Sends the report by email when configured
- Monitors a real Kafka/Redpanda stream in a live dashboard

## Architecture

```text
Document Upload (PDF/CSV)
        ↓
[Agent 1] Extractor     — PyMuPDF + Groq LLM
        ↓
[Agent 2] Validator     — Rule engine
        ↓
[Agent 3] Analyst       — EPA/DEFRA factor lookup + CO2e calculation
        ↓
[Agent 4] Recommender   — Ranked mitigation actions
        ↓
[Agent 5] Report Writer — Markdown + PDF + optional email delivery

Kafka Stream:
producer.py → carbon-events topic → consumer.py → services/processor.py → services/insights_store.py → app.py
```

## Key features

### Document workflow
- Upload PDF or CSV files
- Extract emissions-relevant line items
- Validate and calculate CO2e
- Review charts, recommendations, and final report

### Live Kafka workflow
- Real Kafka/Redpanda broker
- Producer publishes enterprise-style carbon events
- Consumer processes events and updates live metrics
- Dashboard shows current pipeline health and emissions totals

### Email delivery
- Automatically sends the generated PDF report when an email address is provided
- Uses SMTP credentials from `.env`
- Graceful fallback if email is not configured

### PDF compatibility fix
- Reports now use plain ASCII CO2e text in the PDF pipeline
- This avoids the rendering issue caused by Unicode subscript characters

## Supported inputs

- Invoices
- Shipping manifests
- Energy bills
- Purchase orders

## Outputs

- Scope 1/2/3 emissions breakdown
- Activity-wise emissions visualization
- Ranked reduction recommendations
- Full ESG-ready audit report (Markdown + PDF)
- CSV export of line-item calculations
- Company-specific historical run persistence
- Trend comparison vs previous run
- Live Kafka event monitor

## Emission factor sources

- Primary: EPA GHG Emission Factors Hub (2024)
- Fallback: DEFRA/DESNZ UK Conversion Factors (2023)

## Local setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your keys
python app.py
```

Or set the key directly in your shell:

```bash
export GROQ_API_KEY=your_key_here
python app.py
```

## Real-time Kafka demo

Start Kafka/Redpanda and the UI:

```bash
docker compose -f docker-compose.yaml up -d
```

Start the services:

```bash
./startup.sh start
```

Or run them manually in separate terminals:

```bash
./.venv/bin/python producer.py
./.venv/bin/python consumer.py
./.venv/bin/python app.py
```

Open:

- Dashboard: http://127.0.0.1:7860
- Kafka UI: http://127.0.0.1:8080

## Automatic startup options

### Development script

```bash
./startup.sh start
./startup.sh status
./startup.sh logs
./startup.sh stop
```

### Systemd services

Use `carbon-producer.service` and `carbon-consumer.service` for always-on Linux deployments.

## Environment variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key |
| `GROQ_EXTRACTION_MODEL` | Extraction model name |
| `GROQ_RECOMMENDATION_MODEL` | Recommendation model name |
| `SMTP_SERVER` | SMTP host for email delivery |
| `SMTP_PORT` | SMTP port, usually 587 |
| `SENDER_EMAIL` | Sender email address |
| `SENDER_PASSWORD` | SMTP/app password |

## Deployment options

### Best for full stack
- Linux VPS or cloud VM with Docker Compose
- Run Kafka, producer, consumer, and app together
- Good choices: DigitalOcean Droplet, AWS EC2, Hetzner, GCP Compute Engine

### Best for production scale
- App on ECS, Kubernetes, or a VM
- Kafka on Confluent Cloud or Redpanda Cloud
- Secrets managed in AWS Secrets Manager, GCP Secret Manager, or Vault

### Best for UI-only demo
- Hugging Face Spaces for the Gradio app
- Not ideal for always-on Kafka services

## Methodology

```text
CO2e = Activity Data × Emission Factor
```

GHG Protocol Corporate Standard — Scopes 1, 2, and 3.
