from pathlib import Path

from app.rag.store import chunk_text, index_documents, semantic_search


def test_chunk_and_search(tmp_path, monkeypatch):
    runbooks = Path(__file__).resolve().parents[2] / "knowledge_base" / "runbooks"
    docs = []
    for fp in sorted(runbooks.glob("*.md"))[:2]:
        docs.append({"id": fp.stem, "title": fp.stem, "content": fp.read_text(encoding="utf-8"), "source": fp.name})
    assert chunk_text(docs[0]["content"])
    count = index_documents(docs)
    assert count > 0
    hits = semantic_search("database connection pool exhaustion", top_k=3)
    assert hits
    assert any("database" in h["title"].lower() or "connection" in h["content"].lower() for h in hits)
