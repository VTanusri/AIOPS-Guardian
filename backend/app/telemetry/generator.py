from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.events import event_bus
from app.core.utils import utcnow
from app.models import LogEntry, MetricSample, Span, Trace

# Mutable working baseline (starts as DEFAULT_BASELINE; swapped on GitHub import)
DEFAULT_BASELINE: dict[str, dict[str, float]] = {
    "api-gateway": {
        "cpu_utilization": 28,
        "memory_utilization": 42,
        "request_rate": 120,
        "error_rate": 0.4,
        "api_latency": 85,
        "network_utilization": 35,
    },
    "order-service": {
        "cpu_utilization": 32,
        "memory_utilization": 48,
        "request_rate": 95,
        "error_rate": 0.5,
        "api_latency": 110,
        "disk_utilization": 40,
    },
    "payment-service": {
        "cpu_utilization": 25,
        "memory_utilization": 40,
        "request_rate": 60,
        "error_rate": 0.3,
        "api_latency": 140,
    },
    "inventory-service": {
        "cpu_utilization": 22,
        "memory_utilization": 38,
        "request_rate": 70,
        "error_rate": 0.2,
        "api_latency": 90,
    },
    "database": {
        "cpu_utilization": 35,
        "memory_utilization": 55,
        "db_connection_usage": 45,
        "db_latency": 12,
        "disk_utilization": 48,
        "error_rate": 0.1,
    },
    "cache": {
        "cpu_utilization": 18,
        "memory_utilization": 60,
        "network_utilization": 25,
    },
    "external-payment": {
        "api_latency": 180,
        "error_rate": 0.5,
        "network_utilization": 20,
    },
}

BASELINE: dict[str, dict[str, float]] = {k: dict(v) for k, v in DEFAULT_BASELINE.items()}

# Mutable overlay used by simulation
_sim_overrides: dict[str, dict[str, float]] = {}
_sim_log_burst: list[dict[str, Any]] = []


def set_baseline(baseline: dict[str, dict[str, float]]) -> None:
    """Replace live telemetry topology (used after GitHub import)."""
    global BASELINE
    if not baseline:
        BASELINE = {k: dict(v) for k, v in DEFAULT_BASELINE.items()}
    else:
        BASELINE = {k: dict(v) for k, v in baseline.items()}


def get_baseline() -> dict[str, dict[str, float]]:
    return BASELINE


def reset_baseline() -> None:
    set_baseline(DEFAULT_BASELINE)


def set_simulation_overrides(overrides: dict[str, dict[str, float]]) -> None:
    global _sim_overrides
    _sim_overrides = overrides


def clear_simulation_overrides() -> None:
    global _sim_overrides, _sim_log_burst
    _sim_overrides = {}
    _sim_log_burst = []


def enqueue_sim_logs(logs: list[dict[str, Any]]) -> None:
    _sim_log_burst.extend(logs)


def _current_value(service: str, metric: str) -> float:
    base = BASELINE.get(service, {}).get(metric, 30.0)
    if service in _sim_overrides and metric in _sim_overrides[service]:
        return float(_sim_overrides[service][metric])
    noise = random.uniform(-0.04, 0.04) * max(base, 1)
    return max(0.0, base + noise)


def generate_metric_tick(db: Session) -> list[MetricSample]:
    now = utcnow()
    samples: list[MetricSample] = []
    for service, metrics in BASELINE.items():
        for metric in metrics:
            value = _current_value(service, metric)
            unit = "%"
            if metric in {"request_rate"}:
                unit = "rps"
            elif "latency" in metric:
                unit = "ms"
            elif metric == "error_rate":
                unit = "%"
            sample = MetricSample(
                service=service,
                metric=metric,
                value=round(value, 2),
                unit=unit,
                timestamp=now,
                labels={},
            )
            db.add(sample)
            samples.append(sample)
    db.commit()
    return samples


async def publish_metrics(samples: list[MetricSample]) -> None:
    payload = [
        {
            "service": s.service,
            "metric": s.metric,
            "value": s.value,
            "unit": s.unit,
            "timestamp": s.timestamp.isoformat(),
        }
        for s in samples
    ]
    await event_bus.publish("metrics", {"type": "metrics", "data": payload})


