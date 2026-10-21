"""Hybrid search: pgvector semantic + PostgreSQL full-text (tsvector) keyword search."""

import time
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional


def semantic_search(
    db: Session,
    query_embedding: list[float],
    user_id: str,
    kb_ids: list[str],
    limit: int = 10,
) -> list[dict]:
    """Vector similarity search using pgvector."""
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    params = {
        "embedding": embedding_str,
        "user_id": user_id,
        "kb_ids": kb_ids,
        "limit": limit,
    }
    sql = text("""
        SELECT dc.id, dc.doc_id, dc.content, dc.chunk_index,
               dc.embedding::text,
               kb_docs.title, kb_docs.doc_type, kb_docs.source,
               1 - (dc.embedding <=> CAST(:embedding AS vector)) AS score
        FROM document_chunks dc
        JOIN kb_documents kb_docs ON dc.doc_id = kb_docs.id
        WHERE kb_docs.user_id = CAST(:user_id AS uuid)
              AND kb_docs.kb_id = ANY(CAST(:kb_ids AS uuid[]))
        ORDER BY dc.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)
    rows = db.execute(sql, params).fetchall()
    return [
        {
            "doc_id": str(row.doc_id),
            "title": row.title,
            "content": row.content,
            "doc_type": row.doc_type,
            "source": row.source,
            "score": float(row.score) if row.score else 0.0,
            "chunk_index": row.chunk_index,
        }
        for row in rows
    ]


def keyword_search(
    db: Session,
    query: str,
    user_id: str,
    kb_ids: list[str],
    limit: int = 10,
) -> list[dict]:
    """Full-text keyword search using PostgreSQL tsvector with zhparser."""
    params = {
        "query": query,
        "user_id": user_id,
        "kb_ids": kb_ids,
        "limit": limit,
    }
    sql = text("""
        SELECT dc.id, dc.doc_id, dc.content, dc.chunk_index,
               kb_docs.title, kb_docs.doc_type, kb_docs.source,
               ts_rank_cd(kb_docs.search_tsv, plainto_tsquery('chinese_zh', :query)) AS score
        FROM document_chunks dc
        JOIN kb_documents kb_docs ON dc.doc_id = kb_docs.id
        WHERE kb_docs.user_id = CAST(:user_id AS uuid)
              AND kb_docs.kb_id = ANY(CAST(:kb_ids AS uuid[]))
              AND kb_docs.search_tsv @@ plainto_tsquery('chinese_zh', :query)
        ORDER BY score DESC
        LIMIT :limit
    """)
    rows = db.execute(sql, params).fetchall()
    return [
        {
            "doc_id": str(row.doc_id),
            "title": row.title,
            "content": row.content,
            "doc_type": row.doc_type,
            "source": row.source,
            "score": float(row.score) if row.score else 0.0,
            "chunk_index": row.chunk_index,
        }
        for row in rows
    ]


def hybrid_search(
    db: Session,
    query: str,
    query_embedding: list[float],
    user_id: str,
    kb_ids: list[str],
    limit: int = 10,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> list[dict]:
    """Hybrid search combining semantic and keyword results with weighted scoring."""
    t0 = time.time()
    sem_results = semantic_search(db, query_embedding, user_id, kb_ids, limit=limit * 2)
    kw_results = keyword_search(db, query, user_id, kb_ids, limit=limit * 2)
    elapsed_ms = int((time.time() - t0) * 1000)

    # Merge results
    merged = {}
    for r in sem_results:
        key = f"{r['doc_id']}:{r.get('chunk_index', 0)}"
        merged[key] = {
            **r,
            "sem_score": r["score"],
            "kw_score": 0.0,
        }
    for r in kw_results:
        key = f"{r['doc_id']}:{r.get('chunk_index', 0)}"
        if key in merged:
            merged[key]["kw_score"] = r["score"]
        else:
            merged[key] = {
                **r,
                "sem_score": 0.0,
                "kw_score": r["score"],
            }

    # Normalize scores
    max_sem = max((m["sem_score"] for m in merged.values()), default=1) or 1
    max_kw = max((m["kw_score"] for m in merged.values()), default=1) or 1

    for m in merged.values():
        sem_norm = m["sem_score"] / max_sem if max_sem > 0 else 0
        kw_norm = m["kw_score"] / max_kw if max_kw > 0 else 0
        m["score"] = sem_norm * semantic_weight + kw_norm * keyword_weight

    results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:limit]

    return {
        "results": results,
        "total": len(results),
        "elapsed_ms": elapsed_ms,
    }
