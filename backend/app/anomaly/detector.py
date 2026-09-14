from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev

THRESHOLDS = {
    "cpu_utilization": 85,
    "memory_utilization": 90,
    "disk_utilization": 90,
    "db_connection_usage": 80,
    "error_rate": 5,
    "api_latency": 300,
    "db_latency": 50,
    "network_utilization": 90,
}


@dataclass
class AnomalySignal:
    metric: str
    service: str
    value: float
    baseline: float
    severity: str
    anomaly_score: float
    method: str
    expected: str


def _severity_from_score(score: float) -> str:
    if score >= 0.9:
        return "critical"
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    if score >= 0.35:
        return "low"
    return "info"


def detect_threshold(metric: str, service: str, value: float, baseline: float) -> AnomalySignal | None:
    limit = THRESHOLDS.get(metric)
    if limit is None:
        return None
    if value <= limit:
        return None
    over = (value - limit) / max(limit, 1)
    score = min(0.99, 0.55 + over)
    return AnomalySignal(
        metric=metric,
        service=service,
        value=value,
        baseline=baseline,
        severity=_severity_from_score(score),
        anomaly_score=round(score, 3),
        method="threshold",
        expected=f"< {limit}",
    )


def detect_zscore(
    metric: str,
    service: str,
    value: float,
    history: list[float],
    z_threshold: float = 2.5,
) -> AnomalySignal | None:
    if len(history) < 8:
        return None
    m = mean(history)
    std = pstdev(history)
    if std < 1e-6:
        return None
    z = abs((value - m) / std)
    if z < z_threshold:
        return None
    score = min(0.99, z / 6.0)
    return AnomalySignal(
        metric=metric,
        service=service,
        value=value,
        baseline=round(m, 2),
        severity=_severity_from_score(score),
        anomaly_score=round(score, 3),
        method="zscore",
        expected=f"~{m:.1f} ± {std:.1f}",
    )


def detect_isolation_forest(
    metric: str, service: str, value: float, history: list[float]
) -> AnomalySignal | None:
    """Optional Isolation Forest — skipped if sklearn/native libs are blocked."""
    if len(history) < 20:
        return None
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except Exception:
        return None
    data = np.array(history + [value], dtype=float).reshape(-1, 1)
    model = IsolationForest(contamination=0.1, random_state=42)
    preds = model.fit_predict(data)
    scores = model.decision_function(data)
    if preds[-1] != -1:
        return None
    raw = float(-scores[-1])
    score = min(0.99, max(0.4, raw))
    baseline = float(np.mean(history))
    return AnomalySignal(
        metric=metric,
        service=service,
        value=value,
        baseline=round(baseline, 2),
        severity=_severity_from_score(score),
        anomaly_score=round(score, 3),
        method="isolation_forest",
        expected=f"~{baseline:.1f}",
    )


def detect_anomalies_for_sample(
    metric: str, service: str, value: float, history: list[float]
) -> list[AnomalySignal]:
    baseline = mean(history) if history else value
    signals: list[AnomalySignal] = []
    t = detect_threshold(metric, service, value, baseline)
    if t:
        signals.append(t)
    z = detect_zscore(metric, service, value, history)
    if z:
        if signals and signals[0].method == "threshold":
            signals[0].anomaly_score = max(signals[0].anomaly_score, z.anomaly_score)
            signals[0].severity = _severity_from_score(signals[0].anomaly_score)
            signals[0].method = "threshold+zscore"
        else:
            signals.append(z)
    if not signals:
        iso = detect_isolation_forest(metric, service, value, history)
        if iso:
            signals.append(iso)
    return signals
