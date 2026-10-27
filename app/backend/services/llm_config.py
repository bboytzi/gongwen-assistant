"""LLM 配置的可见性规则。

管理员配置并激活的那条对所有用户生效——新账号登录后不需要自己配 Key
就能直接用。普通用户若也配置并激活了自己的，优先用自己的，便于个人
测试不同模型，不影响他人。

这样既避免了「每个新账号都要单独配 Key」的重复劳动，又保留了个人覆盖
的可能。
"""

from typing import Optional

from sqlalchemy.orm import Session

from models.models import LLMConfig, User


def get_active_config(db: Session, user_id) -> Optional[LLMConfig]:
    """取该用户实际可用的激活配置。

    1. 本人有激活配置 → 用本人的
    2. 否则 → 用任一启用的管理员配置（取最近更新的）
    3. 都没有 → None
    """
    own = db.query(LLMConfig).filter(
        LLMConfig.user_id == user_id,
        LLMConfig.is_active == True,  # noqa: E712
    ).first()
    if own is not None:
        return own

    return (
        db.query(LLMConfig)
        .join(User, User.id == LLMConfig.user_id)
        .filter(
            User.role == "admin",
            User.is_active == True,  # noqa: E712
            LLMConfig.is_active == True,  # noqa: E712
        )
        .order_by(LLMConfig.updated_at.desc())
        .first()
    )


def is_global_config(db: Session, cfg: Optional[LLMConfig]) -> bool:
    """这条配置是否来自管理员（即全局共享）。"""
    if cfg is None:
        return False
    owner = db.query(User).filter(User.id == cfg.user_id).first()
    return bool(owner and owner.role == "admin")


def owner_label(db: Session, cfg: Optional[LLMConfig]) -> str:
    """配置归属人的显示名，用于界面提示。"""
    if cfg is None:
        return ""
    owner = db.query(User).filter(User.id == cfg.user_id).first()
    if owner is None:
        return cfg.name or ""
    return owner.display_name or owner.username
