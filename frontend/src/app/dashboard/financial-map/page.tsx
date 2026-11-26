"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { DashboardShell } from "@/components/DashboardShell";
import { PdfViewerModal } from "@/components/PdfViewerModal";
import { api, formatINR } from "@/lib/api";
import { DashboardSummary, DocumentItem } from "@/lib/types";
import { FileText, ArrowRight, Landmark, RefreshCw, Search } from "lucide-react";

export default function FinancialMapPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [activePdf, setActivePdf] = useState<{
    documentId: string | number | null | undefined;
    filename: string;
    evidence?: string;
  } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, d] = await Promise.all([api.getDashboard(), api.listDocuments()]);
      setSummary(s);
      setDocs(d);
    } catch {
      // handled gracefully
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const categories = useMemo(() => {
    const set = new Set((summary?.nominee_tiles || []).map((t) => t.category).filter(Boolean));
    return Array.from(set).sort();
  }, [summary?.nominee_tiles]);

  const visibleTiles = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return (summary?.nominee_tiles || []).filter((tile) => {
      if (categoryFilter !== "ALL" && tile.category !== categoryFilter) return false;
      if (q) {
        const hay = `${tile.asset_name} ${tile.institution} ${tile.category} ${tile.source_document}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [summary?.nominee_tiles, categoryFilter, searchQuery]);

  const openDocumentForTile = (filename: string, note: string) => {
    const matched = docs.find((d) => d.filename.toLowerCase() === filename.toLowerCase());
    setActivePdf({
      documentId: matched?.id,
      filename,
      evidence: note || undefined,
    });
  };

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
          <div className="flex flex-wrap items-center gap-3 text-xs text-white/70">
            <span>
              Linked across {docs.length} processed document{docs.length === 1 ? "" : "s"}
            </span>
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-[11px] font-medium text-white hover:bg-white/10"
            >
              <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Category Filter & Search */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setCategoryFilter("ALL")}
              className={`rounded-full px-3.5 py-1.5 text-xs font-medium border transition-colors ${
                categoryFilter === "ALL"
                  ? "bg-[#090909] text-white border-[#090909]"
                  : "bg-white text-[#777777] border-[#E8E8E8] hover:text-[#111111]"
              }`}
            >
              All ({summary?.nominee_tiles.length ?? 0})
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setCategoryFilter(cat)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-medium border transition-colors ${
                  categoryFilter === cat
                    ? "bg-[#090909] text-white border-[#090909]"
                    : "bg-white text-[#777777] border-[#E8E8E8] hover:text-[#111111]"
                }`}
              >
                {cat.replace(/_/g, " ")}
              </button>
            ))}
          </div>

          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#777777]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter institution or account..."
              className="w-56 rounded-full border border-[#E8E8E8] bg-white pl-8 pr-3 py-1.5 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {visibleTiles.map((tile) => (
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

              <div className="flex items-center justify-between rounded-2xl bg-[#F7F7F7] px-4 py-3 text-xs gap-2">
                <button
                  type="button"
                  onClick={() => openDocumentForTile(tile.source_document, tile.note)}
                  className="inline-flex items-center gap-1.5 text-[#111111] font-medium hover:underline truncate"
                  title={`Open ${tile.source_document}`}
                >
                  <FileText className="h-3.5 w-3.5 text-[#777777] shrink-0" />
                  <span className="truncate">{tile.source_document}</span>
                </button>
                <Link
                  href="/dashboard/nominees"
                  className="inline-flex items-center gap-1 text-[#777777] hover:text-[#111111] shrink-0"
                >
                  Nominee: {tile.status}
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>

      <PdfViewerModal
        open={Boolean(activePdf)}
        documentId={activePdf?.documentId}
        filename={activePdf?.filename || "document.pdf"}
        initialPage={1}
        evidence={activePdf?.evidence}
        onClose={() => setActivePdf(null)}
      />
    </DashboardShell>
  );
}
