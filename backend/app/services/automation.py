"""AI-Powered Financial Action Automation Engine, Workflows, Evidence Verifier, and Guardrails."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import json
import logging
from pathlib import Path
import re
from typing import Any
import uuid

import httpx
import pymupdf
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ActionAuditLog,
    ActionEvidence,
    AutomationTask,
    Document,
    FinancialAsset,
    FinancialReminder,
    Finding,
    FindingProgress,
    Transaction,
    User,
)
from app.services.extraction import mask_reference
from app.services.intelligence import get_reference_date
from app.services.llm import _resolve_groq_endpoint
from app.services.pdf_parser import extract_pdf_pages
from app.timezone_utils import format_ist_display, get_ist_now, get_utc_now, to_ist_iso

logger = logging.getLogger(__name__)

AUTOMATION_LEVELS = (
    "FULLY_AUTOMATABLE",
    "AUTOMATABLE_WITH_USER_APPROVAL",
    "GUIDED_EXTERNAL_ACTION",
    "MANUAL_VERIFICATION_REQUIRED",
)

TASK_STATUSES = (
    "Not Started",
    "In Progress",
    "Awaiting External Confirmation",
    "Evidence Received",
    "Verification Required",
    "Completed",
    "Failed",
)

FORBIDDEN_AUTONOMOUS_ACTIONS = {
    "AUTO_SUBMIT_FORM": "ArthaLens cannot automatically submit external forms without explicit user review and portal authorization.",
    "MODIFY_BANK_NOMINEE": "ArthaLens never alters nominee details directly on bank or insurer systems without official endorsement verification.",
    "PORTAL_LOGIN_WITH_CREDENTIALS": "ArthaLens never stores or uses user banking/insurance passwords to log into external portals.",
    "EXECUTE_TRANSACTION": "ArthaLens is strictly read-only and never executes financial transfers or payments.",
    "AUTO_CANCEL_POLICY": "ArthaLens never cancels policies or financial instruments automatically without user execution.",
    "COMPLETE_WITHOUT_EVIDENCE": "Findings requiring institution confirmation cannot be marked completed without verified evidence.",
}

# Verified directory of official portals & form references (explicitly marked demo where synthetic)
OFFICIAL_INSTITUTION_DIRECTORY: dict[str, dict[str, Any]] = {
    "surakshaguard": {
        "official_name": "SurakshaGuard Life Insurance Co. Ltd.",
        "official_website": "https://portal.surakshaguard-demo.example/nomination",
        "support_email": "servicing@surakshaguard-demo.example",
        "helpline": "1800-209-4400 (Demo Servicing Desk)",
        "form_name": "Section 39 Nomination / Change of Nominee Endorsement Form",
        "form_code": "SG-FORM-39-NOM",
        "update_steps": [
            "Sign in to the official SurakshaGuard policyholder servicing portal using your policy number and OTP.",
            "Navigate to Policy Servicing -> Update / Register Nominee (u/s 39 Insurance Act, 1938).",
            "Upload KYC proof and the signed Section 39 Nomination Endorsement Form.",
            "Download the Nomination Endorsement / Service Request confirmation receipt once approved.",
        ],
        "is_verified_directory": True,
    },
    "bharatlife": {
        "official_name": "BharatLife Insurance Corporation (Demo)",
        "official_website": "https://portal.bharatlife-demo.example/policyholder/nominee",
        "support_email": "support@bharatlife-demo.example",
        "helpline": "1800-266-9900 (Demo Policyholder Desk)",
        "form_name": "Form 3750 / Section 39 Nomination Registration Form",
        "form_code": "BL-FORM-39",
        "update_steps": [
            "Open your BharatLife Customer Portal -> Policy Services -> Nominee Details.",
            "Submit Form 39 / e-Nomination with OTP verification.",
            "Save the downloaded Nomination Endorsement Slip or confirmation email as PDF.",
        ],
        "is_verified_directory": True,
    },
    "kavach": {
        "official_name": "Kavach Protection Assurance",
        "official_website": "https://servicing.kavach-demo.example/nomination",
        "support_email": "care@kavach-demo.example",
        "helpline": "1800-103-7722 (Demo Customer Care)",
        "form_name": "Section 39 Nomination Endorsement Form",
        "form_code": "KV-NOM-39",
        "update_steps": [
            "Verify registered nominee status on the Kavach Policyholder Portal.",
            "Submit signed Section 39 form with nominee ID proof if missing.",
            "Upload the insurer endorsement confirmation here to verify completion.",
        ],
        "is_verified_directory": True,
    },
    "horizon trust": {
        "official_name": "Horizon Trust Bank Ltd.",
        "official_website": "https://netbanking.horizontrust-demo.example/deposits",
        "support_email": "deposits@horizontrust-demo.example",
        "helpline": "1800-425-8800 (Demo Wealth Desk)",
        "form_name": "Term Deposit Maturity Instruction / Form DA-1",
        "form_code": "HTB-FD-INST",
        "update_steps": [
            "Log in cleanly yourself to Horizon Trust NetBanking -> Deposits -> Manage Maturity Instruction.",
            "Compare renewal rate vs payout-to-savings instruction based on your liquidity horizon.",
            "Download confirmation slip / reference number and upload it to verify.",
        ],
        "is_verified_directory": True,
    },
    "metrocivic": {
        "official_name": "MetroCivic Bank Ltd.",
        "official_website": "https://online.metrocivic-demo.example/accounts",
        "support_email": "customercare@metrocivic-demo.example",
        "helpline": "1800-220-7000 (Demo Banking Support)",
        "form_name": "Savings Account Verification & Statement Request",
        "form_code": "MCB-STMT-REQ",
        "update_steps": [
            "Check your registered mobile/email alerts or visit branch to verify account status (Active/Dormant).",
            "Download the FY 2025-26 Savings Account Statement PDF.",
            "Upload the statement PDF under Documents or as Verification Evidence below.",
        ],
        "is_verified_directory": True,
    },
    "crestline": {
        "official_name": "Crestline FinServe Ltd.",
        "official_website": "https://loans.crestline-demo.example/statements",
        "support_email": "loansupport@crestline-demo.example",
        "helpline": "1800-208-3100 (Demo Loan Servicing)",
        "form_name": "Loan Repayment Schedule & Statement Request",
        "form_code": "CLF-LOAN-STMT",
        "update_steps": [
            "Download your Loan Account Statement & Repayment Schedule from Crestline customer portal.",
            "Verify sanctioned ROI, monthly EMI amount, and remaining principal.",
            "Upload the loan statement PDF to complete verification.",
        ],
        "is_verified_directory": True,
    },
    "lic": {
        "official_name": "Life Insurance Corporation of India (LIC)",
        "official_website": "https://licindia.in/web/guest/customer-portal",
        "support_email": "co_crm_fb@licindia.com",
        "helpline": "+91-22-6827-6827",
        "form_name": "Form 3750 (Nomination u/s 39 Insurance Act)",
        "form_code": "LIC-3750",
        "update_steps": [
            "Sign in at licindia.in Customer Portal or visit your servicing branch with original policy bond.",
            "Submit Form 3750 along with KYC of policyholder and nominee.",
            "Upload the stamped endorsement slip or e-confirmation PDF here.",
        ],
        "is_verified_directory": True,
    },
    "hdfc life": {
        "official_name": "HDFC Life Insurance Co. Ltd.",
        "official_website": "https://www.hdfclife.com/customer-service",
        "support_email": "service@hdfclife.com",
        "helpline": "022-68446530",
        "form_name": "Policy Servicing Request Form (Nomination u/s 39)",
        "form_code": "HDFCL-NOM-39",
        "update_steps": [
            "Log into HDFC Life MyAccount portal -> Policy Servicing -> Update Nominee.",
            "Complete Aadhaar/OTP authentication and upload proof if requested.",
            "Download the updated Policy Endorsement PDF and attach it below.",
        ],
        "is_verified_directory": True,
    },
    "streamflix": {
        "official_name": "StreamFlix India",
        "official_website": "https://streamflix-demo.example/account/cancel",
        "support_email": "billing@streamflix-demo.example",
        "cancel_steps": [
            "Open StreamFlix Account -> Membership & Billing -> Cancel Membership directly.",
            "If billed via UPI Autopay / Card Mandate, revoke the mandate in your UPI/bank app.",
        ],
    },
    "cloudnotes": {
        "official_name": "CloudNotes Pro",
        "official_website": "https://cloudnotes-demo.example/billing/subscriptions",
        "support_email": "support@cloudnotes-demo.example",
        "cancel_steps": [
            "Open CloudNotes Settings -> Billing Plan -> Downgrade / Cancel Auto-Renew.",
            "Save the cancellation confirmation email or reference ID.",
        ],
    },
    "tunewave": {
        "official_name": "TuneWave Music",
        "official_website": "https://tunewave-demo.example/settings/subscription",
        "support_email": "help@tunewave-demo.example",
        "cancel_steps": [
            "Open TuneWave Subscription Settings -> Change Plan -> Cancel Premium.",
            "Revoke any recurring e-mandate from your bank/UPI autopay dashboard.",
        ],
    },
}


def _lookup_institution(name: str | None) -> dict[str, Any]:
    low = (name or "").lower()
    for key, info in OFFICIAL_INSTITUTION_DIRECTORY.items():
        if key in low:
            return info
    clean_name = (name or "Your Financial Institution").strip()
    return {
        "official_name": clean_name,
        "official_website": None,
        "support_email": None,
        "helpline": "Check the back of your policy/statement or official regulated website.",
        "form_name": "Official Nomination Endorsement / Customer Servicing Form",
        "form_code": "GEN-SERV-FORM",
        "update_steps": [
            f"Visit the official verified website or branch of {clean_name}.",
            "Request official written confirmation or statement PDF for this record.",
            "Upload the official confirmation document here to complete verification.",
        ],
        "is_verified_directory": False,
    }


def _classify_workflow_and_level(finding: Finding) -> tuple[str, str, bool, bool]:
    """
    Return (workflow_type, automation_level, required_approval, external_institution_required).
    Levels:
    - FULLY_AUTOMATABLE
    - AUTOMATABLE_WITH_USER_APPROVAL
    - GUIDED_EXTERNAL_ACTION
    - MANUAL_VERIFICATION_REQUIRED
    """
    ft = (finding.finding_type or "").upper()
    if "NOMINEE" in ft:
        return "NOMINEE_VERIFICATION", "GUIDED_EXTERNAL_ACTION", True, True
    if "FD_MATURITY" in ft or "MISSING_SUPPORTING_DOC" in ft:
        return "FD_MATURITY", "AUTOMATABLE_WITH_USER_APPROVAL", True, True
    if "SUBSCRIPTION" in ft or "BANK_CHARGES" in ft:
        return "SUBSCRIPTION_AUDIT", "GUIDED_EXTERNAL_ACTION", True, True
    if "SALARY_DISCREPANCY" in ft or "TAX" in ft:
        return "TAX_RECONCILIATION", "AUTOMATABLE_WITH_USER_APPROVAL", True, True
    if "UNDISCOVERED_ACCOUNT" in ft:
        return "BANK_ACCOUNT_VERIFICATION", "GUIDED_EXTERNAL_ACTION", True, True
    if "RECONCILED_LOAN_EMI" in ft:
        return "LOAN_MANAGEMENT", "FULLY_AUTOMATABLE", False, False
    if "LOAN" in ft:
        return "LOAN_MANAGEMENT", "GUIDED_EXTERNAL_ACTION", True, True
    return "GENERAL_VERIFICATION", "MANUAL_VERIFICATION_REQUIRED", True, True


def _write_audit_log(
    db: Session,
    *,
    finding_id: int,
    user_id: int,
    action: str,
    actor: str = "SYSTEM",
    task_id: int | None = None,
    previous_status: str | None = None,
    new_status: str | None = None,
    details: str = "",
    metadata_json: dict[str, Any] | None = None,
) -> ActionAuditLog:
    entry = ActionAuditLog(
        task_id=task_id,
        finding_id=finding_id,
        user_id=user_id,
        action=action,
        actor=actor,
        previous_status=previous_status,
        new_status=new_status,
        details=details,
        metadata_json=metadata_json or {},
    )
    db.add(entry)
    return entry


def _extract_relevant_assets_and_docs(db: Session, user_id: int, finding: Finding) -> dict[str, Any]:
    assets = list(db.scalars(select(FinancialAsset).where(FinancialAsset.user_id == user_id)))
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.user_id == user_id))}
    txns = list(db.scalars(select(Transaction).where(Transaction.user_id == user_id)))
    ev_list = finding.evidence if isinstance(finding.evidence, list) else []
    desc = finding.description or ""

    # Identify matching asset from evidence document_id or reference token
    ev_doc_ids = {int(e["document_id"]) for e in ev_list if isinstance(e, dict) and str(e.get("document_id", "")).isdigit()}
    matching_assets = [a for a in assets if a.source_document_id in ev_doc_ids]

    ref_match = re.search(r"\b([A-Z]{2,6}-(?:LI|FD|SB|PL)-[A-Z0-9X]{4,16})\b", desc)
    extracted_ref = ref_match.group(1) if ref_match else None
    if not extracted_ref and matching_assets:
        extracted_ref = matching_assets[0].account_reference

    institution = None
    if matching_assets:
        institution = matching_assets[0].institution
    if not institution:
        inst_match = re.search(
            r"\b((?:SurakshaGuard|BharatLife|Kavach|Horizon Trust|MetroCivic|Saffron|Deccan|Crestline|HDFC|ICICI|SBI|Axis|LIC|Max Life)[^.,\n(]{0,40})",
            desc,
            re.IGNORECASE,
        )
        if inst_match:
            institution = inst_match.group(1).strip()

    return {
        "assets": assets,
        "matching_assets": matching_assets,
        "docs": docs,
        "txns": txns,
        "ev_list": ev_list,
        "institution": institution,
        "account_or_policy_ref": extracted_ref,
    }


def _build_workflow_payload(
    db: Session,
    user: User,
    finding: Finding,
    ctx: dict[str, Any],
    workflow_type: str,
) -> dict[str, Any]:
    """Build deterministic workflow analysis, entity extraction, and action steps for any finding type."""
    assets: list[FinancialAsset] = ctx["assets"]
    matching_assets: list[FinancialAsset] = ctx["matching_assets"]
    txns: list[Transaction] = ctx["txns"]
    docs: dict[int, Document] = ctx["docs"]
    institution = ctx["institution"]
    ref_code = ctx["account_or_policy_ref"]
    inst_info = _lookup_institution(institution)

    estimated_impact: float | None = None
    expected_evidence = "Upload an official confirmation document, updated statement, or institutional reference."
    draft_email = ""
    steps: list[dict[str, Any]] = []
    workflow_data: dict[str, Any] = {
        "institution_directory": inst_info,
        "extracted_entities": {
            "institution": inst_info["official_name"] if institution else None,
            "reference": ref_code,
            "holder_name": user.name,
            "source_documents": [
                {"document": e.get("document"), "page": e.get("page", 1)}
                for e in ctx["ev_list"]
                if isinstance(e, dict)
            ],
        },
    }

    if workflow_type == "NOMINEE_VERIFICATION":
        ins_asset = next((a for a in matching_assets if a.asset_type == "LIFE_INSURANCE"), None)
        if ins_asset is None:
            ins_asset = next((a for a in assets if a.asset_type == "LIFE_INSURANCE" and a.nominee_status == "NEEDS_VERIFICATION"), None)
        details = ins_asset.details if ins_asset and isinstance(ins_asset.details, dict) else {}
        policy_type = details.get("policy_type") or details.get("plan_type") or "Life Insurance Policy"
        sum_assured = float(ins_asset.amount) if ins_asset else None
        if sum_assured and sum_assured > 0:
            estimated_impact = sum_assured
        workflow_data["extracted_entities"].update({
            "insurer_name": ins_asset.institution if ins_asset else (institution or "Insurance Provider"),
            "policy_number": ins_asset.account_reference if ins_asset else (ref_code or "Unknown Policy Ref"),
            "policy_type": policy_type,
            "sum_assured_inr": sum_assured,
            "current_nominee_status": ins_asset.nominee_status if ins_asset else "NEEDS_VERIFICATION",
            "nominee_note": ins_asset.extracted_text if ins_asset else finding.description,
        })
        policy_lbl = workflow_data["extracted_entities"]["policy_number"]
        insurer_lbl = workflow_data["extracted_entities"]["insurer_name"]
        draft_email = (
            f"To: {inst_info.get('support_email') or 'Customer Care Desk'}\n"
            f"Subject: Request for Section 39 Nomination Status & Endorsement Confirmation – Policy {policy_lbl}\n\n"
            f"Dear {insurer_lbl} Servicing Team,\n\n"
            f"I am the policyholder for {policy_type} bearing Policy Reference {policy_lbl}. "
            f"During my policy review, Section 4 / Nomination details in my policy document copy appear unconfirmed or blank.\n\n"
            f"Kindly confirm:\n"
            f"1. Whether a nominee (u/s 39 of the Insurance Act, 1938) is currently registered in your active system for Policy {policy_lbl}.\n"
            f"2. If not registered, please share your official Section 39 Nomination Endorsement link or accept the signed nomination form attached herewith.\n\n"
            f"Please issue an updated Nomination Endorsement Receipt / Confirmation PDF with the endorsement reference number and date.\n\n"
            f"Regards,\n{user.name}\n({user.email})"
        )
        expected_evidence = (
            "Uploaded insurer endorsement confirmation PDF, updated policy schedule showing nominee name, "
            "or official insurer confirmation email containing endorsement reference and confirmation date."
        )
        steps = [
            {"id": "extract_policy", "label": f"Review extracted policy information ({insurer_lbl} • {policy_lbl}).", "execution_mode": "AUTO_INTERNAL", "completed": True},
            {"id": "download_form", "label": f"Download prefilled {inst_info['form_name']} and review update instructions.", "execution_mode": "AUTO_INTERNAL", "completed": False},
            {"id": "approve_request", "label": "Review and approve the insurer confirmation request email draft.", "execution_mode": "USER_APPROVAL", "completed": False},
            {"id": "submit_portal", "label": "Submit request directly via official insurer portal or branch.", "execution_mode": "EXTERNAL_INSTITUTION", "completed": False},
            {"id": "upload_verify", "label": "Upload received nomination endorsement/confirmation document for automated verification.", "execution_mode": "EVIDENCE_VERIFY", "completed": False},
        ]
        workflow_data["supports_form_download"] = True

    elif workflow_type == "FD_MATURITY":
        fd_asset = next((a for a in assets if a.asset_type == "FIXED_DEPOSIT"), None)
        ref_date = get_reference_date()
        days_left: int | None = None
        mat_date_str = None
        principal = float(fd_asset.amount) if fd_asset else None
        mat_amt = float((fd_asset.details or {}).get("maturity_amount", fd_asset.amount)) if fd_asset else None
        interest_rate = (fd_asset.details or {}).get("interest_rate") if fd_asset else None
        auto_renew = bool((fd_asset.details or {}).get("auto_renewal", False)) if fd_asset else False
        if fd_asset and fd_asset.maturity_date:
            days_left = (fd_asset.maturity_date - ref_date).days
            mat_date_str = fd_asset.maturity_date.strftime("%d-%b-%Y")
        estimated_impact = principal
        bank_name = fd_asset.institution if fd_asset else (institution or "Bank")
        fd_ref = fd_asset.account_reference if fd_asset else (ref_code or "FD Reference")
        workflow_data["fd_analysis"] = {
            "fd_reference": fd_ref,
            "institution": bank_name,
            "principal_inr": principal,
            "maturity_amount_inr": mat_amt,
            "interest_rate_pct": interest_rate,
            "maturity_date": mat_date_str,
            "days_remaining": days_left,
            "reference_date": ref_date.isoformat(),
            "auto_renewal_enabled": auto_renew,
            "renewal_comparison": [
                {"option": "Renew Full Maturity Proceeds", "best_for": "Capital stability & zero reinvestment gap", "note": "Check current bank slab rate before renewal; TDS applies if interest crosses threshold."},
                {"option": "Payout Principal + Interest to Savings", "best_for": "Upcoming liquidity needs / goal rebalancing", "note": "Avoids locking funds at potentially lower auto-renewal tenure."},
                {"option": "Split / Ladder FD Tenure", "best_for": "Balancing emergency liquidity & term yield", "note": "Keep 30-40% liquid and reinvest remainder in 1-2 yr bucket."},
            ],
        }
        draft_email = (
            f"To: {inst_info.get('support_email') or 'Term Deposit Desk'}\n"
            f"Subject: Maturity & Renewal Rate Enquiry – Fixed Deposit {fd_ref}\n\n"
            f"Dear {bank_name} Relationship Team,\n\n"
            f"My Fixed Deposit ({fd_ref}) with principal ₹{(principal or 0):,.2f} is scheduled to mature on {mat_date_str or 'upcoming date'} "
            f"({'auto-renewal enabled' if auto_renew else 'auto-renewal NOT enabled'}).\n\n"
            f"Please confirm current 1-year and 2-year renewal FD card rates applicable on maturity and process payout/renewal only per my verified NetBanking/branch instruction.\n\n"
            f"Regards,\n{user.name}"
        )
        expected_evidence = "Updated FD Renewal Advice, Bank Maturity Payout Confirmation Receipt, or NetBanking SR confirmation reference."
        steps = [
            {"id": "calc_maturity", "label": f"Extracted maturity timeline ({mat_date_str or 'N/A'}, {days_left if days_left is not None else '?'} days remaining) & scheduled reminder.", "execution_mode": "AUTO_INTERNAL", "completed": True},
            {"id": "review_comparison", "label": "Review generated renewal comparison options vs liquidity needs.", "execution_mode": "USER_APPROVAL", "completed": False},
            {"id": "approve_enquiry", "label": "Approve optional bank rate/maturity instruction enquiry draft.", "execution_mode": "USER_APPROVAL", "completed": False},
            {"id": "submit_bank", "label": "Submit renewal/payout instruction in official NetBanking portal.", "execution_mode": "EXTERNAL_INSTITUTION", "completed": False},
            {"id": "upload_receipt", "label": "Upload bank confirmation receipt / SR number to verify completion.", "execution_mode": "EVIDENCE_VERIFY", "completed": False},
        ]
        workflow_data["supports_form_download"] = True

    elif workflow_type == "SUBSCRIPTION_AUDIT":
        sub_txns = [t for t in txns if t.category in ("SUBSCRIPTION", "BANK_FEE_SMS", "BANK_FEE_AMC")]
        by_merchant: dict[str, list[Transaction]] = defaultdict(list)
        for tx in sub_txns:
            by_merchant[re.sub(r"\s+", " ", tx.description.upper()).split("/")[0][:35]].append(tx)

        merchants_audit = []
        annual_total = 0.0
        price_hikes = []
        for mname, items in sorted(by_merchant.items()):
            ordered = sorted(items, key=lambda x: x.transaction_date)
            amts = [float(i.amount) for i in ordered]
            latest_amt = amts[-1]
            # Annualize conservatively using observed cadence
            est_annual = round(sum(amts), 2) if len(amts) >= 6 else round(latest_amt * 12, 2) if any("AMC" not in i.category for i in ordered) else round(sum(amts), 2)
            annual_total += est_annual
            hike_detected = len(amts) >= 2 and amts[-1] > amts[0] + 1.0
            if hike_detected:
                price_hikes.append({"merchant": mname, "from_inr": amts[0], "to_inr": amts[-1]})
            m_info = _lookup_institution(mname)
            merchants_audit.append({
                "merchant": mname,
                "debit_count": len(ordered),
                "latest_amount_inr": latest_amt,
                "estimated_annual_inr": est_annual,
                "price_increase_detected": hike_detected,
                "official_cancel_url": m_info.get("official_website"),
                "cancel_instructions": m_info.get("cancel_steps", [
                    "Open provider billing settings or UPI Autopay section in your banking app to review/revoke mandate."
                ]),
            })
        estimated_impact = round(annual_total, 2) if annual_total > 0 else None
        workflow_data["subscription_audit"] = {
            "total_estimated_annual_inr": estimated_impact or 0.0,
            "price_increases_detected": price_hikes,
            "merchants": merchants_audit,
        }
        top_merch = merchants_audit[0]["merchant"] if merchants_audit else "Subscription Provider"
        draft_email = (
            f"Subject: Subscription Audit & Cancellation Confirmation Request\n\n"
            f"Hello {top_merch} Billing Support,\n\n"
            f"Please confirm cancellation / auto-renewal disablement for my recurring plan under {user.email} and provide a cancellation reference ID so no further recurring charges are billed.\n\n"
            f"Regards,\n{user.name}"
        )
        expected_evidence = "Cancellation confirmation email/receipt, revoked UPI Autopay mandate screenshot/reference, or explicit audit confirmation note."
        steps = [
            {"id": "detect_recurring", "label": f"Detected {len(merchants_audit)} recurring merchant/fee streams (Est. ₹{(estimated_impact or 0):,.2f}/yr).", "execution_mode": "AUTO_INTERNAL", "completed": True},
            {"id": "review_hikes", "label": "Review subscription usage and any price increases detected.", "execution_mode": "USER_APPROVAL", "completed": False},
            {"id": "cancel_provider", "label": "Cancel unwanted plans or revoke UPI Autopay mandate on official provider portal.", "execution_mode": "EXTERNAL_INSTITUTION", "completed": False},
            {"id": "verify_sub", "label": "Upload cancellation confirmation or record verified keep/cancel decision.", "execution_mode": "EVIDENCE_VERIFY", "completed": False},
        ]
        workflow_data["supports_form_download"] = False

    elif workflow_type == "TAX_RECONCILIATION":
        ais_sal = next((a for a in assets if a.asset_type == "AIS_SALARY_SUMMARY"), None)
        f16_sal = next((a for a in assets if a.asset_type == "FORM16_SALARY"), None)
        ais_amt = float(ais_sal.amount) if ais_sal else 0.0
        f16_amt = float(f16_sal.amount) if f16_sal else 0.0
        diff = round(abs(ais_amt - f16_amt), 2)
        estimated_impact = diff if diff > 0 else None
        ais_tds = float((ais_sal.details or {}).get("tds_deposited", 0.0)) if ais_sal else 0.0
        f16_tds = float((f16_sal.details or {}).get("tds_deducted", 0.0)) if f16_sal else 0.0
        cpa_questions = [
            f"Why does AIS TDS-192 report ₹{ais_amt:,.2f} while Form 16 Part B shows ₹{f16_amt:,.2f} (difference ₹{diff:,.2f})?",
            "Could the gap stem from Section 10 exemptions (HRA/LTA), employer perquisites, or a delayed Q4 Form 24Q revision?",
            f"Since TDS matches/reads AIS ₹{ais_tds:,.2f} vs Form 16 ₹{f16_tds:,.2f}, should Form 16 Part B vs AIS Feedback ('Information is not fully correct') be submitted before ITR filing?",
        ]
        workflow_data["tax_reconciliation"] = {
            "ais_gross_salary_inr": ais_amt,
            "form16_gross_salary_inr": f16_amt,
            "discrepancy_inr": diff,
            "ais_tds_inr": ais_tds,
            "form16_tds_inr": f16_tds,
            "questions_for_tax_professional": cpa_questions,
        }
        draft_email = (
            f"Subject: Payroll & Tax Reconciliation Request – AIS vs Form 16 Difference (₹{diff:,.2f})\n\n"
            f"Dear Payroll / Tax Advisor,\n\n"
            f"During my FY 2025-26 tax document check, AIS reports gross salary ₹{ais_amt:,.2f} while Form 16 reports ₹{f16_amt:,.2f} "
            f"(difference ₹{diff:,.2f}; TDS reported: Form 16 ₹{f16_tds:,.2f} / AIS ₹{ais_tds:,.2f}).\n\n"
            f"Please share the itemized salary & Form 24Q break-up clarifying this difference before I finalize my ITR.\n\n"
            f"Regards,\n{user.name}"
        )
        expected_evidence = "Revised Form 16 / Employer Payroll Reconciliation PDF, updated AIS printout, or CA sign-off reference."
        steps = [
            {"id": "compare_ais_f16", "label": f"Cross-compared AIS (₹{ais_amt:,.2f}) vs Form 16 (₹{f16_amt:,.2f}); isolated ₹{diff:,.2f} variance.", "execution_mode": "AUTO_INTERNAL", "completed": True},
            {"id": "review_tax_brief", "label": "Review discrepancy summary & prepared tax advisor questions.", "execution_mode": "USER_APPROVAL", "completed": False},
            {"id": "request_hr_ca", "label": "Send approved payroll reconciliation query to employer HR / CA.", "execution_mode": "EXTERNAL_INSTITUTION", "completed": False},
            {"id": "verify_reconcile", "label": "Upload revised Form 16 / payroll reconciliation statement for verification.", "execution_mode": "EVIDENCE_VERIFY", "completed": False},
        ]
        workflow_data["supports_form_download"] = True

    elif workflow_type == "BANK_ACCOUNT_VERIFICATION":
        ais_sb = next((a for a in assets if a.asset_type == "AIS_SAVINGS_ACCOUNT"), None)
        bank_name = ais_sb.institution if ais_sb else (institution or "Bank")
        acc_ref = ais_sb.account_reference if ais_sb else (ref_code or "AIS Savings Account")
        interest_amt = float(ais_sb.amount) if ais_sb else None
        estimated_impact = interest_amt
        workflow_data["bank_verification"] = {
            "bank_name": bank_name,
            "account_reference": acc_ref,
            "ais_interest_inr": interest_amt,
        }
        draft_email = (
            f"To: {inst_info.get('support_email') or 'Branch Customer Care'}\n"
            f"Subject: Request for Savings Account Status & Statement – Account {acc_ref}\n\n"
            f"Dear {bank_name} Team,\n\n"
            f"My Income Tax AIS (SFT-016 / Interest Schedule) reflects savings account {acc_ref} with interest ₹{(interest_amt or 0):,.2f}. "
            f"Kindly confirm whether this account is active or dormant under my PAN/customer ID and issue the FY 2025-26 statement.\n\n"
            f"Regards,\n{user.name}"
        )
        expected_evidence = "Uploaded Bank Statement PDF for the AIS account, account closure certificate, or official bank confirmation letter."
        steps = [
            {"id": "identify_ais_acc", "label": f"Extracted AIS account reference {acc_ref} ({bank_name}).", "execution_mode": "AUTO_INTERNAL", "completed": True},
            {"id": "approve_bank_mail", "label": "Review and approve bank verification / statement request draft.", "execution_mode": "USER_APPROVAL", "completed": False},
            {"id": "fetch_stmt", "label": "Verify ownership or download FY statement from official bank portal/branch.", "execution_mode": "EXTERNAL_INSTITUTION", "completed": False},
            {"id": "upload_bank_ev", "label": "Upload bank statement / closure proof to resolve finding.", "execution_mode": "EVIDENCE_VERIFY", "completed": False},
        ]
        workflow_data["supports_form_download"] = True

    elif workflow_type == "LOAN_MANAGEMENT":
        loan_asset = next((a for a in assets if a.asset_type == "PERSONAL_LOAN"), None)
        emi_txns = [t for t in txns if t.category == "LOAN_EMI"]
        emi_amt = float((loan_asset.details or {}).get("monthly_emi", 0.0)) if loan_asset else (float(emi_txns[0].amount) if emi_txns else 0.0)
        lender_name = loan_asset.institution if loan_asset else (institution or "Loan Provider")
        loan_ref = loan_asset.account_reference if loan_asset else (ref_code or "Loan Reference")
        outstanding = float(loan_asset.amount) if loan_asset else None
        estimated_impact = outstanding or (emi_amt * 12 if emi_amt else None)
        is_reconciled = (finding.finding_type or "").upper() == "RECONCILED_LOAN_EMI"
        workflow_data["loan_analysis"] = {
            "lender": lender_name,
            "loan_reference": loan_ref,
            "monthly_emi_inr": emi_amt,
            "outstanding_principal_inr": outstanding,
            "emi_debits_observed": len(emi_txns),
            "reconciled": is_reconciled,
        }
        if is_reconciled:
            expected_evidence = "Auto-verified from matching NACH debits in uploaded bank statement and loan schedule."
            steps = [
                {"id": "reconcile_emi", "label": f"Cross-matched {len(emi_txns)} bank NACH debits of ₹{emi_amt:,.2f} with loan terms.", "execution_mode": "AUTO_INTERNAL", "completed": True},
                {"id": "confirm_reconcile", "label": "Automated reconciliation verification ready to finalize.", "execution_mode": "AUTO_INTERNAL", "completed": False},
            ]
        else:
            draft_email = (
                f"To: {inst_info.get('support_email') or 'Loan Servicing Desk'}\n"
                f"Subject: Request for Loan Statement & Repayment Schedule – {loan_ref}\n\n"
                f"Dear {lender_name} Servicing Team,\n\n"
                f"Please share the latest Loan Account Statement, Amortization Schedule (Interest + Principal split), and applicable Rate of Interest for my loan ({loan_ref}, observed EMI ₹{emi_amt:,.2f}).\n\n"
                f"Regards,\n{user.name}"
            )
            expected_evidence = "Uploaded Loan Statement PDF / Repayment Schedule or lender confirmation matching the EMI amount."
            steps = [
                {"id": "extract_emi", "label": f"Extracted EMI debits (₹{emi_amt:,.2f}/mo across {len(emi_txns)} debit(s)) and missing statement gap.", "execution_mode": "AUTO_INTERNAL", "completed": True},
                {"id": "approve_lender", "label": "Review and approve lender statement request email draft.", "execution_mode": "USER_APPROVAL", "completed": False},
                {"id": "obtain_loan_stmt", "label": "Download official Loan Statement from lender portal.", "execution_mode": "EXTERNAL_INSTITUTION", "completed": False},
                {"id": "upload_loan_ev", "label": "Upload Loan Statement PDF or EMI confirmation for verification.", "execution_mode": "EVIDENCE_VERIFY", "completed": False},
            ]
        workflow_data["supports_form_download"] = not is_reconciled

    else:
        steps = [
            {"id": "inspect_ev", "label": "Review flagged financial evidence snippet.", "execution_mode": "AUTO_INTERNAL", "completed": True},
            {"id": "verify_doc", "label": "Confirm record status with institution and upload proof.", "execution_mode": "EVIDENCE_VERIFY", "completed": False},
        ]
        workflow_data["supports_form_download"] = False

    workflow_data["steps"] = steps
    return {
        "steps": steps,
        "draft_email": draft_email or None,
        "expected_evidence": expected_evidence,
        "estimated_impact_inr": estimated_impact,
        "institution_name": inst_info["official_name"] if institution else None,
        "account_or_policy_ref": ref_code,
        "generated_plan": workflow_data,
    }


async def _enrich_action_plan_with_groq(
    finding: Finding,
    workflow_type: str,
    automation_level: str,
    base_plan: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Use Groq LLM to refine issue summary, actionable steps, and draft email safely (falls back cleanly if offline/rate-limited)."""
    settings = get_settings()
    if not settings.is_groq_configured():
        return base_plan, False
    try:
        endpoint, api_key, model, timeout, _retries = _resolve_groq_endpoint()
    except HTTPException:
        return base_plan, False

    prompt_payload = {
        "finding_title": finding.title,
        "finding_type": finding.finding_type,
        "finding_description": finding.description,
        "workflow_type": workflow_type,
        "automation_level": automation_level,
        "extracted_entities": base_plan["generated_plan"].get("extracted_entities"),
        "workflow_summary": {
            k: v
            for k, v in base_plan["generated_plan"].items()
            if k in ("fd_analysis", "subscription_audit", "tax_reconciliation", "bank_verification", "loan_analysis")
        },
        "default_steps": [s["label"] for s in base_plan["steps"]],
    }
    sys_msg = (
        "You are ArthaLens AI Action Architect. Given extracted financial finding evidence, produce a concise, specific JSON object with:\n"
        '{\n'
        '  "issue_summary": "1-2 sentence exact diagnosis citing policy/account ref and institution",\n'
        '  "required_action": "1 sentence clear concrete next action",\n'
        '  "steps": ["concise step 1", "concise step 2", ...],\n'
        '  "draft_email": "Optional polite reviewable request email or null"\n'
        '}\n'
        "Rules: Never claim ArthaLens will auto-submit forms, log into portals with passwords, or modify records directly. Keep steps specific to the extracted numbers/refs."
    )
    try:
        async with httpx.AsyncClient(timeout=min(12.0, timeout)) as client:
            resp = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0.1,
                    "max_tokens": 480,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": json.dumps(prompt_payload, default=str)},
                    ],
                },
            )
            if resp.status_code != 200:
                return base_plan, False
            raw = str((resp.json().get("choices") or [{}])[0].get("message", {}).get("content") or "{}").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
            parsed = json.loads(raw)
            ai_steps = parsed.get("steps")
            if isinstance(ai_steps, list) and len(ai_steps) >= 2:
                # Preserve execution_mode mapping across refined labels cleanly
                orig_steps = base_plan["steps"]
                merged_steps = []
                for idx, lbl in enumerate(ai_steps[:6]):
                    clean_lbl = str(lbl).strip()
                    if not clean_lbl:
                        continue
                    mode = orig_steps[min(idx, len(orig_steps) - 1)]["execution_mode"] if orig_steps else "EVIDENCE_VERIFY"
                    prev_done = orig_steps[idx]["completed"] if idx < len(orig_steps) else False
                    merged_steps.append({
                        "id": f"ai_step_{idx+1}",
                        "label": clean_lbl,
                        "execution_mode": mode,
                        "completed": prev_done,
                    })
                if merged_steps:
                    base_plan["steps"] = merged_steps
                    base_plan["generated_plan"]["steps"] = merged_steps
            if parsed.get("issue_summary"):
                base_plan["issue_summary"] = str(parsed["issue_summary"]).strip()
            if parsed.get("required_action"):
                base_plan["required_action"] = str(parsed["required_action"]).strip()
            if parsed.get("draft_email") and isinstance(parsed["draft_email"], str) and len(parsed["draft_email"].strip()) > 30:
                base_plan["draft_email"] = parsed["draft_email"].strip()
            return base_plan, True
    except Exception as exc:
        logger.info("Groq action plan fallback used cleanly (%s)", type(exc).__name__)
        return base_plan, False


