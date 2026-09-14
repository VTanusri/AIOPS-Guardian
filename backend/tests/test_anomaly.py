from app.anomaly.detector import detect_anomalies_for_sample, detect_threshold


def test_threshold_detects_db_saturation():
    sig = detect_threshold("db_connection_usage", "database", 99, 45)
    assert sig is not None
    assert sig.severity in {"critical", "high", "medium"}


def test_zscore_and_pipeline():
    history = [45 + (i % 2) for i in range(30)]
    assert not detect_anomalies_for_sample("db_connection_usage", "database", 46, history)
    signals = detect_anomalies_for_sample("db_connection_usage", "database", 99, history)
    assert signals
