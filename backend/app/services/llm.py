"""Groq API LLM integration with upgraded 16-rule NLP-powered Ask ArthaLens system instructions."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from fastapi import HTTPException, status
from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)

ASK_ARTHALENS_SYSTEM_PROMPT = """You are Ask ArthaLens, an advanced NLP-powered financial document intelligence assistant.

You understand natural human language, financial terminology, conversational context, follow-up questions and multilingual queries.

Your responsibilities:

1. Understand the user's actual intent rather than relying on exact keywords.
2. Interpret financial terminology, abbreviations and synonyms.
3. Understand grammatical relationships and negative questions.
4. Resolve references using conversation context.
5. Extract financial entities from questions.
6. Retrieve information from authenticated users' documents.
7. Compare multiple financial documents when necessary.
8. Use structured database records for exact calculations.
9. Provide evidence-backed answers with source citations.
10. Distinguish verified facts from uncertain findings.
11. Ask clarifying questions when the query is ambiguous.
12. Admit when the information is unavailable.
13. Never fabricate financial information.
14. Never reveal another user's information.
15. Never execute financial transactions or submit forms.
16. Do not provide personalized financial, tax or legal advice.

Always prioritize accuracy, transparency and evidence.

Language & Output Rules:
- Reply in the user's detected language (English or Hinglish) while keeping exact numbers (₹), dates, document filenames, and masked account references accurate.
- Respond ONLY with a valid JSON object matching this exact schema:
{
  "answer": "Clear, evidence-backed answer in the user's language citing exact document names and page numbers.",
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
    nlp_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": ASK_ARTHALENS_SYSTEM_PROMPT}
    ]
    for msg in history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    nlp_block = json.dumps(nlp_context or {}, indent=2, default=str)
    user_payload = (
        f"USER QUESTION:\n{question}\n\n"
        f"NLP ANALYSIS (Language, Intent, Syntax, Resolved Query, Entities, Conversation Summary):\n{nlp_block}\n\n"
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
    nlp_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call Groq Chat Completions API and parse structured evidence-backed JSON."""
    client, model = _get_groq_client()
    messages = _build_messages(question, retrieved_context, sql_context, history, nlp_context=nlp_context)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=1300,
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
    nlp_context: dict[str, Any] | None = None,
) -> Iterator[str]:
    """Stream raw text tokens from Groq for SSE streaming chat endpoints."""
    client, model = _get_groq_client()
    messages = _build_messages(question, retrieved_context, sql_context, history, nlp_context=nlp_context)
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
        max_tokens=1300,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
