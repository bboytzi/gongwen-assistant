"""系统级配置读写。

配置存在 system_settings 键值表里，未设置时回落到这里的默认值。
logo 以 data URL（base64）存库，避免额外配置静态文件服务；
已在前端上传前限制大小，库里的体积可控。
"""

from typing import Optional

from sqlalchemy.orm import Session

from models.models import SystemSetting

KEY_NAME = "system_name"
KEY_SUBTITLE = "system_subtitle"
KEY_LOGO = "system_logo"

DEFAULT_NAME = "公文辅助系统"
DEFAULT_SUBTITLE = "公文起草 · 制度检索 · 知识库"

MAX_LOGO_BYTES = 200 * 1024  # 200KB，base64 后约 270KB


def get_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None or row.value is None or row.value == "":
        return default
    return row.value


def set_setting(db: Session, key: str, value: Optional[str]) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        row.value = value


def get_public_config(db: Session) -> dict:
    """登录页与全局框架使用的公开配置（无需认证）。"""
    return {
        "system_name": get_setting(db, KEY_NAME, DEFAULT_NAME),
        "system_subtitle": get_setting(db, KEY_SUBTITLE, DEFAULT_SUBTITLE),
        "system_logo": get_setting(db, KEY_LOGO, None),
        "max_logo_bytes": MAX_LOGO_BYTES,
    }


def apply_updates(db: Session, name=None, subtitle=None, logo=None) -> None:
    if name is not None:
        set_setting(db, KEY_NAME, name.strip() or DEFAULT_NAME)
    if subtitle is not None:
        set_setting(db, KEY_SUBTITLE, subtitle.strip() or DEFAULT_SUBTITLE)
    if logo is not None:
        # 传空串表示恢复内置方印
        set_setting(db, KEY_LOGO, logo or None)
