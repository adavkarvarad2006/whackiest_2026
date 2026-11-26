"""
Batch ingestion pipeline for all 500 synthetic PDFs in arthalens_dataset/.
Pipeline: PDF files -> PyMuPDF extraction -> Page preservation -> Text cleaning ->
          LangChain chunking -> all-MiniLM-L6-v2 embeddings -> PostgreSQL + pgvector (or SQLite fallback).
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
from pathlib import Path
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

INGESTION_DIR = Path(__file__).resolve().parent
DATASET_ROOT = INGESTION_DIR.parent
sys.path.insert(0, str(INGESTION_DIR))

from chunking import chunk_extracted_pages  # noqa: E402
from embeddings import generate_embeddings  # noqa: E402
from pdf_parser import extract_pdf_with_pages  # noqa: E402


class Base(DeclarativeBase):
    pass


class VectorType(TypeDecorator):
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
        return json.loads(value) if isinstance(value, str) else [float(x) for x in value]


class JSONBType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(JSONB()) if dialect.name == "postgresql" else dialect.type_descriptor(JSON())


class CustomerRow(Base):
    __tablename__ = "customers"
    customer_id = Column(String(32), primary_key=True)
    full_name = Column(String(150), nullable=False)
    age = Column(Integer, nullable=False)
    occupation = Column(String(120), nullable=False)
    employer = Column(String(200), nullable=False)
    city = Column(String(120), nullable=False)
    pan_masked = Column(String(32), nullable=False)
    profile_category = Column(String(60), nullable=False)


class RagDocumentRow(Base):
    __tablename__ = "rag_documents"
    document_id = Column(String(64), primary_key=True)
    customer_id = Column(String(32), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(80), nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_path = Column(String(512), nullable=False)
    page_count = Column(Integer, nullable=False)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())


class RagChunkRow(Base):
    __tablename__ = "rag_chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(32), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(64), ForeignKey("rag_documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(80), nullable=False)
    page_number = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=False)
    chunk_metadata = Column("metadata", JSONBType(), nullable=False, default=dict)
    embedding = Column(VectorType(384), nullable=False)


def ingest_dataset(database_url: str, batch_size: int = 25) -> dict[str, int]:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {"connect_timeout": 5}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_rag_chunks_hnsw ON rag_chunks USING hnsw (embedding vector_cosine_ops)"))

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    customers = json.loads((DATASET_ROOT / "metadata" / "customers.json").read_text(encoding="utf-8"))
    documents = json.loads((DATASET_ROOT / "metadata" / "documents.json").read_text(encoding="utf-8"))

    total_docs_ingested = 0
    total_chunks_stored = 0

    with SessionLocal() as db:
        # Upsert customers (never touching ground_truth.json!)
        existing_cids = set(db.scalars(select(CustomerRow.customer_id)))
        for c in customers:
            if c["customer_id"] not in existing_cids:
                db.add(CustomerRow(
                    customer_id=c["customer_id"],
                    full_name=c["full_name"],
                    age=c["age"],
                    occupation=c["occupation"],
                    employer=c["employer"],
                    city=c["city"],
                    pan_masked=c["pan"][:5] + "XXXX" + c["pan"][9:],
                    profile_category=c["archetype"],
                ))
        db.commit()

        existing_dids = set(db.scalars(select(RagDocumentRow.document_id)))
        pending_docs = [d for d in documents if d["document_id"] not in existing_dids]

        for start in range(0, len(pending_docs), batch_size):
            batch = pending_docs[start : start + batch_size]
            batch_chunks = []
            for d in batch:
                pdf_path = DATASET_ROOT / d["file_path"]
                pages = extract_pdf_with_pages(pdf_path)
                chunks = chunk_extracted_pages(
                    pages=pages,
                    customer_id=d["customer_id"],
                    document_id=d["document_id"],
                    document_type=d["document_type"],
                    filename=d["filename"],
                )
                db.add(RagDocumentRow(
                    document_id=d["document_id"],
                    customer_id=d["customer_id"],
                    filename=d["filename"],
                    document_type=d["document_type"],
                    file_hash=d["file_hash"],
                    file_path=d["file_path"],
                    page_count=len(pages),
                ))
                batch_chunks.extend(chunks)

            embeddings = generate_embeddings([c.extracted_text for c in batch_chunks], batch_size=64)
            for c, emb in zip(batch_chunks, embeddings):
                db.add(RagChunkRow(
                    customer_id=c.customer_id,
                    document_id=c.document_id,
                    document_type=c.document_type,
                    page_number=c.page_number,
                    chunk_index=c.chunk_index,
                    extracted_text=c.extracted_text,
                    chunk_metadata=c.metadata,
                    embedding=emb,
                ))
            db.commit()
            total_docs_ingested += len(batch)
            total_chunks_stored += len(batch_chunks)
            gc.collect()
            print(f"Ingested batch: +{len(batch)} docs (+{len(batch_chunks)} chunks), total docs={total_docs_ingested}")

        total_docs_db = db.scalar(select(func.count(RagDocumentRow.document_id)))
        total_chunks_db = db.scalar(select(func.count(RagChunkRow.id)))

    engine.dispose()
    return {"documents_in_db": int(total_docs_db or 0), "chunks_in_db": int(total_chunks_db or 0)}


def main():
    parser = argparse.ArgumentParser(description="Ingest all 500 PDFs into PostgreSQL + pgvector (or SQLite)")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL") or f"sqlite:///{(DATASET_ROOT / 'arthalens_rag.db').as_posix()}",
    )
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()
    stats = ingest_dataset(args.database_url, batch_size=args.batch_size)
    print("INGESTION COMPLETE:", stats)


if __name__ == "__main__":
    main()
