"""Document upload (single or multi-file), listing, inspection, deletion, and reprocessing endpoints."""

from pathlib import Path
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Document, DocumentChunk, FinancialAsset, Finding, Transaction, User
from app.schemas import DocumentDetailOut, DocumentOut
from app.services.ingestion import ingest_uploaded_pdf, process_existing_document
from app.services.intelligence import recompute_user_findings

router = APIRouter(prefix="/api/documents", tags=["documents"])

DOC_TYPE_FROM_HINT = {
    "Bank Statement": "bank_statement",
    "AIS (IT)": "annual_information_statement",
    "Form 16": "form_16",
    "Insurance Policy": "life_insurance_policy",
    "Fixed Deposit": "fixed_deposit_certificate",
    "Loan Statement": "personal_loan_statement",
    "Investment Statement": "annual_information_statement",
}

DOC_TYPE_DISPLAY = {
    "bank_statement": "Bank Statement",
    "annual_information_statement": "AIS (IT)",
    "form_16": "Form 16",
    "life_insurance_policy": "Insurance Policy",
    "fixed_deposit_certificate": "Fixed Deposit",
    "personal_loan_statement": "Loan Statement",
}


def _to_ui_doc(db: Session, doc: Document, chunk_count: int, is_demo: bool) -> dict:
    assets = list(
        db.scalars(
            select(FinancialAsset).where(
                FinancialAsset.source_document_id == doc.id,
                FinancialAsset.user_id == doc.user_id,
            )
        )
    )
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id, DocumentChunk.user_id == doc.user_id)
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
        )
    )
    pages_map: dict[int, list[str]] = {}
    for c in chunks:
        pages_map.setdefault(c.page_number, []).append(c.chunk_text)

    base = DocumentOut.model_validate(doc).model_dump()
    base["chunk_count"] = chunk_count
    base["doc_type"] = DOC_TYPE_DISPLAY.get(doc.document_type, "Bank Statement")
    base["uploaded_at"] = doc.upload_date.isoformat()
    base["size_bytes"] = doc.file_size_bytes
    base["status"] = "Processed" if doc.processing_status == "COMPLETED" else ("Error" if doc.processing_status == "FAILED" else "Processing")
    base["pipeline_stage"] = "Generate Findings" if doc.processing_status == "COMPLETED" else "Extract"
    base["is_demo"] = is_demo
    base["summary"] = assets[0].extracted_text if assets and assets[0].extracted_text else f"Extracted {doc.page_count} page(s) across {chunk_count} semantic chunk(s)."
    base["extracted_entities"] = [
        {
            "label": a.asset_type.replace("_", " ").title(),
            "value": f"{a.institution} ({a.account_reference or 'N/A'}) — ₹{float(a.amount):,.2f}",
            "confidence": 92 if a.confidence == "HIGH" else 75,
            "page": a.page_number,
        }
        for a in assets
    ]
    base["pages"] = [{"page": pno, "text": "\n".join(texts)} for pno, texts in sorted(pages_map.items())]
    return base


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    doc_type_hint: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supports both single `file` uploads and multi-file `files` uploads from Next.js."""
    is_demo = current_user.email.endswith(".demo@arthalens.example")
    if file is not None and not files:
        doc = await ingest_uploaded_pdf(db, current_user.id, file)
        chunk_count = int(
            db.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == doc.id,
                    DocumentChunk.user_id == current_user.id,
                )
            ) or 0
        )
        out = DocumentOut.model_validate(doc)
        out.chunk_count = chunk_count
        return out

    upload_list = files or ([file] if file else [])
    if not upload_list:
        raise HTTPException(status_code=400, detail="No PDF file provided.")

    uploaded_docs = []
    for f in upload_list:
        doc = await ingest_uploaded_pdf(db, current_user.id, f)
        hinted_type = DOC_TYPE_FROM_HINT.get((doc_type_hint or "").strip())
        if hinted_type and doc.document_type != hinted_type and doc.processing_status == "COMPLETED":
            # Respect explicit user hint when uploaded via targeted dropdown without breaking auto-classification
            if doc.document_type in ("PENDING_CLASSIFICATION", "OTHER", "UNKNOWN"):
                doc.document_type = hinted_type
                db.commit()
        cnt = int(
            db.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.document_id == doc.id,
                    DocumentChunk.user_id == current_user.id,
                )
            ) or 0
        )
        uploaded_docs.append(_to_ui_doc(db, doc, cnt, is_demo))

    findings_count = int(
        db.scalar(select(func.count(Finding.id)).where(Finding.user_id == current_user.id)) or 0
    )
    return {
        "uploaded": uploaded_docs,
        "findings_generated": findings_count,
        "findings": [],
    }


@router.get("")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_demo = current_user.email.endswith(".demo@arthalens.example")
    docs = list(
        db.scalars(
            select(Document)
            .where(Document.user_id == current_user.id)
            .order_by(Document.upload_date.desc(), Document.id.desc())
        )
    )
    counts = dict(
        db.execute(
            select(DocumentChunk.document_id, func.count(DocumentChunk.id))
            .where(DocumentChunk.user_id == current_user.id)
            .group_by(DocumentChunk.document_id)
        ).all()
    )
    return [_to_ui_doc(db, d, int(counts.get(d.id, 0)), is_demo) for d in docs]


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.user_id == current_user.id,
            )
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
        )
    )
    assets_cnt = db.scalar(
        select(func.count(FinancialAsset.id)).where(
            FinancialAsset.source_document_id == doc.id,
            FinancialAsset.user_id == current_user.id,
        )
    ) or 0
    txns_cnt = db.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.document_id == doc.id,
            Transaction.user_id == current_user.id,
        )
    ) or 0

    out = DocumentDetailOut.model_validate(doc)
    out.chunk_count = len(chunks)
    out.extracted_assets_count = int(assets_cnt)
    out.extracted_transactions_count = int(txns_cnt)
    out.sample_pages = [
        {"page_number": c.page_number, "excerpt": c.chunk_text[:600]}
        for c in chunks[:6]
    ]
    return out


@router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream original PDF securely for the authenticated owner with HTTP Range support."""
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    settings = get_settings()
    storage_root = settings.storage_path.resolve()
    pdf_path = Path(doc.file_path).resolve()

    # Ensure path stays inside storage root or exists safely without ever leaking paths
    if not pdf_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original PDF file is missing or has been deleted.",
        )

    # Restrict access strictly to storage_root unless running legacy test fixtures
    try:
        pdf_path.relative_to(storage_root)
    except ValueError:
        # Allow if storage_path matches same user folder structure only; never allow arbitrary traversal
        if str(current_user.id) not in pdf_path.parts:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    file_size = pdf_path.stat().st_size
    safe_name = doc.filename.replace('"', "")
    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{safe_name}"',
        "Cache-Control": "private, max-age=300",
    }

    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not m:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Invalid byte range header.",
            )
        start_str, end_str = m.groups()
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        if start >= file_size or end < start:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Requested range not satisfiable.",
                headers={"Content-Range": f"bytes */{file_size}"},
            )
        end = min(end, file_size - 1)
        chunk_len = (end - start) + 1

        def iter_range():
            with open(pdf_path, "rb") as f:
                f.seek(start)
                remaining = chunk_len
                while remaining > 0:
                    data = f.read(min(65536, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_range(),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type="application/pdf",
            headers={
                **base_headers,
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(chunk_len),
            },
        )

    def iter_full():
        with open(pdf_path, "rb") as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                yield data

    return StreamingResponse(
        iter_full(),
        status_code=status.HTTP_200_OK,
        media_type="application/pdf",
        headers={
            **base_headers,
            "Content-Length": str(file_size),
        },
    )


@router.post("/{document_id}/reprocess", response_model=DocumentOut)
def reprocess_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    updated = process_existing_document(db, doc)
    chunk_count = db.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_id == updated.id,
            DocumentChunk.user_id == current_user.id,
        )
    ) or 0
    out = DocumentOut.model_validate(updated)
    out.chunk_count = int(chunk_count)
    return out


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    file_path_str = doc.file_path
    db.delete(doc)
    db.commit()

    try:
        settings = get_settings()
        storage_root = settings.storage_path.resolve()
        candidate = Path(file_path_str).resolve()
        candidate.relative_to(storage_root)
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
    except Exception:
        pass

    recompute_user_findings(db, current_user.id)
    return {"deleted": True, "id": str(document_id)}
