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


def test_13_groq_live_integration_and_error_handling(client_and_db, monkeypatch):
    from unittest.mock import AsyncMock, patch
    import httpx
    from app.config import get_settings

    client, _SessionLocal = client_and_db
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

    # 1. Missing API key handling -> 503 configuration error (never exposes key)
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    try:
        missing_res = client.post(
            "/api/chat",
            headers=headers_a,
            json={"message": "What is my total insurance coverage?"},
        )
        assert missing_res.status_code == 503
        assert "GROQ_API_KEY" in missing_res.json()["detail"]
    finally:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        get_settings.cache_clear()

    # 2. Rate-limit (429) handling with retry & clear upstream error
    monkeypatch.setenv("GROQ_MAX_RETRIES", "1")
    get_settings.cache_clear()
    try:
        mock_429 = httpx.Response(status_code=429, headers={"retry-after": "0.1"}, json={"error": {"message": "rate limit"}})
        with patch("app.services.llm.httpx.AsyncClient.post", new=AsyncMock(return_value=mock_429)):
            rl_res = client.post(
                "/api/chat",
                headers=headers_a,
                json={"message": "Find my recurring subscriptions."},
            )
            assert rl_res.status_code == 429
            assert "rate-limited" in rl_res.json()["detail"].lower()
    finally:
        monkeypatch.delenv("GROQ_MAX_RETRIES", raising=False)
        get_settings.cache_clear()

    # 3. Invalid API key handling against live endpoint (or simulated 401)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_invalid_test_key_1234567890")
    monkeypatch.setenv("GROQ_MAX_RETRIES", "0")
    get_settings.cache_clear()
    try:
        inv_res = client.post(
            "/api/chat",
            headers=headers_a,
            json={"message": "What is my total insurance coverage?"},
        )
        assert inv_res.status_code in (401, 502)
        assert "gsk_" not in inv_res.text
    finally:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_MAX_RETRIES", raising=False)
        get_settings.cache_clear()

    # 4. Missing-document scenario (User B has 0 documents, receives explicit unavailable response)
    b_res = client.post("/api/chat", headers=headers_b, json={"message": "Do I have any missing nominees?"})
    assert b_res.status_code == 200
    assert b_res.json()["confidence"] == "UNAVAILABLE"

    # 5. Live Groq API integration (using key from backend/.env): English QA + citations + Hinglish + Follow-up
    settings = get_settings()
    assert settings.is_groq_configured(), "GROQ_API_KEY must be configured in backend/.env"

    live_1 = client.post(
        "/api/chat",
        headers=headers_a,
        json={"message": "Do I have any missing nominee information?"},
    )
    assert live_1.status_code == 200, live_1.text
    d1 = live_1.json()
    assert d1["answer"]
    assert d1["timestamp"].endswith("+05:30")
    assert len(d1["citations"]) >= 1
    assert any("Insurance_Policy" in (c.get("filename") or c.get("document") or "") for c in d1["citations"])
    cid = d1["conversation_id"]

    # Follow-up in same conversation (maintaining context; handles free-tier 429 cleanly if burst-limited)
    import time
    time.sleep(1.5)
    live_2 = client.post(
        "/api/chat",
        headers=headers_a,
        json={"message": "What should I fix first?", "conversation_id": cid},
    )
    assert live_2.status_code == 200, live_2.text
    assert live_2.json()["conversation_id"] == cid

    # Hinglish + streaming endpoint with real Groq (allow TPM window refill cleanly after 2 live calls)
    time.sleep(15.0)
    stream_res = client.post(
        "/api/chat/stream",
        headers=headers_a,
        json={"message": "Mere kitne bank accounts hain?"},
    )
    assert stream_res.status_code == 200, stream_res.text
    assert "data: " in stream_res.text
    assert '"Hinglish"' in stream_res.text

    # Clear all chat history for User A
    clr = client.delete("/api/chat/history", headers=headers_a)
    assert clr.status_code == 200
    assert clr.json()["cleared"] is True
    assert client.get("/api/chat/history", headers=headers_a).json() == []


