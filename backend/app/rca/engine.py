from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANDIDATES = [
    "Database Connection Pool Exhaustion",
    "Database Latency",
    "Memory Leak",
    "Disk Full",
    "Network Failure",
    "Downstream Service Failure",
    "Application Error",
    "Resource Saturation",
    "Configuration Problem",
    "High API Latency",
    "High Error Rate",
]


@dataclass
class CandidateScore:
    root_cause: str
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)


def confidence_label(score: float) -> str:
    if score >= 75:
        return "HIGH CONFIDENCE"
    if score >= 50:
        return "MEDIUM CONFIDENCE"
    return "LOW CONFIDENCE"


def score_candidates(
    anomalies: list[dict[str, Any]],
    logs: list[dict[str, Any]],
    rag_titles: list[str] | None = None,
) -> list[CandidateScore]:
    """Explainable additive scoring over telemetry evidence."""
    rag_titles = rag_titles or []
    metrics = {a["metric"]: a for a in anomalies}
    services = {a.get("service") for a in anomalies}
    log_text = " ".join(l.get("message", "").lower() for l in logs)

    scores: dict[str, CandidateScore] = {
        name: CandidateScore(root_cause=name, score=0.0) for name in CANDIDATES
    }

    def add(name: str, key: str, points: float, evidence: str) -> None:
        c = scores[name]
        c.breakdown[key] = c.breakdown.get(key, 0) + points
        c.score += points
        if points >= 0:
            c.supporting.append(evidence)
        else:
            c.contradicting.append(evidence)

    # DB pool exhaustion
    if "db_connection_usage" in metrics:
        v = metrics["db_connection_usage"]["value"]
        add("Database Connection Pool Exhaustion", "DB utilization", 25 if v >= 90 else 15, f"DB connection utilization at {v}%")
    if "db_latency" in metrics:
        add("Database Connection Pool Exhaustion", "DB timeout/latency", 20, f"DB latency elevated to {metrics['db_latency']['value']}ms")
        add("Database Latency", "DB latency", 25, f"DB latency {metrics['db_latency']['value']}ms")
    if "api_latency" in metrics and "db_connection_usage" in metrics:
        add("Database Connection Pool Exhaustion", "Latency correlation", 15, "API latency correlated with DB saturation")
        add("High API Latency", "API latency", 20, f"API latency {metrics['api_latency']['value']}ms")
    if "error_rate" in metrics and "db_connection_usage" in metrics:
        add("Database Connection Pool Exhaustion", "Error correlation", 10, f"Error rate {metrics['error_rate']['value']}%")
        add("High Error Rate", "Error rate", 20, f"Error rate {metrics['error_rate']['value']}%")
    if "timeout" in log_text or "connection" in log_text:
        add("Database Connection Pool Exhaustion", "Log signals", 10, "Logs mention connection/timeout issues")

    # Memory leak
    if "memory_utilization" in metrics:
        v = metrics["memory_utilization"]["value"]
        add("Memory Leak", "Memory utilization", 25 if v >= 90 else 12, f"Memory at {v}%")
        if v < 70:
            add("Memory Leak", "Contradicting signal", -10, "Memory utilization within normal range")

    # Disk
    if "disk_utilization" in metrics:
        v = metrics["disk_utilization"]["value"]
        add("Disk Full", "Disk utilization", 30 if v >= 95 else 15, f"Disk at {v}%")
        if v < 80:
            add("Disk Full", "Contradicting signal", -8, "Disk utilization not critical")

    # Network / downstream
    if "network_utilization" in metrics and metrics["network_utilization"]["value"] >= 85:
        add("Network Failure", "Network utilization", 20, f"Network util {metrics['network_utilization']['value']}%")
    if "external-payment" in services or "downstream" in log_text:
        add("Downstream Service Failure", "Downstream signals", 18, "Downstream/external service involved")

    # Resource saturation
    if "cpu_utilization" in metrics and metrics["cpu_utilization"]["value"] >= 90:
        add("Resource Saturation", "CPU saturation", 22, f"CPU at {metrics['cpu_utilization']['value']}%")

    # Application error
    if "error_rate" in metrics and metrics["error_rate"]["value"] >= 8 and "db_connection_usage" not in metrics:
        add("Application Error", "Standalone errors", 18, "Elevated errors without DB saturation")

    # RAG boost
    for title in rag_titles:
        for name in scores:
            if name.lower() in title.lower() or title.lower() in name.lower():
                add(name, "RAG match", 10, f"Knowledge match: {title}")

    # Contradictions for DB pool if DB healthy
    if "db_connection_usage" in metrics and metrics["db_connection_usage"]["value"] < 60:
        add("Database Connection Pool Exhaustion", "Contradicting signal", -15, "DB connections not saturated")

    ranked = sorted(scores.values(), key=lambda c: c.score, reverse=True)
    for c in ranked:
        c.score = max(0.0, min(100.0, c.score))
    return ranked


def recommendations_for(root_cause: str) -> list[str]:
    mapping = {
        "Database Connection Pool Exhaustion": [
            "Investigate connection leaks in application code",
            "Inspect long-running transactions and locks",
            "Review connection pool max size and timeouts",
            "Do not restart production DB without change window",
        ],
        "High API Latency": [
            "Identify slowest spans in recent traces",
            "Check downstream dependency latency",
            "Review recent deployments",
        ],
        "High Error Rate": [
            "Sample failing endpoints and status codes",
            "Correlate errors with deploy markers",
            "Inspect exception logs with trace IDs",
        ],
        "Memory Leak": [
            "Capture heap metrics / GC pressure",
            "Check for unbounded caches",
            "Review recent code changes allocating memory",
        ],
        "Disk Full": [
            "Identify largest volumes and log directories",
            "Clear safe temporary files only after verification",
            "Expand volume if capacity planning requires it",
        ],
        "Network Failure": [
            "Check packet loss and DNS resolution",
            "Validate security group / firewall changes",
            "Test downstream connectivity",
        ],
        "Downstream Service Failure": [
            "Check external dependency health status",
            "Enable graceful degradation / circuit breaker",
            "Review retry storm amplification",
        ],
    }
    return mapping.get(
        root_cause,
        [
            "Collect additional telemetry evidence",
            "Compare against recent healthy baseline",
            "Review related runbooks in the knowledge base",
        ],
    )
