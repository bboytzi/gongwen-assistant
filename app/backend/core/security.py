"""密码哈希与 JWT 令牌。

密码哈希直接使用 bcrypt 库，不经过 passlib。
原因：passlib 1.7.4（2020 年后停止维护）会访问 bcrypt 4.1+ 已移除的
`bcrypt.__about__`，触发 AttributeError，随后在内部探测分支里用超长
测试密码调用 bcrypt，被 bcrypt 4.x 的 72 字节校验直接拒绝，导致所有
哈希/校验操作失败。去掉这层中间件可彻底规避该问题。
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt

from core.config import settings

# bcrypt 算法上限为 72 字节，超出部分 bcrypt 4.x 会直接抛 ValueError。
# 统一在此截断，避免上层各处重复处理。
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    """把密码编码为 bcrypt 可接受的字节串（超过 72 字节时截断）。"""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希，返回形如 $2b$12$... 的字符串。"""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。哈希格式非法时返回 False 而非抛异常。"""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm="HS256"
    )


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        return payload
    except Exception:
        return None
