"""Comprehensive end-to-end test suite for ArthaLens RAG + Hybrid SQL backend."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
DATASET_DOCS = Path(__file__).resolve().parents[1] / "ArthaLens_Demo_Dataset" / "Documents"
sys.path.insert(0, str(BACKEND_DIR))

_TEST_TMP = Path(tempfile.mkdtemp(prefix="arthalens_pytest_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_TMP / 'test.db'}"
os.environ["UPLOAD_STORAGE_DIR"] = str(_TEST_TMP / "uploads")
os.environ["ARTHALENS_REFERENCE_DATE"] = "2026-05-15"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import sql_analytics  # noqa: E402
from app.services.retrieval import retrieve_relevant_chunks  # noqa: E402


@pytest.fixture(scope="module")
def client_and_db():
    test_engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, TestingSessionLocal
    app.dependency_overrides.clear()


def _register_and_auth(client: TestClient, name: str, email: str) -> dict[str, str]:
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "SecurePassword123!"},
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_01_authentication_required(client_and_db):
    client, _ = client_and_db
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/findings").status_code == 401
    assert client.post("/api/chat", json={"question": "Hello"}).status_code == 401


def test_02_invalid_file_validation(client_and_db):
    client, _ = client_and_db
    headers = _register_and_auth(client, "Ananya Sharma", "ananya.test@example.com")

    # Non-PDF extension
    res1 = client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert res1.status_code == 400

    # Fake PDF magic header
    res2 = client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("fake.pdf", b"not a pdf body", "application/pdf")},
    )
    assert res2.status_code == 400


def test_03_ingest_all_six_pdfs_and_prevent_duplicates(client_and_db):
    client, _ = client_and_db
    login = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    pdf_names = [
        "Bank_Statement.pdf",
        "AIS_Report.pdf",
        "Form_16.pdf",
        "Insurance_Policy.pdf",
        "FD_Certificate.pdf",
        "Loan_Statement.pdf",
    ]
    uploaded_ids = []
    for name in pdf_names:
        pdf_path = DATASET_DOCS / name
        with open(pdf_path, "rb") as f:
            res = client.post(
                "/api/documents/upload",
                headers=headers,
                files={"file": (name, f, "application/pdf")},
            )
        assert res.status_code == 201, f"{name}: {res.text}"
        body = res.json()
        assert body["processing_status"] == "COMPLETED"
        assert body["chunk_count"] >= 1
        uploaded_ids.append(body["id"])

    # Duplicate upload must be rejected (409)
    with open(DATASET_DOCS / "Bank_Statement.pdf", "rb") as f:
        dup = client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("Bank_Statement.pdf", f, "application/pdf")},
        )
    assert dup.status_code == 409

    # Reprocess works cleanly
    rep = client.post(f"/api/documents/{uploaded_ids[0]}/reprocess", headers=headers)
    assert rep.status_code == 200
    assert rep.json()["processing_status"] == "COMPLETED"


def test_04_extracted_assets_masking_and_nominee_status(client_and_db):
    client, _ = client_and_db
    login = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assets = client.get("/api/assets", headers=headers).json()
    assert len(assets) >= 8

    # Ensure raw unmasked full bank account string is masked
    sb = [a for a in assets if a["asset_type"] == "SAVINGS_ACCOUNT"][0]
    assert "X" in (sb["account_reference"] or "")
    assert "1004582910" not in (sb["account_reference"] or "")

    # Missing nominee must be NEEDS_VERIFICATION, never NO_NOMINEE
    ins = [a for a in assets if a["asset_type"] == "LIFE_INSURANCE"][0]
    assert ins["nominee_status"] == "NEEDS_VERIFICATION"
    assert ins["page_number"] == 2


def test_05_cross_document_findings_and_sql_analytics(client_and_db):
    client, SessionLocal = client_and_db
    login = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user_id = login.json()["user"]["id"]

    findings = client.get("/api/findings", headers=headers).json()
    ftypes = {f["finding_type"]: f for f in findings}

    for f in findings:
        assert isinstance(f.get("recommended_steps"), list) and len(f["recommended_steps"]) >= 1
        assert isinstance(f.get("evidence"), dict)

    assert "GAP_UNDISCOVERED_ACCOUNT" in ftypes
    assert ftypes["GAP_UNDISCOVERED_ACCOUNT"]["raw_severity"] == "AMBER"
    assert "GAP_MISSING_NOMINEE" in ftypes
    assert ftypes["GAP_MISSING_NOMINEE"]["raw_severity"] == "RED"
    assert ftypes["GAP_MISSING_NOMINEE"]["evidence"]["page_number"] == 2
    assert ftypes["GAP_MISSING_NOMINEE"]["evidence_items"][0]["page"] == 2
    assert "LEAK_RECURRING_SUBSCRIPTIONS" in ftypes
    assert "RISK_SALARY_DISCREPANCY" in ftypes
    assert "RISK_UPCOMING_FD_MATURITY" in ftypes
    assert "RECONCILED_LOAN_EMI" in ftypes

    with SessionLocal() as db:
        bank_sum = sql_analytics.sql_bank_accounts_summary(db, user_id)
        assert bank_sum["distinct_bank_accounts_count"] == 2

        subs = sql_analytics.sql_subscription_and_recurring_expenses(db, user_id)
        assert subs["annual_subscriptions_inr"] == 16164.0
        assert subs["monthly_subscriptions_inr"] == 1347.0
        assert subs["bank_fees_annual_inr"] == 770.0

        sal = sql_analytics.sql_ais_vs_form16_comparison(db, user_id)
        assert sal["gross_salary_difference_inr"] == 18000.0

        fds = sql_analytics.sql_upcoming_fd_maturities(db, user_id)
        assert fds["fixed_deposits"][0]["days_remaining_from_reference"] == 41

        loan = sql_analytics.sql_loan_and_emi_reconciliation(db, user_id)
        assert loan["bank_statement_emi_debits_count"] == 12
        assert abs(loan["bank_statement_emi_avg_inr"] - 14689.84) < 0.01


def test_06_semantic_retrieval_and_user_isolation(client_and_db):
    client, SessionLocal = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    user_a_id = login_a.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Create second user B
    headers_b = _register_and_auth(client, "Other User", "other.user@example.com")
    me_b = client.get("/api/auth/me", headers=headers_b).json()
    user_b_id = me_b["id"]

    # User B must see 0 documents, 0 findings, 0 assets
    assert client.get("/api/documents", headers=headers_b).json() == []
    assert client.get("/api/findings", headers=headers_b).json() == []
    assert client.get("/api/assets", headers=headers_b).json() == []

    # User B cannot access User A's document ID
    docs_a = client.get("/api/documents", headers=headers_a).json()
    assert client.get(f"/api/documents/{docs_a[0]['id']}", headers=headers_b).status_code == 404

    with SessionLocal() as db:
        # User A retrieval finds Nominee section on Insurance_Policy.pdf page 2
        res_a = retrieve_relevant_chunks(db, user_a_id, "nominee details in life insurance policy")
        assert any(r.document_name == "Insurance_Policy.pdf" and r.page_number == 2 for r in res_a)

        # User B retrieval returns 0 chunks (strict isolation)
        res_b = retrieve_relevant_chunks(db, user_b_id, "nominee details in life insurance policy")
        assert res_b == []


def test_07_chat_endpoint_followups_and_empty_user_admission(client_and_db):
    client, _ = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    login_b = client.post(
        "/api/auth/login",
        json={"email": "other.user@example.com", "password": "SecurePassword123!"},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # User B with no documents gets UNAVAILABLE admission without calling LLM
    empty_chat = client.post(
        "/api/chat",
        headers=headers_b,
        json={"question": "What is my salary?"},
    )
    assert empty_chat.status_code == 200
    assert empty_chat.json()["confidence"] == "UNAVAILABLE"

    # User A chat turn 1 + follow-up turn 2 (using real retrieval + real SQL; mock only external Groq call)
    mocked_llm_reply = {
        "answer": "Nominee information is not recorded in Section 4 on Page 2 of Insurance_Policy.pdf.",
        "confidence": "NEEDS_REVIEW",
        "sources": [
            {
                "document": "Insurance_Policy.pdf",
                "page": 2,
                "evidence": "SECTION 4 – NOMINEE DETAILS: Nominee Full Name is blank.",
            }
        ],
        "disclaimer": "This finding is based only on the uploaded documents and verified structured records.",
    }

    with patch("app.services.chat.generate_grounded_answer", return_value=mocked_llm_reply):
        c1 = client.post(
            "/api/chat",
            headers=headers_a,
            json={"question": "Do I have any missing nominees?"},
        )
        assert c1.status_code == 200
        body1 = c1.json()
        conv_id = body1["conversation_id"]
        assert body1["confidence"] == "NEEDS_REVIEW"
        assert body1["sources"][0]["document"] == "Insurance_Policy.pdf"
        assert body1["sources"][0]["filename"] == "Insurance_Policy.pdf"
        assert body1["sources"][0]["page"] == 2
        assert body1["sources"][0]["page_number"] == 2
        assert body1["sources"][0]["document_id"] is not None

        # Follow-up question on same conversation
        c2 = client.post(
            "/api/chat",
            headers=headers_a,
            json={"question": "Which document supports this finding?", "conversation_id": conv_id},
        )
        assert c2.status_code == 200

    # History endpoint returns both turns
    hist = client.get(f"/api/chat/history/{conv_id}", headers=headers_a)
    assert hist.status_code == 200
    assert len(hist.json()["messages"]) == 4

    # User B cannot read User A's conversation history
    assert client.get(f"/api/chat/history/{conv_id}", headers=headers_b).status_code == 404


def test_08_citation_to_pdf_streaming_and_range_requests(client_and_db):
    client, _ = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    login_b = client.post(
        "/api/auth/login",
        json={"email": "other.user@example.com", "password": "SecurePassword123!"},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    docs_a = client.get("/api/documents", headers=headers_a).json()
    ins_doc = next(d for d in docs_a if d["filename"] == "Insurance_Policy.pdf")
    doc_id = ins_doc["id"]

    # Unauthenticated request must fail
    assert client.get(f"/api/documents/{doc_id}/file").status_code == 401

    # Another user must not be able to access User A's PDF
    assert client.get(f"/api/documents/{doc_id}/file", headers=headers_b).status_code == 404

    # Full PDF fetch returns application/pdf and exact original PDF bytes
    full_res = client.get(f"/api/documents/{doc_id}/file", headers=headers_a)
    assert full_res.status_code == 200
    assert full_res.headers["content-type"].startswith("application/pdf")
    assert full_res.headers.get("accept-ranges") == "bytes"
    assert full_res.content[:5] == b"%PDF-"
    expected_bytes = (DATASET_DOCS / "Insurance_Policy.pdf").read_bytes()
    assert full_res.content == expected_bytes

    # HTTP Range request returns 206 Partial Content with Content-Range header
    range_res = client.get(
        f"/api/documents/{doc_id}/file",
        headers={**headers_a, "Range": "bytes=0-1023"},
    )
    assert range_res.status_code == 206
    assert range_res.headers["content-range"] == f"bytes 0-1023/{len(expected_bytes)}"
    assert range_res.content == expected_bytes[:1024]


def test_09_chat_history_export_formats_special_chars_and_isolation(client_and_db):
    import json
    import uuid
    import pymupdf
    from app.models import ChatMessage, Conversation

    client, SessionLocal = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    user_a_id = login_a.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    login_b = client.post(
        "/api/auth/login",
        json={"email": "other.user@example.com", "password": "SecurePassword123!"},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Create a special-char + INR currency conversation AND an empty conversation for User A
    special_conv_id = uuid.uuid4()
    empty_conv_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(Conversation(id=special_conv_id, user_id=user_a_id, title="AIS & Form 16 — ₹18,000 Check"))
        db.add(ChatMessage(
            conversation_id=special_conv_id,
            user_id=user_a_id,
            role="user",
            content="Compare AIS ₹11,60,400 & Form 16 <₹11,42,400>?",
        ))
        db.add(ChatMessage(
            conversation_id=special_conv_id,
            user_id=user_a_id,
            role="assistant",
            content="AIS reports ₹11,60,400.00 vs Form 16 ₹11,42,400.00 (diff ₹18,000.00).",
            confidence="NEEDS_REVIEW",
            sources=[{"document_id": 2, "filename": "AIS_Report.pdf", "document": "AIS_Report.pdf", "page_number": 1, "page": 1, "evidence": "Total Reported Salary: ₹11,60,400.00"}],
        ))
        db.add(Conversation(id=empty_conv_id, user_id=user_a_id, title="Empty Thread"))
        db.commit()

    # 1. Single conversation PDF export (with citations & INR ₹)
    pdf_res = client.get(f"/api/chat/history/{special_conv_id}/export?format=pdf", headers=headers_a)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"].startswith("application/pdf")
    assert pdf_res.content[:5] == b"%PDF-"
    pdf_doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
    pdf_text = "\n".join(p.get_text() for p in pdf_doc)
    pdf_doc.close()
    assert "ARTHALENS" in pdf_text
    assert "AIS_Report.pdf" in pdf_text
    assert "Page 1" in pdf_text
    assert "₹11,60,400.00" in pdf_text

    # 2. Single conversation TXT export
    txt_res = client.get(f"/api/chat/history/{special_conv_id}/export?format=txt", headers=headers_a)
    assert txt_res.status_code == 200
    txt_body = txt_res.content.decode("utf-8")
    assert "ARTHALENS" in txt_body
    assert "AIS_Report.pdf (Page 1)" in txt_body
    assert "₹18,000.00" in txt_body

    # 3. Single conversation JSON export
    json_res = client.get(f"/api/chat/history/{special_conv_id}/export?format=json", headers=headers_a)
    assert json_res.status_code == 200
    json_body = json.loads(json_res.content.decode("utf-8"))
    assert json_body["application"] == "ArthaLens"
    assert json_body["conversations"][0]["messages"][1]["sources"][0]["filename"] == "AIS_Report.pdf"

    # 4. Empty conversation export works cleanly across formats
    for fmt in ("pdf", "txt", "json"):
        empty_res = client.get(f"/api/chat/history/{empty_conv_id}/export?format={fmt}", headers=headers_a)
        assert empty_res.status_code == 200

    # 5. Export All Conversations (pdf, txt, json)
    for fmt in ("pdf", "txt", "json"):
        all_res = client.get(f"/api/chat/history/export-all?format={fmt}", headers=headers_a)
        assert all_res.status_code == 200

    # 6. User B isolation: cannot export User A's conversation and export-all excludes User A's threads
    assert client.get(f"/api/chat/history/{special_conv_id}/export?format=json", headers=headers_b).status_code == 404
    b_all = json.loads(client.get("/api/chat/history/export-all?format=json", headers=headers_b).content.decode("utf-8"))
    assert all(c["conversation_id"] != str(special_conv_id) for c in b_all["conversations"])


def test_10_five_level_nlp_hinglish_coreference_ambiguity_and_pragmatic(client_and_db):
    from sqlalchemy import func, select
    from app.models import ExtractedEntityRecord
    from app.services.nlp.intent import classify_intent
    from app.services.nlp.lexical import analyze_lexical
    from app.services.nlp.syntactic import analyze_syntax

    client, SessionLocal = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    user_a_id = login_a.json()["user"]["id"]
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Verify NER entities persisted in database during ingestion
    with SessionLocal() as db:
        ent_count = db.scalar(
            select(func.count(ExtractedEntityRecord.id)).where(ExtractedEntityRecord.user_id == user_a_id)
        )
        assert ent_count and ent_count >= 10

    # Level 1: Spell correction + abbreviations + Hinglish detection
    lex_typo = analyze_lexical("Show insurence FD and EMI details")
    assert lex_typo.spell_corrections.get("insurence") == "insurance"
    assert any("FD ->" in x for x in lex_typo.expanded_abbreviations)
    assert any("EMI ->" in x for x in lex_typo.expanded_abbreviations)

    # Level 2 + Level 3: Negative syntactic equivalence for nominee queries
    for q in (
        "Which policies don't have nominees?",
        "Show me policies where nominee details are unavailable.",
        "Are any of my insurance policies missing nominee information?",
    ):
        lx = analyze_lexical(q)
        sx = analyze_syntax(lx)
        ir = classify_intent(lx, sx)
        assert sx.has_negation is True
        assert sx.relation == "missing_nominee"
        assert ir.intent == "NOMINEE_QUERY"

    # Level 3: Semantic idioms
    ir_sub = classify_intent(
        analyze_lexical("Where is my money getting deducted every month?"),
        analyze_syntax(analyze_lexical("Where is my money getting deducted every month?")),
    )
    assert ir_sub.intent in ("SUBSCRIPTION_QUERY", "EXPENSE_QUERY")

    ir_nom = classify_intent(
        analyze_lexical("Who gets my insurance money if something happens to me?"),
        analyze_syntax(analyze_lexical("Who gets my insurance money if something happens to me?")),
    )
    assert ir_nom.intent == "NOMINEE_QUERY"

    # Level 5: Pragmatic holistic health check
    ir_prag = classify_intent(
        analyze_lexical("Am I financially prepared?"),
        analyze_syntax(analyze_lexical("Am I financially prepared?")),
    )
    assert ir_prag.intent == "GENERAL_FINANCIAL_OVERVIEW"
    assert ir_prag.pragmatic_type == "HOLISTIC_HEALTH_CHECK"

    # Multilingual Hinglish queries
    hinglish_cases = [
        ("Mere kaunse bank accounts missing hain?", "BANK_ACCOUNT_QUERY"),
        ("Kaunsi policy mein nominee details nahi hain?", "NOMINEE_QUERY"),
        ("Mera FD kab mature hoga?", "FD_QUERY"),
        ("Mera loan kitna outstanding hai?", "LOAN_QUERY"),
        ("AIS aur Form 16 mein koi mismatch hai kya?", "TAX_QUERY"),
        ("Meri salary kitni hai Form 16 ke hisaab se?", "SALARY_QUERY"),
    ]
    for hq, expected_intent in hinglish_cases:
        hlx = analyze_lexical(hq)
        hsx = analyze_syntax(hlx)
        hir = classify_intent(hlx, hsx)
        assert hlx.language == "Hinglish", f"Failed Hinglish detection for: {hq}"
        assert hir.intent == expected_intent, f"{hq} got {hir.intent}"

    # Document-aware suggestions endpoint
    sug_res = client.get("/api/chat/suggestions", headers=headers_a)
    assert sug_res.status_code == 200
    assert len(sug_res.json()["suggestions"]) >= 4

    # Ambiguity detection on singular bank account query (User A has 2 bank accounts)
    ambig_res = client.post(
        "/api/chat",
        headers=headers_a,
        json={"question": "What is my bank account balance?"},
    )
    assert ambig_res.status_code == 200
    ab = ambig_res.json()
    assert ab["needs_clarification"] is True
    assert len(ab["clarification_options"]) == 2

    # Level 4: Coreference resolution across multi-turn FD follow-up
    mock_fd_1 = {
        "answer": "Your fixed deposit DEMO-FD-XX2184 matures on 25-Jun-2026.",
        "confidence": "HIGH",
        "sources": [{"document": "FD_Certificate.pdf", "page": 1, "evidence": "Maturity Date: 25-Jun-2026"}],
    }
    mock_fd_2 = {
        "answer": "The principal amount of that fixed deposit is ₹2,50,000.00.",
        "confidence": "HIGH",
        "sources": [{"document": "FD_Certificate.pdf", "page": 1, "evidence": "Principal Amount: ₹2,50,000.00"}],
    }
    with patch("app.services.chat.generate_grounded_answer", side_effect=[mock_fd_1, mock_fd_2]):
        t1 = client.post("/api/chat", headers=headers_a, json={"question": "When does my fixed deposit mature?"})
        assert t1.status_code == 200
        cid = t1.json()["conversation_id"]
        assert t1.json()["intent"] == "FD_QUERY"

        t2 = client.post(
            "/api/chat",
            headers=headers_a,
            json={"question": "What is its principal amount?", "conversation_id": cid},
        )
        assert t2.status_code == 200
        b2 = t2.json()
        assert b2["nlp_metadata"]["coreference_applied"] is True
        assert "fixed deposit" in b2["nlp_metadata"]["resolved_query"].lower()


def test_11_interactive_actions_progress_profile_and_chat_delete(client_and_db):
    client, _SessionLocal = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    orig_name = login_a.json()["user"]["name"]

    # 1. Finding Fix Wizard progress save persists steps and sets status to In Review
    findings = client.get("/api/findings", headers=headers_a).json()
    open_f = next(f for f in findings if f["status"] == "Open")
    first_step = open_f["recommended_steps"][0]

    prog_res = client.post(
        f"/api/findings/{open_f['id']}/progress",
        headers=headers_a,
        json={
            "verification_evidence": "Requested nomination endorsement form",
            "completed_steps": [first_step],
        },
    )
    assert prog_res.status_code == 200
    pb = prog_res.json()
    assert pb["status"] == "In Review"
    assert pb["completed_steps"] == [first_step]

    # 2. Profile name update persists via PATCH /api/auth/me
    patch_res = client.patch(
        "/api/auth/me",
        headers=headers_a,
        json={"name": "Ananya Updated"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Ananya Updated"
    # Restore original name
    client.patch("/api/auth/me", headers=headers_a, json={"name": orig_name})

    # 3. Conversation delete removes conversation cleanly (and 404s afterwards)
    hist = client.get("/api/chat/history", headers=headers_a).json()
    assert len(hist) >= 1
    cid = hist[0]["conversation_id"]
    del_res = client.delete(f"/api/chat/history/{cid}", headers=headers_a)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True
    after_res = client.get(f"/api/chat/history/{cid}", headers=headers_a)
    assert after_res.status_code == 404


def test_12_ist_timezone_consistency_and_exports(client_and_db):
    import json
    from datetime import date, datetime, timezone
    from unittest.mock import patch
    import pymupdf
    from app.services.nlp.syntactic import resolve_relative_temporal_windows
    from app.timezone_utils import IST, format_ist_display, get_ist_now, to_ist, to_ist_iso

    client, _SessionLocal = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    assert "+05:30" in login_a.json()["user"]["created_at"]

    # 1. UTC -> IST midnight boundary & idempotency (no repeated +5:30 shift)
    now_ist = get_ist_now()
    assert now_ist.tzinfo == IST
    utc_late = datetime(2026, 11, 26, 19, 0, 0, tzinfo=timezone.utc)
    converted = to_ist(utc_late)
    assert to_ist_iso(utc_late) == "2026-11-27T00:30:00+05:30"
    assert to_ist_iso(converted) == "2026-11-27T00:30:00+05:30"
    assert format_ist_display(utc_late) == "27 Nov 2026, 12:30 AM IST"
    assert format_ist_display(datetime(2026, 11, 26, 18, 45, 0)) == "27 Nov 2026, 12:15 AM IST"

    # 2. Dashboard, Documents & Findings timestamps include +05:30
    dash = client.get("/api/dashboard", headers=headers_a).json()
    assert dash["server_time_ist"].endswith("+05:30")
    docs = client.get("/api/documents", headers=headers_a).json()
    assert all(d["uploaded_at"].endswith("+05:30") for d in docs)
    findings = client.get("/api/findings", headers=headers_a).json()
    assert all(f["created_at"].endswith("+05:30") for f in findings if f.get("created_at"))

    # 3. Relative date resolution in Asia/Kolkata ("today", "yesterday", "this month", "last week")
    ref_day = date(2026, 11, 27)
    wins = resolve_relative_temporal_windows(
        "Compare spending today vs yesterday and this month vs last week",
        today_ist=ref_day,
    )
    by_expr = {w["expression"]: w for w in wins}
    assert by_expr["today"]["start_date"] == "2026-11-27"
    assert by_expr["yesterday"]["start_date"] == "2026-11-26"
    assert by_expr["this_month"]["start_date"] == "2026-11-01"
    assert by_expr["last_week"]["start_date"] == "2026-11-16"
    assert by_expr["last_week"]["end_date"] == "2026-11-22"

    # 4. Chatbot query with relative IST date + export PDF/TXT/JSON timestamps
    mock_reply = {
        "answer": "Checked expenses for today in Asia/Kolkata.",
        "confidence": "HIGH",
        "sources": [{"document": "Bank_Statement.pdf", "page": 1, "evidence": "Statement Period"}],
    }
    with patch("app.services.chat.generate_grounded_answer", return_value=mock_reply):
        chat_res = client.post(
            "/api/chat",
            headers=headers_a,
            json={"question": "Show my expenses today"},
        )
    assert chat_res.status_code == 200
    body = chat_res.json()
    assert body["nlp_metadata"]["timezone"] == "Asia/Kolkata"
    assert any(w["expression"] == "today" for w in body["nlp_metadata"]["temporal_windows"])
    cid = body["conversation_id"]

    # History returns +05:30 timestamps
    hist = client.get(f"/api/chat/history?conversation_id={cid}", headers=headers_a).json()
    assert hist[0]["updated_at"].endswith("+05:30")
    assert all(m["created_at"].endswith("+05:30") for m in hist[0]["messages"])

    # JSON export preserves IST +05:30 ISO 8601 timestamps
    exp_json = client.get(f"/api/chat/history/{cid}/export?format=json", headers=headers_a)
    jdata = json.loads(exp_json.content.decode("utf-8"))
    assert jdata["timezone"] == "Asia/Kolkata"
    assert jdata["exported_at"].endswith("+05:30")
    assert jdata["conversations"][0]["created_at"].endswith("+05:30")

    # TXT export renders IST (and never UTC)
    exp_txt = client.get(f"/api/chat/history/{cid}/export?format=txt", headers=headers_a)
    txt = exp_txt.content.decode("utf-8")
    assert "IST" in txt and "UTC" not in txt

    # PDF export renders IST (and never UTC)
    exp_pdf = client.get(f"/api/chat/history/{cid}/export?format=pdf", headers=headers_a)
    pdoc = pymupdf.open(stream=exp_pdf.content, filetype="pdf")
    ptxt = "\n".join(pg.get_text() for pg in pdoc)
    pdoc.close()
    assert "IST" in ptxt and "UTC" not in ptxt
