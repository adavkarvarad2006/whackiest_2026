"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  Bell,
  CheckCircle2,
  Download,
  FileCheck2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Upload,
  Wrench,
} from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FixWizardModal } from "@/components/FixWizardModal";
import { api, formatINR } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import {
  AutomationLevel,
  AutomationTaskDetail,
  FinancialReminderItem,
  FindingItem,
} from "@/lib/types";

const LEVEL_BADGE: Record<AutomationLevel, string> = {
  FULLY_AUTOMATABLE: "Fully Automatable",
  AUTOMATABLE_WITH_USER_APPROVAL: "Automatable w/ Approval",
  GUIDED_EXTERNAL_ACTION: "Guided External Action",
  MANUAL_VERIFICATION_REQUIRED: "Manual Verification",
};

export default function ActionsPage() {
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [tasksByFinding, setTasksByFinding] = useState<Record<string, AutomationTaskDetail>>({});
  const [reminders, setReminders] = useState<FinancialReminderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [inspecting, setInspecting] = useState<FindingItem | null>(null);
  const [fixing, setFixing] = useState<FindingItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, autoRes, remRes] = await Promise.all([
        api.listFindings(),
        api.listAutomationTasks().catch(() => ({ tasks: [], total: 0 })),
        api.listFinancialReminders().catch(() => ({ reminders: [] })),
      ]);
      setFindings(list);
      const map: Record<string, AutomationTaskDetail> = {};
      for (const t of autoRes.tasks) {
        map[t.finding_id] = t;
      }
      setTasksByFinding(map);
      setReminders(remRes.reminders);
    } catch {
      // handled gracefully
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => {
      if (active) void load();
    });
    return () => {
      active = false;
    };
  }, [load]);

  const openItems = useMemo(
    () => findings.filter((f) => f.status === "Open" || f.status === "In Review"),
    [findings]
  );
  const resolvedItems = useMemo(
    () => findings.filter((f) => f.status === "Resolved"),
    [findings]
  );

  const stats = useMemo(() => {
    const allTasks = Object.values(tasksByFinding);
    return {
      fullyOrApproval: allTasks.filter(
        (t) =>
          t.automation_level === "FULLY_AUTOMATABLE" ||
          t.automation_level === "AUTOMATABLE_WITH_USER_APPROVAL"
      ).length,
      guidedExternal: allTasks.filter((t) => t.automation_level === "GUIDED_EXTERNAL_ACTION").length,
      awaitingConfirm: allTasks.filter(
        (t) =>
          t.task_status === "Awaiting External Confirmation" ||
          t.task_status === "Verification Required"
      ).length,
      completed: resolvedItems.length,
    };
  }, [tasksByFinding, resolvedItems.length]);

  const quickAutomate = async (finding: FindingItem) => {
    setRunningId(finding.id);
    try {
      await api.automateFinding(finding.id, true);
      await load();
      setFixing(finding);
    } finally {
      setRunningId(null);
    }
  };

  const quickDownloadForm = async (finding: FindingItem) => {
    setRunningId(finding.id);
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
      await load();
    } finally {
      setRunningId(null);
    }
  };

  return (
    <DashboardShell
      title="Automation & Actions"
      subtitle="AI action classification, automated workflows, approval gates, and evidence verification"
      hasDemoData={findings.some((f) => f.is_demo)}
    >
      <div className="space-y-6">
        {/* Automation Summary Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="rounded-2xl border border-[#E8E8E8] bg-white p-4">
            <p className="text-[11px] font-medium text-[#777777]">Auto / Approval Ready</p>
            <p className="mt-1 text-2xl font-semibold text-[#111111] tabular-nums">{stats.fullyOrApproval}</p>
          </div>
          <div className="rounded-2xl border border-[#E8E8E8] bg-white p-4">
            <p className="text-[11px] font-medium text-[#777777]">Guided External Actions</p>
            <p className="mt-1 text-2xl font-semibold text-[#111111] tabular-nums">{stats.guidedExternal}</p>
          </div>
          <div className="rounded-2xl border border-[#E8E8E8] bg-white p-4">
            <p className="text-[11px] font-medium text-[#777777]">Awaiting Verification</p>
            <p className="mt-1 text-2xl font-semibold text-[#111111] tabular-nums">{stats.awaitingConfirm}</p>
          </div>
          <div className="rounded-2xl border border-[#E8E8E8] bg-white p-4">
            <p className="text-[11px] font-medium text-[#777777]">Verified Completed</p>
            <p className="mt-1 text-2xl font-semibold text-[#111111] tabular-nums">{stats.completed}</p>
          </div>
        </div>

        {/* Automated Reminders */}
        {reminders.length > 0 && (
          <div className="rounded-3xl border border-[#E8E8E8] bg-white p-5 space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#777777]">
              <Bell className="h-3.5 w-3.5 text-[#111111]" />
              Scheduled Automated Reminders ({reminders.length})
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {reminders.map((r) => (
                <div key={r.id} className="rounded-2xl border border-amber-200 bg-amber-50/60 px-4 py-3 text-xs">
                  <p className="font-semibold text-[#111111]">{r.title}</p>
                  <p className="mt-0.5 text-[#555555]">{r.message}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pending Actions */}
        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#111111]">
              Pending Financial Actions ({openItems.length})
            </h2>
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
            >
              <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {openItems.length === 0 ? (
            <p className="text-xs text-[#777777]">All open financial actions have verified completions.</p>
          ) : (
            openItems.map((f) => {
              const t = tasksByFinding[f.id];
              const level = (t?.automation_level ||
                f.automation?.automation_level ||
                "GUIDED_EXTERNAL_ACTION") as AutomationLevel;
              const tStatus = t?.task_status || f.automation?.task_status || f.status;
              const progressPct = t?.progress_pct ?? 0;
              const impact = t?.estimated_impact_inr ?? f.impact_amount;
              const evCount = t?.evidences?.length ?? 0;
              const isBusy = runningId === f.id;

              return (
                <div
                  key={f.id}
                  className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-5 space-y-3"
                >
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[10px] font-semibold text-[#111111]">
                          {tStatus}
                        </span>
                        <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[10px] font-medium text-[#555555]">
                          Priority: {f.severity}
                        </span>
                        <span className="rounded-full bg-[#090909] px-2.5 py-0.5 text-[10px] font-medium text-white">
                          {LEVEL_BADGE[level]}
                        </span>
                        {impact !== null && impact !== undefined && impact > 0 && (
                          <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[10px] font-medium text-[#111111] tabular-nums">
                            Impact: {formatINR(impact)}
                          </span>
                        )}
                        {t?.required_approval && (
                          <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[10px] text-[#555555]">
                            {t.approval_granted ? "Approval Granted" : "User Approval Required"}
                          </span>
                        )}
                        <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[10px] text-[#555555] tabular-nums">
                          Evidence: {evCount}
                        </span>
                      </div>

                      <p className="text-sm font-semibold text-[#111111]">{f.title}</p>
                      <p className="text-xs text-[#555555]">
                        <strong className="text-[#111111]">Issue:</strong> {t?.issue_summary || f.evidence?.why_flagged}
                      </p>
                      <p className="text-xs text-[#777777]">
                        <strong className="text-[#111111]">Recommended Action:</strong>{" "}
                        {t?.required_action || f.recommended_steps?.[0] || "Review and verify with institution."}
                      </p>

                      {/* Progress bar */}
                      <div className="pt-1 flex items-center gap-2 max-w-sm">
                        <div className="h-1.5 flex-1 rounded-full bg-[#E0E0E0] overflow-hidden">
                          <div className="h-full bg-[#090909] transition-all" style={{ width: `${progressPct}%` }} />
                        </div>
                        <span className="text-[10px] font-medium text-[#555555] tabular-nums">{progressPct}%</span>
                      </div>
                    </div>

                    {/* Relevant Contextual Action Buttons */}
                    <div className="flex flex-wrap items-center gap-2 shrink-0">
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => quickAutomate(f)}
                        className="inline-flex items-center gap-1 rounded-full bg-[#090909] px-3.5 py-2 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
                      >
                        <Sparkles className="h-3 w-3" />
                        Automate This
                      </button>

                      {t?.supports_form_download && (
                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() => quickDownloadForm(f)}
                          className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-2 text-xs font-medium text-[#111111] hover:border-[#090909]"
                        >
                          <Download className="h-3 w-3" />
                          Download Form
                        </button>
                      )}

                      {t?.required_approval && !t.approval_granted && (
                        <button
                          type="button"
                          onClick={() => setFixing(f)}
                          className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-2 text-xs font-medium text-[#111111] hover:border-[#090909]"
                        >
                          <ShieldCheck className="h-3 w-3" />
                          Review Action
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => setFixing(f)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#090909] bg-white px-3.5 py-2 text-xs font-medium text-[#111111] hover:bg-[#EAEAEA]"
                      >
                        {evCount > 0 ? <FileCheck2 className="h-3 w-3" /> : <Upload className="h-3 w-3" />}
                        {evCount > 0 ? "Verify Completion" : "Upload Evidence"}
                      </button>

                      <button
                        type="button"
                        onClick={() => setInspecting(f)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-2 text-xs font-medium text-[#555555] hover:border-[#090909] hover:text-[#111111]"
                      >
                        Evidence <ArrowUpRight className="h-3 w-3" />
                      </button>

                      <button
                        type="button"
                        onClick={() => setFixing(f)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-2 text-xs font-medium text-[#111111] hover:border-[#090909]"
                      >
                        <Wrench className="h-3 w-3" />
                        Wizard
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Completed Actions */}
        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-4">
          <h2 className="text-base font-semibold text-[#111111]">
            Verified & Completed Actions ({resolvedItems.length})
          </h2>
          {resolvedItems.length === 0 ? (
            <p className="text-xs text-[#777777]">No actions verified as completed yet.</p>
          ) : (
            resolvedItems.map((f) => (
              <div
                key={f.id}
                className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4 flex items-start justify-between gap-3"
              >
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-4 w-4 text-emerald-700 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-[#111111]">{f.title}</p>
                    <p className="mt-1 text-xs text-[#555555]">
                      Verification: {f.resolution_evidence || "Verified and resolved"}
                      {f.resolved_at ? ` • ${formatISTWithTz(f.resolved_at)}` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => setFixing(f)}
                    className="rounded-full border border-[#E8E8E8] bg-white px-3 py-1 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                  >
                    Audit Log
                  </button>
                  <button
                    type="button"
                    onClick={() => setInspecting(f)}
                    className="rounded-full border border-[#E8E8E8] bg-white px-3 py-1 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                  >
                    Details
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <EvidenceDrawer
        finding={inspecting}
        onClose={() => setInspecting(null)}
        onOpenFix={(item) => {
          setInspecting(null);
          setFixing(item);
        }}
        onUpdated={load}
      />

      <FixWizardModal
        finding={fixing}
        onClose={() => setFixing(null)}
        onCompleted={load}
      />
    </DashboardShell>
  );
}
