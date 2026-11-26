"""Ask ArthaLens conversational RAG + SQL orchestration service."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, Conversation, Document
from app.schemas import ChatResponse, EvidenceSource
from app.services.llm import generate_grounded_answer
from app.services.retrieval import RetrievedChunk, retrieve_relevant_chunks
from app.services.router_classifier import classify_and_gather_sql_context


def _expand_followup_query(question: str, history_msgs: list[ChatMessage]) -> str:
    """Enhance short follow-up questions with recent user/assistant context for retrieval."""
    q_lower = question.lower().strip()
    pronoun_triggers = ("this finding", "that", "it", "this", "these", "those", "them", "they", "which document", "why was")
    if history_msgs and (len(q_lower.split()) <= 9 or any(p in q_lower for p in pronoun_triggers)):
        recent = " ".join(m.content[:180] for m in history_msgs[-2:])
        return f"{question} | context: {recent}"
    return question


def _format_chunks_for_prompt(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    blocks = []
    for c in chunks:
        blocks.append(
            f"--- SOURCE: {c.document_name} (doc_id={c.document_id}, page={c.page_number}, score={c.combined_score}) ---\n"
            f"{c.chunk_text}"
        )
    return "\n\n".join(blocks)


def normalize_conversation_id(user_id: int, raw_id: str | uuid.UUID) -> uuid.UUID:
    """Parse UUID or deterministically derive one from client-generated conversation strings."""
    if isinstance(raw_id, uuid.UUID):
        return raw_id
    try:
        return uuid.UUID(str(raw_id))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"arthalens:{user_id}:{raw_id}")


def _merge_sources(
    llm_sources: list[dict[str, Any]],
    chunks: list[RetrievedChunk],
) -> list[EvidenceSource]:
    """Ensure every cited source maps to real retrieved document metadata & scores."""
    chunk_lookup = {(c.document_name.lower(), c.page_number): c for c in chunks}
    doc_id_by_name = {c.document_name.lower(): c.document_id for c in chunks}

    merged: list[EvidenceSource] = []
    seen: set[tuple[str, int]] = set()

    for s in llm_sources:
        doc_name = str(s.get("document", "")).strip()
        try:
            page = int(s.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        evidence = str(s.get("evidence", "")).strip()
        if not doc_name:
            continue
        key = (doc_name.lower(), page)
        if key in seen:
            continue
        seen.add(key)
        matched = chunk_lookup.get(key)
        ev_text = evidence or (matched.chunk_text[:220] if matched else "")
        merged.append(
            EvidenceSource(
                document_id=matched.document_id if matched else doc_id_by_name.get(doc_name.lower()),
                document=matched.document_name if matched else doc_name,
                page=page,
                evidence=ev_text,
                snippet=ev_text,
                relevance_score=matched.combined_score if matched else None,
            )
        )

    # If LLM returned no sources despite retrieved chunks, attach top retrieved evidence
    if not merged and chunks:
        for c in chunks[:3]:
            snip = c.chunk_text[:240]
            merged.append(
                EvidenceSource(
                    document_id=c.document_id,
                    document=c.document_name,
                    page=c.page_number,
                    evidence=snip,
                    snippet=snip,
                    relevance_score=c.combined_score,
                )
            )
    return merged


def handle_chat_turn(
    db: Session,
    user_id: int,
    question: str,
    conversation_id: str | uuid.UUID | None = None,
) -> ChatResponse:
    """Process a user question using hybrid RAG + SQL and persist conversation history."""
    if conversation_id is not None:
        conv_uuid = normalize_conversation_id(user_id, conversation_id)
        conv = db.get(Conversation, conv_uuid)
        if conv is not None and conv.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        if conv is None:
            conv = Conversation(
                id=conv_uuid,
                user_id=user_id,
                title=question[:80],
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
    else:
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=question[:80],
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Check if user has any completed documents
    has_docs = db.scalar(
        select(Document.id).where(
            Document.user_id == user_id,
            Document.processing_status == "COMPLETED",
        ).limit(1)
    )

    history_msgs = list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.user_id == user_id,
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
    )

    # Save user message
    user_msg = ChatMessage(
        conversation_id=conv.id,
        user_id=user_id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    db.commit()

    if has_docs is None:
        resp = ChatResponse(
            answer="No processed financial documents are currently available in your account. Please upload one or more PDF documents first so I can answer with verified evidence.",
            confidence="UNAVAILABLE",
            sources=[],
            disclaimer="This finding is based only on the uploaded documents and verified structured records.",
            conversation_id=conv.id,
            retrieval_mode="NONE",
        )
        db.add(
            ChatMessage(
                conversation_id=conv.id,
                user_id=user_id,
                role="assistant",
                content=resp.answer,
                confidence=resp.confidence,
                sources=[],
                retrieval_mode="NONE",
            )
        )
        db.commit()
        return resp

    retrieval_query = _expand_followup_query(question, history_msgs)
    retrieval_mode, sql_context = classify_and_gather_sql_context(db, user_id, retrieval_query)
    chunks = retrieve_relevant_chunks(db, user_id, retrieval_query)
    retrieved_context = _format_chunks_for_prompt(chunks)

    history_payload = [
        {"role": m.role, "content": m.content}
        for m in history_msgs
    ]

    llm_out = generate_grounded_answer(
        question=question,
        retrieved_context=retrieved_context,
        sql_context=sql_context,
        history=history_payload,
    )

    sources = _merge_sources(llm_out.get("sources", []), chunks)
    answer_text = llm_out.get("answer") or "I could not find enough information in the uploaded documents to answer that."
    confidence = llm_out.get("confidence") or "NEEDS_REVIEW"
    disclaimer = llm_out.get("disclaimer") or "This finding is based only on the uploaded documents and verified structured records."

    assistant_msg = ChatMessage(
        conversation_id=conv.id,
        user_id=user_id,
        role="assistant",
        content=answer_text,
        confidence=confidence,
        sources=[s.model_dump() for s in sources],
        retrieval_mode=retrieval_mode,
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        answer=answer_text,
        confidence=confidence,
        sources=sources,
        disclaimer=disclaimer,
        conversation_id=conv.id,
        retrieval_mode=retrieval_mode,
    )