def _sync_fd_reminder(db: Session, user_id: int, finding: Finding, task: AutomationTask, plan_data: dict[str, Any]) -> FinancialReminder | None:
    if task.workflow_type != "FD_MATURITY":
        return None
    fd_info = plan_data.get("fd_analysis") or {}
    fd_asset = db.scalar(select(FinancialAsset).where(FinancialAsset.user_id == user_id, FinancialAsset.asset_type == "FIXED_DEPOSIT"))
    due = fd_asset.maturity_date if fd_asset else None
    days_left = fd_info.get("days_remaining")
    rem = db.scalar(select(FinancialReminder).where(FinancialReminder.task_id == task.id, FinancialReminder.reminder_type == "FD_MATURITY"))
    msg = (
        f"FD {fd_info.get('fd_reference')} at {fd_info.get('institution')} matures on {fd_info.get('maturity_date') or 'upcoming date'} "
        f"({days_left if days_left is not None else 'upcoming'} days left). Review renewal vs payout options."
    )
    if rem is None:
        rem = FinancialReminder(
            user_id=user_id,
            finding_id=finding.id,
            task_id=task.id,
            reminder_type="FD_MATURITY",
            title=f"FD Maturity Reminder: {fd_info.get('fd_reference')}",
            message=msg,
            due_date=due,
            days_remaining=days_left,
            status="SCHEDULED",
        )
        db.add(rem)
        db.flush()
        _write_audit_log(
            db,
            task_id=task.id,
            finding_id=finding.id,
            user_id=user_id,
            action="REMINDER_CREATED",
            actor="SYSTEM",
            previous_status=task.task_status,
            new_status=task.task_status,
            details=msg,
        )
    else:
        rem.days_remaining = days_left
        rem.due_date = due
        rem.message = msg
    return rem


