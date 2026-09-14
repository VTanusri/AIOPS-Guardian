from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.utils import utcnow
from app.models import Anomaly, Incident, IncidentEvent

# Known failure patterns for correlation titles
PATTERN_TITLES = {
    "db_connection_usage": "Database Connection Pool Exhaustion",
    "db_latency": "Database Latency Spike",
    "api_latency": "High API Latency",
    "error_rate": "Elevated Error Rate",
    "memory_utilization": "Memory Pressure / Possible Leak",
    "disk_utilization": "Disk Capacity Risk",
    "network_utilization": "Network / Downstream Degradation",
}

METRIC_RELATIONSHIPS = {
    "db_connection_usage": {"db_latency", "api_latency", "error_rate"},
    "db_latency": {"api_latency", "error_rate", "db_connection_usage"},
    "api_latency": {"error_rate", "db_latency"},
    "error_rate": {"api_latency", "db_latency"},
    "memory_utilization": {"api_latency", "error_rate", "cpu_utilization"},
    "disk_utilization": {"db_latency", "error_rate"},
    "network_utilization": {"api_latency", "error_rate"},
}

SERVICE_DEPENDENCIES = {
    "api-gateway": {"order-service", "payment-service"},
    "order-service": {"database", "inventory-service"},
    "payment-service": {"database", "external-payment"},
    "inventory-service": {"database"},
}


def _severity_rank(sev: str) -> int:
    order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4, "INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    return order.get(sev, 1)


def _incident_severity(anomalies: list[Anomaly]) -> str:
    rank = max(_severity_rank(a.severity) for a in anomalies)
    return ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"][rank]


def _related(a: Anomaly, b: Anomaly, window_seconds: int) -> bool:
    if abs((a.timestamp - b.timestamp).total_seconds()) > window_seconds:
        return False
    if a.service == b.service:
        return True
    if b.service in SERVICE_DEPENDENCIES.get(a.service, set()) or a.service in SERVICE_DEPENDENCIES.get(
        b.service, set()
    ):
        return True
    related_metrics = METRIC_RELATIONSHIPS.get(a.metric, set())
    if b.metric in related_metrics or a.metric in METRIC_RELATIONSHIPS.get(b.metric, set()):
        return True
    return False


def _title_for(anomalies: list[Anomaly]) -> str:
    metrics = {a.metric for a in anomalies}
    if "db_connection_usage" in metrics:
        return PATTERN_TITLES["db_connection_usage"]
    for key, title in PATTERN_TITLES.items():
        if key in metrics:
            return title
    return f"Correlated anomaly across {len({a.service for a in anomalies})} services"


def correlate_anomalies(db: Session, window_seconds: int = 120) -> list[Incident]:
    """Group recent unassigned anomalies into incidents."""
    cutoff = utcnow() - timedelta(seconds=window_seconds * 2)
    open_statuses = {"Detected", "Investigating", "RCA Available"}
    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.timestamp >= cutoff, Anomaly.incident_id.is_(None))
        .order_by(Anomaly.timestamp.asc())
        .all()
    )
    if not anomalies:
        return []

    # Also attach to existing open incidents if related
    open_incidents = db.query(Incident).filter(Incident.status.in_(open_statuses)).all()
    created: list[Incident] = []
    used: set[int] = set()

    for anomaly in anomalies:
        if anomaly.id in used:
            continue
        attached = False
        for incident in open_incidents + created:
            incident_anomalies = (
                db.query(Anomaly).filter(Anomaly.incident_id == incident.id).all()
                if incident.id
                else []
            )
            # compare against incident's known signals
            probe = incident_anomalies[:1] or [anomaly]
            if any(_related(anomaly, ia, window_seconds) for ia in (incident_anomalies or probe)):
                anomaly.incident_id = incident.id
                services = set(incident.affected_services or [])
                services.add(anomaly.service)
                incident.affected_services = sorted(services)
                signals = list(incident.correlated_signals or [])
                if anomaly.metric not in signals:
                    signals.append(anomaly.metric)
                incident.correlated_signals = signals
                if _severity_rank(anomaly.severity) > _severity_rank(incident.severity.lower()):
                    incident.severity = _incident_severity([anomaly] + incident_anomalies)
                db.add(
                    IncidentEvent(
                        incident_pk=incident.id,
                        event_type="anomaly_correlated",
                        message=f"Correlated {anomaly.metric} on {anomaly.service} ({anomaly.value})",
                        payload={"anomaly_id": anomaly.id},
                    )
                )
                used.add(anomaly.id)
                attached = True
                break
        if attached:
            continue

        cluster = [anomaly]
        used.add(anomaly.id)
        for other in anomalies:
            if other.id in used:
                continue
            if any(_related(other, c, window_seconds) for c in cluster):
                cluster.append(other)
                used.add(other.id)

        title = _title_for(cluster)
        sev = _incident_severity(cluster)
        incident = Incident(
            incident_id=f"INC-{uuid.uuid4().hex[:8].upper()}",
            title=title,
            severity=sev,
            status="Detected",
            started_at=min(a.timestamp for a in cluster),
            affected_services=sorted({a.service for a in cluster}),
            correlated_signals=[a.metric for a in cluster],
            summary=f"Detected {len(cluster)} correlated anomalies starting with {cluster[0].metric}.",
        )
        db.add(incident)
        db.flush()
        for a in cluster:
            a.incident_id = incident.id
        db.add(
            IncidentEvent(
                incident_pk=incident.id,
                event_type="created",
                message=f"Incident created from {len(cluster)} anomalies: {title}",
                payload={"anomaly_ids": [a.id for a in cluster]},
            )
        )
        created.append(incident)
        open_incidents.append(incident)

    db.commit()
    return created
