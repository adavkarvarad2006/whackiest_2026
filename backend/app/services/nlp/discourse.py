"""Level 4 NLP: Discourse tracking, coreference/pronoun resolution, and long-history summarization."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import ChatMessage
from app.services.nlp.lexical import LexicalAnalysis
from app.services.nlp.syntactic import SyntacticAnalysis


@dataclass
class DiscourseState:
    resolved_query: str
    active_topic: str | None
    referenced_documents: list[str]
    coreference_applied: bool
    conversation_summary: str


COREF_TRIGGERS = (
    r"\bit\b", r"\bits\b", r"\bthat\b", r"\bthis\b", r"\bthese\b", r"\bthose\b",
    r"\bthem\b", r"\bthey\b", r"\bwhich one\b", r"\bsame\b", r"\bprevious\b",
    r"\bthat account\b", r"\bthis policy\b", r"\bthat policy\b", r"\bthat investment\b",
    r"\bthat fd\b", r"\bthat loan\b", r"\bthis finding\b", r"\bwhat about\b",
    r"\biska\b", r"\buska\b", r"\buski\b", r"\biski\b", r"\bwo\b",
)


def _infer_topic_from_text(text: str) -> str | None:
    low = text.lower()
    if "recurring deposit" in low or re.search(r"\brd\b", low):
        return "fixed deposit and recurring deposit"
    if "fixed deposit" in low or "fd_certificate" in low or "demo-fd" in low or "mature" in low or re.search(r"\bfd\b", low):
        return "fixed deposit"
    if "credit score" in low or "cibil" in low:
        return "credit score"
    if "inflation" in low:
        return "inflation"
    if "compound interest" in low or "compounding" in low:
        return "compound interest"
    if "health insurance" in low:
        return "health insurance"
    if "insurance" in low or "policy" in low or "nominee" in low:
        return "life insurance policy"
    if "loan" in low or "emi" in low:
        return "personal loan"
    if "bank account" in low or "savings account" in low or "metrocivic" in low or "horizon trust" in low:
        return "savings bank account"
    if "form 16" in low or "form16" in low or "ais" in low or "salary" in low:
        return "AIS and Form 16 salary"
    if "subscription" in low or "streamflix" in low or "cloudnotes" in low:
        return "recurring subscriptions"
    if "mutual fund" in low or "sip" in low or "systematic investment" in low:
        return "SIP and mutual fund investment"
    if "tax-saving" in low or "tax saving" in low or "80c" in low or "elss" in low or "ppf" in low:
        return "tax-saving investments"
    return None


def _summarize_older_history(history_msgs: list[ChatMessage]) -> str:
    if len(history_msgs) <= 6:
        return ""
    older = history_msgs[:-6]
    topics: list[str] = []
    docs: list[str] = []
    for m in older:
        t = _infer_topic_from_text(m.content)
        if t and t not in topics:
            topics.append(t)
        for s in (m.sources or []):
            dname = s.get("filename") or s.get("document")
            if dname and dname not in docs:
                docs.append(str(dname))
    parts = []
    if topics:
        parts.append(f"Earlier topics discussed: {', '.join(topics)}.")
    if docs:
        parts.append(f"Earlier documents cited: {', '.join(docs)}.")
    return " ".join(parts)


def resolve_discourse(
    question: str,
    lexical: LexicalAnalysis,
    syntax: SyntacticAnalysis,
    history_msgs: list[ChatMessage],
) -> DiscourseState:
    """Resolve pronouns/anaphora and summarize extended conversation history."""
    if not history_msgs:
        return DiscourseState(
            resolved_query=lexical.normalized_text or question,
            active_topic=_infer_topic_from_text(lexical.normalized_text),
            referenced_documents=[],
            coreference_applied=False,
            conversation_summary="",
        )

    # Identify active topic & cited documents from most recent turns
    active_topic: str | None = None
    ref_docs: list[str] = []
    recent_snippets: list[str] = []
    for m in reversed(history_msgs[-6:]):
        if active_topic is None:
            active_topic = _infer_topic_from_text(m.content)
        for s in (m.sources or []):
            dname = str(s.get("filename") or s.get("document") or "")
            if dname and dname not in ref_docs:
                ref_docs.append(dname)
        recent_snippets.append(m.content[:140])

    norm = lexical.normalized_text
    has_coref = any(re.search(pat, question.lower()) or re.search(pat, norm) for pat in COREF_TRIGGERS)
    is_short_followup = len(question.split()) <= 7 and active_topic is not None

    resolved = norm or question
    coref_applied = False

    if (has_coref or is_short_followup) and active_topic:
        coref_applied = True
        # Rewrite pronouns explicitly into resolved context
        rewritten = norm
        rewritten = re.sub(r"\b(its|that|this|the same)\b", active_topic, rewritten)
        rewritten = re.sub(r"\b(it|them|they)\b", active_topic, rewritten)
        doc_hint = f" ({', '.join(ref_docs[:2])})" if ref_docs else ""
        if active_topic not in rewritten:
            resolved = f"{rewritten} regarding {active_topic}{doc_hint}"
        else:
            resolved = f"{rewritten}{doc_hint}"

    summary = _summarize_older_history(history_msgs)
    return DiscourseState(
        resolved_query=resolved,
        active_topic=active_topic or _infer_topic_from_text(resolved),
        referenced_documents=ref_docs,
        coreference_applied=coref_applied,
        conversation_summary=summary,
    )
