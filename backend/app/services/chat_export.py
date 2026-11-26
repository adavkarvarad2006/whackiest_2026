"""Secure in-memory Chat History Export service (PDF, TXT, JSON) for Ask ArthaLens."""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import ChatMessage, Conversation

# Register a Unicode-capable font supporting ₹ (INR) across Windows and Linux Docker
_FONTS_INITIALIZED = False
_FONT_REG = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _ensure_fonts() -> tuple[str, str]:
    global _FONTS_INITIALIZED, _FONT_REG, _FONT_BOLD
    if _FONTS_INITIALIZED:
        return _FONT_REG, _FONT_BOLD

    candidates = [
        (Path(r"C:\Windows\Fonts\segoeui.ttf"), Path(r"C:\Windows\Fonts\segoeuib.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]
    for reg_path, bold_path in candidates:
        if reg_path.exists() and bold_path.exists():
            try:
                pdfmetrics.registerFont(TTFont("ArthaExportReg", str(reg_path)))
                pdfmetrics.registerFont(TTFont("ArthaExportBold", str(bold_path)))
                _FONT_REG = "ArthaExportReg"
                _FONT_BOLD = "ArthaExportBold"
                break
            except Exception:
                continue
    _FONTS_INITIALIZED = True
    return _FONT_REG, _FONT_BOLD


def sanitize_filename_part(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", title or "Conversation").strip("_")
    return (cleaned[:48] or "Conversation")


def _normalize_source_item(raw: dict[str, Any]) -> dict[str, Any]:
    doc_name = str(raw.get("filename") or raw.get("document") or "Unknown Document")
    page_num = raw.get("page_number") or raw.get("page")
    evidence = str(raw.get("evidence") or raw.get("snippet") or "").strip()
    return {
        "document_id": raw.get("document_id"),
        "filename": doc_name,
        "page_number": page_num,
        "evidence": evidence,
    }


def _serialize_conversation(conv: Conversation, msgs: list[ChatMessage]) -> dict[str, Any]:
    return {
        "conversation_id": str(conv.id),
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "confidence": m.confidence,
                "sources": [_normalize_source_item(s) for s in (m.sources or [])],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }


def build_json_export(
    conversations_with_msgs: list[tuple[Conversation, list[ChatMessage]]],
    scope: str,
) -> bytes:
    exported_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "application": "ArthaLens",
        "subtitle": "Financial Document Intelligence",
        "export_scope": scope,
        "exported_at": exported_at,
        "conversation_count": len(conversations_with_msgs),
        "conversations": [_serialize_conversation(c, ms) for c, ms in conversations_with_msgs],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def build_txt_export(
    conversations_with_msgs: list[tuple[Conversation, list[ChatMessage]]],
) -> bytes:
    exported_str = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    lines: list[str] = [
        "ARTHALENS",
        "Financial Document Intelligence",
        f"Exported: {exported_str}",
        "=" * 72,
        "",
    ]

    if not conversations_with_msgs:
        lines.append("No conversations found for this account.")
        return "\n".join(lines).encode("utf-8")

    for idx, (conv, msgs) in enumerate(conversations_with_msgs, start=1):
        if idx > 1:
            lines.extend(["", "-" * 72, ""])
        lines.append(f"Conversation: {conv.title}")
        lines.append(f"Conversation ID: {conv.id}")
        if conv.created_at:
            lines.append(f"Created: {conv.created_at.strftime('%d %b %Y %H:%M UTC')}")
        lines.append("")

        if not msgs:
            lines.append("  (No messages recorded in this conversation.)")
            continue

        for m in msgs:
            ts = m.created_at.strftime("%d %b %Y %H:%M UTC") if m.created_at else "Unknown time"
            speaker = "USER" if m.role == "user" else "ASK ARTHALENS"
            lines.append(f"{speaker} [{ts}]:")
            lines.append(m.content)

            if m.role == "assistant":
                if m.confidence:
                    lines.append("")
                    lines.append("CONFIDENCE:")
                    lines.append(str(m.confidence).replace("_", " "))
                sources = [_normalize_source_item(s) for s in (m.sources or [])]
                if sources:
                    lines.append("")
                    lines.append("SOURCES:")
                    for s in sources:
                        pg_txt = f"Page {s['page_number']}" if s["page_number"] is not None else "Page N/A"
                        lines.append(f"- {s['filename']} ({pg_txt})")
                        if s["evidence"]:
                            lines.append(f"  Evidence: {s['evidence']}")
            lines.append("")

    return "\n".join(lines).encode("utf-8")


def build_pdf_export(
    conversations_with_msgs: list[tuple[Conversation, list[ChatMessage]]],
) -> bytes:
    f_reg, f_bold = _ensure_fonts()
    exported_str = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    st_title = ParagraphStyle("ExpTitle", fontName=f_bold, fontSize=16, leading=20, textColor=colors.white)
    st_sub = ParagraphStyle("ExpSub", fontName=f_reg, fontSize=8.5, leading=11, textColor=colors.HexColor("#D4D4D8"))
    st_conv_h = ParagraphStyle("ConvH", fontName=f_bold, fontSize=12, leading=16, textColor=colors.HexColor("#090909"), spaceBefore=6, spaceAfter=2)
    st_meta = ParagraphStyle("Meta", fontName=f_reg, fontSize=8, leading=11, textColor=colors.HexColor("#52525B"))
    st_role = ParagraphStyle("Role", fontName=f_bold, fontSize=8, leading=10, textColor=colors.HexColor("#111111"))
    st_body = ParagraphStyle("Body", fontName=f_reg, fontSize=9, leading=13, textColor=colors.HexColor("#18181B"))
    st_cite = ParagraphStyle("Cite", fontName=f_reg, fontSize=8, leading=11, textColor=colors.HexColor("#3F3F46"))

    buf = io.BytesIO()
    story: list[Any] = []

    banner = Table(
        [
            [Paragraph("ARTHALENS", st_title)],
            [Paragraph(f"Financial Document Intelligence  |  Chat History Export  |  Exported: {escape(exported_str)}", st_sub)],
        ],
        colWidths=[182 * mm],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#090909")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
    ]))
    story.append(banner)
    story.append(Spacer(1, 5 * mm))

    if not conversations_with_msgs:
        story.append(Paragraph("No conversations recorded for this account.", st_body))
    else:
        for idx, (conv, msgs) in enumerate(conversations_with_msgs):
            if idx > 0:
                story.append(PageBreak())

            story.append(Paragraph(escape(conv.title or "Untitled Conversation"), st_conv_h))
            created_txt = conv.created_at.strftime("%d %b %Y, %H:%M UTC") if conv.created_at else "N/A"
            story.append(Paragraph(f"Conversation ID: {escape(str(conv.id))}  |  Created: {escape(created_txt)}", st_meta))
            story.append(Spacer(1, 2.5 * mm))
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#E4E4E7")))
            story.append(Spacer(1, 3 * mm))

            if not msgs:
                story.append(Paragraph("No messages recorded in this conversation yet.", st_meta))
                continue

            for m in msgs:
                ts = m.created_at.strftime("%d %b %Y, %H:%M UTC") if m.created_at else ""
                is_user = m.role == "user"
                speaker = "USER" if is_user else "ASK ARTHALENS"
                conf_label = f"  |  CONFIDENCE: {escape(str(m.confidence).replace('_', ' '))}" if (not is_user and m.confidence) else ""

                msg_rows = [
                    [Paragraph(f"{speaker}  •  {escape(ts)}{conf_label}", st_role)],
                    [Paragraph(escape(m.content).replace("\n", "<br/>"), st_body)],
                ]

                if not is_user:
                    sources = [_normalize_source_item(s) for s in (m.sources or [])]
                    if sources:
                        cite_lines = ["<b>EVIDENCE &amp; SOURCES:</b>"]
                        for s in sources:
                            pg_txt = f"Page {s['page_number']}" if s["page_number"] is not None else "Page N/A"
                            doc_id_txt = f" [ID: {escape(str(s['document_id']))}]" if s["document_id"] is not None else ""
                            line = f"• <b>{escape(s['filename'])}</b> ({pg_txt}){doc_id_txt}"
                            if s["evidence"]:
                                line += f" — {escape(s['evidence'])}"
                            cite_lines.append(line)
                        msg_rows.append([Paragraph("<br/>".join(cite_lines), st_cite)])

                card = Table(msg_rows, colWidths=[182 * mm])
                card.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF" if is_user else "#F7F7F7")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#18181B" if is_user else "#D4D4D8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(card)
                story.append(Spacer(1, 3 * mm))

    def on_page(canvas, doc):
        canvas.saveState()
        w, _h = A4
        canvas.setStrokeColor(colors.HexColor("#E4E4E7"))
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 13 * mm, w - 14 * mm, 13 * mm)
        canvas.setFont(f_reg, 7.5)
        canvas.setFillColor(colors.HexColor("#71717A"))
        canvas.drawString(14 * mm, 9 * mm, "ArthaLens — Financial Document Intelligence (Private User Export)")
        canvas.drawRightString(w - 14 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=17 * mm,
        title="ArthaLens Chat History Export",
        author="ArthaLens",
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
