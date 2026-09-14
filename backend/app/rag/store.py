from __future__ import annotations

"""RAG store with optional SentenceTransformer/Chroma; pure-Python fallbacks for restricted hosts."""

import hashlib
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.utils import utcnow

_collection = None
_embedder = None
_embedder_mode = "none"
_last_index_time: datetime | None = None
_status = "not_initialized"
_memory_index: list[dict[str, Any]] = []


def _hash_embed(texts: list[str], dim: int = 384) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a)) or 1.0


def _get_embedder():
    global _embedder, _embedder_mode
    if _embedder_mode != "none":
        return _embedder, _embedder_mode
    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(settings.embedding_model)
        _embedder_mode = "sentence-transformers"
        return _embedder, _embedder_mode
    except Exception as exc:
        print(f"[aiops] sentence-transformers unavailable ({exc}); using hashing embeddings")
        _embedder = None
        _embedder_mode = "hashing"
        return None, _embedder_mode


def _encode(texts: list[str]) -> list[list[float]]:
    model, mode = _get_embedder()
    if mode == "sentence-transformers" and model is not None:
        return model.encode(texts, show_progress_bar=False).tolist()
    return _hash_embed(texts)


def _get_collection():
    global _collection, _status
    if _collection is not None or _status == "memory_fallback":
        return _collection
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        settings = get_settings()
        Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name="aiops_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        _status = "ready"
        return _collection
    except Exception as exc:
        print(f"[aiops] ChromaDB unavailable ({exc}); using in-memory RAG index")
        _status = "memory_fallback"
        return None


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def index_documents(docs: list[dict[str, str]]) -> int:
    global _last_index_time, _status, _memory_index
    collection = _get_collection()
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for doc in docs:
        pieces = chunk_text(doc["content"])
        for i, piece in enumerate(pieces):
            ids.append(f"{doc['id']}_{i}")
            documents.append(piece)
            metadatas.append(
                {
                    "title": doc["title"],
                    "source": doc.get("source", doc["title"]),
                    "doc_id": str(doc["id"]),
                    "chunk_index": i,
                }
            )

    if not ids:
        _status = "empty"
        return 0

    embeddings = _encode(documents)
    # Always keep memory index so search works even if Chroma native libs are blocked later
    _memory_index = [
        {"id": i, "document": d, "metadata": m, "embedding": e}
        for i, d, m, e in zip(ids, documents, metadatas, embeddings)
    ]

    if collection is None:
        _last_index_time = utcnow()
        _status = "memory_fallback"
        return len(ids)

    try:
        batch = 64
        for i in range(0, len(ids), batch):
            collection.upsert(
                ids=ids[i : i + batch],
                documents=documents[i : i + batch],
                embeddings=embeddings[i : i + batch],
                metadatas=metadatas[i : i + batch],
            )
        _last_index_time = utcnow()
        _status = "ready"
    except Exception as exc:
        print(f"[aiops] Chroma upsert failed ({exc}); using memory index")
        _status = "memory_fallback"
        _last_index_time = utcnow()
    return len(ids)


def delete_document_chunks(doc_id: str) -> None:
    global _memory_index
    _memory_index = [x for x in _memory_index if x["metadata"].get("doc_id") != str(doc_id)]
    collection = _get_collection()
    if collection is None:
        return
    try:
        existing = collection.get(where={"doc_id": str(doc_id)})
        if existing and existing.get("ids"):
            collection.delete(ids=existing["ids"])
    except Exception:
        pass


def semantic_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    q = _encode([query])[0]
    collection = _get_collection()

    # Prefer memory index when populated (most reliable under WDAC)
    if _memory_index:
        scored = []
        for item in _memory_index:
            emb = item["embedding"]
            score = _dot(q, emb) / (_norm(q) * _norm(emb))
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "title": item["metadata"].get("title", "unknown"),
                "content": item["document"],
                "score": round(score, 4),
                "source": item["metadata"].get("source", ""),
            }
            for score, item in scored[:top_k]
        ]

    if collection is None or collection.count() == 0:
        return []
    try:
        result = collection.query(query_embeddings=[q], n_results=min(top_k, max(1, collection.count())))
    except Exception:
        return []
    hits: list[dict[str, Any]] = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        score = 1.0 - float(dist) if dist is not None else 0.0
        hits.append(
            {
                "title": meta.get("title", "unknown"),
                "content": doc,
                "score": round(score, 4),
                "source": meta.get("source", ""),
            }
        )
    return hits


def get_rag_status() -> dict[str, Any]:
    settings = get_settings()
    _, mode = _get_embedder()
    count = len(_memory_index)
    if count == 0:
        try:
            collection = _get_collection()
            if collection is not None:
                count = collection.count()
        except Exception:
            pass
    return {
        "total_chunks": count,
        "embedding_model": f"{settings.embedding_model} ({mode})",
        "vector_db_status": _status,
        "last_indexing_time": _last_index_time,
    }


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_runbook_files() -> list[dict[str, str]]:
    settings = get_settings()
    path = Path(settings.knowledge_runbooks_dir)
    path.mkdir(parents=True, exist_ok=True)
    docs: list[dict[str, str]] = []
    for fp in sorted(path.glob("*.md")):
        text = fp.read_text(encoding="utf-8")
        title = fp.stem.replace("_", " ").title()
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        docs.append({"id": fp.stem, "title": title, "content": text, "source": fp.name})
    uploads = Path(settings.knowledge_uploads_dir)
    if uploads.exists():
        for fp in sorted(list(uploads.glob("*.md")) + list(uploads.glob("*.txt"))):
            text = fp.read_text(encoding="utf-8")
            docs.append({"id": f"upload_{fp.stem}", "title": fp.stem, "content": text, "source": fp.name})
    return docs
