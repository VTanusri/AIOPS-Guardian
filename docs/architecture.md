# AIOps Guardian — Architecture Decisions

## Why not LLM-only RCA?
Hallucinated metrics destroy trust in ops tools. Deterministic detection + scoring produces auditable confidence; the LLM only explains grounded evidence.

## Why SQLite locally?
Docker is optional on student machines. SQLite keeps `uvicorn` one-command runnable; Compose switches to PostgreSQL.

## Why MockLLMProvider?
Ollama may be absent. Mock returns structured RCA from the scoring engine so demos never hard-fail.

## Why ChromaDB?
Single purpose-built vector store; embeddings are not duplicated in Postgres.

## Why Isolation Forest only as supplement?
Primary signals use thresholds and z-scores so every anomaly remains explainable in the UI.
