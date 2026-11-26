"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Wrench } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { FixWizardModal } from "@/components/FixWizardModal";
import { api } from "@/lib/api";
import { FindingItem } from "@/lib/types";

export default function ActionsPage() {
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [fixing, setFixing] = useState<FindingItem | null>(null);

  const load = useCallback(() => {
    api.listFindings().then(setFindings).catch(() => {});
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
          <h2 className="text-base font-semibold text-[#111111]">
            Pending Actions ({openItems.length})
          </h2>
          {openItems.length === 0 ? (
            <p className="text-xs text-[#777777]">All open actions have been resolved.</p>
          ) : (
            openItems.map((f) => (
              <div
                key={f.id}
                className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div>
                  <p className="text-sm font-semibold text-[#111111]">{f.title}</p>
                  <p className="mt-1 text-xs text-[#777777]">
                    {f.recommended_steps[0] || "Review and verify with your institution."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setFixing(f)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800 shrink-0"
                >
                  <Wrench className="h-3.5 w-3.5" />
                  Launch Fix Wizard
                </button>
              </div>
            ))
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
                className="rounded-2xl border border-green-200 bg-green-50/60 p-4 flex items-start gap-3"
              >
                <CheckCircle2 className="h-4 w-4 text-green-700 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-semibold text-[#111111]">{f.title}</p>
                  <p className="mt-1 text-xs text-[#777777]">
                    Verification: {f.resolution_evidence}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <FixWizardModal
        finding={fixing}
        onClose={() => setFixing(null)}
        onCompleted={load}
      />
    </DashboardShell>
  );
}
