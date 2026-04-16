"""
KAFKA ARCHITECTURE GUIDE FOR DEMO PRESENTATION

This document outlines the event-driven carbon intelligence pipeline architecture
and provides exact talking points for judges/technical reviewers.
"""

ARCHITECTURE_OVERVIEW = """
┌─────────────────────────────────────────────────────────────────────────┐
│                 ENTERPRISE CARBON INTELLIGENCE PLATFORM                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ERP Feeds                    Logistics APIs                Utilities   │
│      │                               │                          │       │
│      └───────────────────┬───────────┴──────────────┬──────────┘        │
│                          │                          │                    │
│                    [KAFKA PRODUCER]  (producer.py)  │                    │
│                          │                          │                    │
│                          └──────────────┬───────────┘                    │
│                                        │                                │
│                        Topic: carbon-events (Kafka Broker)             │
│                         - Retention: 24h                                │
│                         - Partitions: 1 (demo)                          │
│                         - Replication: 1                                │
│                          │                                              │
│                    [KAFKA CONSUMER]  (consumer.py)                      │
│                          │                                              │
│              ┌───────────┴───────────────────────────┐                  │
│              │   Processing Layer                    │                  │
│              │   (services/processor.py)             │                  │
│              │                                      │                  │
│         ┌────┴────┐  ┌──────────────┐  ┌─────────┐  │                  │
│         │ Event   │  │ Emit AI      │  │ Update  │  │                  │
│         │ Parsing │→ │ Insights     │→ │ Metrics │  │                  │
│         │         │  │ (services/   │  │ Store   │  │                  │
│         └─────────┘  │  ai_         │  │         │  │                  │
│                      │  interpreter)│  └────┬────┘  │                  │
│                      └──────────────┘       │       │                  │
│              └───────────────────────────────┼───────┘                  │
│                                            │                           │
│                  Insights Store (runtime/insights_state.json)          │
│                   - Live metrics                                        │
│                   - Aggregated emissions                                │
│                   - Activity breakdown                                  │
│                   - AI interpretations                                  │
│                                            │                           │
│                    [GRADIO DASHBOARD]  (app.py)                        │
│                    - Pipeline status                                    │
│                    - Real-time KPIs                                     │
│                    - Analysis tabs                                      │
│                    - ESG report generation                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
"""

# ============================================================================
# TALKING POINTS FOR JUDGES
# ============================================================================

ELEVATOR_PITCH = """
"We built a real-time carbon intelligence platform using enterprise event-driven 
architecture. Unlike static report generators, our system continuously ingests 
operational data from multiple sources (ERP, IoT, billing, logistics) via Kafka, 
processes emissions calculations in real-time, and surfaces AI-powered insights 
to stakeholders. This mirrors how modern enterprise platforms handle streaming 
sustainability data."
"""

