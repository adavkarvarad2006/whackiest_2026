"""LangChain text splitting preserving customer_id, document_id, document_type, and page_number."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from pdf_parser import ExtractedPage


@dataclass
class DocumentChunkRecord:
    customer_id: str
    document_id: str
    document_type: str
    page_number: int
    chunk_index: int
    extracted_text: str
    metadata: dict[str, Any]


def chunk_extracted_pages(
    pages: list[ExtractedPage],
    customer_id: str,
    document_id: str,
    document_type: str,
    filename: str,
    chunk_size: int = 900,
    chunk_overlap: int = 125,
) -> list[DocumentChunkRecord]:
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " | ", ". ", " ", ""],
    )

    chunks: list[DocumentChunkRecord] = []
    idx = 0
    for page in pages:
        if not page.text.strip():
            continue
        for part in splitter.split_text(page.text):
            contextualized = f"[{customer_id} | {document_id} | {document_type} | Page {page.page_number}]\n{part}"
            chunks.append(
                DocumentChunkRecord(
                    customer_id=customer_id,
                    document_id=document_id,
                    document_type=document_type,
                    page_number=page.page_number,
                    chunk_index=idx,
                    extracted_text=contextualized,
                    metadata={
                        "customer_id": customer_id,
                        "document_id": document_id,
                        "document_type": document_type,
                        "filename": filename,
                        "page_number": page.page_number,
                    },
                )
            )
            idx += 1
    return chunks
