"use client";

import React, { useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardShell";
import { api, formatINR } from "@/lib/api";
import { DashboardSummary, DocumentItem } from "@/lib/types";
import { FileText, ArrowRight, Landmark } from "lucide-react";

export default function FinancialMapPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [docs, setDocs] = useState<DocumentItem[]>([]);

  useEffect(() => {
    Promise.all([api.getDashboard(), api.listDocuments()])
      .then(([s, d]) => {
        setSummary(s);
        setDocs(d);
      })
      .catch(() => {});
  }, []);

  return (
    <DashboardShell
      title="Financial Map"
      subtitle="Unified topology of mapped accounts, deposits, policies, and source documents"
      hasDemoData={summary?.has_demo_data}
    >
      <div className="space-y-6">
        <div className="rounded-3xl bg-[#090909] text-white p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-white/50">
              Mapped Net Asset Footprint
            </p>
            <p className="mt-1 text-3xl font-semibold tabular-nums">
              {summary ? formatINR(summary.total_assets_mapped) : "—"}
            </p>
          </div>
          <div className="text-xs text-white/70">
            Linked across {docs.length} processed document{docs.length === 1 ? "" : "s"}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {summary?.nominee_tiles.map((tile) => (
            <div
              key={tile.id}
              className="rounded-3xl border border-[#E8E8E8] bg-white p-6 flex flex-col justify-between gap-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F7F7F7] border border-[#E8E8E8]">
                    <Landmark className="h-4 w-4 text-[#111111]" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#111111]">
                      {tile.asset_name}
                    </p>
                    <p className="text-xs text-[#777777]">
                      {tile.institution} • {tile.category}
                    </p>
                  </div>
                </div>
                <p className="text-sm font-semibold text-[#111111] tabular-nums">
                  {formatINR(tile.value)}
                </p>
              </div>

              <div className="flex items-center justify-between rounded-2xl bg-[#F7F7F7] px-4 py-3 text-xs">
                <span className="inline-flex items-center gap-1.5 text-[#111111] font-medium">
                  <FileText className="h-3.5 w-3.5 text-[#777777]" />
                  {tile.source_document}
                </span>
                <span className="inline-flex items-center gap-1 text-[#777777]">
                  Nominee: {tile.status}
                  <ArrowRight className="h-3 w-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
