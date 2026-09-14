import os
from pathlib import Path
import asyncio

import pytest
from fastapi.testclient import TestClient

# Use isolated sqlite DB for API tests
os.environ["DATABASE_URL"] = f"sqlite:///{Path(__file__).parent / 'test_aiops.db'}"
os.environ["LLM_PROVIDER"] = "mock"

from app.core.database import Base, engine, SessionLocal, init_db  # noqa: E402
from app.core.seed import seed_database  # noqa: E402
from app.main import app  # noqa: E402
from app.services.pipeline import pipeline_worker  # noqa: E402


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    seed_database(db)
    db.close()
    with TestClient(app) as c:
        yield c
    # stop background worker started by lifespan
    try:
        asyncio.run(pipeline_worker.stop())
    except RuntimeError:
        pass


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_services_and_dashboard(client):
    r = client.get("/api/services")
    assert r.status_code == 200
    assert len(r.json()) >= 5
    d = client.get("/api/dashboard/summary")
    assert d.status_code == 200
    assert "system_status" in d.json()


def test_simulation_scenarios(client):
    r = client.get("/api/simulation/scenarios")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()}
    assert "db_pool_exhaustion" in keys
