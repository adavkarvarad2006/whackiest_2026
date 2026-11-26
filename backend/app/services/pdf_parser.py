"""PyMuPDF extraction, table-preserving normalization, and LangChain chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings


@dataclass
class PageText:
    page_number: int
    raw_text: str
    cleaned_text: str


@dataclass
class ChunkPayload:
    chunk_index: int
    page_number: int
    chunk_text: str
    metadata: dict


def _clean_page_lines_preserving_tables(page: pymupdf.Page) -> tuple[str, str]:
    """
    Extract horizontal text from a PyMuPDF page while excluding diagonal watermarks
    and grouping spans on the same visual row so financial tables remain aligned.
    """
    raw_text = page.get_text("text") or ""
    page_dict = page.get_text("dict") or {}
    horizontal_spans: list[tuple[float, float, float, str]] = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            # Skip rotated diagonal watermark lines (dir != (1, 0))
            lx, ly = line.get("dir", (1.0, 0.0))
            if abs(ly) > 0.05 or lx < 0.9:
                continue
            for span in line.get("spans", []):
                txt = (span.get("text") or "").strip()
                if not txt:
                    continue
                # Also skip large faint watermark spans if horizontal
                if span.get("size", 0) >= 30:
                    continue
                x0, y0, x1, _y1 = span["bbox"]
                horizontal_spans.append((x0, y0, x1, txt))

    if not horizontal_spans:
        cleaned = re.sub(r"[ \t]+", " ", raw_text).strip()
        return raw_text, cleaned

    # Group spans into visual rows by y0 tolerance
    horizontal_spans.sort(key=lambda s: (round(s[1] / 3.5), s[0]))
    rows: list[list[tuple[float, float, float, str]]] = []
    for sp in horizontal_spans:
        if not rows:
            rows.append([sp])
            continue
        if abs(sp[1] - rows[-1][0][1]) <= 4.0:
            rows[-1].append(sp)
        else:
            rows.append([sp])

    rendered_lines: list[str] = []
    for row in rows:
        row.sort(key=lambda s: s[0])
        parts: list[str] = []
        prev_x1 = None
        for x0, _y0, x1, txt in row:
            if prev_x1 is not None and (x0 - prev_x1) > 10.0:
                parts.append(" | ")
            elif prev_x1 is not None:
                parts.append(" ")
            parts.append(txt)
            prev_x1 = x1
        line_str = "".join(parts).strip()
        if line_str:
            rendered_lines.append(line_str)

    cleaned = "\n".join(rendered_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return raw_text, cleaned


def extract_pdf_pages(file_path: Path) -> list[PageText]:
    """Extract text per page from a PDF using PyMuPDF."""
    doc = pymupdf.open(str(file_path))
    pages: list[PageText] = []
    try:
        for idx, page in enumerate(doc, start=1):
            raw_text, cleaned_text = _clean_page_lines_preserving_tables(page)
            pages.append(
                PageText(
                    page_number=idx,
                    raw_text=raw_text,
                    cleaned_text=cleaned_text,
                )
            )
    finally:
        doc.close()
    return pages


def detect_document_type(pages: list[PageText], filename: str = "") -> str:
    """Classify financial document type from page-1 header, extracted text, and filename."""
    header = (pages[0].cleaned_text[:600] if pages else "").lower()
    full_text = "\n".join(p.cleaned_text for p in pages).lower()
    fname = filename.lower()

    # Check Page 1 header first so cross-references in terms/notes never misclassify
    if "fixed deposit certificate" in header or "term deposit advice" in header:
        return "fixed_deposit_certificate"
    if "annual information statement" in header:
        return "annual_information_statement"
    if "form no. 16" in header or "section 203" in header:
        return "form_16"
    if "life insurance" in header or "policy schedule" in header:
        return "life_insurance_policy"
    if "personal loan" in header:
        return "personal_loan_statement"
    if "savings account statement" in header:
        return "bank_statement"

    if "fixed deposit" in full_text or "term deposit advice" in full_text:
        return "fixed_deposit_certificate"
    if "annual information statement" in full_text or ("sft-016" in full_text and "tds-192" in full_text):
        return "annual_information_statement"
    if "form no. 16" in full_text or ("section 203" in full_text and "chapter vi-a" in full_text):
        return "form_16"
    if "life insurance" in full_text or ("sum assured" in full_text and "nominee" in full_text and "policy" in full_text):
        return "life_insurance_policy"
    if "personal loan" in full_text or ("emi" in full_text and "outstanding" in full_text and "loan" in full_text):
        return "personal_loan_statement"
    if "savings account statement" in full_text or "transaction ledger" in full_text or "opening balance" in full_text:
        return "bank_statement"

    # Filename fallback
    if "ais" in fname:
        return "annual_information_statement"
    if "form_16" in fname or "form16" in fname:
        return "form_16"
    if "insurance" in fname or "policy" in fname:
        return "life_insurance_policy"
    if "fd" in fname or "deposit" in fname:
        return "fixed_deposit_certificate"
    if "loan" in fname:
        return "personal_loan_statement"
    if "bank" in fname or "statement" in fname:
        return "bank_statement"
    return "financial_document"


def chunk_pages(
    pages: list[PageText],
    document_type: str,
    filename: str,
) -> list[ChunkPayload]:
    """
    Split extracted pages using LangChain RecursiveCharacterTextSplitter (~800-1000 tokens,
    100-150 token overlap) while keeping table rows together and preserving page metadata.
    """
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=settings.chunk_size_tokens,
        chunk_overlap=settings.chunk_overlap_tokens,
        separators=["\n\n", "\n", " | ", ". ", " ", ""],
    )

    chunks: list[ChunkPayload] = []
    global_idx = 0
    for page in pages:
        if not page.cleaned_text.strip():
            continue
        split_texts = splitter.split_text(page.cleaned_text)
        for sub_idx, text_part in enumerate(split_texts):
            contextualized = (
                f"[Document: {filename} | Type: {document_type} | Page: {page.page_number}]\n"
                f"{text_part}"
            )
            chunks.append(
                ChunkPayload(
                    chunk_index=global_idx,
                    page_number=page.page_number,
                    chunk_text=contextualized,
                    metadata={
                        "filename": filename,
                        "document_type": document_type,
                        "page_number": page.page_number,
                        "page_subchunk_index": sub_idx,
                    },
                )
            )
            global_idx += 1
    return chunks
