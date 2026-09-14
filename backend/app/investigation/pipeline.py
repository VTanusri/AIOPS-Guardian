from __future__ import annotations

import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.llm import get_llm_provider
from app.core.events import event_bus
from app.core.utils import utcnow
from app.models import (
    Anomaly,
    Evidence,
    Incident,
    IncidentEvent,
    InvestigationRun,
    LogEntry,
    RcaResult,
    Recommendation,
)
from app.rag import store as rag_store
from app.rca.engine import confidence_label, recommendations_for, score_candidates
from app.schemas import EvidenceOut, StructuredRCA


def _collect_evidence(db: Session, incident: Incident) -> list[Evidence]:
    anomalies = db.query(Anomaly).filter(Anomaly.incident_id == incident.id).all()
    # refresh evidence rows
    db.query(Evidence).filter(Evidence.incident_pk == incident.id).delete()
    rows: list[Evidence] = []
    for a in anomalies:
        row = Evidence(
            incident_pk=incident.id,
            metric=a.metric,
            value=a.value,
            expected_value=a.expected,
            anomaly_status=True,
            timestamp=a.timestamp,
            source="anomaly",
            service=a.service,
            details={"severity": a.severity, "score": a.anomaly_score, "method": a.method},
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


async def investigate_incident(
    db: Session, incident: Incident, question: Optional[str] = None
) -> dict[str, Any]:
    started = time.perf_counter()
    incident.status = "Investigating"
    db.add(
        IncidentEvent(
            incident_pk=incident.id,
            event_type="investigation_started",
            message="AI investigation started",
            payload={"question": question},
        )
    )
    db.commit()
    await event_bus.publish(
        "incidents",
        {"type": "incident_update", "incident_id": incident.incident_id, "status": "Investigating"},
    )

    evidence_rows = _collect_evidence(db, incident)
    anomalies = db.query(Anomaly).filter(Anomaly.incident_id == incident.id).all()
    anomaly_dicts = [
        {
            "metric": a.metric,
            "service": a.service,
            "value": a.value,
            "baseline": a.baseline,
            "severity": a.severity,
            "anomaly_score": a.anomaly_score,
        }
        for a in anomalies
    ]
    recent_logs = (
        db.query(LogEntry)
        .filter(LogEntry.service.in_(incident.affected_services or []))
        .order_by(LogEntry.timestamp.desc())
        .limit(30)
        .all()
    )
    log_dicts = [{"message": l.message, "severity": l.severity, "service": l.service} for l in recent_logs]

    summary = (
        f"Incident {incident.incident_id}: {incident.title}. "
        f"Severity {incident.severity}. Affected: {', '.join(incident.affected_services or [])}. "
        f"Signals: {', '.join(incident.correlated_signals or [])}."
    )
    if question:
        summary += f" Operator question: {question}"

    rag_hits = rag_store.semantic_search(summary, top_k=5)
    rag_titles = list({h["title"] for h in rag_hits})

    ranked = score_candidates(anomaly_dicts, log_dicts, rag_titles=rag_titles)
    best = ranked[0] if ranked else None
    if not best or best.score < 25 or not anomaly_dicts:
        structured = StructuredRCA(
            root_cause="Insufficient evidence for a high-confidence RCA",
            confidence=best.score if best else 0,
            confidence_label="LOW CONFIDENCE",
            severity=incident.severity,
            supporting_evidence=best.supporting if best else [],
            contradicting_evidence=best.contradicting if best else [],
            recommendations=["Collect additional metrics, logs, and traces before remediating."],
            retrieved_knowledge=rag_titles,
            reasoning_summary="Insufficient evidence for a high-confidence RCA.",
            score_breakdown=best.breakdown if best else {},
        )
    else:
        recs = recommendations_for(best.root_cause)
        structured = StructuredRCA(
            root_cause=best.root_cause,
            confidence=round(best.score, 1),
            confidence_label=confidence_label(best.score),
            severity=incident.severity,
            supporting_evidence=best.supporting[:8],
            contradicting_evidence=best.contradicting[:5],
            recommendations=recs,
            retrieved_knowledge=rag_titles,
            reasoning_summary="",
            score_breakdown=best.breakdown,
        )

    llm = await get_llm_provider()
    prompt = f"""You are an AIOps RCA assistant. Use ONLY the evidence below. Do not invent metrics or logs.
Return JSON with keys: root_cause, confidence, severity, supporting_evidence, contradicting_evidence, recommendations, retrieved_knowledge, reasoning_summary.
Confidence MUST remain {structured.confidence}. Do not claim any remediation was executed.

Incident summary:
{summary}

Telemetry evidence:
{anomaly_dicts}

Logs:
{log_dicts[:10]}

Retrieved knowledge titles:
{rag_titles}

Candidate root cause from scoring engine:
{structured.root_cause}
Score breakdown:
{structured.score_breakdown}
"""
    structured = await llm.generate_rca(prompt, structured)

    rca = RcaResult(
        incident_pk=incident.id,
        root_cause=structured.root_cause,
        confidence=structured.confidence,
        confidence_label=structured.confidence_label,
        severity=structured.severity,
        supporting_evidence=structured.supporting_evidence,
        contradicting_evidence=structured.contradicting_evidence,
        recommendations=structured.recommendations,
        retrieved_knowledge=structured.retrieved_knowledge,
        score_breakdown=structured.score_breakdown,
        reasoning_summary=structured.reasoning_summary,
    )
    db.add(rca)
    db.query(Recommendation).filter(Recommendation.incident_pk == incident.id).delete()
    for action in structured.recommendations:
        db.add(
            Recommendation(
                incident_pk=incident.id,
                action=action,
                priority="high",
                risk_warning="Do not execute destructive remediation automatically.",
            )
        )

    incident.status = "RCA Available"
    incident.current_root_cause = structured.root_cause
    incident.confidence = structured.confidence
    incident.summary = structured.reasoning_summary
    latency_ms = (time.perf_counter() - started) * 1000
    db.add(
        IncidentEvent(
            incident_pk=incident.id,
            event_type="rca_available",
            message=f"RCA: {structured.root_cause} ({structured.confidence:.0f}% {structured.confidence_label})",
            payload={"confidence": structured.confidence},
        )
    )
    run = InvestigationRun(
        incident_pk=incident.id,
        question=question,
        status="completed",
        latency_ms=latency_ms,
        result=structured.model_dump(),
    )
    db.add(run)
    db.commit()
    db.refresh(rca)

    await event_bus.publish(
        "incidents",
        {
            "type": "rca_available",
            "incident_id": incident.incident_id,
            "root_cause": structured.root_cause,
            "confidence": structured.confidence,
        },
    )

    return {
        "incident_id": incident.incident_id,
        "rca": structured,
        "evidence_used": [EvidenceOut.model_validate(e) for e in evidence_rows],
        "retrieved_knowledge": rag_hits,
        "latency_ms": latency_ms,
        "llm_provider": llm.name,
    }
