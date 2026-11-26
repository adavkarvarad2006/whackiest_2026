"use client";

import React from "react";
import { NomineeAssetTile } from "@/lib/types";
import { formatINR } from "@/lib/api";

interface NomineeCoverageCardProps {
  coveragePct: number;
  counts: { GREEN: number; AMBER: number; RED: number };
  tiles: NomineeAssetTile[];
}

export function NomineeCoverageCard({
  coveragePct,
  counts,
  tiles,
}: NomineeCoverageCardProps) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (coveragePct / 100) * circumference;

  return (
    <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 sm:p-7">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 pb-6 border-b border-[#E8E8E8]">
        <div>
          <h2 className="text-base font-semibold text-[#111111]">
            Nominee Coverage Map
          </h2>
          <p className="mt-1 text-xs text-[#777777]">
            Never marked GREEN based on assumptions — requires explicit confirmation in uploaded documents.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-4 text-xs">
            <span className="inline-flex items-center gap-1.5 font-medium text-[#111111]">
              <span className="h-2.5 w-2.5 rounded-full bg-green-600" />
              GREEN ({counts.GREEN}) Confirmed
            </span>
            <span className="inline-flex items-center gap-1.5 font-medium text-[#111111]">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
              AMBER ({counts.AMBER}) Indirect
            </span>
            <span className="inline-flex items-center gap-1.5 font-medium text-[#111111]">
              <span className="h-2.5 w-2.5 rounded-full bg-red-600" />
              RED ({counts.RED}) Missing
            </span>
          </div>
        </div>

        {/* Visual Coverage Ring */}
        <div className="relative flex h-28 w-28 shrink-0 items-center justify-center">
          <svg className="h-28 w-28 -rotate-90" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r={radius}
              stroke="#E8E8E8"
              strokeWidth="8"
              fill="none"
            />
            <circle
              cx="50"
              cy="50"
              r={radius}
              stroke="#090909"
              strokeWidth="8"
              strokeLinecap="round"
              fill="none"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
          </svg>
          <div className="absolute text-center">
            <p className="text-xl font-semibold text-[#111111] tabular-nums">
              {coveragePct}%
            </p>
            <p className="text-[10px] text-[#777777]">Verified</p>
          </div>
        </div>
      </div>

      {/* Category-wise Asset Tiles */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {tiles.map((tile) => {
          const badgeStyle =
            tile.status === "GREEN"
              ? "bg-green-50 text-green-700 border-green-200"
              : tile.status === "AMBER"
              ? "bg-amber-50 text-amber-700 border-amber-200"
              : "bg-red-50 text-red-700 border-red-200";

          return (
            <div
              key={tile.id}
              className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 flex flex-col justify-between gap-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-[#111111]">
                    {tile.asset_name}
                  </p>
                  <p className="text-[11px] text-[#777777]">
                    {tile.category} • {tile.institution}
                  </p>
                </div>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${badgeStyle}`}
                >
                  {tile.status}
                </span>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-[#E8E8E8]/80 text-[11px]">
                <span className="text-[#777777] truncate max-w-[60%]">
                  {tile.nominee_name ? `Nominee: ${tile.nominee_name}` : "No nominee confirmed"}
                </span>
                <span className="font-semibold text-[#111111] tabular-nums">
                  {formatINR(tile.value)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
