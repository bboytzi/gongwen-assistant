import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, Boolean, DateTime, ForeignKey,
    JSON, Float, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # admin / user
    department = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="user")
    kb_documents = relationship("KBDocument", back_populates="user")
    llm_configs = relationship("LLMConfig", back_populates="user")
    templates = relationship("WordTemplate", back_populates="user")


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)  # deepseek / qwen / zhipu / custom
    api_url = Column(String(500))  # custom provider base URL
    api_key_encrypted = Column(Text, nullable=False)
    chat_model = Column(String(100), nullable=False)
    embedding_model = Column(String(100))
    embedding_url = Column(String(500))  # separate embedding endpoint if different
    # 向量接口可能使用独立的 Key（如 TokenHub 的 Token Plan Key 不能调 /v1 按量计费接口）
    embedding_api_key_encrypted = Column(Text)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="llm_configs")

    @property
    def has_embedding_key(self) -> bool:
        """是否单独配置了向量接口的 Key。"""
        return bool(self.embedding_api_key_encrypted)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # null = company-level
    name = Column(String(200), nullable=False)
    level = Column(String(20), nullable=False)  # company / personal
    created_at = Column(DateTime, default=datetime.utcnow)


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    doc_type = Column(String(50), default="other")  # regulation / case / template / other
    source = Column(String(200))  # file name or source description
    file_format = Column(String(10))  # pdf / docx
    file_path = Column(String(500))
    status = Column(String(20), default="pending")  # pending / parsing / indexing / done / failed
    error_message = Column(Text)
    meta = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="kb_documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text)  # pgvector stored as hex or text; will use raw SQL for vector ops
    page_number = Column(Integer)

    document = relationship("KBDocument", back_populates="chunks")

    __table_args__ = (
        Index("idx_doc_chunks_doc_id", "doc_id"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    doc_type = Column(String(50), default="request")  # request / report / notice
    doc_category = Column(String(50))  # procurement / personnel / fund / project
    procurement_scenario = Column(String(50))  # project_execution / element_org / joint / admin / client_specified
    budget_amount = Column(Float)
    procurement_method = Column(String(50))  # direct / inquiry / public / tender
    content = Column(Text)  # generated content (HTML or markdown)
    generation_config = Column(JSONB, default={})  # RAG references, prompt params
    source_kb_ids = Column(JSONB, default=[])  # list of KB IDs used
    status = Column(String(20), default="draft")  # draft / generating / done / failed
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    tasks = relationship("GenerationTask", back_populates="document")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    change_note = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="versions")


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending / running / completed / failed / cancelled
    progress = Column(Integer, default=0)  # 0-100
    current_step = Column(String(50))  # intent / rag / outline / generate / validate / format
    result_content = Column(Text)
    error_message = Column(Text)
    references = Column(JSONB, default=[])  # list of references used
    logs = Column(JSONB, default=[])
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="tasks")


class WordTemplate(Base):
    __tablename__ = "word_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # null = system template
    name = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    placeholders = Column(JSONB, default=[])  # list of placeholder names found
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="templates")
