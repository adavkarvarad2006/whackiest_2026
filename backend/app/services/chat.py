"""Ask ArthaLens 5-Level NLP + Hybrid RAG & SQL conversational orchestration service."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, Conversation, Document
from app.schemas import ChatResponse, EvidenceSource
from app.services.llm import generate_grounded_answer
from app.services.nlp.discourse import resolve_discourse
from app.services.nlp.intent import classify_intent
from app.services.nlp.lexical import analyze_lexical
from app.services.nlp.ner import extract_entities_from_query
from app.services.nlp.query_expansion import (
    build_followup_suggestions,
    detect_ambiguity,
    expand_queries,
)
from app.services.nlp.syntactic import analyze_syntax
from app.services.retrieval import RetrievedChunk, retrieve_multi_query_chunks
from app.services.router_classifier import gather_sql_context_for_intent
from app.timezone_utils import format_ist_display, get_ist_now


def normalize_conversation_id(user_id: int, raw_id: str | uuid.UUID) -> uuid.UUID:
    """Parse UUID or deterministically derive one from client-generated conversation strings."""
    if isinstance(raw_id, uuid.UUID):
        return raw_id
    try:
        return uuid.UUID(str(raw_id))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"arthalens:{user_id}:{raw_id}")


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


def _merge_sources(
    llm_sources: list[dict[str, Any]],
    chunks: list[RetrievedChunk],
    db: Session | None = None,
    user_id: int | None = None,
) -> list[EvidenceSource]:
    """Validate and ground every cited source against retrieved chunks and user's real documents."""
    chunk_lookup = {(c.document_name.lower(), c.page_number): c for c in chunks}
    doc_id_by_name = {c.document_name.lower(): c.document_id for c in chunks}
    doc_pages_by_name: dict[str, int] = {}

    if db is not None and user_id is not None:
        user_docs = db.execute(
            select(Document.id, Document.filename, Document.page_count).where(
                Document.user_id == user_id,
                Document.processing_status == "COMPLETED",
            )
        ).all()
        for did, fname, pcount in user_docs:
            doc_id_by_name.setdefault(fname.lower(), did)
            doc_pages_by_name[fname.lower()] = int(pcount or 1)

    merged: list[EvidenceSource] = []
    seen: set[tuple[str, int]] = set()

    for s in llm_sources:
        doc_name = str(s.get("filename") or s.get("document") or "").strip()
        if not doc_name:
            continue
        # Evidence validation: reject fabricated filenames not owned by user or in retrieved chunks
        if doc_name.lower() not in doc_id_by_name:
            continue
        try:
            page = int(s.get("page_number") or s.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        max_p = doc_pages_by_name.get(doc_name.lower())
        if max_p and (page < 1 or page > max_p):
            page = 1

        evidence = str(s.get("evidence", "")).strip()
        key = (doc_name.lower(), page)
        if key in seen:
            continue
        seen.add(key)
        matched = chunk_lookup.get(key)
        resolved_name = matched.document_name if matched else doc_name
        resolved_id = matched.document_id if matched else doc_id_by_name.get(doc_name.lower())
        ev_text = evidence or (matched.chunk_text[:220] if matched else "")
        merged.append(
            EvidenceSource(
                document_id=resolved_id,
                filename=resolved_name,
                document=resolved_name,
                page_number=page,
                page=page,
                evidence=ev_text,
                snippet=ev_text,
                relevance_score=matched.combined_score if matched else None,
            )
        )

    if not merged and chunks:
        for c in chunks[:3]:
            snip = c.chunk_text[:240]
            merged.append(
                EvidenceSource(
                    document_id=c.document_id,
                    filename=c.document_name,
                    document=c.document_name,
                    page_number=c.page_number,
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
    """Execute the full 5-Level NLP + Hybrid RAG/SQL pipeline and persist conversation history."""
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

    # Levels 1-4 NLP Analysis (runs regardless of document presence for language & intent)
    lexical = analyze_lexical(question)
    syntax = analyze_syntax(lexical)
    intent_res = classify_intent(lexical, syntax)
    query_entities = extract_entities_from_query(question)

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

    discourse = resolve_discourse(question, lexical, syntax, history_msgs)

    # Persist user message
    db.add(
        ChatMessage(
            conversation_id=conv.id,
            user_id=user_id,
            role="user",
            content=question,
        )
    )
    db.commit()

    now_ist = get_ist_now()
    nlp_meta = {
        "language": lexical.language,
        "timezone": "Asia/Kolkata",
        "current_ist_time": format_ist_display(now_ist),
        "normalized_query": lexical.normalized_text,
        "expanded_abbreviations": lexical.expanded_abbreviations,
        "spell_corrections": lexical.spell_corrections,
        "question_type": syntax.question_type,
        "has_negation": syntax.has_negation,
        "is_comparison": syntax.is_comparison,
        "relation": syntax.relation,
        "temporal_windows": syntax.temporal_windows,
        "intent": intent_res.intent,
        "intent_confidence": intent_res.confidence,
        "pragmatic_type": intent_res.pragmatic_type,
        "resolved_query": discourse.resolved_query,
        "coreference_applied": discourse.coreference_applied,
        "active_topic": discourse.active_topic,
        "query_entities": query_entities,
    }

    if has_docs is None:
        unavail_msg = (
            "Abhi aapke account mein koi processed financial PDF document upload nahi hai. Kripya pehle documents upload karein."
            if lexical.language == "Hinglish"
            else "No processed financial documents are currently available in your account. Please upload one or more PDF documents first so I can answer with verified evidence."
        )
        resp = ChatResponse(
            answer=unavail_msg,
            intent=intent_res.intent,
            language=lexical.language,
            confidence="UNAVAILABLE",
            sources=[],
            needs_clarification=False,
            clarification_options=[],
            followup_suggestions=[],
            nlp_metadata=nlp_meta,
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

    # Ambiguity Detection (asks clarifying question when multiple matching assets exist)
    is_ambig, clarif_msg, clarif_opts = detect_ambiguity(
        db=db,
        user_id=user_id,
        question=question,
        lexical=lexical,
        syntax=syntax,
        intent_res=intent_res,
        discourse=discourse,
    )
    if is_ambig:
        resp = ChatResponse(
            answer=clarif_msg,
            intent=intent_res.intent,
            language=lexical.language,
            confidence="NEEDS_REVIEW",
            sources=[],
            needs_clarification=True,
            clarification_options=clarif_opts,
            followup_suggestions=[],
            nlp_metadata=nlp_meta,
            disclaimer="Clarification requested based on multiple matching records in your uploaded documents.",
            conversation_id=conv.id,
            retrieval_mode="AMBIGUITY_CHECK",
        )
        db.add(
            ChatMessage(
                conversation_id=conv.id,
                user_id=user_id,
                role="assistant",
                content=resp.answer,
                confidence=resp.confidence,
                sources=[],
                retrieval_mode="AMBIGUITY_CHECK",
            )
        )
        db.commit()
        return resp

    # Query Expansion + Hybrid Retrieval (Multi-Query Vector + Parameterized SQL)
    expanded_queries = expand_queries(question, lexical, discourse, intent_res)
    nlp_meta["expanded_queries"] = expanded_queries

    retrieval_mode, sql_context = gather_sql_context_for_intent(
        db=db,
        user_id=user_id,
        intent_res=intent_res,
        syntax=syntax,
        resolved_query=discourse.resolved_query,
    )
    chunks = retrieve_multi_query_chunks(db, user_id, expanded_queries)
    retrieved_context = _format_chunks_for_prompt(chunks)

    history_payload = [{"role": m.role, "content": m.content} for m in history_msgs]
    llm_nlp_context = {
        "language": lexical.language,
        "timezone": "Asia/Kolkata (IST, UTC+05:30)",
        "current_date_ist": now_ist.date().isoformat(),
        "current_datetime_ist": format_ist_display(now_ist, long_month=True),
        "temporal_windows": syntax.temporal_windows,
        "intent": intent_res.intent,
        "pragmatic_type": intent_res.pragmatic_type,
        "question_type": syntax.question_type,
        "has_negation": syntax.has_negation,
        "is_comparison": syntax.is_comparison,
        "resolved_query": discourse.resolved_query,
        "active_topic": discourse.active_topic,
        "conversation_summary": discourse.conversation_summary,
        "query_entities": query_entities,
    }

    # Support both 4-arg mocks in unit tests and 5-arg nlp_context in production
    try:
        llm_out = generate_grounded_answer(
            question=question,
            retrieved_context=retrieved_context,
            sql_context=sql_context,
            history=history_payload,
            nlp_context=llm_nlp_context,
        )
    except TypeError:
        llm_out = generate_grounded_answer(
            question=question,
            retrieved_context=retrieved_context,
            sql_context=sql_context,
            history=history_payload,
        )

    sources = _merge_sources(llm_out.get("sources", []), chunks, db=db, user_id=user_id)
    answer_text = llm_out.get("answer") or "I could not find enough information in the uploaded documents to answer that."
    confidence = llm_out.get("confidence") or "NEEDS_REVIEW"
    disclaimer = llm_out.get("disclaimer") or "This finding is based only on the uploaded documents and verified structured records."
    followups = build_followup_suggestions(intent_res, lexical.language)

    db.add(
        ChatMessage(
            conversation_id=conv.id,
            user_id=user_id,
            role="assistant",
            content=answer_text,
            confidence=confidence,
            sources=[s.model_dump() for s in sources],
            retrieval_mode=retrieval_mode,
        )
    )
    db.commit()

    return ChatResponse(
        answer=answer_text,
        intent=intent_res.intent,
        language=lexical.language,
        confidence=confidence,
        sources=sources,
        needs_clarification=False,
        clarification_options=[],
        followup_suggestions=followups,
        nlp_metadata=nlp_meta,
        disclaimer=disclaimer,
        conversation_id=conv.id,
        retrieval_mode=retrieval_mode,
    )
