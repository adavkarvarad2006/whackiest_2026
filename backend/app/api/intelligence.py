"""Findings, financial assets, dashboard, transactions, and evaluation endpoints."""

from datetime import datetime
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Document, FinancialAsset, Finding, FindingProgress, Transaction, User
from app.schemas import FinancialAssetOut, FindingOut, TransactionOut
from app.services import sql_analytics
from app.timezone_utils import get_ist_now, get_utc_now, to_ist_iso

router = APIRouter(prefix="/api", tags=["intelligence"])


class FeedbackPayload(BaseModel):
    reason: str = ""


class FixPayload(BaseModel):
    verification_evidence: str = ""
    completed_steps: list[str] = []
    nominee_name: str | None = None


def _recommended_steps_for_finding(finding_type: str) -> list[str]:
    ft = (finding_type or "").upper()
    if "NOMINEE" in ft:
        return [
            "Download or request a Nomination Endorsement Form (u/s 39) from your insurer.",
            "Verify existing policy nomination status in your insurer customer portal.",
            "Enter the endorsement reference or confirmation note below once updated.",
        ]
    if "UNDISCOVERED_ACCOUNT" in ft:
        return [
            "Confirm whether you own or still actively hold the AIS-reported savings account.",
            "Download the FY 2025–26 statement or passbook from the institution.",
            "Upload the bank statement under Documents or record verification details below.",
        ]
    if "SALARY_DISCREPANCY" in ft:
        return [
            "Compare Form 16 Part B salary breakup against AIS TDS-192 quarterly Form 24Q filings.",
            "Request a payroll reconciliation summary from your employer finance team.",
            "Record the verified reconciliation note below before filing your return.",
        ]
    if "FD_MATURITY" in ft:
        return [
            "Review current term deposit renewal rates versus transferring proceeds to your savings account.",
            "Submit renewal or maturity payout instructions to your bank before the maturity date.",
            "Record your instruction reference number below.",
        ]
    if "SUBSCRIPTION" in ft or "BANK_CHARGES" in ft:
        return [
            "Review the recurring charges identified in your bank statement.",
            "Cancel or adjust any unused subscriptions or avoidable service plans directly with the provider.",
            "Record your review or cancellation confirmation below.",
        ]
    if "LOAN_EMI" in ft:
        return [
            "Cross-check the NACH auto-debit amount against your loan repayment schedule.",
            "Contact your lender if any installment amount or due date differs.",
            "Record your confirmation reference below.",
        ]
    return [
        "Inspect the cited page in the Evidence Drawer.",
        "Verify the record status with the reporting financial institution.",
    ]


def _ui_finding(f: Finding, user_id: int, is_demo: bool, progress: FindingProgress | None = None) -> dict:
    sev_map = {"RED": "High", "AMBER": "Medium", "INFO": "Low", "GREEN": "Low"}
    status_map = {
        "RESOLVED": "Resolved",
        "DISMISSED": "Dismissed",
        "IN_REVIEW": "In Review",
        "OPEN": "Open",
    }
    conf_pct = 94 if f.confidence == "HIGH" else 76
    ev_list = f.evidence if isinstance(f.evidence, list) else []
    first_ev = ev_list[0] if ev_list and isinstance(ev_list[0], dict) else {}
    second_ev = ev_list[1] if len(ev_list) > 1 and isinstance(ev_list[1], dict) else {}
    steps = _recommended_steps_for_finding(f.finding_type)
    return {
        "id": str(f.id),
        "user_id": str(user_id),
        "finding_type": f.finding_type,
        "title": f.title or "Financial Finding",
        "description": f.description or "",
        "category": "Nominee Gap" if "NOMINEE" in (f.finding_type or "").upper() else f.finding_type.split("_")[0].title(),
        "severity": sev_map.get(f.severity, "Medium"),
        "raw_severity": f.severity,
        "confidence": conf_pct,
        "raw_confidence": f.confidence,
        "status": status_map.get(f.status, "Open"),
        "is_demo": is_demo,
        "impact_amount": None,
        "evidence": {
            "source_document": first_ev.get("document", "Uploaded Document"),
            "source_document_id": str(first_ev.get("document_id", "")),
            "page_number": first_ev.get("page", 1),
            "extracted_text": first_ev.get("extracted_text", f.description),
            "matching_document": second_ev.get("document"),
            "matching_document_id": str(second_ev.get("document_id", "")) if second_ev else None,
            "matching_page": second_ev.get("page"),
            "matching_text": second_ev.get("extracted_text"),
            "why_flagged": f.description,
            "is_confirmed_fact": f.confidence == "HIGH",
            "fact_label": "Confirmed Fact" if f.confidence == "HIGH" else "Needs Verification",
        },
        "evidence_items": ev_list,
        "recommended_steps": steps if isinstance(steps, list) else [],
        "completed_steps": list(progress.completed_steps) if progress and isinstance(progress.completed_steps, list) else [],
        "resolution_evidence": progress.verification_evidence if progress else None,
        "feedback_wrong": f.status == "DISMISSED",
        "feedback_note": progress.feedback_note if progress else None,
        "resolved_at": to_ist_iso(progress.resolved_at) if progress and progress.resolved_at else None,
        "created_at": to_ist_iso(f.created_at) if f.created_at else None,
    }


