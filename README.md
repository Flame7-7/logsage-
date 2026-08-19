# LogSage AI

**AI-powered log analysis and incident detection platform**

> Upload logs or stream them in real time. LogSage automatically detects anomalies, clusters related incidents, performs AI root cause analysis, and suggests fixes — all backed by vector embeddings and LLM reasoning.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                          │
│  File Upload │ WebSocket Stream │ REST API │ Simulated Data     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Normalizer  │  (TXT / JSON / CSV → LogEntry)
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │   Embedding Generator   │  (SentenceTransformers)
              │     + ChromaDB Store    │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  Incident Cluster Engine │  (DBSCAN + cosine similarity)
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │      AI Analyzer        │  (Claude + RAG retrieval)
              │  Root Cause Analysis    │
              │  Timeline Generation    │
              └────────────┬────────────┘
                           │
         ┌─────────────────▼─────────────────┐
         │    Dashboard + Alerts + WS Feed    │
         └───────────────────────────────────┘
```

### Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.12, FastAPI, AsyncIO, SQLAlchemy 2.0 async |
| **Database** | PostgreSQL 16, Alembic migrations |
| **Cache/Queue** | Redis 7, Celery workers, pub/sub |
| **AI/ML** | SentenceTransformers, ChromaDB, scikit-learn DBSCAN, Anthropic Claude |
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Recharts |
| **Observability** | Prometheus, Grafana, structlog (JSON) |
| **Infra** | Docker Compose, multi-stage builds |

---

## Folder Structure

```
logsage/
├── backend/
│   ├── main.py                    # FastAPI app + lifespan
│   ├── core/
│   │   ├── config.py              # Pydantic Settings v2
│   │   ├── database.py            # Async SQLAlchemy engine
│   │   ├── redis_client.py        # Redis + pub/sub helpers
│   │   ├── logging.py             # structlog setup
│   │   └── metrics.py             # Prometheus counters/histograms
│   ├── models/
│   │   └── models.py              # ORM: LogEntry, Incident, Cluster, Alert
│   ├── schemas/
│   │   └── schemas.py             # Pydantic v2 request/response models
│   ├── repositories/
│   │   └── repositories.py        # Repository pattern (async queries)
│   ├── services/
│   │   └── services.py            # IngestionService, MetricsService
│   ├── ai/
│   │   ├── embeddings/
│   │   │   └── embedding_service.py   # SentenceTransformers + ChromaDB
│   │   ├── analysis/
│   │   │   └── analyzer.py        # LLM RCA + timeline generation
│   │   └── clustering.py          # DBSCAN clustering + anomaly detection
│   ├── workers/
│   │   ├── celery_app.py          # Celery configuration
│   │   └── tasks.py               # Background tasks
│   ├── api/
│   │   └── routes/
│   │       └── routes.py          # All FastAPI route handlers
│   └── utils/
│       ├── log_parser.py          # TXT/JSON/CSV parser + normalizer
│       └── sample_data.py         # Realistic log data generator
├── frontend/
│   └── src/
│       ├── app/                   # Next.js app router
│       ├── components/
│       │   ├── dashboard/         # Sidebar, MetricsBar, ChartsPanel
│       │   ├── incidents/         # IncidentPanel, ClusterPanel
│       │   └── logs/              # LiveFeed, UploadPanel
│       ├── hooks/
│       │   └── useLiveFeed.ts     # WebSocket hook with auto-reconnect
│       ├── lib/
│       │   └── api.ts             # Axios client + SWR hooks
│       └── types/
│           └── index.ts           # Full TypeScript types
├── monitoring/
│   ├── prometheus/prometheus.yml
│   └── grafana/
│       ├── datasources/
│       └── dashboards/
├── tests/
│   ├── unit/test_log_parser.py
│   └── integration/test_api.py
├── docker-compose.yml
└── .env.example
```

---

## Setup

### Prerequisites

- Docker + Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.12+ (for local backend dev)

### Quick Start (Docker)

```bash
# 1. Clone and configure
git clone https://github.com/yourname/logsage-ai
cd logsage-ai
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# 2. Start all services
docker compose up -d

# 3. Open the dashboard
open http://localhost:3000

