from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    username: str          # 登录名，英文
    password: str
    display_name: Optional[str] = None   # 显示名，中文
    department: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: Optional[str] = None
    role: str
    department: Optional[str]
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserCreate(BaseModel):
    username: str          # 登录名，英文
    password: str
    display_name: Optional[str] = None   # 显示名，中文
    department: Optional[str] = None
    role: str = "user"


class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    department: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LLMConfigCreate(BaseModel):
    name: str
    provider: str  # deepseek / qwen / zhipu / tokenhub / custom
    api_url: Optional[str] = None
    api_key: str
    chat_model: str
    embedding_model: Optional[str] = None
    embedding_url: Optional[str] = None
    embedding_api_key: Optional[str] = None


class LLMConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    chat_model: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    is_active: Optional[bool] = None


class LLMConfigResponse(BaseModel):
    id: UUID
    name: str
    provider: str
    api_url: Optional[str]
    chat_model: str
    embedding_model: Optional[str]
    embedding_url: Optional[str]
    has_embedding_key: bool = False
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LLMTestRequest(BaseModel):
    provider: str
    api_url: Optional[str] = None
    # 编辑已有配置时前端不回显明文 Key，允许留空；
    # 此时通过 config_id 从数据库取已存的 Key
    api_key: Optional[str] = None
    chat_model: str
    embedding_model: Optional[str] = None
    embedding_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    config_id: Optional[str] = None


class LLMTestResult(BaseModel):
    chat_ok: bool
    embedding_ok: bool
    chat_latency_ms: Optional[int] = None
    embedding_latency_ms: Optional[int] = None
    embedding_dim: Optional[int] = None
    chat_error: Optional[str] = None
    embedding_error: Optional[str] = None
    resolved_chat_url: Optional[str] = None
    resolved_embedding_url: Optional[str] = None