def get_or_create_automation_task(
    db: Session,
    user: User,
    finding: Finding,
    *,
    force_refresh: bool = False,
) -> AutomationTask:
    """Idempotently build and persist an AutomationTask for `finding`."""
    task = db.scalar(
        select(AutomationTask).where(AutomationTask.finding_id == finding.id, AutomationTask.user_id == user.id)
    )
    workflow_type, automation_level, req_approval, ext_req = _classify_workflow_and_level(finding)
    if task is not None and not force_refresh:
        return task

    ctx = _extract_relevant_assets_and_docs(db, user.id, finding)
    plan = _build_workflow_payload(db, user, finding, ctx, workflow_type)

    if task is None:
        initial_status = "Completed" if finding.status == "RESOLVED" else ("In Progress" if finding.status == "IN_REVIEW" else "Not Started")
        task = AutomationTask(
            finding_id=finding.id,
            user_id=user.id,
            workflow_type=workflow_type,
            automation_level=automation_level,
            task_status=initial_status,
            required_approval=req_approval,
            approval_granted=False,
            issue_summary=finding.description,
            required_action=plan["steps"][0]["label"] if plan["steps"] else finding.title,
            external_institution_required=ext_req,
            institution_name=plan["institution_name"],
            account_or_policy_ref=plan["account_or_policy_ref"],
            expected_evidence=plan["expected_evidence"],
            estimated_impact_inr=plan["estimated_impact_inr"],
            generated_plan=plan["generated_plan"],
            completed_steps=[s["label"] for s in plan["steps"] if s.get("completed")],
            draft_email=plan["draft_email"],
            ai_generated=False,
        )
        db.add(task)
        db.flush()
        _write_audit_log(
            db,
            task_id=task.id,
            finding_id=finding.id,
            user_id=user.id,
            action="PLAN_GENERATED",
            actor="AI_ENGINE",
            new_status=initial_status,
            details=f"Classified as {automation_level} ({workflow_type}).",
        )
    else:
        task.workflow_type = workflow_type
        task.automation_level = automation_level
        task.institution_name = plan["institution_name"]
        task.account_or_policy_ref = plan["account_or_policy_ref"]
        task.expected_evidence = plan["expected_evidence"]
        task.estimated_impact_inr = plan["estimated_impact_inr"]
        task.generated_plan = plan["generated_plan"]
        if not task.draft_email and plan["draft_email"]:
            task.draft_email = plan["draft_email"]

    _sync_fd_reminder(db, user.id, finding, task, plan["generated_plan"])
    db.commit()
    db.refresh(task)
    return task


