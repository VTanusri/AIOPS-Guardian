from app.rca.engine import confidence_label, score_candidates


def test_rca_db_pool_scores_highest():
    anomalies = [
        {"metric": "db_connection_usage", "service": "database", "value": 99, "baseline": 45, "severity": "critical", "anomaly_score": 0.95},
        {"metric": "db_latency", "service": "database", "value": 180, "baseline": 12, "severity": "high", "anomaly_score": 0.85},
        {"metric": "api_latency", "service": "api-gateway", "value": 500, "baseline": 85, "severity": "high", "anomaly_score": 0.8},
        {"metric": "error_rate", "service": "api-gateway", "value": 14, "baseline": 0.4, "severity": "high", "anomaly_score": 0.82},
    ]
    logs = [{"message": "connection pool timeout", "severity": "ERROR", "service": "database"}]
    ranked = score_candidates(anomalies, logs, rag_titles=["Database Connection Pool Exhaustion"])
    assert ranked[0].root_cause == "Database Connection Pool Exhaustion"
    assert ranked[0].score >= 50
    assert confidence_label(ranked[0].score) in {"HIGH CONFIDENCE", "MEDIUM CONFIDENCE", "LOW CONFIDENCE"}
