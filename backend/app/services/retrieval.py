"""Semantic + hybrid keyword/pgvector retrieval engine with strict user_id isolation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document, DocumentChunk
from app.services.embeddings import embed_query


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_name: str
    document_type: str
    page_number: int
    chunk_text: str
    vector_score: float
    keyword_score: float
    combined_score: float


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _keyword_overlap_score(query: str, chunk_text: str) -> float:
    stopwords = {"what", "when", "where", "which", "have", "does", "with", "from", "this", "that", "your", "there", "many", "much", "about"}
    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", query.lower()) if t not in stopwords]
    if not tokens:
        return 0.0
    lower = chunk_text.lower()
    hits = 0
    unique_tokens = set(tokens)
    for tok in unique_tokens:
        stem = tok[:-1] if len(tok) > 4 and tok.endswith("s") else tok
        if tok in lower or stem in lower:
            hits += 1
    return hits / len(unique_tokens)


def retrieve_relevant_chunks(
    db: Session,
    user_id: int,
    query: str,
    top_k: Optional[int] = None,
    similarity_threshold: Optional[float] = None,
    hybrid: bool = True,
) -> list[RetrievedChunk]:
    """
    Retrieve top-K relevant document chunks strictly filtered by `user_id`.
    Uses native pgvector cosine distance + tsvector ranking on PostgreSQL.
    """
    settings = get_settings()
    k = top_k or settings.retrieval_top_k
    threshold = settings.similarity_threshold if similarity_threshold is None else similarity_threshold

    q_vec = embed_query(query)
    dialect_name = db.bind.dialect.name if db.bind is not None else "postgresql"

    results: list[RetrievedChunk] = []

    if dialect_name == "postgresql":
        # Native pgvector cosine distance + PostgreSQL full-text ts_rank_cd
        sql = text(
            """
            SELECT
                dc.id AS chunk_id,
                dc.document_id AS document_id,
                d.filename AS document_name,
                d.document_type AS document_type,
                dc.page_number AS page_number,
                dc.chunk_text AS chunk_text,
                (1.0 - (dc.embedding <=> CAST(:q_vec AS vector))) AS vector_score,
                COALESCE(ts_rank_cd(to_tsvector('english', dc.chunk_text), plainto_tsquery('english', :q_text)), 0.0) AS kw_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.user_id = :user_id
              AND d.user_id = :user_id
              AND d.processing_status = 'COMPLETED'
            ORDER BY (
                (1.0 - (dc.embedding <=> CAST(:q_vec AS vector)))
                + CASE WHEN :use_hybrid THEN 0.20 * LEAST(COALESCE(ts_rank_cd(to_tsvector('english', dc.chunk_text), plainto_tsquery('english', :q_text)), 0.0), 1.0) ELSE 0.0 END
            ) DESC
            LIMIT :fetch_k
            """
        )
        vec_literal = "[" + ",".join(f"{v:.6f}" for v in q_vec) + "]"
        rows = db.execute(
            sql,
            {
                "q_vec": vec_literal,
                "q_text": query,
                "user_id": user_id,
                "use_hybrid": hybrid,
                "fetch_k": max(k * 2, 12),
            },
        ).mappings()

        for row in rows:
            v_score = float(row["vector_score"])
            kw_score = min(float(row["kw_score"]), 1.0)
            combined = v_score + (0.20 * kw_score if hybrid else 0.0)
            if v_score >= threshold or (hybrid and kw_score >= 0.35):
                results.append(
                    RetrievedChunk(
                        chunk_id=int(row["chunk_id"]),
                        document_id=int(row["document_id"]),
                        document_name=str(row["document_name"]),
                        document_type=str(row["document_type"]),
                        page_number=int(row["page_number"]),
                        chunk_text=str(row["chunk_text"]),
                        vector_score=round(v_score, 4),
                        keyword_score=round(kw_score, 4),
                        combined_score=round(combined, 4),
                    )
                )
    else:
        # Dialect-safe fallback for SQLite unit tests (strictly filtered by user_id)
        stmt = (
            select(DocumentChunk, Document.filename, Document.document_type)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                Document.user_id == user_id,
                Document.processing_status == "COMPLETED",
            )
        )
        for chunk, fname, dtype in db.execute(stmt).all():
            v_score = _cosine_sim(q_vec, chunk.embedding)
            kw_score = _keyword_overlap_score(query, chunk.chunk_text) if hybrid else 0.0
            combined = v_score + (0.20 * kw_score if hybrid else 0.0)
            if v_score >= threshold or (hybrid and kw_score >= 0.35):
                results.append(
                    RetrievedChunk(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        document_name=fname,
                        document_type=dtype,
                        page_number=chunk.page_number,
                        chunk_text=chunk.chunk_text,
                        vector_score=round(v_score, 4),
                        keyword_score=round(kw_score, 4),
                        combined_score=round(combined, 4),
                    )
                )

    results.sort(key=lambda r: r.combined_score, reverse=True)
    return results[:k]