async def run_automate_workflow(
    db: Session,
    user: User,
    finding: Finding,
    *,
    use_groq: bool = True,
) -> AutomationTask:
    """Execute safe internal automation (extraction, reminders, form/email preparation, AI planning) and update progress."""
    task = get_or_create_automation_task(db, user, finding, force_refresh=True)
    ctx = _extract_relevant_assets_and_docs(db, user.id, finding)
    plan = _build_workflow_payload(db, user, finding, ctx, task.workflow_type)

    used_groq = False
    if use_groq:
        plan, used_groq = await _enrich_action_plan_with_groq(finding, task.workflow_type, task.automation_level, plan)

    prev_status = task.task_status
    task.generated_plan = plan["generated_plan"]
    task.draft_email = plan["draft_email"]
    task.issue_summary = plan.get("issue_summary") or finding.description
    task.required_action = plan.get("required_action") or (plan["steps"][0]["label"] if plan["steps"] else finding.title)
    task.ai_generated = task.ai_generated or used_groq

    # Safe internal automation completion for FULLY_AUTOMATABLE reconciled checks ONLY
    if task.automation_level == "FULLY_AUTOMATABLE" and task.workflow_type == "LOAN_MANAGEMENT":
        reconciled = bool((plan["generated_plan"].get("loan_analysis") or {}).get("reconciled"))
        if reconciled:
            completed = [s["label"] for s in plan["steps"]]
            task.completed_steps = completed
            task.task_status = "Completed"
            task.last_verification_summary = "Automatically reconciled bank statement NACH EMI debits against loan schedule."
            finding.status = "RESOLVED"
            prog = db.scalar(select(FindingProgress).where(FindingProgress.finding_id == finding.id, FindingProgress.user_id == user.id))
            if prog is None:
                prog = FindingProgress(finding_id=finding.id, user_id=user.id)
                db.add(prog)
            prog.completed_steps = completed
            prog.verification_evidence = task.last_verification_summary
            prog.resolved_at = get_utc_now()
            _write_audit_log(
                db,
                task_id=task.id,
                finding_id=finding.id,
                user_id=user.id,
                action="WORKFLOW_AUTOMATED",
                actor="AI_ENGINE",
                previous_status=prev_status,
                new_status="Completed",
                details=task.last_verification_summary,
            )
            db.commit()
            db.refresh(task)
            return task

    # All external / approval workflows advance ONLY to "In Progress" (never "Completed")
    if task.task_status in ("Not Started", "Failed"):
        task.task_status = "In Progress"
        if finding.status == "OPEN":
            finding.status = "IN_REVIEW"

    # Mark internal extraction steps done
    auto_done = [s["label"] for s in plan["steps"] if s.get("execution_mode") == "AUTO_INTERNAL" and s.get("completed")]
    existing_done = list(task.completed_steps or [])
    for lbl in auto_done:
        if lbl not in existing_done:
            existing_done.append(lbl)
    task.completed_steps = existing_done

    _sync_fd_reminder(db, user.id, finding, task, plan["generated_plan"])
    _write_audit_log(
        db,
        task_id=task.id,
        finding_id=finding.id,
        user_id=user.id,
        action="WORKFLOW_AUTOMATED",
        actor="AI_ENGINE",
        previous_status=prev_status,
        new_status=task.task_status,
        details=(
            f"Prepared automated workflow ({task.workflow_type}); external submission/verification remains required."
            + (" Enriched with Groq AI." if used_groq else "")
        ),
    )
    db.commit()
    db.refresh(task)
    return task


