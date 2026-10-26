from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any
from enum import Enum


class DocStatus(str, Enum):
    draft = "draft"
    generating = "generating"
    done = "done"
    failed = "failed"


class DocumentCreate(BaseModel):
    title: str
    doc_type: str = "request"
    doc_category: str = "procurement"
    procurement_scenario: Optional[str] = None
    key_elements: dict[str, Any] = {}
    budget_amount: Optional[float] = None
    source_kb_ids: List[str] = []
    template_id: Optional[str] = None
    llm_config_id: str


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    doc_type: str
    doc_category: Optional[str]
    procurement_scenario: Optional[str]
    budget_amount: Optional[float]
    procurement_method: Optional[str]
    content: Optional[str]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GenerationTaskResponse(BaseModel):
    id: UUID
    document_id: UUID
    status: str
    progress: int
    current_step: Optional[str]
    result_content: Optional[str]
    error_message: Optional[str]
    references: list = []
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class KBDocumentResponse(BaseModel):
    id: UUID
    kb_id: UUID
    title: str
    doc_type: str
    source: Optional[str]
    file_format: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    mode: str = "semantic"  # semantic / keyword / hybrid
    scope: list[str] = []  # kb_ids to search in
    doc_types: list[str] = []
    doc_categories: list[str] = []
    limit: int = 10
    offset: int = 0


class SearchResult(BaseModel):
    doc_id: str
    title: str
    content: str
    score: float
    doc_type: str
    source: Optional[str] = None
    kb_name: Optional[str] = None
    created_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    elapsed_ms: int


class ExportRequest(BaseModel):
    document_id: UUID
    template_id: Optional[str] = None
    include_references: bool = True
    include_appendix: bool = True
    export_pdf: bool = False


class WordTemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    placeholders: list = []
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True
