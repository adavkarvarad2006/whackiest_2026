"""Ask ArthaLens conversational chat endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ChatMessage, Conversation, User
from app.schemas import ChatHistoryOut, ChatMessageOut, ChatRequest, ChatResponse, ConversationSummaryOut
from app.services.chat import handle_chat_turn, normalize_conversation_id

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
