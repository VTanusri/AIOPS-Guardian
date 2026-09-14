# API Specification (selected)

Base URL: `/api`

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | App health + LLM provider |
| GET | /services | Service catalog |
| GET | /metrics | Metric samples (filters: service, metric, minutes) |
| GET | /logs | Log explorer |
| GET | /traces | Trace list with spans |
| GET | /anomalies | Detected anomalies |
| GET | /incidents | Incident list |
| GET | /incidents/{id} | Incident detail + evidence/RCA |
| POST | /incidents/{id}/investigate | Run RAG+RCA pipeline |
| GET | /incidents/{id}/rca | Latest RCA |
| POST | /rag/search | Semantic knowledge search |
| GET | /knowledge | Documents |
| GET | /knowledge/status | Index status |
| POST | /knowledge/upload | Upload .md/.txt |
| POST | /knowledge/reindex | Rebuild embeddings |
| DELETE | /knowledge/{id} | Delete upload |
| GET | /simulation/scenarios | Scenario catalog |
| POST | /simulation/start | Start scenario |
| POST | /simulation/stop | Stop |
| POST | /simulation/reset | Reset overlays |
| GET | /dashboard/summary | Overview payload |
| GET | /evaluation | Measured evaluation metrics |
| GET | /stream/{channel} | SSE live updates |
| WS | /ws/{channel} | WebSocket live updates |

OpenAPI: `/docs`
