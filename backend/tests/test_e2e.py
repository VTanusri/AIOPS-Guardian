"""Lightweight e2e-style path without waiting for full simulation timing."""

import os
from pathlib import Path

os.environ["DATABASE_URL"] = f"sqlite:///{Path(__file__).parent / 'test_e2e.db'}"
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine, init_db
from app.core.seed import seed_database
from app.core.utils import utcnow
from app.main import app
from app.models import Anomaly, Incident
from app.services.pipeline import pipeline_worker
import asyncio


def test_investigate_path():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    seed_database(db)
    inc = Incident(
        incident_id="INC-TEST001",
        title="Database Connection Pool Exhaustion",
        severity="CRITICAL",
        status="Detected",
        started_at=utcnow(),
        affected_services=["database", "api-gateway"],
        correlated_signals=["db_connection_usage", "api_latency", "error_rate"],
    )
    db.add(inc)
    db.flush()
    for metric, service, value, baseline in [
        ("db_connection_usage", "database", 99, 45),
        ("db_latency", "database", 160, 12),
        ("api_latency", "api-gateway", 480, 85),
        ("error_rate", "api-gateway", 12, 0.4),
    ]:
        db.add(
            Anomaly(
                metric=metric,
                service=service,
                value=value,
                baseline=baseline,
                severity="critical",
                anomaly_score=0.9,
                method="threshold",
                expected="< 80",
                timestamp=utcnow(),
                incident_id=inc.id,
            )
        )
    db.commit()
    db.close()

    with TestClient(app) as client:
        r = client.post("/api/incidents/INC-TEST001/investigate", json={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rca"]["confidence"] >= 40
        assert "Database" in body["rca"]["root_cause"] or "Insufficient" in body["rca"]["root_cause"]
        detail = client.get("/api/incidents/INC-TEST001")
        assert detail.status_code == 200
        assert detail.json()["status"] == "RCA Available"

    try:
        asyncio.run(pipeline_worker.stop())
    except RuntimeError:
        pass
