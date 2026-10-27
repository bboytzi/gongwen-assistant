from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from models.models import User
from api.users import require_admin
from services.settings import get_public_config, apply_updates, MAX_LOGO_BYTES

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SystemConfigUpdate(BaseModel):
    system_name: Optional[str] = None
    system_subtitle: Optional[str] = None
    # data URL（如 data:image/png;base64,...）；传空串表示恢复内置图案
    system_logo: Optional[str] = None


@router.get("/public")
def public_config(db: Session = Depends(get_db)):
    """系统名称与 logo 要在登录页展示，因此不要求认证。"""
    return get_public_config(db)


@router.get("")
def read_config(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_public_config(db)


@router.put("")
def update_config(
    req: SystemConfigUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if req.system_name is not None and len(req.system_name) > 50:
        raise HTTPException(status_code=400, detail="系统名称不超过 50 个字符")
    if req.system_subtitle is not None and len(req.system_subtitle) > 100:
        raise HTTPException(status_code=400, detail="副标题不超过 100 个字符")

    if req.system_logo:
        if not req.system_logo.startswith("data:image/"):
            raise HTTPException(status_code=400, detail="logo 必须是图片文件")
        # base64 体积约为原文件的 4/3，留一倍余量
        if len(req.system_logo) > MAX_LOGO_BYTES * 2:
            raise HTTPException(
                status_code=400,
                detail=f"logo 图片过大，请压缩到 {MAX_LOGO_BYTES // 1024}KB 以内",
            )

    apply_updates(db, req.system_name, req.system_subtitle, req.system_logo)
    db.commit()
    return get_public_config(db)
