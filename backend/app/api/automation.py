"""Authenticated FastAPI routes for ArthaLens AI Action Automation, Evidence Verification, and Guardrails."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ActionAuditLog, FinancialReminder, Finding, User
from app.services.automation import (
    _extract_relevant_assets_and_docs,
    _write_audit_log,
    approve_prepared_action,
    build_prefilled_form_pdf,
    enforce_security_boundary,
    get_or_create_automation_task,
    run_automate_workflow,
    serialize_automation_task,
    submit_and_verify_evidence,
    verify_evidence_against_finding,
)
from app.timezone_utils import to_ist_iso

router = APIRouter(prefix="/api/automation", tags=["automation"])


class AutomateRequest(BaseModel):
    use_groq: bool = True


class ApproveActionRequest(BaseModel):
    approved: bool = True
    edited_draft_email: str | None = None
    notes: str | None = None


class ProtectedActionRequest(BaseModel):
    action_type: str


class VerifyRequest(BaseModel):
    confirmation_text: str | None = None
    nominee_name: str | None = None
    endorsement_reference: str | None = None
    confirmation_date: str | None = None


def _get_user_finding(db: Session, finding_id: int, user_id: int) -> Finding:
    f = db.scalar(select(Finding).where(Finding.id == finding_id, Finding.user_id == user_id))
    if f is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")
    return f


@router.get("/tasks")
def list_automation_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List or initialize AI-classified automation tasks for all of the user's findings."""
    findings = list(
        db.scalars(select(Finding).where(Finding.user_id == current_user.id).order_by(Finding.id.asc()))
    )
    tasks = []
    for f in findings:
        task = get_or_create_automation_task(db, current_user, f)
        tasks.append(serialize_automation_task(db, task))
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/reminders")
def list_financial_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return scheduled automated financial reminders (such as FD maturity countdowns)."""
    # Ensure FD tasks are initialized so reminders exist
    findings = list(db.scalars(select(Finding).where(Finding.user_id == current_user.id)))
    for f in findings:
        get_or_create_automation_task(db, current_user, f)

    reminders = list(
        db.scalars(
            select(FinancialReminder)
            .where(FinancialReminder.user_id == current_user.id)
            .order_by(FinancialReminder.due_date.asc(), FinancialReminder.id.asc())
        )
    )
    return {
        "reminders": [
            {
                "id": str(r.id),
                "finding_id": str(r.finding_id),
                "task_id": str(r.task_id),
                "reminder_type": r.reminder_type,
                "title": r.title,
                "message": r.message,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "days_remaining": r.days_remaining,
                "status": r.status,
                "created_at": to_ist_iso(r.created_at),
            }
            for r in reminders
        ]
    }


@router.get("/findings/{finding_id}")
def get_finding_automation(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    f = _get_user_finding(db, finding_id, current_user.id)
    task = get_or_create_automation_task(db, current_user, f)
    return serialize_automation_task(db, task)


@router.post("/findings/{finding_id}/automate")
async def automate_finding_workflow(
    finding_id: int,
    payload: AutomateRequest = AutomateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute safe internal automation, AI action planning, reminder scheduling, and form/draft generation."""
    f = _get_user_finding(db, finding_id, current_user.id)
    task = await run_automate_workflow(db, current_user, f, use_groq=payload.use_groq)
    return serialize_automation_task(db, task)


