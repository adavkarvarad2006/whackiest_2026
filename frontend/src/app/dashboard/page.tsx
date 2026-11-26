"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { ArrowUpRight, FileText, Wrench } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { NomineeCoverageCard } from "@/components/NomineeCoverageCard";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FixWizardModal } from "@/components/FixWizardModal";
import { api, formatINR } from "@/lib/api";
import { DashboardSummary, FindingItem } from "@/lib/types";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);
  const [fixFinding, setFixFinding] = useState<FindingItem | null>(null);

  const loadDashboard = useCallback(async () => {
    try {
      const res = await api.getDashboard();
      setData(res);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  return (
    <DashboardShell
      title="Financial Intelligence"
      subtitle="Unified asset map, nominee coverage, and evidence-backed blindspots"
      hasDemoData={data?.has_demo_data}
    >
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-32 rounded-3xl border border-[#E8E8E8] bg-white animate-pulse"
            />
          ))}
        </div>
      ) : error || !data ? (
        <div className="rounded-3xl border border-red-200 bg-white p-8 text-sm text-red-600">
          {error || "Unable to load dashboard."}
        </div>
      ) : (
        <div className="space-y-7">
          {/* 4 Primary KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6">
              <p className="text-xs font-medium text-[#777777]">
                Total Assets Mapped
              </p>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight text-[#111111] tabular-nums">
                {formatINR(data.total_assets_mapped)}
              </p>
              <p className="mt-2 text-[11px] text-[#777777]">
                Across bank &amp; deposit records
              </p>
            </div>

            <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6">
              <p className="text-xs font-medium text-[#777777]">
                Potential Blindspots
              </p>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight text-[#111111] tabular-nums">
                {data.potential_blindspots}
              </p>
              <p className="mt-2 text-[11px] text-[#777777]">
                Open findings awaiting review
              </p>
            </div>

            <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6">
              <p className="text-xs font-medium text-[#777777]">
                Potential Annual Leaks
              </p>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight text-[#111111] tabular-nums">
                {formatINR(data.potential_annual_leaks)}
              </p>
              <p className="mt-2 text-[11px] text-[#777777]">
                Recurring mandates detected
              </p>
            </div>

            <div className="rounded-3xl bg-[#090909] text-white p-6">
              <p className="text-xs font-medium text-white/60">
                ArthaLens Score
              </p>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight tabular-nums">
                {data.arthalens_score}
                <span className="text-sm font-normal text-white/50">/100</span>
              </p>
              <p className="mt-2 text-[11px] text-white/60">
                Updates as gaps are verified
              </p>
            </div>
          </div>

          {/* Financial Overview Chart + Nominee Coverage Map */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
            <div className="xl:col-span-6 rounded-3xl border border-[#E8E8E8] bg-white p-6 sm:p-7">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-base font-semibold text-[#111111]">
                    Financial Overview
                  </h2>
                  <p className="text-xs text-[#777777]">
                    Monthly income, expenses &amp; investments trend
                  </p>
                </div>
                <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111] tabular-nums">
                  Flow: {formatINR(data.monthly_financial_flow)}
                </span>
              </div>

              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.trends} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EFEFEF" />
                    <XAxis dataKey="month" tick={{ fontSize: 12, fill: "#777777" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#777777" }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${Math.round(v / 1000)}k`} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#090909",
                        border: "none",
                        borderRadius: "12px",
                        color: "#ffffff",
                        fontSize: "12px",
                      }}
                    />
                    <Area type="monotone" dataKey="income" name="Income" stroke="#090909" strokeWidth={2} fill="#090909" fillOpacity={0.08} />
                    <Area type="monotone" dataKey="investments" name="Investments" stroke="#555555" strokeWidth={2} fill="#555555" fillOpacity={0.05} />
                    <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#A3A3A3" strokeWidth={1.75} fill="#A3A3A3" fillOpacity={0.04} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="xl:col-span-6">
              <NomineeCoverageCard
                coveragePct={data.nominee_coverage_pct}
                counts={data.nominee_counts}
                tiles={data.nominee_tiles}
              />
            </div>
          </div>

          {/* Recent Findings */}
          <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 sm:p-7">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-base font-semibold text-[#111111]">
                  Recent Findings
                </h2>
                <p className="text-xs text-[#777777]">
                  Click Review to inspect exact source document evidence, or Fix to resolve with verification.
                </p>
              </div>
            </div>

            <div className="divide-y divide-[#E8E8E8]">
              {data.recent_findings.map((finding) => {
                const sevStyle =
                  finding.severity === "High"
                    ? "bg-red-50 text-red-700 border-red-200"
                    : finding.severity === "Medium"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-neutral-100 text-[#111111] border-[#E8E8E8]";

                return (
                  <div
                    key={finding.id}
                    className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${sevStyle}`}>
                          {finding.severity}
                        </span>
                        <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-0.5 text-[11px] text-[#777777] tabular-nums">
                          {finding.confidence}% confidence
                        </span>
                        <span className="rounded-full border border-[#E8E8E8] px-2.5 py-0.5 text-[11px] text-[#111111]">
                          {finding.status}
                        </span>
                        {finding.is_demo && (
                          <span className="text-[11px] text-[#777777]">(Demo)</span>
                        )}
                      </div>
                      <p className="text-sm font-semibold text-[#111111]">
                        {finding.title}
                      </p>
                      <p className="inline-flex items-center gap-1.5 text-xs text-[#777777]">
                        <FileText className="h-3.5 w-3.5" />
                        {finding.evidence.source_document} • Page {finding.evidence.page_number}
                      </p>
                    </div>

                    <div className="flex items-center gap-2.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => setSelectedFinding(finding)}
                        className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-4 py-2 text-xs font-medium text-[#111111] hover:border-[#090909] transition-colors"
                      >
                        Review
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </button>
                      {finding.status !== "Resolved" && finding.status !== "Dismissed" && (
                        <button
                          type="button"
                          onClick={() => setFixFinding(finding)}
                          className="inline-flex items-center gap-1.5 rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800 transition-colors"
                        >
                          <Wrench className="h-3.5 w-3.5" />
                          Fix
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <EvidenceDrawer
        finding={selectedFinding}
        onClose={() => setSelectedFinding(null)}
        onOpenFix={(f) => {
          setSelectedFinding(null);
          setFixFinding(f);
        }}
        onUpdated={loadDashboard}
      />

      <FixWizardModal
        finding={fixFinding}
        onClose={() => setFixFinding(null)}
        onCompleted={loadDashboard}
      />
    </DashboardShell>
  );
}
