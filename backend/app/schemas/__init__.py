from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    llm_provider: str
    database: str


class ServiceOut(ORMModel):
    id: int
    name: str
    display_name: str
    tier: str
    status: str
    dependencies: list[str] = Field(default_factory=list)


class MetricOut(ORMModel):
    id: int
    service: str
    metric: str
    value: float
    unit: str
    timestamp: datetime
    labels: dict[str, Any] = Field(default_factory=dict)


class LogOut(ORMModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    timestamp: datetime
    severity: str
    service: str
    message: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    host: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")


class SpanOut(ORMModel):
    span_id: str
    parent_span_id: Optional[str] = None
    service: str
    operation: str
    duration_ms: float
    status: str
    start_offset_ms: float
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceOut(ORMModel):
    id: int
    trace_id: str
    root_service: str
    total_duration_ms: float
    status: str
    started_at: datetime
    spans: list[SpanOut] = Field(default_factory=list)


class AnomalyOut(ORMModel):
    id: int
    metric: str
    service: str
    value: float
    baseline: float
    severity: str
    anomaly_score: float
    method: str
    expected: Optional[str] = None
    timestamp: datetime
    incident_id: Optional[int] = None
    details: dict[str, Any] = Field(default_factory=dict)


class IncidentEventOut(ORMModel):
    id: int
    event_type: str
    message: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceOut(ORMModel):
    id: int
    metric: str
    value: float
    expected_value: Optional[str] = None
    anomaly_status: bool
    timestamp: datetime
    source: str
    service: str
    details: dict[str, Any] = Field(default_factory=dict)


class RcaOut(ORMModel):
    id: int
    root_cause: str
    confidence: float
    confidence_label: str
    severity: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    retrieved_knowledge: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    reasoning_summary: Optional[str] = None
    created_at: datetime


class IncidentOut(ORMModel):
    id: int
    incident_id: str
    title: str
    severity: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    affected_services: list[str] = Field(default_factory=list)
    current_root_cause: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    scenario_key: Optional[str] = None
    correlated_signals: list[str] = Field(default_factory=list)
    anomaly_count: int = 0
    evidence_count: int = 0


class IncidentDetailOut(IncidentOut):
    events: list[IncidentEventOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    rca: Optional[RcaOut] = None
    recommendations: list[str] = Field(default_factory=list)


class StructuredRCA(BaseModel):
    root_cause: str
    confidence: float = Field(ge=0, le=100)
    severity: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    retrieved_knowledge: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    confidence_label: str = "LOW CONFIDENCE"
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class InvestigateRequest(BaseModel):
    question: Optional[str] = None


class InvestigateResponse(BaseModel):
    incident_id: str
    rca: StructuredRCA
    evidence_used: list[EvidenceOut]
    retrieved_knowledge: list[dict[str, Any]]
    latency_ms: float
    llm_provider: str


class KnowledgeDocOut(ORMModel):
    id: int
    title: str
    filename: str
    doc_type: str
    chunk_count: int
    indexed_at: Optional[datetime] = None
    created_at: datetime


class KnowledgeStatusOut(BaseModel):
    total_documents: int
    total_chunks: int
    embedding_model: str
    vector_db_status: str
    last_indexing_time: Optional[datetime] = None


class RagSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class RagSearchHit(BaseModel):
    title: str
    content: str
    score: float
    source: str


class SimulationStartRequest(BaseModel):
    scenario: str


class SimulationStatus(BaseModel):
    running: bool
    scenario: Optional[str] = None
    step: int = 0
    total_steps: int = 0
    message: str = "idle"


class DashboardSummary(BaseModel):
    system_status: str
    service_count: int
    active_incidents: int
    active_anomalies: int
    overall_risk_score: float
    metrics: dict[str, float]
    active_incident_list: list[IncidentOut]
    recent_alerts: list[dict[str, Any]]
    ai_summary: str
    health_timeline: list[dict[str, Any]]
    anomaly_timeline: list[dict[str, Any]]
    service_health: list[dict[str, Any]]
    active_project: Optional[dict[str, Any]] = None
    github_signals: Optional[dict[str, Any]] = None


class GitHubImportRequest(BaseModel):
    url: str
    token: Optional[str] = None


class EvaluationMetrics(BaseModel):
    rca_accuracy: float
    incident_detection: float
    rag_top1_accuracy: float
    false_positive_rate: float
    average_rca_time_s: float
    false_negatives: float
    correlation_accuracy: float
    sample_size: int
    measured_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class AskRequest(BaseModel):
    incident_id: str
    question: str
