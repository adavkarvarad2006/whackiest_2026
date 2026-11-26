"""Pydantic schemas for ArthaLens API requests and responses."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer

from app.timezone_utils import to_ist_iso

ISTDatetime = Annotated[datetime, PlainSerializer(lambda dt: to_ist_iso(dt), return_type=str)]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    is_demo: bool = False
    created_at: ISTDatetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    document_type: str
    file_hash: str
    file_size_bytes: int
    page_count: int
    upload_date: ISTDatetime
    processing_status: str
    error_message: Optional[str] = None
    chunk_count: int = 0


class DocumentDetailOut(DocumentOut):
    extracted_assets_count: int = 0
    extracted_transactions_count: int = 0
    sample_pages: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Assets, Transactions, Findings
# ---------------------------------------------------------------------------
class FinancialAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    asset_type: str
    institution: str
    account_reference: Optional[str] = None
    amount: float
    nominee_status: str
    maturity_date: Optional[date] = None
    source_document_id: int
    source_document_name: Optional[str] = None
    page_number: int
    extracted_text: Optional[str] = None
    confidence: str
    details: dict[str, Any] = Field(default_factory=dict)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    transaction_date: date
    description: str
    amount: float
    transaction_type: str
    category: str
    reference_no: Optional[str] = None
    page_number: int
    confidence: str


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    finding_type: str
    title: str
    description: str
    severity: str
    confidence: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    created_at: ISTDatetime


# ---------------------------------------------------------------------------
# Chat & Evidence
# ---------------------------------------------------------------------------
class EvidenceSource(BaseModel):
    document_id: Optional[int | str] = None
    filename: Optional[str] = None
    document: str
    page_number: Optional[int] = None
    page: int
    evidence: str
    snippet: Optional[str] = None
    relevance_score: Optional[float] = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    intent: str = "UNKNOWN_INTENT"
    language: str = "English"
    confidence: str
    sources: list[EvidenceSource] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_options: list[str] = Field(default_factory=list)
    followup_suggestions: list[str] = Field(default_factory=list)
    nlp_metadata: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = "This finding is based only on the uploaded documents and verified structured records."
    conversation_id: UUID
    retrieval_mode: str = "HYBRID"


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    confidence: Optional[str] = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_mode: Optional[str] = None
    created_at: ISTDatetime


class ChatHistoryOut(BaseModel):
    conversation_id: UUID
    title: str
    messages: list[ChatMessageOut] = Field(default_factory=list)


class ConversationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    created_at: ISTDatetime
    updated_at: ISTDatetime
