# AIOps Guardian

AI-powered AIOps platform for **incident detection**, **explainable root-cause analysis**, and **RAG-backed investigation**.

Telemetry → Anomaly Detection → Incident Correlation → Evidence → RAG → LLM reasoning over evidence → Structured RCA → Dashboard.

The LLM is **not** the sole source of truth. Confidence scores come from a deterministic RCA engine; the LLM structures explanations from telemetry evidence and retrieved runbooks only.

## Problem

When something breaks in a distributed system, engineers need to know: what happened, what is the most probable root cause, what evidence supports it, which runbook applies, and what to investigate next — without hallucinated metrics.

## Solution

AIOps Guardian is a working academic/demo platform with:

- Live metrics, logs, and traces
- Explainable anomaly detection (threshold, z-score, Isolation Forest)
- Incident correlation across related signals
- ChromaDB + Sentence Transformers RAG over operational runbooks
- Pluggable `LLMProvider` (Ollama or Mock)
- Simulation Center for end-to-end demos
- Measured Evaluation page (not fabricated scores)

## Architecture

```text
Simulation / Telemetry Generator
        ↓
 Anomaly Detection  →  Incident Correlation
        ↓
 Evidence Extraction  +  RAG (ChromaDB)
        ↓
 Explainable RCA Scoring Engine
        ↓
 LLMProvider (Ollama | Mock) → Structured RCA JSON
        ↓
 FastAPI + React Observability Dashboard
```

## Tech stack

| Layer | Tech |
|-------|------|
| Frontend | React, Vite, TypeScript, Tailwind, Recharts, TanStack Query |
| Backend | Python, FastAPI, SQLAlchemy, Pydantic |
| Data | SQLite (local) / PostgreSQL (Compose) |
| ML | NumPy, pandas, scikit-learn |
| RAG | Sentence Transformers (`all-MiniLM-L6-v2`), ChromaDB |
| LLM | Ollama (`LLMProvider` abstraction + Mock fallback) |
| Observability | Prometheus + Grafana stubs, OpenTelemetry-ready layout |
| Runtime | Docker Compose |

## Project layout

See `backend/`, `frontend/`, `knowledge_base/`, `observability/`, `docker/`.

## Quick start (local, no Docker)

### Prerequisites

- Python 3.11+ (3.12 recommended for Docker image; 3.14 works with hashing-embedding fallback if needed)
- Node.js 20+
- Optional: [Ollama](https://ollama.com) with `ollama pull llama3.2`
- Optional: Docker Desktop for full Compose stack

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
set PYTHONPATH=.
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 (API proxied to :8000).

### Docker Compose

```bash
docker compose up --build
```

- UI: http://localhost:3000
- API: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin)

## Environment variables

Copy `.env.example` to `.env`. Important keys:

- `DATABASE_URL` — SQLite by default; Postgres URL in Compose
- `LLM_PROVIDER` — `auto` | `ollama` | `mock`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- `EMBEDDING_MODEL`, `CHROMA_PERSIST_DIR`

## GitHub-driven mode (A + B)

1. Open **GitHub Project** (`/project`) and paste a repo URL
2. Optional: `GITHUB_TOKEN` in `.env` for private repos / rate limits
3. **Import** → services inferred + docs indexed (A), Actions/commits/issues attached (B)
4. Simulation / incidents / RCA now run against that project's topology

## Demo flow

1. Open Overview — system should be **HEALTHY**
2. Go to **Simulation Center**
3. Start **Database Connection Pool Exhaustion**
4. Watch Live Metrics / Overview risk rise
5. Open **Incidents** — correlated incident appears
6. Open incident → **Run AI Investigation**
7. Inspect evidence, RAG hits, explainable confidence, recommendations
8. Reset simulation and repeat

## API (selected)

- `GET /api/health`
- `GET /api/dashboard/summary`
- `GET /api/metrics|logs|traces|anomalies|incidents`
- `POST /api/incidents/{id}/investigate`
- `POST /api/rag/search`, `POST /api/knowledge/reindex`
- `POST /api/simulation/start|stop|reset`
- `GET /api/evaluation`
- `GET /api/stream/{channel}` (SSE)

Interactive docs: http://localhost:8000/docs

## RCA methodology

Candidate root causes are scored with additive evidence weights (DB utilization, latency correlation, errors, RAG match, contradictions). Score maps to LOW / MEDIUM / HIGH confidence. The LLM may rephrase but cannot invent telemetry or override the numeric confidence from the engine.

## RAG pipeline

Documents → chunk → embed (`all-MiniLM-L6-v2` or hashing fallback) → ChromaDB (or in-memory) → top-k semantic retrieval during investigation.

## Evaluation

`GET /api/evaluation` and the Evaluation page run known scenarios and report measured:

- RCA accuracy
- Detection / correlation accuracy
- RAG top-1 accuracy
- False positive rate
- Average RCA time

## Testing

```bash
cd backend
set PYTHONPATH=.
pytest -q
```

```bash
cd frontend
npm run build
```

## Limitations

- Demo telemetry is simulated (not a full production agent fleet)
- Deep learning anomaly models intentionally omitted for explainability
- Ollama quality depends on local model availability
- First SentenceTransformer download can take time
- On some Windows hosts with Application Control (WDAC), native wheels (NumPy/SciPy/Chroma/Vite rolldown) may be blocked when the project lives on the Desktop — the app falls back to pure-Python anomaly stats + hashing embeddings, and uses Vite 5/esbuild for the frontend

## Future work

- OpenTelemetry collector ingestion from real services
- Historical incident similarity index
- Multi-tenant RBAC
- Safer semi-automated remediation playbooks with human approval

## License

Academic / educational project.
