import os
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from core.database import get_db
from core.config import settings
from models.models import User, Document, GenerationTask, WordTemplate, DocumentVersion
from schemas.document import DocumentCreate, DocumentResponse, GenerationTaskResponse, ExportRequest
from api.auth import get_current_user
from tasks.tasks import generate_document
from services.word_renderer import TemplateRenderer, extract_placeholders

router = APIRouter(prefix="/api/documents", tags=["documents"])

# 注意：FastAPI 按注册顺序匹配路由。所有固定路径（/export、/templates）
# 必须写在动态路径（/{doc_id}）之前，否则 "templates" 会被当成 doc_id
# 送进 UUID 字段查询，PostgreSQL 直接抛类型错误返回 500。


# ---------------------------------------------------------------- 集合

@router.get("", response_model=list[DocumentResponse])
def list_documents(
    status: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if status:
        query = query.filter(Document.status == status)
    return query.order_by(Document.created_at.desc()).all()


@router.post("", response_model=DocumentResponse)
def create_document(
    req: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from services.generation import determine_procurement_method_en
    procurement_method = None
    if req.budget_amount is not None:
        procurement_method = determine_procurement_method_en(req.budget_amount)

    doc = Document(
        user_id=current_user.id,
        title=req.title,
        doc_type=req.doc_type,
        doc_category=req.doc_category,
        procurement_scenario=req.procurement_scenario,
        budget_amount=req.budget_amount,
        procurement_method=procurement_method,
        source_kb_ids=req.source_kb_ids,
        generation_config={"key_elements": req.key_elements},
        status="draft",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------- 固定路径

@router.post("/export")
def export_document(
    req: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == req.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get template
    template_path = None
    if req.template_id:
        try:
            UUID(str(req.template_id))
        except (ValueError, AttributeError, TypeError):
            # 非 UUID（如内置的 system-default）→ 走默认公文格式
            req.template_id = None
        if req.template_id:
            template = db.query(WordTemplate).filter(
                WordTemplate.id == req.template_id
            ).first()
            if template and template.file_path:
                template_path = template.file_path

    # Prepare replacements from document content and config
    key_elements = doc.generation_config.get("key_elements", {}) if doc.generation_config else {}
    replacements = {
        "标题": doc.title,
        "事由段落": key_elements.get("事由", ""),
        "依据段落": key_elements.get("依据", ""),
        "请示事项段落": doc.content or "",
        "起草部门": key_elements.get("起草部门", current_user.department or ""),
        "文号": key_elements.get("文号", ""),
        "签发人": key_elements.get("签发人", ""),
        "联系人": current_user.username,
    }

    # Render
    output_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id), "exports")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{doc.title}.docx"
    output_path = os.path.join(output_dir, f"{uuid.uuid4()}.docx")

    renderer = TemplateRenderer(template_path)
    renderer.render(replacements, output_path)

    return {"file_path": output_path, "filename": output_filename}


@router.post("/templates", response_model=dict)
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".docx":
        raise HTTPException(status_code=400, detail="Template must be .docx")

    template_id = str(uuid.uuid4())
    user_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id), "templates")
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, f"{template_id}.docx")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    placeholders = extract_placeholders(file_path)

    template = WordTemplate(
        user_id=current_user.id,
        name=name,
        file_path=file_path,
        placeholders=placeholders,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        "id": str(template.id),
        "name": template.name,
        "placeholders": placeholders,
    }


@router.get("/templates", response_model=list)
def list_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # System templates + user's templates
    system = db.query(WordTemplate).filter(WordTemplate.is_system == True).all()
    user_templates = db.query(WordTemplate).filter(WordTemplate.user_id == current_user.id).all()
    result = [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description,
            "placeholders": t.placeholders,
            "is_system": t.is_system,
        }
        for t in system + user_templates
    ]

    # 一个模板都没上传时，给一个内置格式选项，避免下拉框空白
    if not result:
        result.append({
            "id": "system-default",
            "name": "系统默认公文格式",
            "description": "标题方正小标宋2号、正文方正仿宋3号、行距30磅，"
                           "页边距上37下35左28右26mm",
            "placeholders": [],
            "is_system": True,
        })

    return result


# ---------------------------------------------------------------- 动态路径

@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return doc


@router.post("/{doc_id}/generate", response_model=GenerationTaskResponse)
def start_generation(
    doc_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Cancel any existing running task
    existing = db.query(GenerationTask).filter(
        GenerationTask.document_id == doc_id,
        GenerationTask.status.in_(["running", "pending"]),
    ).first()
    if existing:
        existing.status = "cancelled"
        db.commit()

    task = GenerationTask(
        document_id=doc.id,
        user_id=current_user.id,
        status="pending",
        progress=0,
        current_step="init",
    )
    db.add(task)
    doc.status = "generating"
    db.commit()
    db.refresh(task)

    generate_document.delay(str(task.id))
    return task


@router.get("/{doc_id}/task", response_model=GenerationTaskResponse)
def get_task_status(
    doc_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(GenerationTask).filter(
        GenerationTask.document_id == doc_id,
    ).order_by(GenerationTask.created_at.desc()).first()
    if not task:
        raise HTTPException(status_code=404, detail="No generation task found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return task


@router.put("/{doc_id}/content")
def update_content(
    doc_id: UUID,
    content: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Save version
    if doc.content:
        version = DocumentVersion(
            document_id=doc.id,
            version_number=doc.version,
            content=doc.content,
            change_note="auto-save",
        )
        db.add(version)
        doc.version += 1

    doc.content = content.get("content", "")
    db.commit()
    return {"ok": True, "version": doc.version}


@router.get("/{doc_id}/versions")
def list_versions(
    doc_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id,
    ).order_by(DocumentVersion.created_at.desc()).all()
    return [
        {
            "id": str(v.id),
            "version_number": v.version_number,
            "change_note": v.change_note,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]
