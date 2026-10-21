from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    username: str
    password: str
    department: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    role: str
    department: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LLMConfigCreate(BaseModel):
    name: str
    provider: str  # deepseek / qwen / zhipu / custom
    api_url: Optional[str] = None
    api_key: str
    chat_model: str
    embedding_model: Optional[str] = None
    embedding_url: Optional[str] = None


class LLMConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    chat_model: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_url: Optional[str] = None
    is_active: Optional[bool] = None


class LLMConfigResponse(BaseModel):
    id: UUID
    name: str
    provider: str
    api_url: Optional[str]
    chat_model: str
    embedding_model: Optional[str]
    embedding_url: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LLMTestRequest(BaseModel):
    provider: str
    api_url: Optional[str] = None
    api_key: str
    chat_model: str
    embedding_model: Optional[str] = None
    embedding_url: Optional[str] = None


class LLMTestResult(BaseModel):
    chat_ok: bool
    embedding_ok: bool
    chat_latency_ms: Optional[int] = None
    embedding_latency_ms: Optional[int] = None
    chat_error: Optional[str] = None
    embedding_error: Optional[str] = None
