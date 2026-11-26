"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, RefreshCw } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { api, clearAuthSession } from "@/lib/api";
import { User } from "@/lib/types";

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [nameInput, setNameInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadUser = async () => {
    setLoading(true);
    try {
      const me = await api.me();
      setUser(me);
      setNameInput(me.name);
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load profile");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage("");
    setError("");
    if (nameInput.trim().length < 2) {
      setError("Display name must be at least 2 characters.");
      return;
    }
    setSaving(true);
    try {
      const updated = await api.updateProfile(nameInput.trim());
      setUser(updated);
      setNameInput(updated.name);
      setMessage("Profile updated cleanly.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

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
        <form
          onSubmit={handleSaveProfile}
          className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-4"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#111111]">Account Profile</h2>
            <button
              type="button"
              onClick={loadUser}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] px-3 py-1 text-[11px] text-[#777777] hover:text-[#111111]"
            >
              <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
              Sync
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-[#777777] mb-1.5">Display Name</label>
              <input
                type="text"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                required
                minLength={2}
                className="w-full rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] px-3.5 py-2.5 text-xs font-semibold text-[#111111] focus:border-[#090909] focus:bg-white focus:outline-none"
              />
            </div>
            <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-3.5">
              <p className="text-[#777777]">Email</p>
              <p className="mt-1 font-semibold text-[#111111]">{user?.email || "—"}</p>
            </div>
          </div>

          {message && (
            <p className="inline-flex items-center gap-1.5 text-xs text-green-700">
              <Check className="h-3.5 w-3.5" />
              {message}
            </p>
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="rounded-full bg-[#090909] px-5 py-2 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Profile"}
            </button>
          </div>
        </form>

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
