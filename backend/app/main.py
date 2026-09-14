from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.seed import seed_database
from app.rag import store as rag_store
from app.services.pipeline import pipeline_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.knowledge_uploads_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    # Index knowledge base (may download embedding model on first run)
    try:
        docs = rag_store.load_runbook_files()
        if docs:
            rag_store.index_documents(docs)
            db = SessionLocal()
            try:
                from app.core.utils import utcnow
                from app.models import KnowledgeDocument

                for doc in docs:
                    existing = (
                        db.query(KnowledgeDocument)
                        .filter(KnowledgeDocument.filename == doc["source"])
                        .first()
                    )
                    chunks = len(rag_store.chunk_text(doc["content"]))
                    if not existing:
                        db.add(
                            KnowledgeDocument(
                                title=doc["title"],
                                filename=doc["source"],
                                doc_type="runbook",
                                chunk_count=chunks,
                                content_hash=rag_store.content_hash(doc["content"]),
                                indexed_at=utcnow(),
                            )
                        )
                    else:
                        existing.chunk_count = chunks
                        existing.indexed_at = utcnow()
                db.commit()
            finally:
                db.close()
    except Exception as exc:
        print(f"[aiops] RAG index deferred: {exc}")

    await pipeline_worker.start()
    yield
    await pipeline_worker.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()
