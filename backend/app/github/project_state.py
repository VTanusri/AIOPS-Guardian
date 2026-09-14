from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.utils import utcnow
from app.models import KnowledgeDocument, Service
from app.rag import store as rag_store
from app.telemetry import generator as telem


class ActiveProjectStore:
    """In-memory active GitHub project (A+B combined mode)."""

    def __init__(self) -> None:
        self.project: Optional[dict[str, Any]] = None

    def clear(self) -> None:
        self.project = None

    def set(self, project: dict[str, Any]) -> None:
        # keep docs out of the lightweight status payload
        slim = {k: v for k, v in project.items() if k != "docs"}
        self.project = slim

    def get(self) -> Optional[dict[str, Any]]:
        return self.project

    def status(self) -> dict[str, Any]:
        if not self.project:
            return {
                "active": False,
                "message": "No GitHub project imported. Paste a repo URL to scope metrics & RCA.",
                "mode": None,
            }
        p = self.project
        return {
            "active": True,
            "full_name": p.get("full_name"),
            "html_url": p.get("html_url"),
            "description": p.get("description"),
            "language": p.get("language"),
            "stars": p.get("stars"),
            "service_count": len(p.get("services") or []),
            "docs_indexed": p.get("docs_indexed"),
            "signals": p.get("signals"),
            "mode": p.get("mode"),
            "imported_at": p.get("imported_at"),
        }


active_project = ActiveProjectStore()


def apply_project_to_runtime(db: Session, project: dict[str, Any]) -> dict[str, Any]:
    """Replace service catalog + telemetry baselines + RAG with repo-derived data."""
    services = project.get("services") or []
    baseline: dict[str, dict[str, float]] = {}
    for s in services:
        baseline[s["name"]] = dict(s.get("metrics") or {})

    telem.set_baseline(baseline)

    # Replace services table entries for this project scope
    db.query(Service).delete()
    for s in services:
        db.add(
            Service(
                name=s["name"],
                display_name=s["display_name"],
                tier=s.get("tier") or "app",
                status="healthy",
                dependencies=s.get("dependencies") or [],
            )
        )
    db.commit()

    # Index repo docs into RAG (merge with existing runbooks)
    docs = list(project.get("docs") or [])
    runbooks = rag_store.load_runbook_files()
    # Prefer runbooks + repo docs together
    combined = runbooks + docs
    if combined:
        rag_store.index_documents(combined)

    for doc in docs:
        existing = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.filename == doc["source"])
            .first()
        )
        chunks = len(rag_store.chunk_text(doc["content"]))
        if existing:
            existing.title = doc["title"]
            existing.chunk_count = chunks
            existing.content_hash = rag_store.content_hash(doc["content"])
            existing.indexed_at = utcnow()
            existing.doc_type = "github"
        else:
            db.add(
                KnowledgeDocument(
                    title=doc["title"],
                    filename=doc["source"],
                    doc_type="github",
                    chunk_count=chunks,
                    content_hash=rag_store.content_hash(doc["content"]),
                    indexed_at=utcnow(),
                    metadata_json={"repo": project.get("full_name")},
                )
            )
    db.commit()

    project["imported_at"] = utcnow().isoformat()
    active_project.set(project)
    return active_project.status()