@router.post("/findings/{finding_id}/generate-request")
async def generate_finding_request(
    finding_id: int,
    payload: AutomateRequest = AutomateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate/refresh tailored institution request draft, contacts, and official instructions."""
    f = _get_user_finding(db, finding_id, current_user.id)
    task = await run_automate_workflow(db, current_user, f, use_groq=payload.use_groq)
    _write_audit_log(
        db,
        task_id=task.id,
        finding_id=f.id,
        user_id=current_user.id,
        action="DRAFT_GENERATED",
        actor="AI_ENGINE",
        previous_status=task.task_status,
        new_status=task.task_status,
        details="Generated reviewable institution request draft and servicing checklist.",
    )
    db.commit()
    return serialize_automation_task(db, task)


@router.post("/findings/{finding_id}/approve")
def approve_finding_action(
    finding_id: int,
    payload: ApproveActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly approve or update prepared draft/action (does not auto-submit or mark external actions complete)."""
    f = _get_user_finding(db, finding_id, current_user.id)
    task = approve_prepared_action(
        db,
        current_user,
        f,
        approved=payload.approved,
        edited_draft_email=payload.edited_draft_email,
        notes=payload.notes,
    )
    return serialize_automation_task(db, task)


@router.get("/findings/{finding_id}/download-form")
def download_prefilled_form(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream downloadable prefilled Section 39 / servicing request PDF packet without completing verification."""
    f = _get_user_finding(db, finding_id, current_user.id)
    pdf_bytes, filename = build_prefilled_form_pdf(db, current_user, f)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/findings/{finding_id}/evidence")
async def upload_and_verify_evidence(
    finding_id: int,
    evidence_type: str = Form(default="Uploaded Endorsement"),
    confirmation_text: str = Form(default=""),
    nominee_name: str = Form(default=""),
    endorsement_reference: str = Form(default=""),
    confirmation_date: str = Form(default=""),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload endorsement/confirmation file or confirmation text and run automatic verification."""
    f = _get_user_finding(db, finding_id, current_user.id)
    file_bytes: bytes | None = None
    filename: str | None = None
    if file is not None and file.filename:
        file_bytes = await file.read()
        filename = file.filename
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Evidence file exceeds 10 MB limit.")

    if not file_bytes and not confirmation_text.strip() and not (nominee_name.strip() and endorsement_reference.strip()):
        raise HTTPException(
            status_code=400,
            detail="Please upload a confirmation document or enter verification details.",
        )

    task, ev = submit_and_verify_evidence(
        db,
        current_user,
        f,
        evidence_type=evidence_type,
        filename=filename,
        file_bytes=file_bytes,
        confirmation_text=confirmation_text,
        nominee_name=nominee_name or None,
        endorsement_reference=endorsement_reference or None,
        confirmation_date=confirmation_date or None,
    )
    serialized = serialize_automation_task(db, task)
    serialized["latest_evidence"] = {
        "id": str(ev.id),
        "evidence_type": ev.evidence_type,
        "filename": ev.filename,
        "extracted_data": ev.extracted_data,
        "verification_status": ev.verification_status,
        "verification_explanation": ev.verification_explanation,
        "uploaded_at": to_ist_iso(ev.uploaded_at),
    }
    return serialized


@router.post("/findings/{finding_id}/verify")
def verify_finding_completion(
    finding_id: int,
    payload: VerifyRequest = VerifyRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Strictly verify completion using uploaded evidence or explicit confirmation text; blocks unverified completion."""
    f = _get_user_finding(db, finding_id, current_user.id)
    task = get_or_create_automation_task(db, current_user, f)

    if payload.confirmation_text or (payload.nominee_name and payload.endorsement_reference):
        task, _ev = submit_and_verify_evidence(
            db,
            current_user,
            f,
            evidence_type="Confirmation Details",
            confirmation_text=payload.confirmation_text or "",
            nominee_name=payload.nominee_name,
            endorsement_reference=payload.endorsement_reference,
            confirmation_date=payload.confirmation_date,
        )
        return serialize_automation_task(db, task)

    if task.automation_level == "FULLY_AUTOMATABLE":
        ctx = _extract_relevant_assets_and_docs(db, current_user.id, f)
        verdict, explanation = verify_evidence_against_finding(
            f, task, f.description or "", {"institution": ctx["institution"]}
        )
        if verdict == "VERIFIED":
            prev = task.task_status
            task.task_status = "Completed"
            task.last_verification_summary = explanation
            f.status = "RESOLVED"
            _write_audit_log(
                db,
                task_id=task.id,
                finding_id=f.id,
                user_id=current_user.id,
                action="VERIFICATION_PASSED",
                actor="AI_ENGINE",
                previous_status=prev,
                new_status="Completed",
                details=explanation,
            )
            db.commit()
            return serialize_automation_task(db, task)

    # No valid evidence uploaded yet -> mark Verification Required / Failed instead of completing!
    prev = task.task_status
    task.task_status = "Verification Required" if prev != "Failed" else "Failed"
    task.last_verification_summary = (
        f"Verification cannot complete yet: {task.expected_evidence}"
    )
    _write_audit_log(
        db,
        task_id=task.id,
        finding_id=f.id,
        user_id=current_user.id,
        action="VERIFICATION_FAILED",
        actor="SYSTEM",
        previous_status=prev,
        new_status=task.task_status,
        details=task.last_verification_summary,
    )
    db.commit()
    return serialize_automation_task(db, task)


@router.post("/findings/{finding_id}/execute-protected")
def execute_protected_action(
    finding_id: int,
    payload: ProtectedActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Security guardrail endpoint enforcing that unauthorized autonomous actions are blocked and audited."""
    f = _get_user_finding(db, finding_id, current_user.id)
    enforce_security_boundary(db, current_user, f, payload.action_type)


@router.get("/findings/{finding_id}/audit-logs")
def get_finding_audit_logs(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    f = _get_user_finding(db, finding_id, current_user.id)
    logs = list(
        db.scalars(
            select(ActionAuditLog)
            .where(ActionAuditLog.finding_id == f.id, ActionAuditLog.user_id == current_user.id)
            .order_by(ActionAuditLog.created_at.desc(), ActionAuditLog.id.desc())
        )
    )
    return {
        "finding_id": str(f.id),
        "logs": [
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
    }
