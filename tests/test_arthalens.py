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

    assert "GAP_UNDISCOVERED_ACCOUNT" in ftypes
    assert ftypes["GAP_UNDISCOVERED_ACCOUNT"]["severity"] == "AMBER"
    assert "GAP_MISSING_NOMINEE" in ftypes
    assert ftypes["GAP_MISSING_NOMINEE"]["severity"] == "RED"
    assert ftypes["GAP_MISSING_NOMINEE"]["evidence"][0]["page"] == 2
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
        assert body1["sources"][0]["page"] == 2

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
