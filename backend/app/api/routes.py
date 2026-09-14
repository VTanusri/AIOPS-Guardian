from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.llm import get_llm_provider
from app.core.config import get_settings
from app.core.database import get_db
from app.core.events import event_bus
from app.core.utils import utcnow
from app.investigation.pipeline import investigate_incident
from app.models import (
    Anomaly,
    Evidence,
    Incident,
    IncidentEvent,
    KnowledgeDocument,
    LogEntry,
    MetricSample,
    RcaResult,
    Recommendation,
    Service,
    Span,
    Trace,
)
from app.rag import store as rag_store
from app.schemas import (
    AnomalyOut,
    AskRequest,
    DashboardSummary,
    EvaluationMetrics,
    HealthResponse,
    IncidentDetailOut,
    IncidentOut,
    InvestigateRequest,
    InvestigateResponse,
    KnowledgeDocOut,
    KnowledgeStatusOut,
    LogOut,
    MetricOut,
    RagSearchHit,
    RagSearchRequest,
    RcaOut,
    ServiceOut,
    SimulationStartRequest,
    SimulationStatus,
    TraceOut,
)
from app.simulation.manager import list_scenarios, simulation_manager
from app.telemetry.generator import latest_metric_map
from app import __version__
from app.services.evaluation import run_evaluation
from app.github.importer import fetch_repo_bundle
from app.github.project_state import active_project, apply_project_to_runtime
from app.telemetry import generator as telem
from app.core.seed import seed_database
from app.schemas import GitHubImportRequest

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    llm = await get_llm_provider()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=__version__,
        llm_provider=llm.name,
        database="sqlite" if settings.resolved_database_url.startswith("sqlite") else "postgres",
    )


@router.post("/github/import")
async def github_import(body: GitHubImportRequest, db: Session = Depends(get_db)):
    try:
        bundle = await fetch_repo_bundle(body.url, token=body.token)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"GitHub fetch failed: {exc}") from exc
    status = apply_project_to_runtime(db, bundle)
    await event_bus.publish(
        "system",
        {"type": "github_imported", "full_name": status.get("full_name"), "services": status.get("service_count")},
    )
    return {
        "status": status,
        "services": bundle.get("services"),
        "signals": bundle.get("signals"),
        "docs_indexed": bundle.get("docs_indexed"),
        "message": (
            "Project imported. Metrics/simulation now follow inferred services (mode A). "
            "GitHub Actions/commits/issues attached as real signals (mode B)."
        ),
    }


@router.get("/github/project")
def github_project():
    return active_project.status()


@router.post("/github/refresh-signals")
async def github_refresh_signals(db: Session = Depends(get_db)):
    current = active_project.get()
    if not current:
        raise HTTPException(400, "No active GitHub project")
    url = current.get("html_url")
    try:
        bundle = await fetch_repo_bundle(url)
    except Exception as exc:
        raise HTTPException(502, f"GitHub refresh failed: {exc}") from exc
    # Keep existing service topology; refresh signals + docs
    current_services = current.get("services")
    bundle["services"] = current_services or bundle.get("services")
    status = apply_project_to_runtime(db, bundle)
    return {"status": status, "signals": bundle.get("signals")}


@router.post("/github/clear")
def github_clear(db: Session = Depends(get_db)):
    active_project.clear()
    telem.reset_baseline()
    # restore default seed services
    db.query(Service).delete()
    db.commit()
    seed_database(db)
    return {"cleared": True, "status": active_project.status()}