def approve_prepared_action(
    db: Session,
    user: User,
    finding: Finding,
    *,
    approved: bool,
    edited_draft_email: str | None = None,
    notes: str | None = None,
) -> AutomationTask:
    """Record explicit user approval of prepared drafts/forms. Never marks external actions as Completed."""
    task = get_or_create_automation_task(db, user, finding)
    prev_status = task.task_status
    if edited_draft_email is not None and edited_draft_email.strip():
        task.draft_email = edited_draft_email.strip()

    if not approved:
        _write_audit_log(
            db,
            task_id=task.id,
            finding_id=finding.id,
            user_id=user.id,
            action="APPROVAL_WITHHELD",
            actor="USER",
            previous_status=prev_status,
            new_status=prev_status,
            details=notes or "User reviewed without approving external submission yet.",
        )
        db.commit()
        db.refresh(task)
        return task

    task.approval_granted = True
    task.approved_at = get_utc_now()
    if task.task_status not in ("Completed", "Evidence Received"):
        task.task_status = "Awaiting External Confirmation" if task.external_institution_required else "Verification Required"
    if finding.status == "OPEN":
        finding.status = "IN_REVIEW"

    # Mark USER_APPROVAL step done
    steps = (task.generated_plan or {}).get("steps") or []
    done = list(task.completed_steps or [])
    for s in steps:
        if isinstance(s, dict) and s.get("execution_mode") == "USER_APPROVAL":
            if s["label"] not in done:
                done.append(s["label"])
    task.completed_steps = done

    _write_audit_log(
        db,
        task_id=task.id,
        finding_id=finding.id,
        user_id=user.id,
        action="DRAFT_APPROVED",
        actor="USER",
        previous_status=prev_status,
        new_status=task.task_status,
        details=notes or "User reviewed and approved prepared draft/instructions. Awaiting external confirmation & evidence upload.",
    )
    db.commit()
    db.refresh(task)
    return task


