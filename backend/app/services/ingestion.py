"""Automated PDF validation, deduplication, ingestion, embedding, and extraction pipeline."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document, DocumentChunk, FinancialAsset, Transaction
from app.services.embeddings import embed_texts
from app.services.extraction import extract_structured_data
from app.services.intelligence import recompute_user_findings
from app.services.pdf_parser import chunk_pages, detect_document_type, extract_pdf_pages

logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    base = Path(filename).name
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return safe[:180] or "document.pdf"


async def ingest_uploaded_pdf(
    db: Session,
    user_id: int,
    upload_file: UploadFile,
) -> Document:
    """
    Validate, deduplicate, persist original PDF, extract text & chunks,
    embed with Sentence Transformers, extract financial entities, and refresh findings.
    """
    settings = get_settings()
    filename = _sanitize_filename(upload_file.filename or "upload.pdf")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files (.pdf) are supported.",
        )

    raw_bytes = await upload_file.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF file is empty.",
        )
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB.",
        )
    if not raw_bytes[:5].startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file signature: file is not a valid PDF document.",
        )

    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    existing = db.scalar(
        select(Document).where(
            Document.user_id == user_id,
            Document.file_hash == file_hash,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate document detected: '{existing.filename}' (id={existing.id}) has identical SHA-256 hash.",
        )

    user_dir = settings.storage_path / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_path = user_dir / f"{uuid.uuid4().hex}_{filename}"
    stored_path.write_bytes(raw_bytes)

    doc = Document(
        user_id=user_id,
        filename=filename,
        document_type="PENDING_CLASSIFICATION",
        file_hash=file_hash,
        file_path=str(stored_path),
        file_size_bytes=len(raw_bytes),
        page_count=0,
        processing_status="PROCESSING",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return process_existing_document(db, doc)


def process_existing_document(db: Session, doc: Document) -> Document:
    """Process or reprocess a stored Document in place without discarding the original PDF."""
    file_path = Path(doc.file_path)
    if not file_path.exists():
        doc.processing_status = "FAILED"
        doc.error_message = "Original PDF file not found in storage."
        db.commit()
        raise HTTPException(status_code=404, detail=doc.error_message)

    try:
        doc.processing_status = "PROCESSING"
        doc.error_message = None
        db.commit()

        # Clear prior derived records on reprocess
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == doc.id,
            DocumentChunk.user_id == doc.user_id,
        ).delete()
        db.query(FinancialAsset).filter(
            FinancialAsset.source_document_id == doc.id,
            FinancialAsset.user_id == doc.user_id,
        ).delete()
        db.query(Transaction).filter(
            Transaction.document_id == doc.id,
            Transaction.user_id == doc.user_id,
        ).delete()
        db.flush()

        pages = extract_pdf_pages(file_path)
        doc_type = detect_document_type(pages, doc.filename)
        doc.document_type = doc_type
        doc.page_count = len(pages)

        chunks = chunk_pages(pages, doc_type, doc.filename)
        embeddings = embed_texts([c.chunk_text for c in chunks])

        for chunk_obj, vec in zip(chunks, embeddings):
            db.add(
                DocumentChunk(
                    user_id=doc.user_id,
                    document_id=doc.id,
                    chunk_text=chunk_obj.chunk_text,
                    chunk_index=chunk_obj.chunk_index,
                    page_number=chunk_obj.page_number,
                    chunk_metadata=chunk_obj.metadata,
                    embedding=vec,
                )
            )

        extracted = extract_structured_data(doc_type, pages)
        for asset in extracted.assets:
            db.add(
                FinancialAsset(
                    user_id=doc.user_id,
                    asset_type=asset.asset_type,
                    institution=asset.institution,
                    account_reference=asset.account_reference,
                    amount=asset.amount,
                    nominee_status=asset.nominee_status,
                    maturity_date=asset.maturity_date,
                    source_document_id=doc.id,
                    page_number=asset.page_number,
                    extracted_text=asset.extracted_text,
                    confidence=asset.confidence,
                    details=asset.details,
                )
            )

        for tx in extracted.transactions:
            db.add(
                Transaction(
                    user_id=doc.user_id,
                    document_id=doc.id,
                    transaction_date=tx.transaction_date,
                    description=tx.description,
                    amount=tx.amount,
                    transaction_type=tx.transaction_type,
                    category=tx.category,
                    reference_no=tx.reference_no,
                    page_number=tx.page_number,
                    confidence=tx.confidence,
                )
            )

        doc.processing_status = "COMPLETED"
        db.commit()
        db.refresh(doc)

        # Recompute cross-document intelligence findings for this user
        recompute_user_findings(db, doc.user_id)
        logger.info("Ingested doc_id=%s type=%s chunks=%d", doc.id, doc.document_type, len(chunks))
        return doc
    except Exception as exc:
        db.rollback()
        doc.processing_status = "FAILED"
        doc.error_message = f"Processing failed: {type(exc).__name__}"
        db.add(doc)
        db.commit()
        logger.exception("Failed processing doc_id=%s", doc.id)
        raise
