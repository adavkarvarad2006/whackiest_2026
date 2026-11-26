"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUpRight, FileText, RefreshCw, Search, Wrench } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FixWizardModal } from "@/components/FixWizardModal";
import { api } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import { FindingItem } from "@/lib/types";

const SEVERITY_ORDER: Record<string, number> = { High: 3, Medium: 2, Low: 1 };
const STATUS_ORDER: Record<string, number> = { Open: 4, "In Review": 3, Resolved: 2, Dismissed: 1 };

export default function FindingsPage() {
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<"All" | "Open" | "In Review" | "Resolved" | "Dismissed">("All");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [confidenceFilter, setConfidenceFilter] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<"severity" | "confidence" | "status" | "title">("severity");
  const [searchQuery, setSearchQuery] = useState("");
  const [selected, setSelected] = useState<FindingItem | null>(null);
  const [fixing, setFixing] = useState<FindingItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listFindings();
      setFindings(list);
      setError("");

      if (typeof window !== "undefined") {
        const sp = new URLSearchParams(window.location.search);
        const fid = sp.get("findingId");
        if (fid) {
          const hit = list.find((item) => item.id === fid);
          if (hit) setSelected(hit);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load findings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      const st = sp.get("status");
      if (st === "Open" || st === "In Review" || st === "Resolved" || st === "Dismissed") {
        setStatusFilter(st);
      }
      const q = sp.get("search");
      if (q) setSearchQuery(q);
      const sev = sp.get("severity");
      if (sev) setSeverityFilter(sev);
    }
    load();
  }, [load]);

  const categories = useMemo(
    () => Array.from(new Set(findings.map((f) => f.category).filter(Boolean))).sort(),
    [findings]
  );

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const list = findings.filter((f) => {
      if (statusFilter !== "All" && f.status !== statusFilter) return false;
      if (categoryFilter !== "ALL" && f.category !== categoryFilter) return false;
      if (severityFilter !== "ALL" && f.severity !== severityFilter) return false;
      if (confidenceFilter === "HIGH" && f.confidence < 90) return false;
      if (confidenceFilter === "REVIEW" && f.confidence >= 90) return false;
      if (q) {
        const hay = `${f.title} ${f.category} ${f.evidence?.source_document || ""} ${f.evidence?.why_flagged || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    return [...list].sort((a, b) => {
      if (sortBy === "confidence") return b.confidence - a.confidence;
      if (sortBy === "status") return (STATUS_ORDER[b.status] || 0) - (STATUS_ORDER[a.status] || 0);
      if (sortBy === "title") return a.title.localeCompare(b.title);
      return (SEVERITY_ORDER[b.severity] || 0) - (SEVERITY_ORDER[a.severity] || 0) || b.confidence - a.confidence;
    });
  }, [findings, statusFilter, categoryFilter, severityFilter, confidenceFilter, searchQuery, sortBy]);

  const resetFilters = () => {
    setStatusFilter("All");
    setCategoryFilter("ALL");
    setSeverityFilter("ALL");
    setConfidenceFilter("ALL");
    setSortBy("severity");
    setSearchQuery("");
  };

  return (
    <DashboardShell
      title="Findings"
      subtitle="All cross-document blindspots, nominee gaps, and recurring leaks"
      hasDemoData={findings.some((f) => f.is_demo)}
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {(["All", "Open", "In Review", "Resolved", "Dismissed"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setStatusFilter(tab)}
                className={`rounded-full px-4 py-1.5 text-xs font-medium border transition-colors ${statusFilter === tab
                  ? "bg-[#090909] text-white border-[#090909]"
                  : "bg-white text-[#777777] border-[#E8E8E8] hover:text-[#111111]"
                  }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-3.5 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909] disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Search, Category, Severity, Confidence & Sort Bar */}
        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5 items-center">
          <div className="relative lg:col-span-2">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#777777]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search title, category, or PDF..."
              className="w-full rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] pl-8 pr-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:bg-white focus:outline-none"
            />
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Filter by category"
            className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
          >
            <option value="ALL">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            aria-label="Filter by severity"
            className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
          >
            <option value="ALL">All Severities</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>

          <select
            value={confidenceFilter}
            onChange={(e) => setConfidenceFilter(e.target.value)}
            aria-label="Filter by confidence"
            className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
          >
            <option value="ALL">All Confidence</option>
            <option value="HIGH">High (90%+)</option>
            <option value="REVIEW">Needs Verification (&lt;90%)</option>
          </select>

          <div className="flex items-center gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as "severity" | "confidence" | "status" | "title")}
              aria-label="Sort findings"
              className="flex-1 rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
            >
              <option value="severity">Sort: Severity</option>
              <option value="confidence">Sort: Confidence</option>
              <option value="status">Sort: Status</option>
              <option value="title">Sort: Title (A-Z)</option>
            </select>
            {(statusFilter !== "All" || categoryFilter !== "ALL" || severityFilter !== "ALL" || confidenceFilter !== "ALL" || searchQuery) && (
              <button
                type="button"
                onClick={resetFilters}
                className="rounded-xl border border-[#E8E8E8] px-2.5 py-2 text-[11px] font-medium text-[#777777] hover:text-[#111111]"
              >
                Reset
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">
            {error}
          </div>
        )}

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
                      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${f.severity === "High"
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
                    {f.created_at ? ` • ${formatISTWithTz(f.created_at)}` : ""}
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
