"""Ask ArthaLens conversational chat endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ChatMessage, Conversation, Document, User
from app.schemas import ChatHistoryOut, ChatMessageOut, ChatRequest, ChatResponse, ConversationSummaryOut
from app.services.chat import handle_chat_turn, normalize_conversation_id
from app.services.chat_export import (
    build_json_export,
    build_pdf_export,
    build_txt_export,
    sanitize_filename_part,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat_endpoint(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return handle_chat_turn(
        db=db,
        user_id=current_user.id,
        question=payload.question.strip(),
        conversation_id=payload.conversation_id,
    )


@router.post("/stream")
def chat_stream_endpoint(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE endpoint returning grounded response events incrementally for UI streaming."""
    resp = handle_chat_turn(
        db=db,
        user_id=current_user.id,
        question=payload.question.strip(),
        conversation_id=payload.conversation_id,
    )

    def event_stream():
        words = resp.answer.split(" ")
        for i in range(0, len(words), 4):
            chunk_txt = " ".join(words[i : i + 4]) + (" " if i + 4 < len(words) else "")
            yield f"data: {json.dumps({'type': 'token', 'token': chunk_txt})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'payload': resp.model_dump(mode='json')})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/suggestions")
def get_suggested_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return document-aware English and Hinglish suggested questions for the authenticated user."""
    doc_types = set(
        db.scalars(
            select(Document.document_type).where(
                Document.user_id == current_user.id,
                Document.processing_status == "COMPLETED",
            )
        )
    )
    suggestions: list[str] = []
    if "life_insurance_policy" in doc_types:
        suggestions.append("Which policies don't have nominees?")
    if "annual_information_statement" in doc_types and "bank_statement" in doc_types:
        suggestions.append("Mere kaunse bank accounts missing hain?")
    if "annual_information_statement" in doc_types and "form_16" in doc_types:
        suggestions.append("AIS aur Form 16 mein koi mismatch hai kya?")
    if "fixed_deposit_certificate" in doc_types:
        suggestions.append("Mera FD kab mature hoga?")
    if "bank_statement" in doc_types:
        suggestions.append("Where is my money getting deducted every month?")
    if "personal_loan_statement" in doc_types:
        suggestions.append("Mera loan kitna outstanding hai?")
    suggestions.append("Am I financially prepared? Anything I should worry about?")

    if len(suggestions) < 4:
        suggestions = [
            "Do I have any missing nominees?",
            "Where is my money getting deducted every month?",
            "AIS aur Form 16 mein koi mismatch hai kya?",
            "Am I financially prepared?",
        ]
    return {"suggestions": suggestions[:6]}


@router.get("/conversations", response_model=list[ConversationSummaryOut])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convs = list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.updated_at.desc())
        )
    )
    return [ConversationSummaryOut.model_validate(c) for c in convs]


@router.get("/history")
def get_all_chat_history(
    conversation_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns ChatConversation[] formatted for Next.js frontend chat history sidebar."""
    stmt = select(Conversation).where(Conversation.user_id == current_user.id)
    if conversation_id:
        cid_uuid = normalize_conversation_id(current_user.id, conversation_id)
        stmt = stmt.where(Conversation.id == cid_uuid)
    convs = list(db.scalars(stmt.order_by(Conversation.updated_at.desc())))

    results = []
    for c in convs:
        msgs = list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == c.id, ChatMessage.user_id == current_user.id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            )
        )
        results.append({
            "conversation_id": str(c.id),
            "title": c.title,
            "updated_at": c.updated_at.isoformat(),
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "confidence": m.confidence,
                    "sources": m.sources,
                    "created_at": m.created_at.isoformat(),
                }
                for m in msgs
            ],
        })
    return results


def _render_export_response(
    conversations_with_msgs: list[tuple[Conversation, list[ChatMessage]]],
    export_format: str,
    filename_stem: str,
    scope: str,
) -> Response:
    fmt = export_format.lower().strip()
    if fmt == "pdf":
        content = build_pdf_export(conversations_with_msgs)
        media_type = "application/pdf"
        ext = "pdf"
    elif fmt == "txt":
        content = build_txt_export(conversations_with_msgs)
        media_type = "text/plain; charset=utf-8"
        ext = "txt"
    elif fmt == "json":
        content = build_json_export(conversations_with_msgs, scope=scope)
        media_type = "application/json; charset=utf-8"
        ext = "json"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export format. Allowed formats: pdf, txt, json.",
        )

    safe_filename = f"{filename_stem}.{ext}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "X-Export-Filename": safe_filename,
            "Cache-Control": "no-store",
        },
    )


@router.get("/history/export-all")
def export_all_conversations(
    format: str = Query(default="pdf"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all conversations belonging strictly to the authenticated user."""
    convs = list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.created_at.asc(), Conversation.id.asc())
        )
    )
    bundles: list[tuple[Conversation, list[ChatMessage]]] = []
    for c in convs:
        msgs = list(
            db.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.conversation_id == c.id,
                    ChatMessage.user_id == current_user.id,
                )
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            )
        )
        bundles.append((c, msgs))

    stem = "ArthaLens_Chat_History" if format.lower().strip() == "txt" else "ArthaLens_All_Conversations"
    return _render_export_response(bundles, format, stem, scope="all_conversations")


@router.get("/history/{conversation_id}/export")
def export_single_conversation(
    conversation_id: str,
    format: str = Query(default="pdf"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export one conversation belonging strictly to the authenticated user."""
    cid_uuid = normalize_conversation_id(current_user.id, conversation_id)
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == cid_uuid,
            Conversation.user_id == current_user.id,
        )
    )
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    msgs = list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.user_id == current_user.id,
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
    )
    stem = f"ArthaLens_Chat_{sanitize_filename_part(conv.title)}"
    return _render_export_response([(conv, msgs)], format, stem, scope="single_conversation")


@router.get("/history/{conversation_id}", response_model=ChatHistoryOut)
def get_chat_history(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid_uuid = normalize_conversation_id(current_user.id, conversation_id)
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == cid_uuid,
            Conversation.user_id == current_user.id,
        )
    )
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    msgs = list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.user_id == current_user.id,
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
    )
    return ChatHistoryOut(
        conversation_id=conv.id,
        title=conv.title,
        messages=[ChatMessageOut.model_validate(m) for m in msgs],
    )


@router.delete("/history/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete one conversation and all its messages for the authenticated user."""
    cid_uuid = normalize_conversation_id(current_user.id, conversation_id)
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == cid_uuid,
            Conversation.user_id == current_user.id,
        )
    )
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    db.delete(conv)
    db.commit()
    return {"deleted": True, "conversation_id": str(cid_uuid)}
