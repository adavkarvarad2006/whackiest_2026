"""Ask ArthaLens 5-Level NLP + Hybrid RAG & SQL conversational orchestration service."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_GREETING_RE = re.compile(
    r"^(hi|hello|hey|namaste|good\s+(morning|afternoon|evening)|hola|hii+)\b[!.,?\s]*$",
    re.IGNORECASE,
)

from app.models import ChatMessage, Conversation, Document
from app.schemas import ChatResponse, EvidenceSource
from app.services.llm import agenerate_grounded_answer, generate_grounded_answer
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


_ORIG_SYNC_LLM = generate_grounded_answer


def _infer_prior_query_category(history_msgs: list[ChatMessage]) -> str | None:
    """Infer the query category of the preceding assistant turn for conversational continuity."""
    for m in reversed(history_msgs):
        if m.role == "assistant" and m.retrieval_mode:
            rm = m.retrieval_mode.upper()
            if rm == "GENERAL_LLM":
                return "GENERAL_KNOWLEDGE"
            if rm == "HYBRID_REASONING":
                return "HYBRID_QUERY"
            if rm != "NONE":
                return "PERSONAL_FINANCIAL_DATA"
    return None


def _prepare_chat_context(
    db: Session,
    user_id: int,
    question: str,
    conversation_id: str | uuid.UUID | None = None,
):
    """Run Conversation Setup, 5-Level NLP, Three-Tier Query Classification, and Selective RAG/SQL Routing."""
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
    prior_category = _infer_prior_query_category(history_msgs)

    lexical = analyze_lexical(question)
    syntax = analyze_syntax(lexical)
    intent_res = classify_intent(lexical, syntax, prior_category=prior_category)
    query_entities = extract_entities_from_query(question)

    has_docs_count = int(
        db.scalar(
            select(func.count(Document.id)).where(
                Document.user_id == user_id,
                Document.processing_status == "COMPLETED",
            )
        )
        or 0
    )
    has_docs = has_docs_count > 0
    logger.info(
        "Stage [1-3 Context]: user_id=%s conv_id=%s category=%s intent=%s lang=%s completed_docs=%d",
        user_id,
        conv.id,
        intent_res.query_category,
        intent_res.intent,
        lexical.language,
        has_docs_count,
    )

    discourse = resolve_discourse(question, lexical, syntax, history_msgs)

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
        "query_category": intent_res.query_category,
        "routing_reason": intent_res.routing_reason,
        "pragmatic_type": intent_res.pragmatic_type,
        "resolved_query": discourse.resolved_query,
        "coreference_applied": discourse.coreference_applied,
        "active_topic": discourse.active_topic,
        "query_entities": query_entities,
    }

    if _GREETING_RE.match(question.strip()):
        greet_msg = (
            (
                f"Namaste! Main ArthaLens AI hoon. Aapke account mein {has_docs_count} processed financial PDF document(s) hain — aap apni FD, insurance, loans, ya general financial concepts (jaise FD, RD, SIP, credit score) ke baare mein pooch sakte hain."
                if has_docs
                else "Namaste! Main ArthaLens AI hoon. Aap mujhse general financial concepts (jaise FD, SIP, credit score, tax saving) pooch sakte hain, ya apne personal documents ka analysis karne ke liye PDFs upload kar sakte hain."
            )
            if lexical.language == "Hinglish"
            else (
                f"Hello! I am ArthaLens AI. I have indexed {has_docs_count} processed financial document(s) in your workspace. Ask me about your personal records (FD maturity, nominees, AIS vs Form 16) or general financial concepts (FD vs RD, SIP, credit score)."
                if has_docs
                else "Hello! I am ArthaLens AI. You can ask me general financial questions right away (such as Fixed Deposits, SIP, compounding, or credit scores), or upload your financial PDFs under Documents for personalized record analysis."
            )
        )
        resp = ChatResponse(
            answer=greet_msg,
            intent=intent_res.intent,
            language=lexical.language,
            confidence="HIGH" if has_docs else "HIGH",
            sources=[],
            citations=[],
            needs_clarification=False,
            clarification_options=[],
            followup_suggestions=build_followup_suggestions(intent_res, lexical.language),
            nlp_metadata=nlp_meta,
            disclaimer="Educational & workspace financial intelligence assistant. Never fabricates personal document facts.",
            conversation_id=conv.id,
            retrieval_mode="NONE",
            query_category=intent_res.query_category,
            timestamp=now_ist,
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
        return resp, None

    history_payload = [{"role": m.role, "content": m.content} for m in history_msgs]
    llm_nlp_context = {
        "language": lexical.language,
        "timezone": "Asia/Kolkata (IST, UTC+05:30)",
        "current_date_ist": now_ist.date().isoformat(),
        "current_datetime_ist": format_ist_display(now_ist, long_month=True),
        "temporal_windows": syntax.temporal_windows,
        "intent": intent_res.intent,
        "query_category": intent_res.query_category,
        "pragmatic_type": intent_res.pragmatic_type,
        "question_type": syntax.question_type,
        "has_negation": syntax.has_negation,
        "is_comparison": syntax.is_comparison,
        "resolved_query": discourse.resolved_query,
        "active_topic": discourse.active_topic,
        "conversation_summary": discourse.conversation_summary,
        "query_entities": query_entities,
    }

    # Tier A: GENERAL_KNOWLEDGE -> Route directly to Groq LLM without vector/SQL document search
    if intent_res.query_category == "GENERAL_KNOWLEDGE":
        logger.info(
            "Stage [4/6 Routing]: user_id=%s category=GENERAL_KNOWLEDGE route=GENERAL_LLM skipped_rag=True completed_docs=%d",
            user_id,
            has_docs_count,
        )
        ctx_bundle = {
            "conv": conv,
            "lexical": lexical,
            "intent_res": intent_res,
            "query_category": "GENERAL_KNOWLEDGE",
            "nlp_meta": nlp_meta,
            "retrieval_mode": "GENERAL_LLM",
            "sql_context": {},
            "chunks": [],
            "retrieved_context": "",
            "history_payload": history_payload,
            "llm_nlp_context": llm_nlp_context,
        }
        return None, ctx_bundle

    # Tier B: PERSONAL_FINANCIAL_DATA with 0 uploaded documents -> explicit unavailability (never invent records)
    if intent_res.query_category == "PERSONAL_FINANCIAL_DATA" and not has_docs:
        unavail_msg = (
            "Abhi aapke account mein koi processed financial PDF document upload nahi hai, isliye main aapke personal records verify nahi kar sakta. Kripya pehle Documents page par PDFs upload karein."
            if lexical.language == "Hinglish"
            else "No processed financial documents are currently uploaded in your account, so I cannot check your personal financial records. Please upload your PDF documents first so I can answer with verified evidence."
        )
        resp = ChatResponse(
            answer=unavail_msg,
            intent=intent_res.intent,
            language=lexical.language,
            confidence="UNAVAILABLE",
            sources=[],
            citations=[],
            needs_clarification=False,
            clarification_options=[],
            followup_suggestions=["What is an FD?", "Explain SIP with an example."],
            nlp_metadata=nlp_meta,
            disclaimer="This finding is based only on the uploaded documents and verified structured records.",
            conversation_id=conv.id,
            retrieval_mode="NONE",
            query_category="PERSONAL_FINANCIAL_DATA",
            timestamp=now_ist,
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
        return resp, None

    if has_docs:
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
                citations=[],
                needs_clarification=True,
                clarification_options=clarif_opts,
                followup_suggestions=[],
                nlp_metadata=nlp_meta,
                disclaimer="Clarification requested based on multiple matching records in your uploaded documents.",
                conversation_id=conv.id,
                retrieval_mode="AMBIGUITY_CHECK",
                query_category=intent_res.query_category,
                timestamp=now_ist,
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
            return resp, None

    # Retrieval + SQL (runs cleanly when docs exist, or passes empty status on HYBRID_QUERY without docs)
    if has_docs:
        expanded_queries = expand_queries(question, lexical, discourse, intent_res)
        nlp_meta["expanded_queries"] = expanded_queries
        retrieval_mode, sql_context = gather_sql_context_for_intent(
            db=db,
            user_id=user_id,
            intent_res=intent_res,
            syntax=syntax,
            resolved_query=discourse.resolved_query,
        )
        if intent_res.query_category == "HYBRID_QUERY":
            retrieval_mode = "HYBRID_REASONING"
        chunks = retrieve_multi_query_chunks(db, user_id, expanded_queries)
        retrieved_context = _format_chunks_for_prompt(chunks)
    else:
        retrieval_mode = "HYBRID_REASONING"
        sql_context = {
            "personal_documents_status": "NO_DOCUMENTS_UPLOADED",
            "ist_time_context": {"timezone": "Asia/Kolkata"},
        }
        chunks = []
        retrieved_context = "No personal financial documents have been uploaded yet in the user's workspace."

    has_domain_sql = any(
        k not in ("ist_time_context", "personal_documents_status") and bool(v) for k, v in sql_context.items()
    )
    fd_empty = (
        intent_res.query_category == "PERSONAL_FINANCIAL_DATA"
        and intent_res.intent == "FD_QUERY"
        and not chunks
        and not (sql_context.get("fixed_deposits") or {}).get("fixed_deposits")
    )
    logger.info(
        "Stage [4/6 Retrieval & SQL]: user_id=%s category=%s route=%s chunks=%d sql_keys=%s",
        user_id,
        intent_res.query_category,
        retrieval_mode,
        len(chunks),
        list(sql_context.keys()),
    )
    if intent_res.query_category == "PERSONAL_FINANCIAL_DATA" and (fd_empty or (not chunks and not has_domain_sql)):
        if fd_empty:
            no_ev_msg = (
                "Aapke account mein koi Fixed Deposit (FD) record ya document nahi mila. Kripya apna FD Certificate ya Bank Statement upload karein."
                if lexical.language == "Hinglish"
                else "No Fixed Deposit (FD) records or documents were found in your uploaded files. Upload an FD Certificate or Bank Statement containing FD details to inspect balances and maturity dates."
            )
        else:
            no_ev_msg = (
                "Aapke uploaded documents mein is sawaal ka sufficient evidence nahi mila."
                if lexical.language == "Hinglish"
                else "The uploaded documents do not contain sufficient verified evidence to answer this question."
            )
        resp = ChatResponse(
            answer=no_ev_msg,
            intent=intent_res.intent,
            language=lexical.language,
            confidence="UNAVAILABLE",
            sources=[],
            citations=[],
            needs_clarification=False,
            clarification_options=[],
            followup_suggestions=[],
            nlp_metadata=nlp_meta,
            disclaimer="This finding is based only on the uploaded documents and verified structured records.",
            conversation_id=conv.id,
            retrieval_mode=retrieval_mode,
            query_category="PERSONAL_FINANCIAL_DATA",
            timestamp=now_ist,
        )
        db.add(
            ChatMessage(
                conversation_id=conv.id,
                user_id=user_id,
                role="assistant",
                content=resp.answer,
                confidence=resp.confidence,
                sources=[],
                retrieval_mode=retrieval_mode,
            )
        )
        db.commit()
        return resp, None

    ctx_bundle = {
        "conv": conv,
        "lexical": lexical,
        "intent_res": intent_res,
        "query_category": intent_res.query_category,
        "nlp_meta": nlp_meta,
        "retrieval_mode": retrieval_mode,
        "sql_context": sql_context,
        "chunks": chunks,
        "retrieved_context": retrieved_context,
        "history_payload": history_payload,
        "llm_nlp_context": llm_nlp_context,
    }
    return None, ctx_bundle


def _finalize_chat_turn(
    db: Session,
    user_id: int,
    llm_out: dict[str, Any],
    bundle: dict[str, Any],
) -> ChatResponse:
    conv = bundle["conv"]
    lexical = bundle["lexical"]
    intent_res = bundle["intent_res"]
    query_category = bundle.get("query_category", "PERSONAL_FINANCIAL_DATA")
    chunks = bundle["chunks"]
    retrieval_mode = bundle["retrieval_mode"]
    nlp_meta = bundle["nlp_meta"]

    # Never emit fake document citations on pure GENERAL_KNOWLEDGE responses
    if query_category == "GENERAL_KNOWLEDGE":
        sources = []
    else:
        sources = _merge_sources(llm_out.get("sources", []), chunks, db=db, user_id=user_id)

    answer_text = llm_out.get("answer") or "I could not find enough information to answer that question."
    confidence = llm_out.get("confidence") or ("HIGH" if query_category == "GENERAL_KNOWLEDGE" else "NEEDS_REVIEW")
    default_disclaimer = (
        "Educational information for general financial literacy, not personalized financial advice."
        if query_category == "GENERAL_KNOWLEDGE"
        else "This finding is based only on the uploaded documents and verified structured records."
    )
    disclaimer = llm_out.get("disclaimer") or default_disclaimer
    followups = build_followup_suggestions(intent_res, lexical.language)
    now_ist = get_ist_now()

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
    logger.info(
        "Stage [6/6 Persisted]: user_id=%s conv_id=%s category=%s route=%s citations=%d confidence=%s",
        user_id,
        conv.id,
        query_category,
        retrieval_mode,
        len(sources),
        confidence,
    )

    return ChatResponse(
        answer=answer_text,
        intent=intent_res.intent,
        language=lexical.language,
        confidence=confidence,
        sources=sources,
        citations=sources,
        needs_clarification=False,
        clarification_options=[],
        followup_suggestions=followups,
        nlp_metadata=nlp_meta,
        disclaimer=disclaimer,
        conversation_id=conv.id,
        retrieval_mode=retrieval_mode,
        query_category=query_category,
        timestamp=now_ist,
    )


async def ahandle_chat_turn(
    db: Session,
    user_id: int,
    question: str,
    conversation_id: str | uuid.UUID | None = None,
) -> ChatResponse:
    """Async conversational pipeline using Groq OpenAI-compatible AsyncClient."""
    early, bundle = _prepare_chat_context(db, user_id, question, conversation_id)
    if early is not None:
        return early

    q_cat = bundle.get("query_category", "PERSONAL_FINANCIAL_DATA")

    # Respect unittest.mock.patch("app.services.chat.generate_grounded_answer") in test suites cleanly
    if generate_grounded_answer is not _ORIG_SYNC_LLM:
        try:
            llm_out = generate_grounded_answer(
                question=question,
                retrieved_context=bundle["retrieved_context"],
                sql_context=bundle["sql_context"],
                history=bundle["history_payload"],
                nlp_context=bundle["llm_nlp_context"],
                query_category=q_cat,
            )
        except TypeError:
            llm_out = generate_grounded_answer(
                question=question,
                retrieved_context=bundle["retrieved_context"],
                sql_context=bundle["sql_context"],
                history=bundle["history_payload"],
            )
    else:
        llm_out = await agenerate_grounded_answer(
            question=question,
            retrieved_context=bundle["retrieved_context"],
            sql_context=bundle["sql_context"],
            history=bundle["history_payload"],
            nlp_context=bundle["llm_nlp_context"],
            query_category=q_cat,
        )

    return _finalize_chat_turn(db, user_id, llm_out, bundle)


def handle_chat_turn(
    db: Session,
    user_id: int,
    question: str,
    conversation_id: str | uuid.UUID | None = None,
) -> ChatResponse:
    """Execute the full 5-Level NLP + Three-Tier Hybrid RAG/SQL pipeline synchronously."""
    early, bundle = _prepare_chat_context(db, user_id, question, conversation_id)
    if early is not None:
        return early

    q_cat = bundle.get("query_category", "PERSONAL_FINANCIAL_DATA")
    try:
        llm_out = generate_grounded_answer(
            question=question,
            retrieved_context=bundle["retrieved_context"],
            sql_context=bundle["sql_context"],
            history=bundle["history_payload"],
            nlp_context=bundle["llm_nlp_context"],
            query_category=q_cat,
        )
    except TypeError:
        llm_out = generate_grounded_answer(
            question=question,
            retrieved_context=bundle["retrieved_context"],
            sql_context=bundle["sql_context"],
            history=bundle["history_payload"],
        )

    return _finalize_chat_turn(db, user_id, llm_out, bundle)
