from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="Operator")
    role: Mapped[str] = mapped_column(String(32), default="sre")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    tier: Mapped[str] = mapped_column(String(32), default="app")
    status: Mapped[str] = mapped_column(String(32), default="healthy")
    dependencies: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricSample(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    metric: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32), default="%")
    labels: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class LogEntry(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    message: Mapped[str] = mapped_column(Text)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    span_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    host: Mapped[str] = mapped_column(String(128), default="demo-node-1")
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    root_service: Mapped[str] = mapped_column(String(128))
    total_duration_ms: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    spans: Mapped[list[Span]] = relationship("Span", back_populates="trace", cascade="all, delete-orphan")


class Span(Base):
    __tablename__ = "spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_pk: Mapped[int] = mapped_column(ForeignKey("traces.id", ondelete="CASCADE"), index=True)
    span_id: Mapped[str] = mapped_column(String(32), index=True)
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    operation: Mapped[str] = mapped_column(String(256))
    duration_ms: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="ok")
    start_offset_ms: Mapped[float] = mapped_column(Float, default=0.0)
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    trace: Mapped[Trace] = relationship("Trace", back_populates="spans")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric: Mapped[str] = mapped_column(String(128), index=True)
    service: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[float] = mapped_column(Float)
    baseline: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    anomaly_score: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(64), default="zscore")
    expected: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id"), nullable=True, index=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    severity: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="Detected")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    affected_services: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    current_root_cause: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    correlated_signals: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    events: Mapped[list[IncidentEvent]] = relationship(
        "IncidentEvent", back_populates="incident", cascade="all, delete-orphan"
    )
    rca_results: Mapped[list[RcaResult]] = relationship(
        "RcaResult", back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_pk: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    incident: Mapped[Incident] = relationship("Incident", back_populates="events")


class RcaResult(Base):
    __tablename__ = "rca_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_pk: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    root_cause: Mapped[str] = mapped_column(String(256))
    confidence: Mapped[float] = mapped_column(Float)
    confidence_label: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(32))
    supporting_evidence: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    contradicting_evidence: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    recommendations: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    retrieved_knowledge: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    reasoning_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    incident: Mapped[Incident] = relationship("Incident", back_populates="rca_results")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_pk: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(128))
    value: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    anomaly_status: Mapped[bool] = mapped_column(Boolean, default=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(64), default="metric")
    service: Mapped[str] = mapped_column(String(128), default="")
    details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_pk: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    risk_warning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), index=True)
    filename: Mapped[str] = mapped_column(String(256))
    doc_type: Mapped[str] = mapped_column(String(64), default="runbook")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (UniqueConstraint("filename", name="uq_knowledge_filename"),)


class InvestigationRun(Base):
    __tablename__ = "investigation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_pk: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