def enforce_security_boundary(
    db: Session,
    user: User,
    finding: Finding,
    requested_action: str,
) -> None:
    """Block unauthorized autonomous actions (auto-submit, portal logins, cancellations, unverified completion) and log to audit."""
    act_key = (requested_action or "").strip().upper()
    reason = FORBIDDEN_AUTONOMOUS_ACTIONS.get(
        act_key,
        "Action blocked by ArthaLens Financial Safety Guardrail: unauthorized autonomous external execution is prohibited.",
    )
    task = get_or_create_automation_task(db, user, finding)
    _write_audit_log(
        db,
        task_id=task.id,
        finding_id=finding.id,
        user_id=user.id,
        action="UNAUTHORIZED_ACTION_BLOCKED",
        actor="SYSTEM",
        previous_status=task.task_status,
        new_status=task.task_status,
        details=f"Blocked '{act_key}': {reason}",
        metadata_json={"blocked_action": act_key},
    )
    db.commit()
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


def build_prefilled_form_pdf(db: Session, user: User, finding: Finding) -> tuple[bytes, str]:
    """Generate a prefilled PDF Nomination Endorsement / Institution Servicing Packet (user must review & submit externally)."""
    task = get_or_create_automation_task(db, user, finding)
    plan = task.generated_plan or {}
    entities = plan.get("extracted_entities") or {}
    inst = plan.get("institution_directory") or {}

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    margin = 48
    y = 54

    def write_line(text: str, size: float = 10.5, bold: bool = False, color=(0.07, 0.07, 0.07), gap: float = 16):
        nonlocal y
        page.insert_text(
            pymupdf.Point(margin, y),
            text,
            fontsize=size,
            fontname="helv",
            color=color,
        )
        y += gap

    write_line("ARTHALENS FINANCIAL ACTION PACKET (PREFILLED FOR USER SUBMISSION)", size=12, gap=18)
    write_line(f"Official Form: {inst.get('form_name', 'Service Request Form')} ({inst.get('form_code', 'ARTHA-FORM')})", size=9.5, color=(0.35, 0.35, 0.35), gap=14)
    write_line(f"Generated (IST): {format_ist_display(get_ist_now(), long_month=True)}", size=9, color=(0.45, 0.45, 0.45), gap=20)
    page.draw_line(pymupdf.Point(margin, y - 6), pymupdf.Point(547, y - 6), color=(0.85, 0.85, 0.85))
    y += 10

    write_line("1. HOLDER & EXTRACTED RECORD DETAILS", size=10.5, gap=16)
    write_line(f"Holder / Customer Name : {user.name} ({user.email})", size=10, gap=15)
    write_line(f"Institution            : {task.institution_name or inst.get('official_name', 'N/A')}", size=10, gap=15)
    write_line(f"Account / Policy Ref   : {task.account_or_policy_ref or 'Refer attached policy/statement'}", size=10, gap=15)
    if entities.get("policy_type"):
        write_line(f"Policy Type            : {entities.get('policy_type')}", size=10, gap=15)
    if inst.get("official_website"):
        write_line(f"Official Portal        : {inst.get('official_website')}", size=9.5, gap=15)
    if inst.get("support_email"):
        write_line(f"Support Email          : {inst.get('support_email')}", size=9.5, gap=22)

    if task.workflow_type == "NOMINEE_VERIFICATION":
        write_line("2. SECTION 39 NOMINATION DETAILS (TO BE COMPLETED / VERIFIED BY HOLDER)", size=10.5, gap=18)
        for field in (
            "Nominee Full Name      : __________________________________________________",
            "Relationship to Insured: __________________________________________________",
            "Nominee Date of Birth  : ____ / ____ / ________   Share (%): 100%",
            "Appointee (if minor)   : __________________________________________________",
            "Action Requested       : [ ] Confirm Existing Nomination   [ ] Register / Update Nominee",
        ):
            write_line(field, size=10, gap=18)
    else:
        write_line("2. REQUEST SUMMARY", size=10.5, gap=16)
        for line in (finding.description or "")[:500].splitlines() or [finding.title]:
            while len(line) > 88:
                write_line(line[:88], size=9.5, gap=13)
                line = line[88:]
            write_line(line, size=9.5, gap=15)

    y += 16
    write_line("3. DECLARATION & SUBMISSION INSTRUCTIONS", size=10.5, gap=16)
    write_line("I confirm the above details are reviewed by me for submission to my financial institution.", size=9.5, gap=24)
    write_line("Policyholder / Customer Signature: ______________________    Date: ____________", size=10, gap=26)
    write_line(
        "NOTE: Downloading this packet does NOT change your institution record or complete verification.",
        size=8.5,
        color=(0.45, 0.45, 0.45),
        gap=12,
    )
    write_line(
        "Submit directly through your official insurer/bank portal, then upload the stamped receipt/endorsement in ArthaLens.",
        size=8.5,
        color=(0.45, 0.45, 0.45),
        gap=12,
    )

    pdf_bytes = doc.tobytes()
    doc.close()

    prev_status = task.task_status
    # Downloading a form advances Not Started -> In Progress ONLY (NEVER Completed!)
    if task.task_status == "Not Started":
        task.task_status = "In Progress"
        if finding.status == "OPEN":
            finding.status = "IN_REVIEW"

    _write_audit_log(
        db,
        task_id=task.id,
        finding_id=finding.id,
        user_id=user.id,
        action="FORM_DOWNLOADED",
        actor="USER",
        previous_status=prev_status,
        new_status=task.task_status,
        details=f"Downloaded prefilled {inst.get('form_code', 'FORM')} packet. Status NOT marked completed (external confirmation required).",
    )
    db.commit()

    safe_ref = re.sub(r"[^A-Za-z0-9_-]+", "_", task.account_or_policy_ref or f"Finding_{finding.id}")
    return pdf_bytes, f"ArthaLens_{task.workflow_type}_{safe_ref}.pdf"


