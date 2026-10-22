from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.encryption import encrypt_api_key, decrypt_api_key
from models.models import User, LLMConfig
from schemas.user import LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse, LLMTestRequest, LLMTestResult
from services.llm_client import LLMClient
from api.auth import get_current_user

router = APIRouter(prefix="/api/llm", tags=["llm"])
PROVIDERS = ["deepseek", "qwen", "zhipu", "custom"]


@router.get("/providers")
def list_providers():
    return {"providers": PROVIDERS}


@router.get("/configs", response_model=list[LLMConfigResponse])
def list_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(LLMConfig).filter(LLMConfig.user_id == current_user.id).all()


@router.post("/configs", response_model=LLMConfigResponse)
def create_config(
    req: LLMConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = LLMConfig(
        user_id=current_user.id,
        name=req.name,
        provider=req.provider,
        api_url=req.api_url,
        api_key_encrypted=encrypt_api_key(req.api_key),
        chat_model=req.chat_model,
        embedding_model=req.embedding_model,
        embedding_url=req.embedding_url,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return LLMConfigResponse.model_validate(config)


@router.put("/configs/{config_id}", response_model=LLMConfigResponse)
def update_config(
    config_id: str,
    req: LLMConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = db.query(LLMConfig).filter(
        LLMConfig.id == config_id,
        LLMConfig.user_id == current_user.id,
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    if req.name is not None:
        config.name = req.name
    if req.provider is not None:
        config.provider = req.provider
    if req.api_url is not None:
        config.api_url = req.api_url
    if req.api_key is not None:
        config.api_key_encrypted = encrypt_api_key(req.api_key)
    if req.chat_model is not None:
        config.chat_model = req.chat_model
    if req.embedding_model is not None:
        config.embedding_model = req.embedding_model
    if req.embedding_url is not None:
        config.embedding_url = req.embedding_url
    if req.is_active is not None and req.is_active:
        # Deactivate all other configs for this user
        db.query(LLMConfig).filter(
            LLMConfig.user_id == current_user.id,
            LLMConfig.id != config.id,
        ).update({"is_active": False})
        config.is_active = True
    elif req.is_active is not None:
        config.is_active = req.is_active

    db.commit()
    db.refresh(config)
    return LLMConfigResponse.model_validate(config)


@router.delete("/configs/{config_id}")
def delete_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = db.query(LLMConfig).filter(
        LLMConfig.id == config_id,
        LLMConfig.user_id == current_user.id,
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()
    return {"ok": True}


@router.post("/test", response_model=LLMTestResult)
def test_llm(req: LLMTestRequest):
    try:
        llm = LLMClient(
            provider=req.provider,
            api_key=req.api_key,
            chat_model=req.chat_model,
            api_url=req.api_url,
            embedding_model=req.embedding_model,
            embedding_url=req.embedding_url,
        )
        result = llm.test_connectivity()
        llm.close()
        return LLMTestResult(
            chat_ok=result["chat_ok"],
            embedding_ok=result["embedding_ok"],
            chat_latency_ms=result["chat_latency_ms"],
            embedding_latency_ms=result["embedding_latency_ms"],
            embedding_dim=result.get("embedding_dim"),
            chat_error=result["chat_error"],
            embedding_error=result["embedding_error"],
            resolved_chat_url=result.get("resolved_chat_url"),
            resolved_embedding_url=result.get("resolved_embedding_url"),
        )
    except Exception as e:
        return LLMTestResult(
            chat_ok=False,
            embedding_ok=False,
            chat_error=str(e),
            embedding_error=None,
        )