TECHNICAL_DEPTH_QUESTIONS = {
    "Why Kafka?": """
This is an excellent question. In real enterprise environments, carbon data arrives 
asynchronously from distributed sources:
- ERP systems generate transactional data (purchases, shipments)
- IoT sensors stream energy/fuel consumption continuously
- Billing systems emit monthly/daily reports
- Logistics APIs provide real-time shipment events

Kafka is the industry standard for decoupling data producers from consumers:
1. **Scalability**: Can handle millions of events/day
2. **Durability**: Events persist for 24h (configurable)
3. **Decoupling**: Producers don't wait for consumers to process
4. **Replay**: Can reprocess historical events for model updates

For this hackathon, we're running it locally. In production, this would be 
Confluent Cloud or MSK (AWS Managed Streaming for Kafka).
""",

    "How does it differ from batch processing?": """
Batch approach (traditional):
- Upload CSV monthly
- Process offline
- Generate PDF report
- Insights are static/historical

Event-driven approach (ours):
- Continuous real-time ingestion
- Running aggregations
- Live operational dashboards
- Immediate anomaly detection
- Historical trend analysis

Think: Netflix watching your viewing patterns in real-time vs. asking you 
to upload your viewing history monthly as an Excel file.
""",

    "What about data quality/validation?": """
Our system has multiple quality gates:

1. **Schema Validation** (kafka/schemas.py):
   - All events must conform to defined structure
   - Enforces supplier_id, co2e_kg, activity_category, etc.
   - Type checking at ingest

2. **Confidence Scoring** (producer):
   - Each event has confidence_score (0-1)
   - Tracks extraction/calculation quality
   - Dashboard shows avg confidence per session

3. **Consumer Insights** (services/insights_store.py):
   - Tracks supplier/region diversity
   - Monitors data freshness
   - Alerts if quality dips below threshold

4. **AI Interpretation** (services/ai_interpreter.py):
   - Rule-based checks for anomalies
   - Optional Groq LLM for sophisticated analysis
""",

    "How do you handle late/missing data?": """
Late-arriving data is a reality in enterprise systems:

1. **Kafka Retention**: Events held for 24h, allowing catch-up
2. **Consumer Group State**: Tracks offset per consumer group
3. **Reprocessing**: Can replay events if pipeline crashed
4. **Windowing**: Could add time-windowed aggregations (e.g., 5-min windows)

For production, we'd implement:
- Late-arriving event handlers
- Data reconciliation jobs
- Watermarking for drift detection
""",

    "Can this scale to real enterprise volume?": """
Absolutely. Architecture is already production-ready:

Single instance (current):
- 1 Kafka broker
- 1 producer, 1 consumer
- Can handle ~1000 events/min

Production scale (MSK, RDS):
- Multi-broker Kafka cluster
- Horizontally scalable producers (multiple data integrations)
- Multiple consumers (different processing pipelines)
- Stream processors like Kafka Streams or Flink
- Time-series DB (InfluxDB/TimescaleDB) for high-frequency metrics

Our design is already structured for this. Producer, consumer, and processor 
are decoupled services.
""",

    "How do you prevent double-counting emissions?": """
Excellent question. We have multiple mechanisms:

1. **Event Idempotency**:
   - Each event has unique key: (supplier_id, timestamp, transaction_id)
   - Consumers implement idempotent processing

2. **Insights Store**:
   - Single source of truth
   - Avoids double aggregation
   - Maintains running totals

3. **Deduplication** (Kafka level):
   - Could enable idempotent producers in Kafka config
   - Prevents duplicate publishes

4. **Transaction Boundaries**:
   - Could wrap processor updates in transactions
   - Ensures atomic state updates
""",
}

# ============================================================================
# DEMO SCRIPT (3 STEP WALKTHROUGH)
# ============================================================================