def _extract_evidence_fields(text: str) -> dict[str, Any]:
    """Extract structured confirmation fields (nominee name, endorsement ref, date, policy/account refs) from text/PDF."""
    clean = re.sub(r"\s+", " ", text or "").strip()
    nominee_match = re.search(
        r"(?:nominee(?:\s+full)?\s+name|registered\s+nominee|nominee\s+updated\s+to|nominee)\s*[:\-–]\s*([A-Za-z][A-Za-z .'-]{2,60}(?:\([A-Za-z]+\))?)",
        clean,
        re.IGNORECASE,
    )
    endorse_match = (
        re.search(
            r"(?:endorsement\s*(?:ref|reference|no|number|id|#)|service\s*request(?:\s*(?:ref|no|id|#))?|sr\s*#|confirmation\s*(?:ref|reference|id|no|#))\s*[:\-#]?\s*([A-Z0-9-]{4,30})",
            clean,
            re.IGNORECASE,
        )
        or re.search(
            r"(?<!policy\s)(?<!account\s)\breference\s*(?:no|number|id|#)?\s*[:\-#]\s*([A-Z0-9-]{4,30})",
            clean,
            re.IGNORECASE,
        )
    )
    date_match = re.search(
        r"\b(\d{1,2}[-/ ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2})[-/ ]\d{2,4}|\d{4}-\d{2}-\d{2})\b",
        clean,
        re.IGNORECASE,
    )
    ref_matches = re.findall(r"\b([A-Z]{2,6}-(?:LI|FD|SB|PL)-[A-Z0-9X]{4,16})\b", clean.upper())
    last4_matches = re.findall(r"(?:XX|xx|\*{2,4}|ending\s+in\s+|account\s+#?)(\d{4})\b", clean)

    nominee_val = nominee_match.group(1).strip(" .,;") if nominee_match else None
    if nominee_val and re.search(r"\b(blank|none|not registered|missing|unavailable|n/a|nil|pending)\b", nominee_val, re.IGNORECASE):
        nominee_val = None

    return {
        "nominee_name": nominee_val,
        "endorsement_reference": endorse_match.group(1).strip() if endorse_match else None,
        "confirmation_date": date_match.group(1).strip() if date_match else None,
        "document_references": ref_matches,
        "last4_digits": last4_matches,
    }


def verify_evidence_against_finding(
    finding: Finding,
    task: AutomationTask,
    evidence_text: str,
    extracted: dict[str, Any],
    *,
    nominee_override: str | None = None,
    endorsement_override: str | None = None,
    date_override: str | None = None,
) -> tuple[str, str]:
    """
    Validate uploaded evidence strictly against expected completion criteria.
    Returns (verification_status: 'VERIFIED' | 'FAILED', explanation: str).
    """
    text = (evidence_text or "").strip()
    low = text.lower()
    nominee = (nominee_override or extracted.get("nominee_name") or "").strip()
    endorse_ref = (endorsement_override or extracted.get("endorsement_reference") or "").strip()
    conf_date = (date_override or extracted.get("confirmation_date") or "").strip()

    if len(text) < 10 and not (nominee and endorse_ref):
        return "FAILED", "Insufficient evidence text or document content provided to verify completion."

    # Guard against unrelated / mismatched policy or account references
    expected_ref = (task.account_or_policy_ref or "").upper()
    exp_last4 = expected_ref[-4:] if len(expected_ref) >= 4 and expected_ref[-4:].isdigit() else ""
    found_refs = [r.upper() for r in (extracted.get("document_references") or [])]
    found_last4 = extracted.get("last4_digits") or []
    if found_refs and expected_ref:
        # Fail if evidence explicitly references a different last-4 ID!
        ref_last4s = [r[-4:] for r in found_refs if r[-4:].isdigit()]
        if exp_last4 and ref_last4s and exp_last4 not in ref_last4s:
            return (
                "FAILED",
                f"Document belongs to reference(s) {', '.join(found_refs)} which do not match target {expected_ref}.",
            )
    elif exp_last4 and found_last4 and exp_last4 not in found_last4 and (task.institution_name or "").split()[0].lower() not in low:
        return (
            "FAILED",
            f"Uploaded confirmation mentions account ending {found_last4[0]}, which does not match expected {expected_ref}.",
        )

    # Guard against negative/incomplete states (draft emails, blank forms, rejections, pending requests)
    if re.search(r"\b(rejected|declined|invalid|failed|cannot process|not registered|nominee:\s*blank|pending approval|draft email|form downloaded)\b", low):
        return (
            "FAILED",
            "Uploaded document indicates a pending, blank, draft, or rejected status rather than completed official confirmation.",
        )

    wf = task.workflow_type
    if wf == "NOMINEE_VERIFICATION":
        has_confirm = bool(
            re.search(r"\b(endorsed|endorsement|registered|updated|confirmed|confirmation|approved|section\s*39|nominee\s+recorded)\b", low)
            or endorse_ref
        )
        if not nominee:
            return (
                "FAILED",
                "Nominee verification failed: no confirmed nominee name found in the uploaded endorsement or form.",
            )
        if not has_confirm:
            return (
                "FAILED",
                "Nominee verification failed: document shows a nominee name but lacks endorsement/confirmation proof (e.g., endorsement reference or confirmation status).",
            )
        ref_note = f" (Ref: {endorse_ref}" + (f", Date: {conf_date})" if conf_date else ")") if endorse_ref else ""
        return "VERIFIED", f"Verified nominee '{nominee}' confirmed for {expected_ref or 'policy'}{ref_note}."

    if wf == "FD_MATURITY":
        if not re.search(r"\b(renewed|renewal|maturity|matured|payout|credited|closed|instruction|sr-|ref)\b", low):
            return "FAILED", "Evidence does not confirm FD renewal, maturity payout, or bank instruction reference."
        return "VERIFIED", f"Verified FD maturity/renewal confirmation for {expected_ref or 'Fixed Deposit'}."

    if wf == "SUBSCRIPTION_AUDIT":
        if not re.search(r"\b(cancel|cancelled|canceled|revoked|stopped|autopay|mandate|keep|retained|reviewed)\b", low):
            return "FAILED", "Evidence must confirm subscription cancellation, mandate revocation, or verified keep decision."
        return "VERIFIED", "Verified subscription audit confirmation."

    if wf == "TAX_RECONCILIATION":
        if not re.search(r"\b(reconcil|revised|form\s*16|ais|form\s*24q|itr|ca\s+verified|matched|clarified|resolved)\b", low):
            return "FAILED", "Evidence does not substantiate AIS vs Form 16 payroll reconciliation or tax resolution."
        return "VERIFIED", "Verified AIS / Form 16 tax discrepancy reconciliation evidence."

    if wf == "BANK_ACCOUNT_VERIFICATION":
        if not re.search(r"\b(statement|passbook|balance|closed|closure|active|dormant|verified|sft|bank)\b", low):
            return "FAILED", "Evidence does not verify ownership, statement, or closure status of the AIS-reported bank account."
        return "VERIFIED", f"Verified bank account status evidence for {expected_ref or 'savings account'}."

    if wf == "LOAN_MANAGEMENT":
        if not re.search(r"\b(loan|emi|schedule|amortization|statement|principal|interest|lender|confirmed)\b", low):
            return "FAILED", "Evidence does not contain loan statement, repayment schedule, or lender EMI confirmation."
        return "VERIFIED", f"Verified loan statement / EMI confirmation for {expected_ref or 'loan account'}."

    return "VERIFIED", "Verification evidence accepted."


