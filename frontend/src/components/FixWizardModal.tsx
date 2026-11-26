"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Bell,
  Check,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  History,
  Loader2,
  Mail,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { api, formatINR } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import {
  AutomationLevel,
  AutomationStep,
  AutomationTaskDetail,
  AutomationTaskStatus,
  FindingItem,
} from "@/lib/types";

interface FixWizardModalProps {
  finding: FindingItem | null;
  onClose: () => void;
  onCompleted: () => void;
}

const AUTOMATION_LABELS: Record<AutomationLevel, string> = {
  FULLY_AUTOMATABLE: "Fully Automatable",
  AUTOMATABLE_WITH_USER_APPROVAL: "Automatable with User Approval",
  GUIDED_EXTERNAL_ACTION: "Guided External Action",
  MANUAL_VERIFICATION_REQUIRED: "Manual Verification Required",
};

const EXECUTION_BADGE: Record<AutomationStep["execution_mode"], string> = {
  AUTO_INTERNAL: "Auto Internal",
  USER_APPROVAL: "User Approval",
  EXTERNAL_INSTITUTION: "External Institution",
  EVIDENCE_VERIFY: "Verify Evidence",
};

function statusPillClass(status: AutomationTaskStatus | string): string {
  if (status === "Completed" || status === "VERIFIED") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (status === "Failed" || status === "FAILED") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (
    status === "Awaiting External Confirmation" ||
    status === "Verification Required" ||
    status === "Evidence Received"
  ) {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-[#E8E8E8] bg-white text-[#111111]";
}

export function FixWizardModal({ finding, onClose, onCompleted }: FixWizardModalProps) {
  const [task, setTask] = useState<AutomationTaskDetail | null>(null);
  const [loadingTask, setLoadingTask] = useState(false);
  const [checkedSteps, setCheckedSteps] = useState<string[]>([]);
  const [draftEmail, setDraftEmail] = useState("");
  const [evidenceType, setEvidenceType] = useState("Uploaded Endorsement");
  const [evidenceText, setEvidenceText] = useState("");
  const [nomineeName, setNomineeName] = useState("");
  const [endorsementRef, setEndorsementRef] = useState("");
  const [confirmationDate, setConfirmationDate] = useState("");
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);

  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const hydrateFromTask = useCallback((detail: AutomationTaskDetail) => {
    setTask(detail);
    const done = detail.steps.filter((s) => s.completed).map((s) => s.label);
    setCheckedSteps(done);
    setDraftEmail(detail.draft_email || "");
  }, []);

  useEffect(() => {
    let active = true;
    const fid = finding?.id;
    Promise.resolve().then(() => {
      if (!active) return;
      if (!fid || !finding) {
        setTask(null);
        return;
      }
      setCheckedSteps(Array.isArray(finding.completed_steps) ? finding.completed_steps : []);
      setEvidenceText(finding.resolution_evidence || "");
      setDraftEmail(finding.draft_email || "");
      setNomineeName("");
      setEndorsementRef("");
      setConfirmationDate("");
      setEvidenceFile(null);
      setError("");
      setSuccessMsg("");
      setCopied(false);
      setLoadingTask(true);
      api
        .getFindingAutomation(fid)
        .then((detail) => {
          if (active) hydrateFromTask(detail);
        })
        .catch(() => {
          // Fallback gracefully to finding props if offline
        })
        .finally(() => {
          if (active) setLoadingTask(false);
        });
    });
    return () => {
      active = false;
    };
  }, [finding, hydrateFromTask]);

  if (!finding || typeof finding !== "object") return null;

  const steps: AutomationStep[] =
    task?.steps && task.steps.length > 0
      ? task.steps
      : (Array.isArray(finding.recommended_steps) ? finding.recommended_steps : [])
          .filter((s): s is string => typeof s === "string" && s.trim().length > 0)
          .map((label, i) => ({
            id: `step_${i}`,
            label,
            execution_mode: "EVIDENCE_VERIFY",
            completed: checkedSteps.includes(label),
          }));

  const safeChecked = Array.isArray(checkedSteps) ? checkedSteps : [];
  const completedCount = steps.filter((s) => safeChecked.includes(s.label)).length;
  const progressPct =
    task?.progress_pct ??
    (steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0);

  const workflowType = task?.workflow_type || finding.automation?.workflow_type || "";
  const automationLevel = (task?.automation_level ||
    finding.automation?.automation_level ||
    "GUIDED_EXTERNAL_ACTION") as AutomationLevel;
  const taskStatus = (task?.task_status ||
    finding.automation?.task_status ||
    (finding.status === "Resolved" ? "Completed" : finding.status === "In Review" ? "In Progress" : "Not Started")) as AutomationTaskStatus;
  const impactAmount = task?.estimated_impact_inr ?? finding.impact_amount ?? null;
  const isNomineeWorkflow =
    workflowType === "NOMINEE_VERIFICATION" || finding.category === "Nominee Gap";
  const supportsFormDownload = Boolean(task?.supports_form_download);
  const requiresApproval = task?.required_approval ?? true;
  const hasDraftOrRequest = Boolean(draftEmail || task?.institution_directory?.official_name);

  const toggleStep = (label: string) => {
    setSuccessMsg("");
    setCheckedSteps((prev) => {
      const base = Array.isArray(prev) ? prev : [];
      return base.includes(label) ? base.filter((s) => s !== label) : [...base, label];
    });
  };

  const handleAutomateThis = async () => {
    setError("");
    setSuccessMsg("");
    setBusyAction("automate");
    try {
      const updated = await api.automateFinding(finding.id, true);
      hydrateFromTask(updated);
      setSuccessMsg(
        updated.task_status === "Completed"
          ? "Automated check passed and marked Completed."
          : "AI action plan, extracted details, and workflow preparations are ready for your review."
      );
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not run automation workflow.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleGenerateRequest = async () => {
    setError("");
    setSuccessMsg("");
    setBusyAction("generate");
    try {
      const updated = await api.generateFindingRequest(finding.id, true);
      hydrateFromTask(updated);
      setSuccessMsg("Generated tailored request draft and institution submission instructions.");
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not generate request.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleDownloadForm = async () => {
    setError("");
    setSuccessMsg("");
    setBusyAction("download");
    try {
      const { blob, filename } = await api.downloadAutomationForm(finding.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      const refreshed = await api.getFindingAutomation(finding.id);
      hydrateFromTask(refreshed);
      setSuccessMsg(
        "Prefilled form downloaded. Review, sign, and submit via your official portal — status remains open until verified evidence is uploaded."
      );
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not download prefilled form.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleApproveReview = async () => {
    setError("");
    setSuccessMsg("");
    setBusyAction("approve");
    try {
      const updated = await api.approveFindingAction(finding.id, {
        approved: true,
        edited_draft_email: draftEmail.trim() || undefined,
        notes: "Reviewed extracted details and approved request draft for manual external submission.",
      });
      hydrateFromTask(updated);
      setSuccessMsg(
        "Action approved and logged. Status updated to Awaiting External Confirmation until you upload proof."
      );
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not record approval.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleUploadEvidence = async () => {
    setError("");
    setSuccessMsg("");
    if (
      !evidenceFile &&
      evidenceText.trim().length < 8 &&
      !(nomineeName.trim() && endorsementRef.trim())
    ) {
      setError(
        "Upload a confirmation PDF/document or enter clear confirmation text (plus nominee & endorsement reference where applicable)."
      );
      return;
    }
    setBusyAction("upload");
    try {
      const updated = await api.uploadActionEvidence(finding.id, {
        evidence_type: evidenceType,
        confirmation_text: evidenceText.trim(),
        nominee_name: nomineeName.trim() || undefined,
        endorsement_reference: endorsementRef.trim() || undefined,
        confirmation_date: confirmationDate.trim() || undefined,
        file: evidenceFile,
      });
      hydrateFromTask(updated);
      setEvidenceFile(null);
      if (updated.task_status === "Completed") {
        setSuccessMsg(
          updated.last_verification_summary || "Evidence verified cleanly! Task marked Completed."
        );
      } else {
        setError(
          updated.last_verification_summary ||
            "Uploaded evidence failed strict verification checks. See details below."
        );
      }
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Evidence upload failed.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleVerifyCompletion = async () => {
    setError("");
    setSuccessMsg("");
    setBusyAction("verify");
    try {
      const updated = await api.verifyFindingCompletion(finding.id, {
        confirmation_text: evidenceText.trim() || undefined,
        nominee_name: nomineeName.trim() || undefined,
        endorsement_reference: endorsementRef.trim() || undefined,
        confirmation_date: confirmationDate.trim() || undefined,
      });
      hydrateFromTask(updated);
      if (updated.task_status === "Completed") {
        setSuccessMsg(updated.last_verification_summary || "Verification passed!");
        onCompleted();
      } else {
        setError(
          updated.last_verification_summary ||
            "Cannot complete yet: valid confirmation evidence is required."
        );
        onCompleted();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification check failed.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleSaveProgress = async () => {
    setError("");
    setSuccessMsg("");
    setBusyAction("save");
    try {
      await api.saveFixProgress(finding.id, {
        verification_evidence: evidenceText.trim(),
        completed_steps: safeChecked,
        nominee_name: nomineeName.trim() || undefined,
      });
      setSuccessMsg("Checklist progress saved.");
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not save progress.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleCopyEmail = () => {
    if (!draftEmail) return;
    navigator.clipboard.writeText(draftEmail);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const entities = (task?.extracted_entities || {}) as Record<string, unknown>;
  const inst = task?.institution_directory;
  const wfData = (task?.workflow_data || {}) as Record<string, Record<string, unknown>>;
  const fdAnalysis = wfData.fd_analysis;
  const subAudit = wfData.subscription_audit;
  const taxRecon = wfData.tax_reconciliation;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />

      <div className="relative z-10 w-full max-w-3xl rounded-3xl border border-[#E8E8E8] bg-white shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[#E8E8E8] px-6 py-5 bg-white">
          <div className="min-w-0 pr-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#777777]">
                AI Action & Fix Wizard
              </span>
              <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-0.5 text-[10px] font-semibold text-[#111111]">
                {AUTOMATION_LABELS[automationLevel]}
              </span>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${statusPillClass(
                  taskStatus
                )}`}
              >
                {taskStatus}
              </span>
              {task?.ai_generated && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#090909] px-2 py-0.5 text-[10px] font-medium text-white">
                  <Sparkles className="h-2.5 w-2.5" />
                  Groq AI Planned
                </span>
              )}
            </div>
            <h2 className="mt-1.5 text-lg font-semibold text-[#111111]">{finding.title}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[#777777]">
              <span>Priority: <strong className="text-[#111111]">{finding.severity}</strong></span>
              {impactAmount !== null && impactAmount > 0 && (
                <span>Estimated Impact: <strong className="text-[#111111] tabular-nums">{formatINR(impactAmount)}</strong></span>
              )}
              {task?.account_or_policy_ref && (
                <span>Ref: <strong className="text-[#111111]">{task.account_or_policy_ref}</strong></span>
              )}
              {(finding.resolved_at || finding.created_at) && (
                <span>
                  {finding.resolved_at
                    ? `Verified: ${formatISTWithTz(finding.resolved_at)}`
                    : `Flagged: ${formatISTWithTz(finding.created_at)}`}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#E8E8E8] p-2 text-[#777777] hover:text-[#111111]"
            aria-label="Close Fix Wizard"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5 overflow-y-auto">
          {loadingTask && !task && (
            <div className="flex items-center gap-2 text-xs text-[#777777]">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading automated action analysis...
            </div>
          )}

          {/* Security & Execution Boundary Notice */}
          <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 flex items-start gap-3">
            <ShieldAlert className="h-4 w-4 text-[#111111] mt-0.5 shrink-0" />
            <div className="text-xs text-[#555555] leading-relaxed space-y-1">
              <p>
                <strong className="text-[#111111]">Strict Safety & Evidence Control:</strong>{" "}
                ArthaLens automatically prepares forms, extracts policy/account data, tracks reminders, and verifies uploaded proof — it{" "}
                <strong className="text-[#111111]">never</strong> auto-submits external forms, executes transactions, cancels policies, or logs into bank portals with stored passwords.
              </p>
              {task?.expected_evidence && (
                <p className="text-[11px] text-[#777777]">
                  <strong className="text-[#111111]">Required Evidence:</strong> {task.expected_evidence}
                </p>
              )}
            </div>
          </div>

          {/* Primary Contextual Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={busyAction !== null || taskStatus === "Completed"}
              onClick={handleAutomateThis}
              className="inline-flex items-center gap-1.5 rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
            >
              {busyAction === "automate" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Automate This
            </button>

            {task?.external_institution_required !== false && (
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={handleGenerateRequest}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#090909] bg-white px-3.5 py-2 text-xs font-medium text-[#111111] hover:bg-[#F7F7F7] disabled:opacity-50"
              >
                {busyAction === "generate" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Mail className="h-3.5 w-3.5" />
                )}
                Generate Request
              </button>
            )}

            {supportsFormDownload && (
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={handleDownloadForm}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-3.5 py-2 text-xs font-medium text-[#111111] hover:border-[#090909] disabled:opacity-50"
              >
                {busyAction === "download" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                Download Form
              </button>
            )}

            {requiresApproval && hasDraftOrRequest && taskStatus !== "Completed" && (
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={handleApproveReview}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3.5 py-2 text-xs font-medium text-[#111111] hover:border-[#090909] disabled:opacity-50"
              >
                {busyAction === "approve" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <ShieldCheck className="h-3.5 w-3.5" />
                )}
                {task?.approval_granted ? "Approved (Update)" : "Review Action"}
              </button>
            )}
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-700 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-xs text-emerald-800 flex items-start gap-2">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Extracted Institution & Policy Information */}
          {(inst?.official_name || Object.keys(entities).length > 0) && (
            <div className="rounded-2xl border border-[#E8E8E8] bg-white p-4 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                  Extracted Record & Official Institution Desk
                </p>
                {inst?.official_website && (
                  <a
                    href={inst.official_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-[#111111] underline"
                  >
                    Official Portal <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-[#444444]">
                <div><span className="text-[#777777]">Institution:</span> <strong className="text-[#111111]">{inst?.official_name || task?.institution_name || "N/A"}</strong></div>
                <div><span className="text-[#777777]">Reference:</span> <strong className="text-[#111111]">{String(entities.policy_number || task?.account_or_policy_ref || "Refer attached PDF")}</strong></div>
                {Boolean(entities.policy_type) && (
                  <div><span className="text-[#777777]">Policy Type:</span> <strong className="text-[#111111]">{String(entities.policy_type)}</strong></div>
                )}
                {inst?.support_email && (
                  <div><span className="text-[#777777]">Support Email:</span> <strong className="text-[#111111]">{inst.support_email}</strong></div>
                )}
                {inst?.form_name && (
                  <div className="sm:col-span-2"><span className="text-[#777777]">Required Form:</span> <strong className="text-[#111111]">{inst.form_name}</strong></div>
                )}
              </div>
            </div>
          )}

          {/* Workflow-Specific Automated Intelligence Panels */}
          {fdAnalysis && (
            <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                  Fixed Deposit Renewal & Maturity Analysis
                </p>
                {fdAnalysis.days_remaining !== undefined && fdAnalysis.days_remaining !== null && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800">
                    <Bell className="h-3 w-3" />
                    {String(fdAnalysis.days_remaining)} days remaining
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {((fdAnalysis.renewal_comparison as Array<Record<string, string>>) || []).map((opt) => (
                  <div key={opt.option} className="rounded-xl border border-[#E8E8E8] bg-white p-2.5 text-[11px]">
                    <p className="font-semibold text-[#111111]">{opt.option}</p>
                    <p className="mt-1 text-[#555555]">{opt.best_for}</p>
                    <p className="mt-1 text-[#777777]">{opt.note}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {subAudit && (
            <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                Recurring Subscriptions Audit ({formatINR(Number(subAudit.total_estimated_annual_inr || 0))}/yr est.)
              </p>
              <div className="space-y-1.5">
                {((subAudit.merchants as Array<Record<string, unknown>>) || []).map((m) => (
                  <div key={String(m.merchant)} className="rounded-xl border border-[#E8E8E8] bg-white px-3 py-2 text-xs flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="font-semibold text-[#111111]">{String(m.merchant)}</span>{" "}
                      <span className="text-[#777777]">• Est. {formatINR(Number(m.estimated_annual_inr || 0))}/yr</span>
                      {Boolean(m.price_increase_detected) && (
                        <span className="ml-2 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                          Price Increase Detected
                        </span>
                      )}
                    </div>
                    {Boolean(m.official_cancel_url) && (
                      <a
                        href={String(m.official_cancel_url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-[#111111] underline"
                      >
                        Cancellation Portal <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {taxRecon && (
            <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                AIS vs Form 16 Discrepancy Summary & Advisor Brief
              </p>
              <p className="text-xs text-[#111111]">
                AIS Salary: <strong>{formatINR(Number(taxRecon.ais_gross_salary_inr || 0))}</strong> vs Form 16:{" "}
                <strong>{formatINR(Number(taxRecon.form16_gross_salary_inr || 0))}</strong>{" "}
                (Variance: <strong>{formatINR(Number(taxRecon.discrepancy_inr || 0))}</strong>)
              </p>
              <ul className="list-disc pl-4 space-y-1 text-[11px] text-[#555555]">
                {((taxRecon.questions_for_tax_professional as string[]) || []).map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Action Steps Checklist */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                Context-Aware Action Plan
              </p>
              {steps.length > 0 && (
                <span className="text-[11px] font-medium text-[#111111] tabular-nums">
                  {completedCount} of {steps.length} completed ({progressPct}%)
                </span>
              )}
            </div>
            {steps.length > 0 && (
              <div className="mb-3 h-1.5 w-full rounded-full bg-[#E8E8E8] overflow-hidden">
                <div
                  className="h-full bg-[#090909] transition-all duration-300"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            )}
            <div className="space-y-2">
              {steps.length === 0 ? (
                <p className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-3 text-xs text-[#777777]">
                  No recommended steps available yet.
                </p>
              ) : (
                steps.map((step, index) => {
                  const done = safeChecked.includes(step.label);
                  return (
                    <button
                      key={`${step.id}-${index}`}
                      type="button"
                      onClick={() => toggleStep(step.label)}
                      className="w-full flex items-start justify-between gap-3 rounded-xl border border-[#E8E8E8] bg-white p-3 text-left hover:border-[#111111]/40 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                            done ? "bg-[#090909] border-[#090909] text-white" : "border-[#CCCCCC]"
                          }`}
                        >
                          {done && <Check className="h-3 w-3" />}
                        </span>
                        <span
                          className={`text-xs leading-relaxed ${
                            done ? "line-through text-[#777777]" : "text-[#111111]"
                          }`}
                        >
                          {step.label}
                        </span>
                      </div>
                      <span className="shrink-0 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-2 py-0.5 text-[10px] font-medium text-[#555555]">
                        {EXECUTION_BADGE[step.execution_mode] || "Action"}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Reviewable Draft Email */}
          {hasDraftOrRequest && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                  Review & Edit Request Email Draft {task?.approval_granted ? "(Approved)" : "(Approval Required)"}
                </p>
                {draftEmail && (
                  <button
                    type="button"
                    onClick={handleCopyEmail}
                    className="inline-flex items-center gap-1 text-xs font-medium text-[#111111] hover:underline"
                  >
                    <Copy className="h-3 w-3" />
                    {copied ? "Copied" : "Copy"}
                  </button>
                )}
              </div>
              <textarea
                rows={5}
                value={draftEmail}
                onChange={(e) => setDraftEmail(e.target.value)}
                placeholder="Click 'Generate Request' to prepare a personalized institutional request email."
                className="w-full rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-3 text-xs font-mono text-[#111111] leading-relaxed focus:border-[#090909] focus:bg-white focus:outline-none"
              />
            </div>
          )}

          {/* Upload Evidence & Automated Verification Section */}
          <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                Evidence Upload & Automated Completion Verification
              </p>
              <span className="text-[11px] text-[#777777]">PDF / TXT / Confirmation Details</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div>
                <label className="block text-[11px] font-medium text-[#555555] mb-1">
                  Evidence Type
                </label>
                <select
                  value={evidenceType}
                  onChange={(e) => setEvidenceType(e.target.value)}
                  className="w-full rounded-xl border border-[#E8E8E8] bg-white px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
                >
                  <option value="Uploaded Endorsement">Uploaded Endorsement</option>
                  <option value="Bank Confirmation">Bank Confirmation</option>
                  <option value="Insurance Confirmation Email">Insurance Confirmation Email</option>
                  <option value="Updated Financial Statement">Updated Financial Statement</option>
                  <option value="Official Receipt">Official Receipt</option>
                  <option value="Transaction Confirmation">Transaction Confirmation</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-[#555555] mb-1">
                  Attach Document (Optional PDF / Confirmation)
                </label>
                <label className="flex items-center justify-between gap-2 rounded-xl border border-dashed border-[#CCCCCC] bg-white px-3 py-1.5 text-xs text-[#555555] cursor-pointer hover:border-[#090909]">
                  <span className="truncate">
                    {evidenceFile ? evidenceFile.name : "Choose confirmation PDF / TXT..."}
                  </span>
                  <Upload className="h-3.5 w-3.5 shrink-0 text-[#111111]" />
                  <input
                    type="file"
                    accept=".pdf,.txt,.eml,.md"
                    className="hidden"
                    onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
                  />
                </label>
              </div>
            </div>

            {isNomineeWorkflow && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-[11px] font-medium text-[#555555] mb-1">
                    Confirmed Nominee Name
                  </label>
                  <input
                    type="text"
                    value={nomineeName}
                    onChange={(e) => setNomineeName(e.target.value)}
                    placeholder="e.g., Rohan Sharma (Spouse)"
                    className="w-full rounded-xl border border-[#E8E8E8] bg-white px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-[#555555] mb-1">
                    Endorsement Reference
                  </label>
                  <input
                    type="text"
                    value={endorsementRef}
                    onChange={(e) => setEndorsementRef(e.target.value)}
                    placeholder="e.g., END-SG-99412"
                    className="w-full rounded-xl border border-[#E8E8E8] bg-white px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-[#555555] mb-1">
                    Confirmation Date
                  </label>
                  <input
                    type="text"
                    value={confirmationDate}
                    onChange={(e) => setConfirmationDate(e.target.value)}
                    placeholder="e.g., 27-Nov-2026"
                    className="w-full rounded-xl border border-[#E8E8E8] bg-white px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-medium text-[#555555] mb-1">
                Confirmation Details / Receipt Summary
              </label>
              <textarea
                rows={2}
                value={evidenceText}
                onChange={(e) => setEvidenceText(e.target.value)}
                placeholder="Paste confirmation text, endorsement ref, or statement confirmation notes..."
                className="w-full rounded-xl border border-[#E8E8E8] bg-white p-3 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={busyAction !== null}
                onClick={handleUploadEvidence}
                className="inline-flex items-center gap-1.5 rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
              >
                {busyAction === "upload" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Upload className="h-3.5 w-3.5" />
                )}
                Upload Evidence
              </button>

              <button
                type="button"
                disabled={busyAction !== null}
                onClick={handleVerifyCompletion}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#090909] bg-white px-4 py-2 text-xs font-medium text-[#111111] hover:bg-[#EAEAEA] disabled:opacity-50"
              >
                {busyAction === "verify" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FileCheck2 className="h-3.5 w-3.5" />
                )}
                Verify Completion
              </button>
            </div>
          </div>

          {/* Evidence Uploaded & Verification History */}
          {task && task.evidences.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                Submitted Evidence ({task.evidences.length})
              </p>
              {task.evidences.map((ev) => (
                <div
                  key={ev.id}
                  className="rounded-xl border border-[#E8E8E8] bg-white px-3.5 py-2.5 text-xs space-y-1"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 font-medium text-[#111111]">
                      <FileText className="h-3.5 w-3.5" />
                      {ev.evidence_type} {ev.filename ? `• ${ev.filename}` : ""}
                    </span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusPillClass(
                        ev.verification_status
                      )}`}
                    >
                      {ev.verification_status}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#555555]">{ev.verification_explanation}</p>
                  <p className="text-[10px] text-[#888888]">{formatISTWithTz(ev.uploaded_at)}</p>
                </div>
              ))}
            </div>
          )}

          {/* Audit History Timeline */}
          {task && task.audit_logs.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#777777]">
                <History className="h-3.5 w-3.5" />
                Audit History ({task.audit_logs.length})
              </div>
              <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-3 space-y-1.5 max-h-40 overflow-y-auto">
                {task.audit_logs.map((log) => (
                  <div key={log.id} className="text-[11px] flex items-start justify-between gap-2 border-b last:border-none border-[#E8E8E8] pb-1.5 last:pb-0">
                    <div>
                      <span className="font-semibold text-[#111111]">{log.action}</span>{" "}
                      <span className="text-[#777777]">({log.actor})</span>
                      {log.new_status && (
                        <span className="text-[#555555]"> → {log.new_status}</span>
                      )}
                      <p className="text-[#555555]">{log.details}</p>
                    </div>
                    <span className="text-[10px] text-[#888888] shrink-0">
                      {formatISTWithTz(log.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Footer Buttons */}
          <div className="flex flex-wrap items-center justify-end gap-2.5 pt-2 border-t border-[#E8E8E8]">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-[#E8E8E8] px-4 py-2 text-xs font-medium text-[#777777] hover:text-[#111111]"
            >
              Close
            </button>
            <button
              type="button"
              disabled={busyAction !== null}
              onClick={handleSaveProgress}
              className="rounded-full border border-[#090909] bg-white px-4 py-2 text-xs font-medium text-[#111111] hover:bg-[#F7F7F7] disabled:opacity-50"
            >
              {busyAction === "save" ? "Saving..." : "Save Progress"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
