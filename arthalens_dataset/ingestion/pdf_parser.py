"""PyMuPDF text extraction with page preservation and table-safe whitespace cleaning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class ExtractedPage:
    page_number: int
    text: str


def extract_pdf_with_pages(pdf_path: Path) -> list[ExtractedPage]:
    """Extract selectable text page-by-page using PyMuPDF while preserving table rows."""
    doc = pymupdf.open(str(pdf_path))
    pages: list[ExtractedPage] = []
    try:
        for idx, page in enumerate(doc, start=1):
            raw = page.get_text("text") or ""
            # Normalize horizontal spacing while preserving line breaks and columns
            lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.splitlines()]
            cleaned = "\n".join(ln for ln in lines if ln)
            pages.append(ExtractedPage(page_number=idx, text=cleaned))
    finally:
        doc.close()
    return pages
