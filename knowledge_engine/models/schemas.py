"""
Pydantic schemas for all API request/response models.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field


# ─── Documents ────────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: str
    source: Optional[str] = None
    category: Optional[str] = None
    product_family: Optional[str] = None
    version: str = "v1.0"
    language: str = "sv"
    collection_ids: list[UUID] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: UUID
    canonical_id: UUID
    version_num: int
    is_latest: bool
    title: str
    source: Optional[str]
    category: Optional[str]
    product_family: Optional[str]
    version: Optional[str]
    language: str
    status: str
    storage_path: str
    checksum: str
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


# ─── Collections ──────────────────────────────────────────────────────────────

class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_default: bool
    created_at: datetime


# ─── Query ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    collection_id: UUID
    mode: str = Field(..., pattern="^(technical|sales|investor)$")
    question: str = Field(..., min_length=3, max_length=2000)
    constraints: Optional[str] = None


class CitationItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    document_version: Optional[str]
    page_start: Optional[int]
    page_end: Optional[int]
    section: Optional[str]
    content_preview: str  # First 300 chars of the chunk


class RetrievedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    score: float
    rank: int
    page_start: Optional[int]
    page_end: Optional[int]
    section: Optional[str]


class QueryResponse(BaseModel):
    query_id: UUID
    answer: str
    citations: list[CitationItem]
    retrieved_chunks: list[RetrievedChunk]
    confidence: str  # high, medium, low
    latency_ms: int


# ─── Feedback ─────────────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    query_id: UUID
    rating: int = Field(..., ge=1, le=5)
    issue_type: Optional[str] = Field(
        None,
        pattern="^(wrong|missing|unclear|too_long|other)$"
    )
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: UUID
    query_id: UUID
    rating: int
    created_at: datetime