@router.get("/services", response_model=list[ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).order_by(Service.name).all()


@router.get("/metrics", response_model=list[MetricOut])
def get_metrics(
    service: Optional[str] = None,
    metric: Optional[str] = None,
    minutes: int = Query(30, ge=1, le=1440),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    q = db.query(MetricSample).filter(MetricSample.timestamp >= utcnow() - timedelta(minutes=minutes))
    if service:
        q = q.filter(MetricSample.service == service)
    if metric:
        q = q.filter(MetricSample.metric == metric)
    return q.order_by(MetricSample.timestamp.desc()).limit(limit).all()


@router.get("/logs", response_model=list[LogOut])
def get_logs(
    service: Optional[str] = None,
    severity: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(LogEntry)
    if service:
        query = query.filter(LogEntry.service == service)
    if severity:
        query = query.filter(LogEntry.severity == severity.upper())
    if q:
        query = query.filter(LogEntry.message.ilike(f"%{q}%"))
    rows = query.order_by(LogEntry.timestamp.desc()).offset(offset).limit(limit).all()
    return rows


@router.get("/traces", response_model=list[TraceOut])
def get_traces(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    traces = db.query(Trace).order_by(Trace.started_at.desc()).limit(limit).all()
    # ensure spans loaded
    for t in traces:
        _ = t.spans
    return traces


@router.get("/traces/{trace_id}", response_model=TraceOut)
def get_trace(trace_id: str, db: Session = Depends(get_db)):
    trace = db.query(Trace).filter(Trace.trace_id == trace_id).first()
    if not trace:
        raise HTTPException(404, "Trace not found")
    _ = trace.spans
    return trace


@router.get("/anomalies", response_model=list[AnomalyOut])
def get_anomalies(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(Anomaly).order_by(Anomaly.timestamp.desc()).limit(limit).all()


def _incident_out(db: Session, inc: Incident) -> IncidentOut:
    anomaly_count = db.query(Anomaly).filter(Anomaly.incident_id == inc.id).count()
    evidence_count = db.query(Evidence).filter(Evidence.incident_pk == inc.id).count()
    data = IncidentOut.model_validate(inc)
    data.anomaly_count = anomaly_count
    data.evidence_count = evidence_count
    return data


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    incidents = db.query(Incident).order_by(Incident.started_at.desc()).all()
    return [_incident_out(db, i) for i in incidents]


@router.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not inc:
        # also allow numeric pk
        if incident_id.isdigit():
            inc = db.query(Incident).filter(Incident.id == int(incident_id)).first()
    if not inc:
        raise HTTPException(404, "Incident not found")
    base = _incident_out(db, inc)
    events = (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_pk == inc.id)
        .order_by(IncidentEvent.timestamp.asc())
        .all()
    )
    evidence = db.query(Evidence).filter(Evidence.incident_pk == inc.id).all()
    rca_row = (
        db.query(RcaResult).filter(RcaResult.incident_pk == inc.id).order_by(RcaResult.created_at.desc()).first()
    )
    recs = [r.action for r in db.query(Recommendation).filter(Recommendation.incident_pk == inc.id).all()]
    detail = IncidentDetailOut(
        **base.model_dump(),
        events=events,
        evidence=evidence,
        rca=RcaOut.model_validate(rca_row) if rca_row else None,
        recommendations=recs or (rca_row.recommendations if rca_row else []),
    )
    return detail


@router.post("/incidents/{incident_id}/investigate", response_model=InvestigateResponse)
async def investigate(incident_id: str, body: InvestigateRequest | None = None, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not inc:
        raise HTTPException(404, "Incident not found")
    question = body.question if body else None
    result = await investigate_incident(db, inc, question=question)
    return InvestigateResponse(**result)


@router.get("/incidents/{incident_id}/rca", response_model=RcaOut)
def get_rca(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not inc:
        raise HTTPException(404, "Incident not found")
    rca = db.query(RcaResult).filter(RcaResult.incident_pk == inc.id).order_by(RcaResult.created_at.desc()).first()
    if not rca:
        raise HTTPException(404, "RCA not available")
    return rca


@router.post("/rag/search", response_model=list[RagSearchHit])
def rag_search(body: RagSearchRequest):
    hits = rag_store.semantic_search(body.query, top_k=body.top_k)
    return [RagSearchHit(**h) for h in hits]


@router.get("/knowledge", response_model=list[KnowledgeDocOut])
def list_knowledge(db: Session = Depends(get_db)):
    return db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).all()


@router.get("/knowledge/status", response_model=KnowledgeStatusOut)
def knowledge_status(db: Session = Depends(get_db)):
    docs = db.query(KnowledgeDocument).all()
    rag = rag_store.get_rag_status()
    last = max((d.indexed_at for d in docs if d.indexed_at), default=rag.get("last_indexing_time"))
    return KnowledgeStatusOut(
        total_documents=len(docs),
        total_chunks=rag["total_chunks"],
        embedding_model=rag["embedding_model"],
        vector_db_status=rag["vector_db_status"],
        last_indexing_time=last,
    )


@router.post("/knowledge/reindex")
def reindex_knowledge(db: Session = Depends(get_db)):
    docs = rag_store.load_runbook_files()
    # sync DB records
    for doc in docs:
        existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.filename == doc["source"]).first()
        ch = rag_store.content_hash(doc["content"])
        chunks = len(rag_store.chunk_text(doc["content"]))
        if existing:
            existing.title = doc["title"]
            existing.content_hash = ch
            existing.chunk_count = chunks
            existing.indexed_at = utcnow()
        else:
            db.add(
                KnowledgeDocument(
                    title=doc["title"],
                    filename=doc["source"],
                    doc_type="runbook",
                    chunk_count=chunks,
                    content_hash=ch,
                    indexed_at=utcnow(),
                )
            )
    db.commit()
    count = rag_store.index_documents(docs)
    return {"indexed_chunks": count, "documents": len(docs)}


@router.post("/knowledge/upload", response_model=KnowledgeDocOut)
async def upload_knowledge(file: UploadFile = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    name = file.filename or "upload.txt"
    if not name.lower().endswith((".md", ".txt")):
        raise HTTPException(400, "Only .md and .txt files are allowed")
    raw = await file.read()
    if len(raw) > 1_000_000:
        raise HTTPException(400, "File too large (max 1MB)")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "File must be UTF-8 text") from exc
    # basic safety: reject executable-looking content
    if "\x00" in text:
        raise HTTPException(400, "Binary content not allowed")

    upload_dir = Path(settings.knowledge_uploads_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(name).name
    dest = upload_dir / safe_name
    dest.write_text(text, encoding="utf-8")

    title = safe_name
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    chunks = len(rag_store.chunk_text(text))
    existing = db.query(KnowledgeDocument).filter(KnowledgeDocument.filename == safe_name).first()
    if existing:
        existing.title = title
        existing.chunk_count = chunks
        existing.content_hash = rag_store.content_hash(text)
        existing.indexed_at = utcnow()
        doc = existing
    else:
        doc = KnowledgeDocument(
            title=title,
            filename=safe_name,
            doc_type="upload",
            chunk_count=chunks,
            content_hash=rag_store.content_hash(text),
            indexed_at=utcnow(),
        )
        db.add(doc)
    db.commit()
    db.refresh(doc)
    rag_store.index_documents(rag_store.load_runbook_files())
    return doc


@router.delete("/knowledge/{doc_id}")
def delete_knowledge(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    settings = get_settings()
    for folder in (settings.knowledge_runbooks_dir, settings.knowledge_uploads_dir):
        fp = Path(folder) / doc.filename
        if fp.exists() and Path(settings.knowledge_uploads_dir) in fp.resolve().parents:
            fp.unlink(missing_ok=True)
    rag_store.delete_document_chunks(str(doc.id))
    db.delete(doc)
    db.commit()
    rag_store.index_documents(rag_store.load_runbook_files())
    return {"deleted": doc_id}


@router.get("/simulation/scenarios")
def simulation_scenarios():
    return list_scenarios()


@router.get("/simulation/status", response_model=SimulationStatus)
def simulation_status():
    return SimulationStatus(**simulation_manager.status())


@router.post("/simulation/start", response_model=SimulationStatus)
async def simulation_start(body: SimulationStartRequest):
    try:
        status = await simulation_manager.start(body.scenario)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return SimulationStatus(**status)


@router.post("/simulation/stop", response_model=SimulationStatus)
async def simulation_stop():
    return SimulationStatus(**(await simulation_manager.stop()))


@router.post("/simulation/reset", response_model=SimulationStatus)
async def simulation_reset():
    return SimulationStatus(**(await simulation_manager.reset()))


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    services = db.query(Service).all()
    active_incidents = (
        db.query(Incident).filter(Incident.status.in_(["Detected", "Investigating", "RCA Available"])).all()
    )
    recent_anomalies = (
        db.query(Anomaly).filter(Anomaly.timestamp >= utcnow() - timedelta(minutes=15)).all()
    )
    metrics = latest_metric_map(db)

    # derived health
    critical_inc = sum(1 for i in active_incidents if i.severity == "CRITICAL")
    high_inc = sum(1 for i in active_incidents if i.severity in {"HIGH", "CRITICAL"})
    err = metrics.get("error_rate", 0)
    latency = metrics.get("api_latency", 0)
    if critical_inc or err >= 15 or any(s.status == "critical" for s in services):
        system_status = "CRITICAL"
        risk = 85 + min(15, critical_inc * 5)
    elif high_inc or err >= 5 or latency >= 300:
        system_status = "WARNING"
        risk = 55 + min(25, high_inc * 8)
    elif active_incidents or recent_anomalies:
        system_status = "DEGRADED"
        risk = 30 + min(20, len(active_incidents) * 5)
    else:
        system_status = "HEALTHY"
        risk = max(5, err * 2)

    ai_summary = "System operating within normal baselines."
    proj = active_project.get()
    if proj:
        ai_summary = (
            f"Scoped to GitHub project {proj.get('full_name')}. "
            f"Topology has {len(proj.get('services') or [])} inferred services. "
        )
        sig = proj.get("signals") or {}
        if sig.get("failed_workflow_count"):
            ai_summary += f"Real signal: {sig['failed_workflow_count']} recent failed GitHub Actions run(s). "
            risk = max(risk, 45)
            if system_status == "HEALTHY":
                system_status = "DEGRADED"
        elif sig.get("open_bug_count"):
            ai_summary += f"{sig['open_bug_count']} open bug issue(s) on GitHub. "
    if active_incidents:
        top = sorted(active_incidents, key=lambda i: {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}.get(i.severity, 0), reverse=True)[0]
        ai_summary += (
            f"Priority incident {top.incident_id}: {top.title}. "
            f"Status {top.status}. "
            + (f"Probable cause: {top.current_root_cause} ({top.confidence:.0f}%)." if top.current_root_cause else "Investigation pending.")
        )

    health_timeline = []
    for i in range(12):
        health_timeline.append(
            {
                "t": (utcnow() - timedelta(minutes=5 * (11 - i))).isoformat(),
                "status": system_status if i > 8 else "HEALTHY",
                "risk": risk if i > 8 else 10,
            }
        )

    anomaly_timeline = [
        {"t": a.timestamp.isoformat(), "metric": a.metric, "severity": a.severity, "service": a.service}
        for a in recent_anomalies[:40]
    ]

    return DashboardSummary(
        system_status=system_status,
        service_count=len(services),
        active_incidents=len(active_incidents),
        active_anomalies=len(recent_anomalies),
        overall_risk_score=round(float(risk), 1),
        metrics={
            "cpu": metrics.get("cpu", 0),
            "memory": metrics.get("memory", 0),
            "request_rate": metrics.get("request_rate", 0),
            "error_rate": metrics.get("error_rate", 0),
            "api_latency": metrics.get("api_latency", 0),
            "db_connections": metrics.get("db_connections", 0),
            "disk": metrics.get("disk", 0),
            "network": metrics.get("network", 0),
        },
        active_incident_list=[_incident_out(db, i) for i in active_incidents[:10]],
        recent_alerts=[
            {
                "id": a.id,
                "message": f"{a.metric}={a.value} on {a.service}",
                "severity": a.severity,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in recent_anomalies[:10]
        ],
        ai_summary=ai_summary,
        health_timeline=health_timeline,
        anomaly_timeline=anomaly_timeline,
        service_health=[{"name": s.name, "display_name": s.display_name, "status": s.status} for s in services],
        active_project=active_project.status() if active_project.get() else active_project.status(),
        github_signals=(active_project.get() or {}).get("signals"),
    )


@router.post("/investigation/ask")
async def ask_investigation(body: AskRequest, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.incident_id == body.incident_id).first()
    if not inc:
        raise HTTPException(404, "Incident not found")
    result = await investigate_incident(db, inc, question=body.question)
    rca = result["rca"]
    answer = (
        f"{rca.reasoning_summary}\n\nRoot cause: {rca.root_cause} "
        f"({rca.confidence:.0f}% — {rca.confidence_label})."
    )
    return {
        "answer": answer,
        "evidence_used": result["evidence_used"],
        "retrieved_knowledge": result["retrieved_knowledge"],
        "confidence": rca.confidence,
        "affected_services": inc.affected_services,
        "rca": rca,
        "llm_provider": result["llm_provider"],
    }


@router.get("/evaluation", response_model=EvaluationMetrics)
def evaluation(db: Session = Depends(get_db)):
    return run_evaluation(db)


async def _sse(channel: str):
    queue = event_bus.subscribe(channel)

    async def gen():
        try:
            yield f"data: {json.dumps({'type': 'subscribed', 'channel': channel})}\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {json.dumps(item, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            event_bus.unsubscribe(channel, queue)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/stream/{channel}")
async def stream(channel: str):
    if channel not in {"metrics", "logs", "anomalies", "incidents", "simulation", "system"}:
        raise HTTPException(400, "Invalid channel")
    return await _sse(channel)


@router.websocket("/ws/{channel}")
async def ws_channel(websocket: WebSocket, channel: str):
    if channel not in {"metrics", "logs", "anomalies", "incidents", "simulation", "system"}:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = event_bus.subscribe(channel)
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=20)
                await websocket.send_json(item)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(channel, queue)
