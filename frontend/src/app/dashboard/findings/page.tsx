"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, FileText, Wrench } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FixWizardModal } from "@/components/FixWizardModal";
import { api } from "@/lib/api";
import { FindingItem } from "@/lib/types";

export default function FindingsPage() {
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [filter, setFilter] = useState<"All" | "Open" | "Resolved" | "Dismissed">("All");
  const [selected, setSelected] = useState<FindingItem | null>(null);
  const [fixing, setFixing] = useState<FindingItem | null>(null);

  const load = useCallback(() => {
    api.listFindings().then(setFindings).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = findings.filter((f) =>
    filter === "All" ? true : f.status === filter
  );

  return (
    <DashboardShell
      title="Findings"
      subtitle="All cross-document blindspots, nominee gaps, and recurring leaks"
      hasDemoData={findings.some((f) => f.is_demo)}
    >
      <div className="space-y-5">
        <div className="flex flex-wrap gap-2">
          {(["All", "Open", "Resolved", "Dismissed"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setFilter(tab)}
              className={`rounded-full px-4 py-1.5 text-xs font-medium border transition-colors ${
                filter === tab
                  ? "bg-[#090909] text-white border-[#090909]"
                  : "bg-white text-[#777777] border-[#E8E8E8] hover:text-[#111111]"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="rounded-3xl border border-[#E8E8E8] bg-white divide-y divide-[#E8E8E8]">
          {filtered.length === 0 ? (
            <p className="p-8 text-sm text-[#777777]">No findings match this filter.</p>
          ) : (
            filtered.map((f) => (
              <div
                key={f.id}
                className="p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
                        f.severity === "High"
                          ? "bg-red-50 text-red-700 border-red-200"
                          : f.severity === "Medium"
                          ? "bg-amber-50 text-amber-700 border-amber-200"
                          : "bg-neutral-100 text-[#111111] border-[#E8E8E8]"
                      }`}
                    >
                      {f.severity}
                    </span>
                    <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-0.5 text-[11px] text-[#777777] tabular-nums">
                      {f.confidence}% confidence
                    </span>
                    <span className="rounded-full border border-[#E8E8E8] px-2.5 py-0.5 text-[11px] text-[#111111]">
                      {f.status}
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-[#111111]">{f.title}</p>
                  <p className="inline-flex items-center gap-1.5 text-xs text-[#777777]">
                    <FileText className="h-3.5 w-3.5" />
                    {f.evidence.source_document} • Page {f.evidence.page_number}
                  </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => setSelected(f)}
                    className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-4 py-2 text-xs font-medium text-[#111111] hover:border-[#090909]"
                  >
                    Review
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                  {f.status !== "Resolved" && f.status !== "Dismissed" && (
                    <button
                      type="button"
                      onClick={() => setFixing(f)}
                      className="inline-flex items-center gap-1.5 rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800"
                    >
                      <Wrench className="h-3.5 w-3.5" />
                      Fix
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <EvidenceDrawer
        finding={selected}
        onClose={() => setSelected(null)}
        onOpenFix={(item) => {
          setSelected(null);
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
