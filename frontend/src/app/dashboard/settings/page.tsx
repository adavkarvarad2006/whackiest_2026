"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/DashboardShell";
import { api, clearAuthSession } from "@/lib/api";
import { User } from "@/lib/types";

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api.me().then(setUser).catch(() => {});
  }, []);

  const handleLogout = () => {
    clearAuthSession();
    router.push("/login");
  };

  return (
    <DashboardShell
      title="Settings"
      subtitle="Account details, data boundaries, and security preferences"
      hasDemoData={user?.is_demo}
    >
      <div className="max-w-2xl space-y-6">
        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-4">
          <h2 className="text-base font-semibold text-[#111111]">Account Profile</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4">
              <p className="text-[#777777]">Name</p>
              <p className="mt-1 font-semibold text-[#111111]">{user?.name || "—"}</p>
            </div>
            <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4">
              <p className="text-[#777777]">Email</p>
              <p className="mt-1 font-semibold text-[#111111]">{user?.email || "—"}</p>
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-3">
          <h2 className="text-base font-semibold text-[#111111]">
            Intelligence &amp; Verification Guarantees
          </h2>
          <p className="text-xs text-[#777777] leading-relaxed">
            ArthaLens operates strictly as a read-only document intelligence platform. It never submits forms or alters records at your bank, insurer, or tax portal automatically. Nominee statuses are only marked GREEN when confirmed directly in an uploaded document or backed by user-supplied verification evidence.
          </p>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="rounded-full border border-[#E8E8E8] bg-white px-6 py-2.5 text-xs font-medium text-[#111111] hover:border-[#090909]"
        >
          Sign Out of Workspace
        </button>
      </div>
    </DashboardShell>
  );
}
