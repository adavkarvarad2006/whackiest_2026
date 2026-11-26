"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, CheckCircle2, RefreshCw, Wrench } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FixWizardModal } from "@/components/FixWizardModal";
import { api } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import { FindingItem } from "@/lib/types";

export default function ActionsPage() {
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [inspecting, setInspecting] = useState<FindingItem | null>(null);
  const [fixing, setFixing] = useState<FindingItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listFindings();
      setFindings(list);
    } catch {
      // handled gracefully
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openItems = findings.filter((f) => f.status === "Open" || f.status === "In Review");
  const resolvedItems = findings.filter((f) => f.status === "Resolved");

  return (
    <DashboardShell
      title="Actions"
      subtitle="Guided resolution checklist with verification evidence"
      hasDemoData={findings.some((f) => f.is_demo)}
    >
      <div className="space-y-6">
        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#111111]">
              Pending Actions ({openItems.length})
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
            <p className="text-xs text-[#777777]">All open actions have been resolved.</p>
          ) : (
            openItems.map((f) => {
              const totalSteps = Array.isArray(f.recommended_steps) ? f.recommended_steps.length : 0;
              const doneSteps = Array.isArray(f.completed_steps) ? f.completed_steps.length : 0;
              return (
                <div
                  key={f.id}
                  className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[10px] font-medium text-[#111111]">
                        {f.status}
                      </span>
                      {totalSteps > 0 && doneSteps > 0 && (
                        <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[10px] font-medium text-[#777777] tabular-nums">
                          {doneSteps}/{totalSteps} steps saved
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-[#111111]">{f.title}</p>
                    <p className="mt-1 text-xs text-[#777777]">
                      {(Array.isArray(f.recommended_steps) ? f.recommended_steps[0] : undefined) || "Review and verify with your institution."}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setInspecting(f)}
                      className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3.5 py-2 text-xs font-medium text-[#111111] hover:border-[#090909]"
                    >
                      Evidence
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setFixing(f)}
                      className="inline-flex items-center gap-1.5 rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800"
                    >
                      <Wrench className="h-3.5 w-3.5" />
                      {f.status === "In Review" ? "Resume Fix Wizard" : "Launch Fix Wizard"}
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-4">
          <h2 className="text-base font-semibold text-[#111111]">
            Completed Actions ({resolvedItems.length})
          </h2>
          {resolvedItems.length === 0 ? (
            <p className="text-xs text-[#777777]">No actions completed yet.</p>
          ) : (
            resolvedItems.map((f) => (
              <div
                key={f.id}
                className="rounded-2xl border border-green-200 bg-green-50/60 p-4 flex items-start justify-between gap-3"
              >
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-4 w-4 text-green-700 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-[#111111]">{f.title}</p>
                    <p className="mt-1 text-xs text-[#777777]">
                      Verification: {f.resolution_evidence || "Verified and resolved"}
                      {f.resolved_at ? ` • ${formatISTWithTz(f.resolved_at)}` : ""}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setInspecting(f)}
                  className="rounded-full border border-[#E8E8E8] bg-white px-3 py-1 text-[11px] font-medium text-[#111111] hover:border-[#090909] shrink-0"
                >
                  View Details
                </button>
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
