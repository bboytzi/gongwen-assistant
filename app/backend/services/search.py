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
    """Vector similarity search using pgvector.

    embedding 列未建立向量索引或类型不符时返回空列表，由调用方降级到关键词检索。
    """
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
              AND dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)
    try:
        rows = db.execute(sql, params).fetchall()
    except Exception as e:
        db.rollback()
        print(f"[semantic_search] 向量检索不可用，跳过: {e}")
        return []

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


_zhparser_available = None


def has_zhparser(db: Session) -> bool:
    """检测数据库是否安装了 zhparser 与 chinese_zh 配置（结果缓存）。"""
    global _zhparser_available
    if _zhparser_available is not None:
        return _zhparser_available
    try:
        row = db.execute(
            text("SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese_zh'")
        ).first()
        _zhparser_available = bool(row)
    except Exception:
        _zhparser_available = False
    return _zhparser_available


def _split_keywords(query: str) -> list[str]:
    """把中文查询切成关键词，用于 pg_trgm 降级检索。"""
    import re
    stopwords = {
        "的", "了", "和", "与", "及", "关于", "申请", "请示", "材料",
        "请", "我", "们", "怎么", "如何", "什么", "哪些", "是否",
    }
    parts = re.split(r"[，。、；：？！,.\s/]+", query)
    kws = []
    for p in parts:
        p = p.strip()
        if len(p) >= 2 and p not in stopwords:
            kws.append(p)
    return kws or [query]


def _keyword_search_trgm(
    db: Session,
    query: str,
    user_id: str,
    kb_ids: list[str],
    limit: int,
) -> list[dict]:
    """pg_trgm 模糊匹配降级方案（zhparser 不可用时使用）。

    中文没有空格分词，用 trigram 相似度 + ILIKE 关键词匹配兜底。
    """
    keywords = _split_keywords(query)
    params = {
        "query": query,
        "user_id": user_id,
        "kb_ids": kb_ids,
        "limit": limit,
    }

    # 动态构造关键词 ILIKE 条件
    like_clauses = []
    for i, kw in enumerate(keywords[:6]):
        key = f"kw{i}"
        params[key] = f"%{kw}%"
        like_clauses.append(f"kb_docs.content ILIKE :{key}")
        like_clauses.append(f"kb_docs.title ILIKE :{key}")

    like_sql = " OR ".join(like_clauses) if like_clauses else "FALSE"

    sql = text(f"""
        SELECT dc.id, dc.doc_id, dc.content, dc.chunk_index,
               kb_docs.title, kb_docs.doc_type, kb_docs.source,
               GREATEST(
                   similarity(kb_docs.title, :query),
                   similarity(kb_docs.content, :query)
               ) AS sim,
               (CASE WHEN kb_docs.title ILIKE '%' || :query || '%' THEN 0.5 ELSE 0 END) AS exact_bonus
        FROM document_chunks dc
        JOIN kb_documents kb_docs ON dc.doc_id = kb_docs.id
        WHERE kb_docs.user_id = CAST(:user_id AS uuid)
              AND kb_docs.kb_id = ANY(CAST(:kb_ids AS uuid[]))
              AND ({like_sql} OR kb_docs.content % :query)
        ORDER BY (GREATEST(
                   similarity(kb_docs.title, :query),
                   similarity(kb_docs.content, :query)
                 ) + (CASE WHEN kb_docs.title ILIKE '%' || :query || '%' THEN 0.5 ELSE 0 END)) DESC
        LIMIT :limit
    """)

    try:
        rows = db.execute(sql, params).fetchall()
    except Exception:
        db.rollback()
        return []

    return [
        {
            "doc_id": str(row.doc_id),
            "title": row.title,
            "content": row.content,
            "doc_type": row.doc_type,
            "source": row.source,
            "score": float(row.sim) if row.sim else 0.0,
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
    """关键词检索。

    优先使用 zhparser 中文分词全文检索；若数据库未安装 zhparser，
    自动降级到 pg_trgm 模糊匹配，避免接口直接报错。
    """
    if not has_zhparser(db):
        return _keyword_search_trgm(db, query, user_id, kb_ids, limit)

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
    try:
        rows = db.execute(sql, params).fetchall()
    except Exception:
        db.rollback()
        return _keyword_search_trgm(db, query, user_id, kb_ids, limit)

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
