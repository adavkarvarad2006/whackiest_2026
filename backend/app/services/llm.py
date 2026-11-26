"""Groq API LLM integration with Ask ArthaLens system instructions."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from fastapi import HTTPException, status
from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)

ASK_ARTHALENS_SYSTEM_PROMPT = """You are Ask ArthaLens, a financial document intelligence assistant.

Your responsibility is to analyze the user's uploaded financial documents and provide accurate, evidence-backed answers.

Rules:

1. Answer using retrieved document context and verified structured database records only.
2. Never fabricate financial information.
3. Never assume that an absent field proves something does not exist.
4. Clearly distinguish confirmed facts, potential findings and unverified information.
5. Cite the source document and page number for document-based claims.
6. If sources conflict, explain the discrepancy instead of silently choosing one.
7. If information cannot be found, explicitly say that it is unavailable in the uploaded documents.
8. Never reveal another user's information.
9. Never execute financial transactions or submit forms.
10. Do not provide legal, tax or investment advice.
11. Explain findings in simple, user-friendly language.
12. Do not present AI-generated assumptions as verified facts.

Output Format Requirement:
Respond ONLY with a valid JSON object matching this exact schema:
{
  "answer": "Clear, user-friendly, evidence-backed answer citing exact document names and page numbers.",
  "confidence": "HIGH | MEDIUM | NEEDS_REVIEW | UNAVAILABLE",
  "sources": [
    {
      "document": "exact_filename.pdf",
      "page": 1,
      "evidence": "Short verbatim or exact supporting snippet from the retrieved context."
    }
  ],
  "disclaimer": "This finding is based only on the uploaded documents and verified structured records."
}"""


def _get_groq_client() -> tuple[Groq, str]:
    settings = get_settings()
    api_key = (settings.groq_api_key or "").strip()
    if not api_key or api_key == "your_groq_api_key_here":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GROQ_API_KEY is not configured. Set GROQ_API_KEY in your .env file to enable Ask ArthaLens LLM inference.",
        )
    return Groq(api_key=api_key), settings.groq_model


def _build_messages(
    question: str,
    retrieved_context: str,
    sql_context: dict[str, Any],
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": ASK_ARTHALENS_SYSTEM_PROMPT}
    ]
    # Include recent conversation turns for follow-up support
    for msg in history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    user_payload = (
        f"USER QUESTION:\n{question}\n\n"
        f"RETRIEVED DOCUMENT CHUNKS (user-isolated):\n{retrieved_context or 'No matching document chunks retrieved.'}\n\n"
        f"VERIFIED STRUCTURED SQL RECORDS (user-isolated):\n{json.dumps(sql_context, indent=2, default=str)}\n\n"
        "Provide your grounded response as a single JSON object."
    )
    messages.append({"role": "user", "content": user_payload})
    return messages


def generate_grounded_answer(
    question: str,
    retrieved_context: str,
    sql_context: dict[str, Any],
    history: list[dict[str, str]],
) -> dict[str, Any]:
    """Call Groq Chat Completions API and parse structured evidence-backed JSON."""
    client, model = _get_groq_client()
    messages = _build_messages(question, retrieved_context, sql_context, history)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        return {
            "answer": str(parsed.get("answer", "")).strip(),
            "confidence": str(parsed.get("confidence", "NEEDS_REVIEW")).strip(),
            "sources": parsed.get("sources") or [],
            "disclaimer": str(
                parsed.get(
                    "disclaimer",
                    "This finding is based only on the uploaded documents and verified structured records.",
                )
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Groq inference failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Groq LLM inference error: {type(exc).__name__}",
        ) from exc


def stream_grounded_answer_tokens(
    question: str,
    retrieved_context: str,
    sql_context: dict[str, Any],
    history: list[dict[str, str]],
) -> Iterator[str]:
    """Stream raw text tokens from Groq for SSE streaming chat endpoints."""
    client, model = _get_groq_client()
    messages = _build_messages(question, retrieved_context, sql_context, history)
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=1200,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