def test_14_three_tier_intelligent_routing_and_general_knowledge(client_and_db):
    """Verify GENERAL_KNOWLEDGE, PERSONAL_FINANCIAL_DATA, HYBRID_QUERY routing, Hinglish concepts, and multi-turn switches."""
    from unittest.mock import patch
    from app.services.nlp.intent import classify_intent
    from app.services.nlp.lexical import analyze_lexical
    from app.services.nlp.syntactic import analyze_syntax

    client, _SessionLocal = client_and_db
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

    # 1. General Financial Knowledge variants (including Hinglish & definitions)
    for gq, expected_lang in (
        ("What is an FD?", "English"),
        ("What is FD?", "English"),
        ("FD kya hota hai?", "Hinglish"),
        ("Explain fixed deposits.", "English"),
        ("FD kaise work karta hai?", "Hinglish"),
        ("Fixed deposit meaning?", "English"),
        ("Difference between FD and RD?", "English"),
        ("What is compound interest?", "English"),
        ("Explain SIP with an example.", "English"),
        ("What is a credit score?", "English"),
        ("Explain inflation.", "English"),
        ("How does health insurance work?", "English"),
        ("What are tax-saving investments?", "English"),
    ):
        lx = analyze_lexical(gq)
        sx = analyze_syntax(lx)
        ir = classify_intent(lx, sx)
        assert lx.language == expected_lang, f"{gq} expected lang {expected_lang}, got {lx.language}"
        assert ir.query_category == "GENERAL_KNOWLEDGE", f"{gq} got category {ir.query_category}"
        assert ir.processing_route == "GENERAL_LLM"

    # 2. Personal Financial Data queries
    for pq in (
        "When will my FD mature?",
        "How many FDs do I have?",
        "What is my total FD amount?",
        "Who is my insurance nominee?",
        "Summarize my bank statement.",
        "What is my monthly EMI?",
    ):
        lx = analyze_lexical(pq)
        sx = analyze_syntax(lx)
        ir = classify_intent(lx, sx)
        assert ir.query_category == "PERSONAL_FINANCIAL_DATA", f"{pq} got {ir.query_category}"

    # 3. Hybrid Queries
    for hq in (
        "Is my FD interest rate good?",
        "Am I paying too much in insurance premiums?",
        "Is my current investment allocation diversified?",
        "Is my investment portfolio diversified?",
        "Explain whether my loan interest rate is high.",
    ):
        lx = analyze_lexical(hq)
        sx = analyze_syntax(lx)
        ir = classify_intent(lx, sx)
        assert ir.query_category == "HYBRID_QUERY", f"{hq} got {ir.query_category}"
        assert ir.processing_route == "HYBRID_REASONING"

    # 4. Empty Document Library (User B has 0 docs) MUST answer GENERAL_KNOWLEDGE cleanly without RAG or doc warnings
    mock_general = {
        "answer": "A Fixed Deposit (FD) is a bank term deposit earning fixed interest. For example, ₹1,00,000 deposited for 1 year grows at the agreed rate. Pros: predictable returns; Cons: premature withdrawal penalty.",
        "confidence": "HIGH",
        "sources": [{"document": "fake_hallucinated.pdf", "page": 1}],
        "disclaimer": "Educational explanation only.",
    }
    with patch("app.services.chat.generate_grounded_answer", return_value=mock_general) as m_llm, patch(
        "app.services.chat.retrieve_multi_query_chunks"
    ) as m_rag:
        empty_gen_res = client.post("/api/chat", headers=headers_b, json={"question": "What is an FD?"})
        assert empty_gen_res.status_code == 200
        gb = empty_gen_res.json()
        assert gb["query_category"] == "GENERAL_KNOWLEDGE"
        assert gb["retrieval_mode"] == "GENERAL_LLM"
        assert gb["citations"] == []  # Strictly strip any fake citations on GENERAL_KNOWLEDGE
        assert m_rag.call_count == 0
        assert m_llm.call_count == 1

    # 5. Multi-turn context: GENERAL_KNOWLEDGE -> general follow-up -> PERSONAL_FINANCIAL_DATA switch
    mock_fd_gen = {"answer": "An FD is a fixed-tenure term deposit.", "confidence": "HIGH", "sources": []}
    mock_fd_benefits = {"answer": "Key FD benefits include capital stability and predictable returns.", "confidence": "HIGH", "sources": []}
    mock_fd_personal = {
        "answer": "Your uploaded FD certificate shows Fixed Deposit DEMO-FD-XX2184 maturing on 25-Jun-2026.",
        "confidence": "HIGH",
        "sources": [{"document": "FD_Certificate.pdf", "page": 1, "evidence": "Maturity Date: 25-Jun-2026"}],
    }
    with patch("app.services.chat.generate_grounded_answer", side_effect=[mock_fd_gen, mock_fd_benefits, mock_fd_personal]), patch(
        "app.services.chat.retrieve_multi_query_chunks", wraps=__import__("app.services.chat", fromlist=["retrieve_multi_query_chunks"]).retrieve_multi_query_chunks
    ) as spy_rag:
        t1 = client.post("/api/chat", headers=headers_a, json={"question": "What is an FD?"})
        assert t1.status_code == 200
        d1 = t1.json()
        cid = d1["conversation_id"]
        assert d1["query_category"] == "GENERAL_KNOWLEDGE"
        assert d1["retrieval_mode"] == "GENERAL_LLM"
        assert spy_rag.call_count == 0

        t2 = client.post("/api/chat", headers=headers_a, json={"question": "What are its benefits?", "conversation_id": cid})
        assert t2.status_code == 200
        d2 = t2.json()
        assert d2["query_category"] == "GENERAL_KNOWLEDGE"
        assert d2["retrieval_mode"] == "GENERAL_LLM"
        assert spy_rag.call_count == 0

        t3 = client.post("/api/chat", headers=headers_a, json={"question": "What about my FD?", "conversation_id": cid})
        assert t3.status_code == 200
        d3 = t3.json()
        assert d3["query_category"] == "PERSONAL_FINANCIAL_DATA"
        assert spy_rag.call_count == 1
        assert len(d3["citations"]) >= 1