# 4. Generate sample data to get started
curl -X POST "http://localhost:8000/api/v1/logs/simulate?count=200&scenario=incident"
```

### Local Development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# Celery worker (separate terminal)
celery -A workers.celery_app worker --loglevel=info

# Frontend
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/unit/ -v
pytest tests/integration/ -v  # requires running DB + Redis
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/logs/upload` | Upload log file (TXT/JSON/CSV) |
| `POST` | `/api/v1/logs/stream` | Ingest log batch via REST |
| `POST` | `/api/v1/logs/simulate` | Generate + ingest sample data |
| `GET` | `/api/v1/incidents` | List incidents with filters |
| `GET` | `/api/v1/incidents/{id}` | Get incident detail |
| `PATCH` | `/api/v1/incidents/{id}` | Update status/severity |
| `POST` | `/api/v1/incidents/{id}/analyze` | Trigger AI root cause analysis |
| `GET` | `/api/v1/incidents/{id}/summary` | Get AI-generated summary |
| `GET` | `/api/v1/clusters` | List incident clusters |
| `GET` | `/api/v1/metrics` | Current metrics snapshot |
| `GET` | `/api/v1/metrics/dashboard` | Full dashboard data |
| `GET` | `/api/v1/alerts` | Active/firing alerts |
| `WS` | `/api/v1/live` | WebSocket real-time feed |
| `GET` | `/metrics/prometheus` | Prometheus scrape endpoint |

---

## Key Features

### Log Ingestion
- Accepts TXT (plain/syslog), JSON Lines, CSV
- Auto-detects format and encoding (chardet)
- Handles up to 50,000 lines per upload
- Live WebSocket streaming with auto-reconnect

### Embedding-Based Clustering
- SentenceTransformers (`all-MiniLM-L6-v2`) for semantic embeddings
- DBSCAN density clustering on cosine distance
- Automatic severity scoring from message semantics
- Human-readable cluster naming

### AI Root Cause Analysis
- Structured JSON output from Claude
- RAG retrieval of similar past incidents
- Confidence scoring per root cause
- Step-by-step recommended fixes
- Causal timeline generation

### Anomaly Detection
- Error rate spike detection (rolling window)
- Critical keyword matching
- Anomaly score per log entry
- Real-time flagging in the live feed

### Alert Engine
- Redis failure threshold
- Reconnect storm detection
- Queue saturation alerts
- Real-time push via Redis pub/sub → WebSocket

### Observability
- Prometheus metrics: `logsage_request_total`, `logsage_incident_total`, `logsage_processing_latency_seconds`, `logsage_queue_size`, `logsage_events_per_second`
- Grafana dashboards (pre-configured datasource)
- Structured JSON logs (structlog) for Loki ingestion
- Request ID tracing middleware

---

## Resume Bullet Points

```
• Built LogSage AI, a production-grade log analysis platform processing 50k+ log
  entries/batch using FastAPI async, PostgreSQL, Redis, and Celery background workers

• Implemented semantic log clustering with SentenceTransformers embeddings + DBSCAN,
  achieving automatic incident grouping without manual rule configuration

• Designed RAG-powered root cause analysis pipeline using ChromaDB vector store and
  Anthropic Claude, delivering structured diagnoses with confidence scores and fix recommendations

• Architected event-driven ingestion pipeline (file upload, REST, WebSocket) with
  multi-format normalization (TXT/JSON/CSV), anomaly detection, and real-time alert engine

• Built real-time monitoring dashboard in Next.js/TypeScript with live WebSocket feed,
  Recharts visualizations, and Prometheus/Grafana observability stack

• Followed clean architecture: repository pattern, service layer, dependency injection,
  Pydantic v2 schemas, Alembic migrations, Docker Compose deployment
```

---

## Scaling Roadmap

| Area | Improvement |
|------|------------|
| **Ingestion** | Kafka/Kinesis for high-throughput streaming (>1M logs/min) |
| **Embeddings** | GPU-accelerated batch processing, custom fine-tuned model |
| **Storage** | TimescaleDB for time-series log queries, S3 archival |
| **Clustering** | Online clustering (HDBSCAN) for incremental updates |
| **AI** | Fine-tune smaller model on labeled incident data, reduce latency |
| **Auth** | OAuth2/OIDC, RBAC, API key management |
| **Multi-tenancy** | Workspace isolation, per-tenant vector collections |
| **Alerting** | PagerDuty/Slack integration, alert routing rules |
