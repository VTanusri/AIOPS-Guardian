from datetime import datetime, timezone

from app.correlation.engine import _related
from app.models.entities import Anomaly


def test_related_anomalies_correlate():
    now = datetime.now(timezone.utc)
    a = Anomaly(
        id=1,
        metric="db_connection_usage",
        service="database",
        value=99,
        baseline=45,
        severity="critical",
        anomaly_score=0.9,
        method="threshold",
        timestamp=now,
    )
    b = Anomaly(
        id=2,
        metric="api_latency",
        service="api-gateway",
        value=400,
        baseline=85,
        severity="high",
        anomaly_score=0.8,
        method="threshold",
        timestamp=now,
    )
    assert _related(a, b, 120)
