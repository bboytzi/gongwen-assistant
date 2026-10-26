from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.models import User, Document, KBDocument, KnowledgeBase
from api.auth import get_current_user

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """首页工作台统计。只统计当前用户可见的数据。"""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    base = db.query(Document).filter(Document.user_id == current_user.id)

    month_documents = base.filter(Document.created_at >= month_start).count()
    total_documents = base.count()
    generating = base.filter(Document.status == "generating").count()
    completed = base.filter(Document.status == "done").count()

    # 可见知识库：公司级 + 本人个人级
    company_ids = [
        kb.id for kb in db.query(KnowledgeBase)
        .filter(KnowledgeBase.level == "company").all()
    ]
    personal_ids = [
        kb.id for kb in db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == current_user.id,
            KnowledgeBase.level == "personal",
        ).all()
    ]
    kb_ids = company_ids + personal_ids

    kb_documents = (
        db.query(KBDocument).filter(KBDocument.kb_id.in_(kb_ids)).count()
        if kb_ids else 0
    )
    kb_indexed = (
        db.query(KBDocument)
        .filter(KBDocument.kb_id.in_(kb_ids), KBDocument.status == "done")
        .count()
        if kb_ids else 0
    )

    kb_chunks = db.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar() or 0
    vector_chunks = db.execute(
        text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
    ).scalar() or 0

    return {
        "month_documents": month_documents,
        "total_documents": total_documents,
        "generating": generating,
        "completed": completed,
        "kb_documents": kb_documents,
        "kb_indexed": kb_indexed,
        "kb_chunks": kb_chunks,
        "vector_chunks": vector_chunks,
        "vector_ready": vector_chunks > 0,
    }