def generate_logs(db: Session, count: int = 3) -> list[LogEntry]:
    now = utcnow()
    entries: list[LogEntry] = []
    service_names = list(BASELINE.keys()) or ["app"]
    templates = [
        ("INFO", service_names[0], "Request handled successfully"),
        ("INFO", service_names[min(1, len(service_names) - 1)], "Operation completed"),
        ("DEBUG", "database" if "database" in BASELINE else service_names[0], "Query executed"),
        ("WARN", service_names[0], "Elevated latency observed"),
    ]
    # Real GitHub signals occasionally appear as INFO/WARN logs when project active
    try:
        from app.github.project_state import active_project

        proj = active_project.get()
        if proj and proj.get("signals"):
            failed = proj["signals"].get("failed_workflow_count") or 0
            if failed and random.random() < 0.25:
                templates.append(
                    (
                        "ERROR",
                        service_names[0],
                        f"GitHub Actions: {failed} recent workflow failure(s) detected for {proj.get('full_name')}",
                    )
                )
    except Exception:
        pass

    for _ in range(count):
        if _sim_log_burst:
            item = _sim_log_burst.pop(0)
            entry = LogEntry(
                timestamp=now,
                severity=item.get("severity", "ERROR"),
                service=item.get("service", "database"),
                message=item.get("message", "Simulated failure"),
                trace_id=item.get("trace_id"),
                span_id=item.get("span_id"),
                host=item.get("host", "demo-node-1"),
                metadata_json=item.get("metadata", {}),
            )
        else:
            severity, service, message = random.choice(templates)
            if service not in BASELINE:
                service = service_names[0]
            entry = LogEntry(
                timestamp=now,
                severity=severity,
                service=service,
                message=message,
                trace_id=None,
                span_id=None,
                host="demo-node-1",
                metadata_json={},
            )
        db.add(entry)
        entries.append(entry)
    db.commit()
    return entries


async def publish_logs(entries: list[LogEntry]) -> None:
    payload = [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "severity": e.severity,
            "service": e.service,
            "message": e.message,
            "trace_id": e.trace_id,
        }
        for e in entries
    ]
    await event_bus.publish("logs", {"type": "logs", "data": payload})


def generate_trace(db: Session, force_error: bool = False) -> Trace:
    now = utcnow()
    trace_id = uuid.uuid4().hex
    names = list(BASELINE.keys())
    edge = next((n for n, m in BASELINE.items() if "api_latency" in m and n != "database"), names[0])
    app = next((n for n in names if n not in {edge, "database", "cache"}), edge)
    has_db = "database" in BASELINE

    db_slow = False
    if has_db:
        db_slow = _current_value("database", "db_latency") > 40 or _current_value(
            "database", "db_connection_usage"
        ) > 80
    err = force_error or db_slow or _current_value(edge, "error_rate") > 5

    spans_spec = [
        (edge, "HTTP GET /", 0, 40, "ok"),
        (app, "handle_request", 20, 90, "ok"),
    ]
    if has_db:
        spans_spec.append(
            ("database", "SELECT", 40, 80 if not db_slow else 220, "error" if err else "ok")
        )

    total = max(s[2] + s[3] for s in spans_spec)
    parent = None
    trace = Trace(
        trace_id=trace_id,
        root_service=edge,
        total_duration_ms=float(total),
        status="error" if err else "ok",
        started_at=now,
    )
    db.add(trace)
    db.flush()
    for i, (service, op, offset, dur, status) in enumerate(spans_spec):
        sid = uuid.uuid4().hex[:16]
        if err and service == "database":
            status = "error"
            dur = max(dur, 180)
        db.add(
            Span(
                trace_pk=trace.id,
                span_id=sid,
                parent_span_id=parent,
                service=service,
                operation=op,
                duration_ms=float(dur),
                status=status,
                start_offset_ms=float(offset),
                attributes={"db.system": "postgresql"} if service == "database" else {},
            )
        )
        parent = sid if i < 2 else parent
    db.commit()
    db.refresh(trace)
    return trace


def latest_metric_map(db: Session) -> dict[str, float]:
    """Return latest value per metric name across services (prefer aggregate-ish keys)."""
    # Prefer an edge/app service that has the metric
    preferred = []
    for name, metrics in BASELINE.items():
        if name != "database":
            preferred.append(name)
    primary = preferred[0] if preferred else next(iter(BASELINE), "app")

    wanted = [
        "cpu_utilization",
        "memory_utilization",
        "request_rate",
        "error_rate",
        "api_latency",
        "db_connection_usage",
        "db_latency",
        "disk_utilization",
        "network_utilization",
    ]
    result: dict[str, float] = {}
    for metric in wanted:
        # find any service that owns this metric
        service = None
        if metric in BASELINE.get("database", {}):
            service = "database"
        elif metric in BASELINE.get(primary, {}):
            service = primary
        else:
            for sname, mets in BASELINE.items():
                if metric in mets:
                    service = sname
                    break
        if not service:
            result[metric] = 0.0
            continue
        row = (
            db.query(MetricSample)
            .filter(MetricSample.service == service, MetricSample.metric == metric)
            .order_by(MetricSample.timestamp.desc())
            .first()
        )
        result[metric] = row.value if row else BASELINE.get(service, {}).get(metric, 0.0)

    result["cpu"] = result.get("cpu_utilization", 0)
    result["memory"] = result.get("memory_utilization", 0)
    result["disk"] = result.get("disk_utilization", 40)
    result["network"] = result.get("network_utilization", 30)
    result["db_connections"] = result.get("db_connection_usage", 45)
    return result


def prune_old_telemetry(db: Session, keep_hours: int = 6) -> None:
    cutoff = utcnow() - timedelta(hours=keep_hours)
    db.query(MetricSample).filter(MetricSample.timestamp < cutoff).delete()
    db.query(LogEntry).filter(LogEntry.timestamp < cutoff).delete()
    db.commit()
