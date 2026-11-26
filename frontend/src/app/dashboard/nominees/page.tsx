"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { NomineeCoverageCard } from "@/components/NomineeCoverageCard";
import { PdfViewerModal } from "@/components/PdfViewerModal";
import { api } from "@/lib/api";
import { DashboardSummary, DocumentItem, NomineeAssetTile } from "@/lib/types";

export default function NomineesPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activePdf, setActivePdf] = useState<{
    documentId: string | number | null | undefined;
    filename: string;
    evidence?: string;
  } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [summary, d] = await Promise.all([api.getDashboard(), api.listDocuments()]);
      setData(summary);
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

  const handleTileClick = (tile: NomineeAssetTile) => {
    const matched = docs.find((d) => d.filename.toLowerCase() === tile.source_document.toLowerCase());
    setActivePdf({
      documentId: matched?.id,
      filename: tile.source_document,
      evidence: tile.note || undefined,
    });
  };

  return (
    <DashboardShell
      title="Nominee Coverage"
      subtitle="Strict verification status across all mapped accounts and policies"
      hasDemoData={data?.has_demo_data}
    >
      {data ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Link
              href="/dashboard/findings?search=nominee"
              className="inline-flex items-center gap-1.5 rounded-full bg-[#090909] px-4 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
            >
              Review Missing Nominees
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-3.5 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909]"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          <NomineeCoverageCard
            coveragePct={data.nominee_coverage_pct}
            counts={data.nominee_counts}
            tiles={data.nominee_tiles}
            onTileClick={handleTileClick}
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