def test_15_ai_action_automation_workflows_and_security(client_and_db):
    """Test all 10 Fix Wizard Automation scenarios: workflows, forms, approval, PDF evidence, failure, & security."""
    import pymupdf
    from sqlalchemy import select
    from app.models import FinancialAsset

    client, SessionLocal = client_and_db
    login_a = client.post(
        "/api/auth/login",
        json={"email": "ananya.test@example.com", "password": "SecurePassword123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    user_a_id = login_a.json()["user"]["id"]

    login_b = client.post(
        "/api/auth/login",
        json={"email": "other.user@example.com", "password": "SecurePassword123!"},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Fetch automation tasks across all User A findings
    tasks_res = client.get("/api/automation/tasks", headers=headers_a)
    assert tasks_res.status_code == 200
    tasks = tasks_res.json()["tasks"]
    by_wf = {t["workflow_type"]: t for t in tasks}

    # Verify required classifications & workflows exist
    assert "NOMINEE_VERIFICATION" in by_wf
    assert "FD_MATURITY" in by_wf
    assert "SUBSCRIPTION_AUDIT" in by_wf
    assert "TAX_RECONCILIATION" in by_wf
    assert "BANK_ACCOUNT_VERIFICATION" in by_wf

    # 1. FD Maturity Reminder + Renewal Comparison + Bank Enquiry Draft
    rem_res = client.get("/api/automation/reminders", headers=headers_a)
    assert rem_res.status_code == 200
    rems = rem_res.json()["reminders"]
    assert any(r["reminder_type"] == "FD_MATURITY" for r in rems)
    fd_task = client.post(
        f"/api/automation/findings/{by_wf['FD_MATURITY']['finding_id']}/automate",
        headers=headers_a,
        json={"use_groq": False},
    ).json()
    assert fd_task["automation_level"] == "AUTOMATABLE_WITH_USER_APPROVAL"
    assert "renewal_comparison" in fd_task["workflow_data"]["fd_analysis"]
    assert fd_task["draft_email"]

    # 2. Subscription Detection + Annual Expenditure + Official Cancellation Links
    sub_task = by_wf["SUBSCRIPTION_AUDIT"]
    assert sub_task["estimated_impact_inr"] and sub_task["estimated_impact_inr"] > 0
    assert len(sub_task["workflow_data"]["subscription_audit"]["merchants"]) >= 1

    # 3. Tax Discrepancy (AIS vs Form 16) + Advisor Questions
    tax_task = by_wf["TAX_RECONCILIATION"]
    tax_info = tax_task["workflow_data"]["tax_reconciliation"]
    assert tax_info["discrepancy_inr"] > 0
    assert len(tax_info["questions_for_tax_professional"]) >= 2

    # 4. Security Guardrails: unauthorized autonomous actions blocked & audited; cross-user blocked
    nom_fid = by_wf["NOMINEE_VERIFICATION"]["finding_id"]
    for forbidden in ("AUTO_SUBMIT_FORM", "PORTAL_LOGIN_WITH_CREDENTIALS", "MODIFY_BANK_NOMINEE", "EXECUTE_TRANSACTION", "AUTO_CANCEL_POLICY"):
        sec_res = client.post(
            f"/api/automation/findings/{nom_fid}/execute-protected",
            headers=headers_a,
            json={"action_type": forbidden},
        )
        assert sec_res.status_code == 403
    assert client.get(f"/api/automation/findings/{nom_fid}", headers=headers_b).status_code == 404

    # Cannot mark external nominee finding completed without verified proof
    unver_res = client.post(
        f"/api/automation/findings/{nom_fid}/verify",
        headers=headers_a,
        json={},
    )
    assert unver_res.status_code == 200
    assert unver_res.json()["task_status"] in ("Verification Required", "Failed")
    bad_fix = client.post(
        f"/api/findings/{nom_fid}/fix",
        headers=headers_a,
        json={"verification_evidence": "Downloaded form only"},
    )
    assert bad_fix.status_code == 400

    # 5. Nominee Verification Flow: Automate -> Generate Request -> Download Form (never completes!) -> Approve Draft
    auto_nom = client.post(
        f"/api/automation/findings/{nom_fid}/automate",
        headers=headers_a,
        json={"use_groq": False},
    ).json()
    assert auto_nom["automation_level"] == "GUIDED_EXTERNAL_ACTION"
    assert auto_nom["task_status"] == "In Progress"
    assert auto_nom["extracted_entities"]["insurer_name"]
    assert auto_nom["extracted_entities"]["policy_number"]
    assert auto_nom["institution_directory"]["form_name"]

    dl_res = client.get(f"/api/automation/findings/{nom_fid}/download-form", headers=headers_a)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"].startswith("application/pdf")
    assert dl_res.content[:5] == b"%PDF-"
    after_dl = client.get(f"/api/automation/findings/{nom_fid}", headers=headers_a).json()
    assert after_dl["task_status"] != "Completed"  # Downloading form NEVER completes verification!

    app_res = client.post(
        f"/api/automation/findings/{nom_fid}/approve",
        headers=headers_a,
        json={"approved": True, "notes": "Reviewed policy info and email draft"},
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["approval_granted"] is True
    assert app_data["task_status"] == "Awaiting External Confirmation"

    # 6. Failed Verification: Mismatched policy reference or blank nominee fails cleanly
    wrong_pdf_doc = pymupdf.open()
    wp = wrong_pdf_doc.new_page()
    wp.insert_text((50, 80), "Nominee Endorsement for Policy XX-LI-999999\nNominee Name: Wrong User\nEndorsement Ref: END-0001")
    wrong_pdf_bytes = wrong_pdf_doc.tobytes()
    wrong_pdf_doc.close()

    fail_up = client.post(
        f"/api/automation/findings/{nom_fid}/evidence",
        headers=headers_a,
        data={"evidence_type": "Uploaded Endorsement"},
        files={"file": ("wrong_endorsement.pdf", wrong_pdf_bytes, "application/pdf")},
    )
    assert fail_up.status_code == 200
    fd_json = fail_up.json()
    assert fd_json["task_status"] == "Failed"
    assert fd_json["latest_evidence"]["verification_status"] == "FAILED"

    # 7. Real Evidence Upload + Automatic Extraction & Completion
    target_ref = auto_nom["account_or_policy_ref"] or "SG-LI-0000"
    ok_doc = pymupdf.open()
    op = ok_doc.new_page()
    op.insert_text(
        (50, 80),
        f"OFFICIAL NOMINATION ENDORSEMENT CONFIRMATION\n"
        f"Policy Reference: {target_ref}\n"
        f"Nominee Name: Rohan Sharma (Spouse)\n"
        f"Endorsement Ref: SR-NOM-88421\n"
        f"Confirmation Date: 27-Nov-2026\n"
        f"Status: Section 39 Nomination Confirmed & Registered",
    )
    ok_pdf_bytes = ok_doc.tobytes()
    ok_doc.close()

    pass_up = client.post(
        f"/api/automation/findings/{nom_fid}/evidence",
        headers=headers_a,
        data={"evidence_type": "Uploaded Endorsement"},
        files={"file": ("nominee_endorsement.pdf", ok_pdf_bytes, "application/pdf")},
    )
    assert pass_up.status_code == 200
    pj = pass_up.json()
    assert pj["task_status"] == "Completed"
    assert pj["latest_evidence"]["verification_status"] == "VERIFIED"
    assert pj["latest_evidence"]["extracted_data"]["nominee_name"].startswith("Rohan Sharma")
    assert pj["latest_evidence"]["extracted_data"]["endorsement_reference"] == "SR-NOM-88421"

    # Verify Finding status updated to RESOLVED and FinancialAsset updated to RECORDED, plus audit trail
    resolved_f = next(f for f in client.get("/api/findings", headers=headers_a).json() if f["id"] == nom_fid)
    assert resolved_f["status"] == "Resolved"
    with SessionLocal() as db:
        ins_assets = list(db.scalars(select(FinancialAsset).where(FinancialAsset.user_id == user_a_id, FinancialAsset.asset_type == "LIFE_INSURANCE")))
        assert any(a.nominee_status == "RECORDED" for a in ins_assets)

    logs = client.get(f"/api/automation/findings/{nom_fid}/audit-logs", headers=headers_a).json()["logs"]
    act_names = {l["action"] for l in logs}
    assert {"PLAN_GENERATED", "FORM_DOWNLOADED", "DRAFT_APPROVED", "VERIFICATION_FAILED", "VERIFICATION_PASSED", "UNAUTHORIZED_ACTION_BLOCKED"} <= act_names

    # 8. Missing Loan Statement Detection + Loan Management Workflow (User C with Bank Statement ONLY)
    client.post(
        "/api/auth/register",
        json={"name": "Loan Gap Tester", "email": "loangap.test@example.com", "password": "SecurePassword123!"},
    )
    login_c = client.post(
        "/api/auth/login",
        json={"email": "loangap.test@example.com", "password": "SecurePassword123!"},
    )
    headers_c = {"Authorization": f"Bearer {login_c.json()['access_token']}"}
    bank_pdf = DATASET_DOCS / "Bank_Statement.pdf"
    with open(bank_pdf, "rb") as fp:
        up_c = client.post(
            "/api/documents/upload",
            headers=headers_c,
            files={"file": ("Bank_Statement.pdf", fp, "application/pdf")},
        )
    assert up_c.status_code in (200, 201)
    tasks_c = client.get("/api/automation/tasks", headers=headers_c).json()["tasks"]
    loan_tasks = [t for t in tasks_c if t["workflow_type"] == "LOAN_MANAGEMENT"]
    assert len(loan_tasks) >= 1
    assert loan_tasks[0]["draft_email"] and loan_tasks[0]["workflow_data"]["loan_analysis"]["monthly_emi_inr"] > 0