def submit_and_verify_evidence(
    db: Session,
    user: User,
    finding: Finding,
    *,
    evidence_type: str = "Uploaded Endorsement",
    filename: str | None = None,
    file_bytes: bytes | None = None,
    confirmation_text: str = "",
    nominee_name: str | None = None,
    endorsement_reference: str | None = None,
    confirmation_date: str | None = None,
) -> tuple[AutomationTask, ActionEvidence]:
    """Save uploaded/textual evidence, extract details, verify strictly, update statuses, and write audit logs."""
    task = get_or_create_automation_task(db, user, finding)
    prev_status = task.task_status
    saved_path: str | None = None
    parsed_text = (confirmation_text or "").strip()

    if file_bytes and filename:
        settings = get_settings()
        ev_dir = settings.storage_path / str(user.id) / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        safe_fname = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)
        dest = ev_dir / f"{uuid.uuid4().hex[:10]}_{safe_fname}"
        dest.write_bytes(file_bytes)
        saved_path = str(dest)

        if safe_fname.lower().endswith(".pdf"):
            try:
                pages = extract_pdf_pages(dest)
                pdf_text = "\n".join(p.cleaned_text or p.raw_text for p in pages)
                parsed_text = f"{parsed_text}\n{pdf_text}".strip()
            except Exception as exc:
                logger.warning("Evidence PDF parse failed for %s: %s", safe_fname, type(exc).__name__)
        else:
            decoded = file_bytes.decode("utf-8", errors="ignore").strip()
            parsed_text = f"{parsed_text}\n{decoded}".strip()

    extracted = _extract_evidence_fields(parsed_text)
    if nominee_name and nominee_name.strip():
        extracted["nominee_name"] = nominee_name.strip()
    if endorsement_reference and endorsement_reference.strip():
        extracted["endorsement_reference"] = endorsement_reference.strip()
    if confirmation_date and confirmation_date.strip():
        extracted["confirmation_date"] = confirmation_date.strip()

    task.task_status = "Evidence Received"
    _write_audit_log(
        db,
        task_id=task.id,
        finding_id=finding.id,
        user_id=user.id,
        action="EVIDENCE_UPLOADED",
        actor="USER",
        previous_status=prev_status,
        new_status="Evidence Received",
        details=f"Received {evidence_type}" + (f" ({filename})" if filename else "") + ".",
        metadata_json={"extracted": extracted},
    )

    verdict, explanation = verify_evidence_against_finding(
        finding,
        task,
        parsed_text,
        extracted,
        nominee_override=nominee_name,
        endorsement_override=endorsement_reference,
        date_override=confirmation_date,
    )

    ev_record = ActionEvidence(
        task_id=task.id,
        finding_id=finding.id,
        user_id=user.id,
        evidence_type=evidence_type,
        filename=filename,
        file_path=saved_path,
        raw_text=parsed_text[:8000],
        extracted_data=extracted,
        verification_status=verdict,
        verification_explanation=explanation,
    )
    db.add(ev_record)
    db.flush()

    if verdict == "VERIFIED":
        task.task_status = "Completed"
        task.last_verification_summary = explanation
        finding.status = "RESOLVED"

        # Mark all workflow steps complete & update FindingProgress cleanly
        all_labels = [s["label"] for s in (task.generated_plan or {}).get("steps", []) if isinstance(s, dict)]
        task.completed_steps = all_labels or task.completed_steps
        prog = db.scalar(select(FindingProgress).where(FindingProgress.finding_id == finding.id, FindingProgress.user_id == user.id))
        if prog is None:
            prog = FindingProgress(finding_id=finding.id, user_id=user.id)
            db.add(prog)
        prog.completed_steps = task.completed_steps
        prog.verification_evidence = explanation
        prog.nominee_name = extracted.get("nominee_name")
        prog.resolved_at = get_utc_now()

        # Propagate verified nominee update back to matching FinancialAsset safely ONLY upon verification
        if task.workflow_type == "NOMINEE_VERIFICATION":
            ctx = _extract_relevant_assets_and_docs(db, user.id, finding)
            for asset in ctx["matching_assets"]:
                if asset.asset_type == "LIFE_INSURANCE":
                    asset.nominee_status = "RECORDED"
                    details_copy = dict(asset.details or {})
                    if extracted.get("nominee_name"):
                        details_copy["verified_nominee"] = extracted["nominee_name"]
                    if extracted.get("endorsement_reference"):
                        details_copy["endorsement_reference"] = extracted["endorsement_reference"]
                    asset.details = details_copy

        _write_audit_log(
            db,
            task_id=task.id,
            finding_id=finding.id,
            user_id=user.id,
            action="VERIFICATION_PASSED",
            actor="SYSTEM",
            previous_status="Evidence Received",
            new_status="Completed",
            details=explanation,
            metadata_json={"evidence_id": ev_record.id},
        )
    else:
        task.task_status = "Failed"
        task.last_verification_summary = explanation
        if finding.status == "OPEN":
            finding.status = "IN_REVIEW"
        _write_audit_log(
            db,
            task_id=task.id,
            finding_id=finding.id,
            user_id=user.id,
            action="VERIFICATION_FAILED",
            actor="SYSTEM",
            previous_status="Evidence Received",
            new_status="Failed",
            details=explanation,
            metadata_json={"evidence_id": ev_record.id},
        )

    db.commit()
    db.refresh(task)
    db.refresh(ev_record)
    return task, ev_record


def serialize_automation_task(db: Session, task: AutomationTask) -> dict[str, Any]:
    evidences = list(
        db.scalars(
            select(ActionEvidence)
            .where(ActionEvidence.task_id == task.id)
            .order_by(ActionEvidence.uploaded_at.desc(), ActionEvidence.id.desc())
        )
    )
    logs = list(
        db.scalars(
            select(ActionAuditLog)
            .where(ActionAuditLog.finding_id == task.finding_id, ActionAuditLog.user_id == task.user_id)
            .order_by(ActionAuditLog.created_at.desc(), ActionAuditLog.id.desc())
            .limit(25)
        )
    )
    reminders = list(
        db.scalars(
            select(FinancialReminder).where(FinancialReminder.task_id == task.id)
        )
    )
    plan = task.generated_plan or {}
    steps = plan.get("steps") or []
    completed_set = set(task.completed_steps or [])
    hydrated_steps = [
        {**s, "completed": bool(s.get("completed") or s.get("label") in completed_set)}
        for s in steps
        if isinstance(s, dict)
    ]
    progress_pct = round((sum(1 for s in hydrated_steps if s["completed"]) / len(hydrated_steps)) * 100) if hydrated_steps else (100 if task.task_status == "Completed" else 0)

    return {
        "id": str(task.id),
        "finding_id": str(task.finding_id),
        "workflow_type": task.workflow_type,
        "automation_level": task.automation_level,
        "task_status": task.task_status,
        "required_approval": task.required_approval,
        "approval_granted": task.approval_granted,
        "approved_at": to_ist_iso(task.approved_at) if task.approved_at else None,
        "issue_summary": task.issue_summary,
        "required_action": task.required_action,
        "external_institution_required": task.external_institution_required,
        "institution_name": task.institution_name,
        "account_or_policy_ref": task.account_or_policy_ref,
        "expected_evidence": task.expected_evidence,
        "estimated_impact_inr": float(task.estimated_impact_inr) if task.estimated_impact_inr is not None else None,
        "progress_pct": progress_pct,
        "steps": hydrated_steps,
        "draft_email": task.draft_email,
        "ai_generated": task.ai_generated,
        "last_verification_summary": task.last_verification_summary,
        "supports_form_download": bool(plan.get("supports_form_download", False)),
        "extracted_entities": plan.get("extracted_entities") or {},
        "institution_directory": plan.get("institution_directory") or {},
        "workflow_data": {
            k: v
            for k, v in plan.items()
            if k in ("fd_analysis", "subscription_audit", "tax_reconciliation", "bank_verification", "loan_analysis")
        },
        "evidences": [
            {
                "id": str(e.id),
                "evidence_type": e.evidence_type,
                "filename": e.filename,
                "extracted_data": e.extracted_data or {},
                "verification_status": e.verification_status,
                "verification_explanation": e.verification_explanation,
                "uploaded_at": to_ist_iso(e.uploaded_at),
            }
            for e in evidences
        ],
        "audit_logs": [
            {
                "id": str(l.id),
                "action": l.action,
                "actor": l.actor,
                "previous_status": l.previous_status,
                "new_status": l.new_status,
                "details": l.details,
                "created_at": to_ist_iso(l.created_at),
            }
            for l in logs
        ],
        "reminders": [
            {
                "id": str(r.id),
                "reminder_type": r.reminder_type,
                "title": r.title,
                "message": r.message,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "days_remaining": r.days_remaining,
                "status": r.status,
            }
            for r in reminders
        ],
        "created_at": to_ist_iso(task.created_at),
        "updated_at": to_ist_iso(task.updated_at),
    }
