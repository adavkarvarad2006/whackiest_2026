"use client";

import React, { useEffect, useState } from "react";
import { X, Check, Copy, ShieldAlert } from "lucide-react";
import { FindingItem } from "@/lib/types";
import { api } from "@/lib/api";

interface FixWizardModalProps {
  finding: FindingItem | null;
  onClose: () => void;
  onCompleted: () => void;
}

export function FixWizardModal({
  finding,
  onClose,
  onCompleted,
}: FixWizardModalProps) {
  const [checkedSteps, setCheckedSteps] = useState<string[]>([]);
  const [evidenceText, setEvidenceText] = useState("");
  const [nomineeName, setNomineeName] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [savingProgress, setSavingProgress] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setCheckedSteps(Array.isArray(finding?.completed_steps) ? finding.completed_steps : []);
    setEvidenceText(finding?.resolution_evidence || "");
    setNomineeName("");
    setError("");
    setSuccessMsg("");
    setCopied(false);
  }, [finding?.id, finding?.completed_steps, finding?.resolution_evidence]);

  if (!finding || typeof finding !== "object") return null;

  const recommendedSteps = Array.isArray(finding?.recommended_steps)
    ? finding.recommended_steps.filter((s): s is string => typeof s === "string" && s.trim().length > 0)
    : [];
  const safeCheckedSteps = Array.isArray(checkedSteps) ? checkedSteps : [];
  const completedCount = recommendedSteps.filter((s) => safeCheckedSteps.includes(s)).length;
  const progressPct = recommendedSteps.length > 0 ? Math.round((completedCount / recommendedSteps.length) * 100) : 0;

  const toggleStep = (step: string) => {
    setSuccessMsg("");
    setCheckedSteps((prev) => {
      const base = Array.isArray(prev) ? prev : [];
      return base.includes(step) ? base.filter((s) => s !== step) : [...base, step];
    });
  };

  const handleSaveProgress = async () => {
    setError("");
    setSuccessMsg("");
    setSavingProgress(true);
    try {
      await api.saveFixProgress(finding.id, {
        verification_evidence: evidenceText.trim(),
        completed_steps: safeCheckedSteps,
        nominee_name: nomineeName.trim() || undefined,
      });
      setSuccessMsg("Progress saved. Finding marked In Review until finalized.");
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not save progress");
    } finally {
      setSavingProgress(false);
    }
  };

  const handleCopyEmail = () => {
    if (!finding?.draft_email) return;
    navigator.clipboard.writeText(finding.draft_email);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleComplete = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (evidenceText.trim().length < 8) {
      setError("Please provide verification evidence (at least 8 characters) before marking complete.");
      return;
    }
    setSubmitting(true);
    try {
      await api.completeFix(finding.id, {
        verification_evidence: evidenceText.trim(),
        completed_steps: safeCheckedSteps,
        nominee_name: nomineeName.trim() || undefined,
      });
      setEvidenceText("");
      setNomineeName("");
      setCheckedSteps([]);
      onCompleted();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not complete fix");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />

      <div className="relative z-10 w-full max-w-xl rounded-3xl border border-[#E8E8E8] bg-white shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="flex items-start justify-between border-b border-[#E8E8E8] px-6 py-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#777777]">
              Guided Fix Wizard
            </p>
            <h2 className="mt-1 text-lg font-semibold text-[#111111]">
              {finding.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#E8E8E8] p-2 text-[#777777] hover:text-[#111111]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleComplete} className="p-6 space-y-5 overflow-y-auto">
          {/* Disclaimer */}
          <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 flex items-start gap-3">
            <ShieldAlert className="h-4 w-4 text-[#111111] mt-0.5 shrink-0" />
            <p className="text-xs text-[#777777] leading-relaxed">
              <strong className="text-[#111111]">Manual action required:</strong> ArthaLens does not submit forms or modify bank/insurance records automatically. Complete the steps below with your provider, then enter verification evidence to update your dashboard.
            </p>
          </div>

          {/* Recommended Next Steps */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                Recommended Next Steps
              </p>
              {recommendedSteps.length > 0 && (
                <span className="text-[11px] font-medium text-[#111111] tabular-nums">
                  {completedCount} of {recommendedSteps.length} completed ({progressPct}%)
                </span>
              )}
            </div>
            {recommendedSteps.length > 0 && (
              <div className="mb-3 h-1.5 w-full rounded-full bg-[#E8E8E8] overflow-hidden">
                <div
                  className="h-full bg-[#090909] transition-all duration-300"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            )}
            <div className="space-y-2">
              {recommendedSteps.length === 0 ? (
                <p className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-3 text-xs text-[#777777]">
                  No recommended steps available yet.
                </p>
              ) : (
                recommendedSteps.map((step, index) => {
                  const done = safeCheckedSteps.includes(step);
                  return (
                    <button
                      key={`${index}-${step}`}
                      type="button"
                      onClick={() => toggleStep(step)}
                      className="w-full flex items-start gap-3 rounded-xl border border-[#E8E8E8] bg-white p-3 text-left hover:border-[#111111]/40 transition-colors"
                    >
                      <span
                        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                          done
                            ? "bg-[#090909] border-[#090909] text-white"
                            : "border-[#CCCCCC]"
                        }`}
                      >
                        {done && <Check className="h-3 w-3" />}
                      </span>
                      <span className={`text-xs leading-relaxed ${done ? "line-through text-[#777777]" : "text-[#111111]"}`}>
                        {step}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Draft Email */}
          {finding.draft_email && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                  Draft Request Email
                </p>
                <button
                  type="button"
                  onClick={handleCopyEmail}
                  className="inline-flex items-center gap-1 text-xs font-medium text-[#111111] hover:underline"
                >
                  <Copy className="h-3 w-3" />
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <pre className="whitespace-pre-wrap rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-3.5 text-xs font-mono text-[#111111] leading-relaxed">
                {finding.draft_email}
              </pre>
            </div>
          )}

          {/* Nominee Name if Nominee Gap */}
          {finding.category === "Nominee Gap" && (
            <div>
              <label className="block text-xs font-medium text-[#111111] mb-1.5">
                Confirmed Nominee Name (Optional)
              </label>
              <input
                type="text"
                value={nomineeName}
                onChange={(e) => setNomineeName(e.target.value)}
                placeholder="e.g., Priya Mehta (Spouse)"
                className="w-full rounded-xl border border-[#E8E8E8] bg-white px-3.5 py-2 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
              />
            </div>
          )}

          {/* Verification Evidence */}
          <div>
            <label className="block text-xs font-medium text-[#111111] mb-1.5">
              Verification Evidence <span className="text-red-600">*</span>
            </label>
            <textarea
              required
              rows={2}
              value={evidenceText}
              onChange={(e) => setEvidenceText(e.target.value)}
              placeholder="e.g., Endorsement reference #SR-99412 received from Max Life on 26 Nov 2026"
              className="w-full rounded-xl border border-[#E8E8E8] bg-white p-3 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2 text-xs text-red-700">
              {error}
            </div>
          )}

          {successMsg && (
            <div className="rounded-xl border border-green-200 bg-green-50 px-3.5 py-2 text-xs text-green-800">
              {successMsg}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-end gap-2.5 pt-2 border-t border-[#E8E8E8]">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-[#E8E8E8] px-4 py-2 text-xs font-medium text-[#777777] hover:text-[#111111]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={savingProgress || submitting}
              onClick={handleSaveProgress}
              className="rounded-full border border-[#090909] bg-white px-4 py-2 text-xs font-medium text-[#111111] hover:bg-[#F7F7F7] disabled:opacity-50"
            >
              {savingProgress ? "Saving..." : "Save Progress"}
            </button>
            <button
              type="submit"
              disabled={submitting || savingProgress}
              className="rounded-full bg-[#090909] px-5 py-2 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
            >
              {submitting ? "Updating..." : "Mark as Completed"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
