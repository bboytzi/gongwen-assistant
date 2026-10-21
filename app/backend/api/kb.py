import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from core.database import get_db
from core.config import settings
from models.models import User, KBDocument, KnowledgeBase
from schemas.document import KBDocumentResponse
from api.auth import get_current_user
from tasks.tasks import process_kb_document

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}


@router.get("/bases")
def list_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_kbs = db.query(KnowledgeBase).filter(KnowledgeBase.level == "company").all()
    personal_kbs = db.query(KnowledgeBase).filter(
        KnowledgeBase.user_id == current_user.id,
        KnowledgeBase.level == "personal",
    ).all()
    return {
        "company": [{"id": str(kb.id), "name": kb.name} for kb in company_kbs],
        "personal": [{"id": str(kb.id), "name": kb.name} for kb in personal_kbs],
    }


@router.get("/documents", response_model=list[KBDocumentResponse])
def list_documents(
    kb_id: str = None,
    level: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(KBDocument)
    if level == "company":
        company_kbs = db.query(KnowledgeBase).filter(KnowledgeBase.level == "company").all()
        kb_ids = [kb.id for kb in company_kbs]
        query = query.filter(KBDocument.kb_id.in_(kb_ids))
    elif level == "personal":
        query = query.filter(KBDocument.user_id == current_user.id)
    else:
        query = query.filter(KBDocument.user_id == current_user.id)
    if kb_id:
        query = query.filter(KBDocument.kb_id == kb_id)
    return query.order_by(KBDocument.created_at.desc()).all()


@router.post("/upload", response_model=KBDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    kb_id: str = Form(...),
    doc_type: str = Form("other"),
    title: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not supported. Use PDF or DOCX.")

    # Verify KB access
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    if kb.level == "company" and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can upload to company knowledge base")
    if kb.level == "personal" and kb.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your knowledge base")

    # Save file
    file_id = str(uuid.uuid4())
    user_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, f"{file_id}{ext}")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create document record
    doc_title = title or os.path.splitext(file.filename)[0]
    doc = KBDocument(
        kb_id=kb.id,
        user_id=current_user.id,
        title=doc_title,
        doc_type=doc_type,
        source=file.filename,
        file_format=ext.lstrip("."),
        file_path=file_path,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Trigger async processing
    process_kb_document.delay(str(doc.id))

    return doc


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(KBDocument).filter(KBDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    # Delete file
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    # Delete chunks
    db.query(KBDocument).filter(KBDocument.id == doc_id).delete()
    db.commit()
    return {"ok": True}


@router.post("/documents/{doc_id}/retry")
def retry_processing(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(KBDocument).filter(KBDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = "pending"
    doc.error_message = None
    db.commit()
    process_kb_document.delay(str(doc.id))
    return {"ok": True, "status": "pending"}
