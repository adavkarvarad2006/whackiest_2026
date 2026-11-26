"""Document upload (single or multi-file), listing, inspection, deletion, and reprocessing endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Document, DocumentChunk, FinancialAsset, Finding, Transaction, User
from app.schemas import DocumentDetailOut, DocumentOut
from app.services.ingestion import ingest_uploaded_pdf, process_existing_document
from app.services.intelligence import recompute_user_findings

router = APIRouter(prefix="/api/documents", tags=["documents"])

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
    db.delete(doc)
    db.commit()
    recompute_user_findings(db, current_user.id)
    return {"deleted": True, "id": str(document_id)}
