"use client";

import React, { useEffect, useState } from "react";
import { DashboardShell } from "@/components/DashboardShell";
import { NomineeCoverageCard } from "@/components/NomineeCoverageCard";
import { api } from "@/lib/api";
import { DashboardSummary } from "@/lib/types";

export default function NomineesPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    api.getDashboard().then(setData).catch(() => {});
  }, []);

  return (
    <DashboardShell
      title="Nominee Coverage"
      subtitle="Strict verification status across all mapped accounts and policies"
      hasDemoData={data?.has_demo_data}
    >
      {data ? (
        <div className="space-y-6">
          <NomineeCoverageCard
            coveragePct={data.nominee_coverage_pct}
            counts={data.nominee_counts}
            tiles={data.nominee_tiles}
          />
          <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 text-xs text-[#777777] space-y-2">
            <p className="font-semibold text-[#111111]">Classification Policy</p>
            <p>
              <strong className="text-green-700">GREEN</strong> — Confirmed directly in an uploaded document or backed by user verification evidence.
            </p>
            <p>
              <strong className="text-amber-700">AMBER</strong> — Discovered indirectly (e.g., CIF reference without explicit nominee name) and requires verification.
            </p>
            <p>
              <strong className="text-red-700">RED</strong> — Missing, explicitly marked &ldquo;Not Registered&rdquo;, or no supporting document uploaded.
            </p>
          </div>
        </div>
      ) : (
        <div className="h-48 rounded-3xl border border-[#E8E8E8] bg-white animate-pulse" />
      )}
    </DashboardShell>
  );
}
