from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy.orm import Session

from app.anomaly.detector import detect_anomalies_for_sample
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.events import event_bus
from app.core.utils import utcnow
from app.correlation.engine import correlate_anomalies
from app.models import Anomaly, MetricSample, Service
from app.telemetry import generator as telem


class PipelineWorker:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        settings = get_settings()
        tick = 0
        while self._running:
            db = SessionLocal()
            try:
                samples = telem.generate_metric_tick(db)
                await telem.publish_metrics(samples)
                logs = telem.generate_logs(db, count=2)
                await telem.publish_logs(logs)
                if tick % 3 == 0:
                    telem.generate_trace(db)
                self._detect(db, samples)
                created = correlate_anomalies(db, window_seconds=settings.correlation_window_seconds)
                for inc in created:
                    await event_bus.publish(
                        "incidents",
                        {
                            "type": "incident_created",
                            "incident_id": inc.incident_id,
                            "title": inc.title,
                            "severity": inc.severity,
                        },
                    )
                self._update_service_status(db)
                if tick % 40 == 0:
                    telem.prune_old_telemetry(db)
            except Exception as exc:  # keep loop alive
                await event_bus.publish("system", {"type": "worker_error", "message": str(exc)})
            finally:
                db.close()
            tick += 1
            await asyncio.sleep(settings.telemetry_interval_seconds)

    def _detect(self, db: Session, samples: list[MetricSample]) -> None:
        settings = get_settings()
        for sample in samples:
            history_rows = (
                db.query(MetricSample)
                .filter(
                    MetricSample.service == sample.service,
                    MetricSample.metric == sample.metric,
                    MetricSample.id != sample.id,
                )
                .order_by(MetricSample.timestamp.desc())
                .limit(settings.anomaly_window_size)
                .all()
            )
            history = [r.value for r in reversed(history_rows)]
            signals = detect_anomalies_for_sample(sample.metric, sample.service, sample.value, history)
            for sig in signals:
                # de-dupe similar anomaly in last 30s
                recent = (
                    db.query(Anomaly)
                    .filter(
                        Anomaly.service == sig.service,
                        Anomaly.metric == sig.metric,
                        Anomaly.timestamp >= utcnow() - timedelta(seconds=30),
                    )
                    .first()
                )
                if recent:
                    continue
                row = Anomaly(
                    metric=sig.metric,
                    service=sig.service,
                    value=sig.value,
                    baseline=sig.baseline,
                    severity=sig.severity,
                    anomaly_score=sig.anomaly_score,
                    method=sig.method,
                    expected=sig.expected,
                    timestamp=sample.timestamp,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                asyncio.create_task(
                    event_bus.publish(
                        "anomalies",
                        {
                            "type": "anomaly",
                            "id": row.id,
                            "metric": row.metric,
                            "service": row.service,
                            "value": row.value,
                            "severity": row.severity,
                            "anomaly_score": row.anomaly_score,
                        },
                    )
                )

    def _update_service_status(self, db: Session) -> None:
        services = db.query(Service).all()
        cutoff = utcnow() - timedelta(minutes=2)
        for svc in services:
            critical = (
                db.query(Anomaly)
                .filter(
                    Anomaly.service == svc.name,
                    Anomaly.timestamp >= cutoff,
                    Anomaly.severity.in_(["critical", "high"]),
                )
                .count()
            )
            medium = (
                db.query(Anomaly)
                .filter(Anomaly.service == svc.name, Anomaly.timestamp >= cutoff)
                .count()
            )
            if critical:
                svc.status = "critical"
            elif medium:
                svc.status = "degraded"
            else:
                svc.status = "healthy"
        db.commit()


pipeline_worker = PipelineWorker()
