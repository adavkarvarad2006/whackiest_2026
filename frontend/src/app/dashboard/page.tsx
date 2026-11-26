"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { ArrowUpRight, FileText, RefreshCw, Search, Wrench } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { NomineeCoverageCard } from "@/components/NomineeCoverageCard";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FixWizardModal } from "@/components/FixWizardModal";
import { api, formatINR } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import { DashboardSummary, FindingItem } from "@/lib/types";

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);
  const [fixFinding, setFixFinding] = useState<FindingItem | null>(null);
  const [dateRange, setDateRange] = useState<"ALL" | "3M" | "6M">("ALL");
  const [findingSearch, setFindingSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<"All" | "High" | "Medium" | "Low">("All");

  const loadDashboard = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const res = await api.getDashboard();
      setData(res);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const filteredTrends = useMemo(() => {
    if (!data?.trends) return [];
    if (dateRange === "3M") return data.trends.slice(-3);
    if (dateRange === "6M") return data.trends.slice(-6);
    return data.trends;
  }, [data?.trends, dateRange]);

  const displayedMonthlyFlow = useMemo(() => {
    if (filteredTrends.length === 0) return data?.monthly_financial_flow ?? 0;
    const sum = filteredTrends.reduce((acc, t) => acc + (t.net_flow || 0), 0);
    return sum / filteredTrends.length;
  }, [filteredTrends, data?.monthly_financial_flow]);

  const filteredRecentFindings = useMemo(() => {
    const base = data?.recent_findings ?? [];
    const q = findingSearch.trim().toLowerCase();
    return base.filter((f) => {
      if (severityFilter !== "All" && f.severity !== severityFilter) return false;
      if (q) {
        const hay = `${f.title} ${f.category} ${f.evidence?.source_document || ""} ${f.status}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [data?.recent_findings, findingSearch, severityFilter]);

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
          {/* Toolbar: Quick Refresh */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-[#777777]">
              <span>
                Interactive summary synced with PostgreSQL/RAG pipeline
                {data.server_time_ist ? ` • ${formatISTWithTz(data.server_time_ist)}` : ""}
              </span>
            </div>
            <button
              type="button"
              onClick={() => loadDashboard(true)}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-4 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909] disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {/* 4 Primary KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <button
              type="button"
              onClick={() => router.push("/dashboard/financial-map")}
              className="text-left rounded-3xl border border-[#E8E8E8] bg-white p-6 hover:border-[#090909] transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-[#777777]">
                  Total Assets Mapped
                </p>
                <ArrowUpRight className="h-3.5 w-3.5 text-[#777777]" />
              </div>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight text-[#111111] tabular-nums">
                {formatINR(data.total_assets_mapped)}
              </p>
              <p className="mt-2 text-[11px] text-[#777777]">
                View mapped accounts &amp; deposits
              </p>
            </button>

            <button
              type="button"
              onClick={() => router.push("/dashboard/findings?status=Open")}
              className="text-left rounded-3xl border border-[#E8E8E8] bg-white p-6 hover:border-[#090909] transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-[#777777]">
                  Potential Blindspots
                </p>
                <ArrowUpRight className="h-3.5 w-3.5 text-[#777777]" />
              </div>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight text-[#111111] tabular-nums">
                {data.potential_blindspots}
              </p>
              <p className="mt-2 text-[11px] text-[#777777]">
                Inspect open gaps &amp; risks
              </p>
            </button>

            <button
              type="button"
              onClick={() => router.push("/dashboard/findings?search=subscription")}
              className="text-left rounded-3xl border border-[#E8E8E8] bg-white p-6 hover:border-[#090909] transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-[#777777]">
                  Potential Annual Leaks
                </p>
                <ArrowUpRight className="h-3.5 w-3.5 text-[#777777]" />
              </div>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight text-[#111111] tabular-nums">
                {formatINR(data.potential_annual_leaks)}
              </p>
              <p className="mt-2 text-[11px] text-[#777777]">
                Review recurring mandates
              </p>
            </button>

            <button
              type="button"
              onClick={() => router.push("/dashboard/actions")}
              className="text-left rounded-3xl bg-[#090909] text-white p-6 hover:bg-neutral-900 transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-white/60">
                  ArthaLens Score
                </p>
                <ArrowUpRight className="h-3.5 w-3.5 text-white/60" />
              </div>
              <p className="mt-2.5 text-3xl font-semibold tracking-tight tabular-nums">
                {data.arthalens_score}
                <span className="text-sm font-normal text-white/50">/100</span>
              </p>
              <p className="mt-2 text-[11px] text-white/60">
                Open guided action checklist
              </p>
            </button>
          </div>

          {/* Financial Overview Chart + Nominee Coverage Map */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
            <div className="xl:col-span-6 rounded-3xl border border-[#E8E8E8] bg-white p-6 sm:p-7">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                <div>
                  <h2 className="text-base font-semibold text-[#111111]">
                    Financial Overview
                  </h2>
                  <p className="text-xs text-[#777777]">
                    Monthly income, expenses &amp; investments trend
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="inline-flex rounded-full border border-[#E8E8E8] bg-[#F7F7F7] p-0.5 text-[11px]">
                    {(["ALL", "6M", "3M"] as const).map((rng) => (
                      <button
                        key={rng}
                        type="button"
                        onClick={() => setDateRange(rng)}
                        className={`rounded-full px-2.5 py-0.5 font-medium transition-colors ${
                          dateRange === rng
                            ? "bg-[#090909] text-white"
                            : "text-[#777777] hover:text-[#111111]"
                        }`}
                      >
                        {rng === "ALL" ? "All" : rng}
                      </button>
                    ))}
                  </div>
                  <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111] tabular-nums">
                    Flow: {formatINR(displayedMonthlyFlow)}
                  </span>
                </div>
              </div>

              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={filteredTrends} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
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
                onTileClick={() => router.push("/dashboard/nominees")}
              />
            </div>
          </div>

          {/* Recent Findings */}
          <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 sm:p-7">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-semibold text-[#111111]">
                    Recent Findings
                  </h2>
                  <Link
                    href="/dashboard/findings"
                    className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                  >
                    View All ({data.recent_findings.length})
                    <ArrowUpRight className="h-3 w-3" />
                  </Link>
                </div>
                <p className="mt-1 text-xs text-[#777777]">
                  Click Review to inspect exact source document evidence, or Fix to resolve with verification.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#777777]" />
                  <input
                    type="text"
                    value={findingSearch}
                    onChange={(e) => setFindingSearch(e.target.value)}
                    placeholder="Search findings..."
                    className="w-44 sm:w-52 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] pl-8 pr-3 py-1.5 text-xs text-[#111111] focus:border-[#090909] focus:bg-white focus:outline-none"
                  />
                </div>
                {(["All", "High", "Medium", "Low"] as const).map((sev) => (
                  <button
                    key={sev}
                    type="button"
                    onClick={() => setSeverityFilter(sev)}
                    className={`rounded-full px-3 py-1 text-[11px] font-medium border transition-colors ${
                      severityFilter === sev
                        ? "bg-[#090909] text-white border-[#090909]"
                        : "bg-white text-[#777777] border-[#E8E8E8] hover:text-[#111111]"
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            <div className="divide-y divide-[#E8E8E8]">
              {filteredRecentFindings.length === 0 ? (
                <p className="py-6 text-xs text-[#777777]">
                  No findings match your current search or filter.
                </p>
              ) : (
              filteredRecentFindings.map((finding) => {
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
                        {finding.created_at ? ` • ${formatISTWithTz(finding.created_at)}` : ""}
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
              }))}
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