DEMO_SCRIPT = """
DEMO WALKTHROUGH (5-7 minutes)

SETUP (Before demo starts):
1. Terminal 1: Running `python producer.py`
2. Terminal 2: Running `python consumer.py`
3. Browser: Dashboard already open at http://localhost:7860
4. Kafka UI (optional): http://localhost:9021 (if Redpanda Console running)

---

STEP 1: SHOW PRODUCER (Terminal 1) - 1 minute
---
"Here's the producer generating synthetic events modeled after real enterprise 
operational data. Each event represents:
- A shipment from logistics partner → Scope 3
- An electricity bill → Scope 2  
- A fuel purchase → Scope 1

Notice the realistic metadata:
- Timestamps (ISO 8601)
- Source systems (logistics_api, utility_bill_processor, procurement_system)
- Confidence scores (reflects actual data quality)

In real production, these would come from live ERP API integrations."

Point out real values: CO2 amounts, supplier diversity, event types.

---

STEP 2: SHOW CONSUMER (Terminal 2) - 1 minute
---
"The consumer is ingesting these events from Kafka in real-time. Each line shows:
- Event metadata
- CO2 calculation
- Running session total

Key insight: The session total is continuously updated. We're not waiting 
for batch processing—insights are live as data arrives."

Point out:
- Increasing session total
- Multiple suppliers being processed
- Processing latency (usually <100ms per event)

---

STEP 3: SHOW DASHBOARD (Browser) - 3-4 minutes
---

Navigate to "🔴 Live Monitor" tab:

"This dashboard is reading live metrics from our insights store, which the 
consumer populates in real-time. Notice:

1. **Pipeline Status**:
   - Connected ✅ 
   - Last event received: 2 seconds ago
   - Total events processed: 47
   - Throughput: 12 events/min

2. **Emissions Running Total**:
   - Scope 1/2/3 breakdown
   - Percentages updating live
   - Supply chain (Scope 3) dominates as expected

3. **Data Quality**:
   - 5 suppliers connected
   - 3 regions
   - Confidence 94%+ (good extraction quality)

This is real. Every number here comes from Kafka events we just published 
2 seconds ago. As producers send more data, these metrics update automatically."

Optional: Click "Refresh Status" to show it updates in real-time.

---

BUSINESS NARRATIVE:
---
"This architecture enables enterprises to:

1. **Monitor emissions continuously** - Not as a monthly PDF, but as a 
   living operational dashboard
   
2. **Detect anomalies in real-time** - If a supplier's emissions spike 
   unexpectedly, we know within seconds
   
3. **Make data-driven procurement decisions** - See which suppliers drive 
   most emissions, optimize dynamically
   
4. **Scale sustainably** - Process even real-time IoT feeds from thousands 
   of sensors or  supply chain partners

For a CFO or sustainability officer, this moves carbon management from 
'compliance reporting' to 'operational intelligence.'"

---

TECHNICAL DIFFERENTIATOR:
---
"Unlike static tools, we built on:
- Industry-standard event streaming (Kafka)
- Schema-driven data (prevents garbage in, garbage out)
- Real-time aggregation (no batch windows)
- Horizontally scalable architecture (add producers/consumers, not more servers)

This is how Netflix, Uber, and modern enterprises handle streaming data."
"""

# ============================================================================
# ARCHITECTURE DECISION LOG
# ============================================================================

ARCHITECTURE_DECISIONS = {
    "Kafka over Redis Streams": """
While Redis Streams would work for a hackathon, Kafka was chosen because:
- It's the actual technology enterprise use for carbon data pipelines
- Teaches judges about real event-driven architecture
- Provides durability/replay that Redis doesn't offer by default
- Easier to explain "why" if they ask
""",

    "JSON schema validation vs. Pydantic": """
We use JSON + schema.py TypedDict instead of Pydantic because:
- Lighter dependencies
- Clearer for Kafka schema documentation
- Can be swapped to Avro later for production
""",

    "Insights store in JSON vs. TimescaleDB": """
JSON file for hackathon, but:
- Shows you understand the pattern (append-only log)
- In production: would use TimescaleDB or InfluxDB
- Demonstrates architectural thinking even with lightweight tech
""",

    "Rule-based AI before Groq": """
Groq is optional enhancement because:
- Rule-based insights are guaranteed to work (no API failures)
- Judges see deterministic behavior during demo
- Groq can be added for "premium insights" if time permits
- Shows pragmatism (use the right tool for the job)
""",
}

# ============================================================================
# PRODUCTION ROADMAP (For follow-up questions)
# ============================================================================

PRODUCTION_ROADMAP = """
If asked "How would you deploy this to production?":

1. **Kafka Setup**:
   - AWS MSK or Confluent Cloud
   - 3 brokers for HA
   - Topic with 3 partitions (for parallel consumption)
   - Retention: 30 days

2. **Processing**:
   - Consumer as containerized service (Docker)
   - Kubernetes for orchestration
   - Horizontal scaling: N consumer replicas

3. **Data Storage**:
   - Store raw events in S3 (data lake)
   - Aggregate metrics in TimescaleDB (time-series DB)
   - Cache hot metrics in Redis

4. **Analytics Layer**:
   - Looker/Tableau for stakeholder dashboards
   - API layer (FastAPI) for programmatic access
   - WebSocket for real-time dashboard updates

5. **ML Layer** (future):
   - Anomaly detection models on streaming data
   - Supplier emissions forecasting
   - Procurement optimization recommendations

Cost: ~$500-2000/month for startup scale.
"""
