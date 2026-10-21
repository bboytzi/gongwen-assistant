from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.encryption import decrypt_api_key
from models.models import User, LLMConfig, KnowledgeBase
from schemas.document import SearchRequest, SearchResponse, SearchResult
from api.auth import get_current_user
from services.llm_client import LLMClient
from services.search import hybrid_search, keyword_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Determine KB IDs to search
    if req.scope:
        kb_ids = req.scope
    else:
        company_kbs = db.query(KnowledgeBase).filter(KnowledgeBase.level == "company").all()
        personal_kbs = db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == current_user.id,
            KnowledgeBase.level == "personal",
        ).all()
        kb_ids = [str(kb.id) for kb in company_kbs + personal_kbs]

    if req.mode == "keyword":
        # Pure keyword search
        results = keyword_search(
            db=db,
            query=req.query,
            user_id=str(current_user.id),
            kb_ids=kb_ids,
            limit=req.limit,
        )
        return SearchResponse(
            results=[
                SearchResult(
                    doc_id=r["doc_id"],
                    title=r["title"],
                    content=r["content"][:500],
                    score=r["score"],
                    doc_type=r.get("doc_type", ""),
                    source=r.get("source"),
                )
                for r in results
            ],
            total=len(results),
            elapsed_ms=0,
        )

    # Semantic or hybrid: need embedding
    llm_config = db.query(LLMConfig).filter(
        LLMConfig.user_id == current_user.id,
        LLMConfig.is_active == True,
    ).first()
    if not llm_config:
        raise HTTPException(status_code=400, detail="No active LLM config. Please configure one in Settings.")

    api_key = decrypt_api_key(llm_config.api_key_encrypted)
    llm = LLMClient(
        provider=llm_config.provider,
        api_key=api_key,
        chat_model=llm_config.chat_model,
        api_url=llm_config.api_url,
        embedding_model=llm_config.embedding_model,
        embedding_url=llm_config.embedding_url,
    )

    try:
        embed_resp = llm.embed(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")
    finally:
        llm.close()

    if req.mode == "semantic":
        from services.search import semantic_search
        results = semantic_search(
            db=db,
            query_embedding=embed_resp.vector,
            user_id=str(current_user.id),
            kb_ids=kb_ids,
            limit=req.limit,
        )
        return SearchResponse(
            results=[
                SearchResult(
                    doc_id=r["doc_id"],
                    title=r["title"],
                    content=r["content"][:500],
                    score=r["score"],
                    doc_type=r.get("doc_type", ""),
                    source=r.get("source"),
                )
                for r in results
            ],
            total=len(results),
            elapsed_ms=0,
        )

    # Hybrid (default)
    result = hybrid_search(
        db=db,
        query=req.query,
        query_embedding=embed_resp.vector,
        user_id=str(current_user.id),
        kb_ids=kb_ids,
        limit=req.limit,
    )
    return SearchResponse(
        results=[
            SearchResult(
                doc_id=r["doc_id"],
                title=r["title"],
                content=r["content"][:500],
                score=r["score"],
                doc_type=r.get("doc_type", ""),
                source=r.get("source"),
            )
            for r in result["results"]
        ],
        total=result["total"],
        elapsed_ms=result["elapsed_ms"],
    )
