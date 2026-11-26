"""Findings, financial assets, dashboard, transactions, and evaluation endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Document, FinancialAsset, Finding, Transaction, User
from app.schemas import FinancialAssetOut, FindingOut, TransactionOut
from app.services import sql_analytics

router = APIRouter(prefix="/api", tags=["intelligence"])


class FeedbackPayload(BaseModel):
    reason: str = ""


class FixPayload(BaseModel):
    verification_evidence: str = ""
    completed_steps: list[str] = []
    nominee_name: str | None = None


def _ui_finding(f: Finding, user_id: int, is_demo: bool) -> dict:
    sev_map = {"RED": "High", "AMBER": "Medium", "INFO": "Low", "GREEN": "Low"}
    conf_pct = 94 if f.confidence == "HIGH" else 76
    ev_list = f.evidence or []
    first_ev = ev_list[0] if ev_list else {}
    second_ev = ev_list[1] if len(ev_list) > 1 else {}
    return {
        "id": str(f.id),
        "user_id": str(user_id),
        "finding_type": f.finding_type,
        "title": f.title,
        "description": f.description,
        "category": f.finding_type.split("_")[0].title(),
        "severity": sev_map.get(f.severity, "Medium"),
        "raw_severity": f.severity,
        "confidence": conf_pct,
        "raw_confidence": f.confidence,
        "status": "Resolved" if f.status == "RESOLVED" else ("Dismissed" if f.status == "DISMISSED" else "Open"),
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
        "recommended_steps": [
            "Inspect the cited page in the Evidence Drawer.",
            "Verify record status with the reporting institution.",
        ],
        "feedback_wrong": f.status == "DISMISSED",
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

    open_blindspots = sum(1 for f in findings if f.severity in ("RED", "AMBER") and f.status == "OPEN")
    score = max(40, min(98, 92 - open_blindspots * 8))

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
        "recent_findings": [_ui_finding(f, current_user.id, is_demo) for f in findings],
        "has_demo_data": is_demo or len(assets) > 0,
    }


@router.get("/evaluation/report")
def get_evaluation_report(current_user: User = Depends(get_current_user)):
    """Serve the aggregate 500-PDF RAG evaluation metrics (never exposing ground-truth answers)."""
    report_path = Path(__file__).resolve().parents[3] / "arthalens_dataset" / "evaluation" / "evaluation_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Evaluation report has not been generated yet.")
    return json.loads(report_path.read_text(encoding="utf-8"))


@router.get("/findings", response_model=list[FindingOut])
def get_findings(
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Finding).where(Finding.user_id == current_user.id)
    if severity:
        stmt = stmt.where(Finding.severity == severity.upper())
    stmt = stmt.order_by(Finding.id.asc())
    return [FindingOut.model_validate(f) for f in db.scalars(stmt)]


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
    db.commit()
    db.refresh(f)
    return _ui_finding(f, current_user.id, current_user.email.endswith(".demo@arthalens.example"))


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
    db.commit()
    db.refresh(f)
    return _ui_finding(f, current_user.id, current_user.email.endswith(".demo@arthalens.example"))


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
