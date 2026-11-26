"""ORM models for ArthaLens PostgreSQL + pgvector database."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.database import Base
from app.timezone_utils import get_utc_now


class VectorType(TypeDecorator):
    """Uses native pgvector VECTOR(dim) on PostgreSQL; JSON text fallback for unit-test SQLite."""

    impl = Text
    cache_ok = True

    def __init__(self, dim: int = 384):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return [float(x) for x in value]
        return json.dumps([float(x) for x in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return [float(x) for x in value]


class JSONBType(TypeDecorator):
    """Uses PostgreSQL JSONB in production and standard JSON in SQLite unit tests."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class UUIDType(TypeDecorator):
    """Uses PostgreSQL UUID in production and String(36) in SQLite unit tests."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )

    documents: Mapped[list[Document]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("user_id", "file_hash", name="uq_documents_user_hash"),
        Index("ix_documents_user_type", "user_id", "document_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document", cascade="all, delete-orphan")
    assets: Mapped[list[FinancialAsset]] = relationship(back_populates="source_document", cascade="all, delete-orphan")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_chunks_user_doc", "user_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONBType(), nullable=False, default=dict)
    embedding: Mapped[list[float]] = mapped_column(VectorType(384), nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")


class FinancialAsset(Base):
    __tablename__ = "financial_assets"
    __table_args__ = (
        Index("ix_assets_user_type", "user_id", "asset_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(60), nullable=False)
    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    account_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    nominee_status: Mapped[str] = mapped_column(String(60), nullable=False, default="UNKNOWN")
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False, default="MEDIUM")
    details: Mapped[dict[str, Any]] = mapped_column(JSONBType(), nullable=False, default=dict)

    source_document: Mapped[Document] = relationship(back_populates="assets")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
        Index("ix_transactions_user_cat", "user_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="OTHER")
    reference_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False, default="HIGH")

    document: Mapped[Document] = relationship(back_populates="transactions")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_user_severity", "user_id", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONBType(), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Ask ArthaLens Session")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, onupdate=get_utc_now, nullable=False
    )

    messages: Mapped[list[ChatMessage]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_conv_user", "conversation_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONBType(), nullable=False, default=list)
    retrieval_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ExtractedEntityRecord(Base):
    __tablename__ = "extracted_entities"
    __table_args__ = (
        Index("ix_entities_user_type", "user_id", "entity_type"),
        Index("ix_entities_user_doc", "user_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_value: Mapped[str] = mapped_column(String(255), nullable=False)
    supporting_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False, default="HIGH")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )


class FindingProgress(Base):
    __tablename__ = "finding_progress"
    __table_args__ = (
        UniqueConstraint("finding_id", "user_id", name="uq_finding_progress_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    completed_steps: Mapped[list[str]] = mapped_column(JSONBType(), nullable=False, default=list)
    verification_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    nominee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class AutomationTask(Base):
    """AI-classified action workflow state for a financial finding."""

    __tablename__ = "automation_tasks"
    __table_args__ = (
        UniqueConstraint("finding_id", "user_id", name="uq_automation_task_finding_user"),
        Index("ix_automation_tasks_user_status", "user_id", "task_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_type: Mapped[str] = mapped_column(String(60), nullable=False)
    automation_level: Mapped[str] = mapped_column(String(50), nullable=False)
    task_status: Mapped[str] = mapped_column(String(50), nullable=False, default="Not Started")
    required_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approval_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issue_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    external_institution_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    institution_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_or_policy_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expected_evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    estimated_impact_inr: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    generated_plan: Mapped[dict[str, Any]] = mapped_column(JSONBType(), nullable=False, default=dict)
    completed_steps: Mapped[list[str]] = mapped_column(JSONBType(), nullable=False, default=list)
    draft_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_verification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, onupdate=get_utc_now, nullable=False
    )


class ActionEvidence(Base):
    """Uploaded or submitted confirmation evidence attached to an automation task."""

    __tablename__ = "action_evidence"
    __table_args__ = (
        Index("ix_action_evidence_task_user", "task_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSONBType(), nullable=False, default=dict)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="NEEDS_REVIEW")
    verification_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )


class ActionAuditLog(Base):
    """Immutable audit log of every automation action, approval, block, and status transition."""

    __tablename__ = "action_audit_logs"
    __table_args__ = (
        Index("ix_action_audit_finding_user", "finding_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(40), nullable=False, default="SYSTEM")
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONBType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )


class FinancialReminder(Base):
    """Scheduled automated financial reminders (e.g. FD maturity countdowns)."""

    __tablename__ = "financial_reminders"
    __table_args__ = (
        UniqueConstraint("task_id", "reminder_type", name="uq_reminder_task_type"),
        Index("ix_financial_reminders_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(60), nullable=False, default="FD_MATURITY")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="SCHEDULED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=get_utc_now, nullable=False
    )