def _ui_asset_tile(a: FinancialAsset, fname: str, is_demo: bool) -> dict:
    status_ring = "GREEN" if a.nominee_status == "RECORDED" else ("RED" if a.nominee_status == "NEEDS_VERIFICATION" else "AMBER")
    return {
        "id": str(a.id),
        "asset_name": f"{a.asset_type.replace('_', ' ').title()} ({a.account_reference or 'N/A'})",
        "category": a.asset_type,
        "institution": a.institution,
        "value": float(a.amount),
        "status": status_ring,
        "nominee_name": "Registered" if a.nominee_status == "RECORDED" else None,
        "source_document": fname,
        "note": a.extracted_text or "",
        "is_demo": is_demo,
    }


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate real DashboardSummary from PostgreSQL/SQLite tables for Next.js DashboardPage."""
    is_demo = current_user.email.endswith(".demo@arthalens.example")
    assets = db.execute(
        select(FinancialAsset, Document.filename)
        .join(Document, Document.id == FinancialAsset.source_document_id)
        .where(FinancialAsset.user_id == current_user.id)
    ).all()
    findings = list(db.scalars(select(Finding).where(Finding.user_id == current_user.id).order_by(Finding.id.asc())))
    subs = sql_analytics.sql_subscription_and_recurring_expenses(db, current_user.id)

    total_mapped = sum(
        float(a.amount) for a, _ in assets if a.asset_type in ("SAVINGS_ACCOUNT", "FIXED_DEPOSIT")
    )
    tiles = [_ui_asset_tile(a, fn, is_demo) for a, fn in assets]
    counts = {
        "GREEN": sum(1 for t in tiles if t["status"] == "GREEN"),
        "AMBER": sum(1 for t in tiles if t["status"] == "AMBER"),
        "RED": sum(1 for t in tiles if t["status"] == "RED"),
    }
    cov_pct = round((counts["GREEN"] / len(tiles)) * 100) if tiles else 0

    # Monthly cashflow trends aggregated from actual transactions
    txns = list(
        db.scalars(
            select(Transaction)
            .where(Transaction.user_id == current_user.id)
            .order_by(Transaction.transaction_date.asc())
        )
    )
    month_map: dict[str, dict[str, float]] = {}
    for tx in txns:
        lbl = tx.transaction_date.strftime("%b %y")
        slot = month_map.setdefault(lbl, {"income": 0.0, "expenses": 0.0, "investments": 0.0})
        if tx.transaction_type == "CREDIT":
            slot["income"] += float(tx.amount)
        elif tx.category == "FD_TRANSFER":
            slot["investments"] += float(tx.amount)
        else:
            slot["expenses"] += float(tx.amount)

    trends = [
        {
            "month": m,
            "income": round(v["income"], 2),
            "expenses": round(v["expenses"], 2),
            "investments": round(v["investments"], 2),
            "net_flow": round(v["income"] - v["expenses"], 2),
        }
        for m, v in month_map.items()
    ]

    open_blindspots = sum(1 for f in findings if f.severity in ("RED", "AMBER") and f.status in ("OPEN", "IN_REVIEW"))
    score = max(40, min(98, 92 - open_blindspots * 8))

    prog_map = {
        p.finding_id: p
        for p in db.scalars(select(FindingProgress).where(FindingProgress.user_id == current_user.id))
    }

    return {
        "total_assets_mapped": round(total_mapped, 2),
        "potential_blindspots": open_blindspots,
        "potential_annual_leaks": subs["annual_subscriptions_inr"] + subs["bank_fees_annual_inr"],
        "arthalens_score": score,
        "monthly_financial_flow": round(sum(t["net_flow"] for t in trends) / len(trends), 2) if trends else 0.0,
        "nominee_coverage_pct": cov_pct,
        "nominee_counts": counts,
        "trends": trends,
        "nominee_tiles": tiles,
        "recent_findings": [_ui_finding(f, current_user.id, is_demo, prog_map.get(f.id)) for f in findings],
        "has_demo_data": is_demo or len(assets) > 0,
        "server_time_ist": get_ist_now().isoformat(),
    }


@router.get("/evaluation/report")
def get_evaluation_report(current_user: User = Depends(get_current_user)):
    """Serve the aggregate 500-PDF RAG evaluation metrics (never exposing ground-truth answers)."""
    report_path = Path(__file__).resolve().parents[3] / "arthalens_dataset" / "evaluation" / "evaluation_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Evaluation report has not been generated yet.")
    return json.loads(report_path.read_text(encoding="utf-8"))


def _upsert_finding_progress(
    db: Session,
    finding_id: int,
    user_id: int,
    completed_steps: list[str] | None = None,
    verification_evidence: str | None = None,
    nominee_name: str | None = None,
    feedback_note: str | None = None,
    resolved: bool = False,
) -> FindingProgress:
    prog = db.scalar(
        select(FindingProgress).where(
            FindingProgress.finding_id == finding_id,
            FindingProgress.user_id == user_id,
        )
    )
    if prog is None:
        prog = FindingProgress(finding_id=finding_id, user_id=user_id)
        db.add(prog)
    if completed_steps is not None:
        prog.completed_steps = completed_steps
    if verification_evidence is not None:
        prog.verification_evidence = verification_evidence
    if nominee_name is not None:
        prog.nominee_name = nominee_name
    if feedback_note is not None:
        prog.feedback_note = feedback_note
    if resolved:
        prog.resolved_at = get_utc_now()
    return prog


@router.get("/findings")
def get_findings(
    severity: str | None = Query(default=None),
    finding_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_demo = current_user.email.endswith(".demo@arthalens.example")
    stmt = select(Finding).where(Finding.user_id == current_user.id)
    if severity:
        stmt = stmt.where(Finding.severity == severity.upper())
    if finding_status:
        stmt = stmt.where(Finding.status == finding_status.upper().replace(" ", "_"))
    stmt = stmt.order_by(Finding.id.asc())
    prog_map = {
        p.finding_id: p
        for p in db.scalars(select(FindingProgress).where(FindingProgress.user_id == current_user.id))
    }
    return [_ui_finding(f, current_user.id, is_demo, prog_map.get(f.id)) for f in db.scalars(stmt)]


@router.post("/findings/{finding_id}/feedback")
def report_finding_feedback(
    finding_id: int,
    payload: FeedbackPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    f = db.scalar(select(Finding).where(Finding.id == finding_id, Finding.user_id == current_user.id))
    if f is None:
        raise HTTPException(status_code=404, detail="Finding not found.")
    f.status = "DISMISSED"
    prog = _upsert_finding_progress(
        db,
        f.id,
        current_user.id,
        feedback_note=payload.reason.strip() or "Dismissed by user",
    )
    db.commit()
    db.refresh(f)
    return _ui_finding(f, current_user.id, current_user.email.endswith(".demo@arthalens.example"), prog)


@router.post("/findings/{finding_id}/progress")
def save_finding_progress(
    finding_id: int,
    payload: FixPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    f = db.scalar(select(Finding).where(Finding.id == finding_id, Finding.user_id == current_user.id))
    if f is None:
        raise HTTPException(status_code=404, detail="Finding not found.")
    if f.status == "OPEN":
        f.status = "IN_REVIEW"
    prog = _upsert_finding_progress(
        db,
        f.id,
        current_user.id,
        completed_steps=payload.completed_steps,
        verification_evidence=payload.verification_evidence.strip() or None,
        nominee_name=payload.nominee_name.strip() if payload.nominee_name else None,
        resolved=False,
    )
    db.commit()
    db.refresh(f)
    return _ui_finding(f, current_user.id, current_user.email.endswith(".demo@arthalens.example"), prog)


@router.post("/findings/{finding_id}/fix")
def resolve_finding(
    finding_id: int,
    payload: FixPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    f = db.scalar(select(Finding).where(Finding.id == finding_id, Finding.user_id == current_user.id))
    if f is None:
        raise HTTPException(status_code=404, detail="Finding not found.")
    f.status = "RESOLVED"
    prog = _upsert_finding_progress(
        db,
        f.id,
        current_user.id,
        completed_steps=payload.completed_steps,
        verification_evidence=payload.verification_evidence.strip() or None,
        nominee_name=payload.nominee_name.strip() if payload.nominee_name else None,
        resolved=True,
    )
    db.commit()
    db.refresh(f)
    return _ui_finding(f, current_user.id, current_user.email.endswith(".demo@arthalens.example"), prog)


@router.get("/assets", response_model=list[FinancialAssetOut])
def get_assets(
    asset_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(FinancialAsset, Document.filename)
        .join(Document, Document.id == FinancialAsset.source_document_id)
        .where(FinancialAsset.user_id == current_user.id)
    )
    if asset_type:
        stmt = stmt.where(FinancialAsset.asset_type == asset_type.upper())
    stmt = stmt.order_by(FinancialAsset.id.asc())

    results = []
    for asset, fname in db.execute(stmt).all():
        item = FinancialAssetOut.model_validate(asset)
        item.source_document_name = fname
        results.append(item)
    return results


@router.get("/transactions", response_model=list[TransactionOut])
def get_transactions(
    category: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Transaction).where(Transaction.user_id == current_user.id)
    if category:
        stmt = stmt.where(Transaction.category == category.upper())
    stmt = stmt.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(limit)
    return [TransactionOut.model_validate(t) for t in db.scalars(stmt)]
