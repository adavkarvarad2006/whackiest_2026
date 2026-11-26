"use client";

import React, { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  FileText,
  ArrowUpRight,
  Check,
  Shield,
  Lock,
  Eye,
  AlertTriangle,
} from "lucide-react";
import { ArthaLogo } from "./ArthaLogo";

const STACKED_DOCS = [
  { title: "Bank Statement", meta: "HDFC Savings • 4 pages", offset: 0 },
  { title: "AIS (IT)", meta: "Annual Information Statement", offset: 1 },
  { title: "Insurance Policy", meta: "Term Life • Section 39", offset: 2 },
  { title: "Fixed Deposit", meta: "SBI Term Deposit Advice", offset: 3 },
  { title: "Loan Statement", meta: "Home Loan Amortization", offset: 4 },
];

const INITIAL_TASKS = [
  { id: "t1", label: "Add nominee to insurance policy.", done: false },
  { id: "t2", label: "Verify additional bank account.", done: false },
  { id: "t3", label: "Review unused subscriptions.", done: true },
];

export function EditorialSections() {
  const [tasks, setTasks] = useState(INITIAL_TASKS);

  const toggleTask = (id: string) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t))
    );
  };

  return (
    <div className="bg-white text-[#111111]">
      {/* SECTION 1 – Unify Your Financial Life */}
      <section
        id="product"
        className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32 border-b border-[#E8E8E8]"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-14 items-center">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6 }}
            className="lg:col-span-5"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#777777]">
              01 / Document Unification
            </p>
            <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-[-0.03em] leading-[1.1]">
              Unify your financial life.
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[#777777] leading-relaxed">
              Upload your bank statements, AIS, insurance policies, loans and more – all in one secure place.
            </p>
            <div className="mt-8">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-[#090909] px-6 py-3 text-sm font-medium text-white hover:bg-neutral-800 transition-colors"
              >
                Learn More
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </div>
          </motion.div>

          {/* Layered 3D Document Stack */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.7 }}
            className="lg:col-span-7 flex justify-center"
          >
            <div className="relative w-full max-w-lg rounded-3xl bg-[#F7F7F7] border border-[#E8E8E8] p-8 sm:p-10">
              <div className="space-y-3">
                {STACKED_DOCS.map((doc, idx) => (
                  <motion.div
                    key={doc.title}
                    whileHover={{ x: 6, y: -2 }}
                    transition={{ type: "spring", stiffness: 320, damping: 24 }}
                    style={{
                      marginLeft: `${idx * 10}px`,
                    }}
                    className="flex items-center justify-between rounded-2xl border border-[#E8E8E8] bg-white px-5 py-4 shadow-[0_10px_30px_rgba(0,0,0,0.04)]"
                  >
                    <div className="flex items-center gap-3.5">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#090909] text-white">
                        <FileText className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[#111111]">
                          {doc.title}
                        </p>
                        <p className="text-xs text-[#777777]">{doc.meta}</p>
                      </div>
                    </div>
                    <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111]">
                      Indexed
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* SECTION 2 – Discover Hidden Risks */}
      <section
        id="how-it-works"
        className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32 border-b border-[#E8E8E8]"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-14 items-center">
          {/* Dark Floating Findings Panel */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.7 }}
            className="lg:col-span-7 order-2 lg:order-1"
          >
            <div className="rounded-3xl bg-[#090909] p-7 sm:p-10 text-white shadow-[0_30px_70px_rgba(0,0,0,0.18)]">
              <div className="flex items-center justify-between border-b border-white/10 pb-5 mb-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.14em] text-white/50">
                    Cross-Document Reconciliation
                  </p>
                  <p className="mt-1 text-lg font-semibold">
                    3 Active Findings Flagged
                  </p>
                </div>
                <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/80">
                  Evidence-backed
                </span>
              </div>

              <div className="space-y-3.5">
                <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-4">
                  <div className="flex items-center gap-3.5">
                    <AlertTriangle className="h-4 w-4 text-red-400 shrink-0" />
                    <span className="text-sm font-medium">
                      Insurance nominee not found
                    </span>
                  </div>
                  <span className="rounded-full bg-red-500/15 px-3 py-1 text-xs font-medium text-red-400">
                    High
                  </span>
                </div>

                <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-4">
                  <div className="flex items-center gap-3.5">
                    <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                    <span className="text-sm font-medium">
                      Additional bank account in AIS
                    </span>
                  </div>
                  <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400">
                    Medium
                  </span>
                </div>

                <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-4">
                  <div className="flex items-center gap-3.5">
                    <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                    <span className="text-sm font-medium">
                      Recurring subscriptions detected
                    </span>
                  </div>
                  <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400">
                    Medium
                  </span>
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6 }}
            className="lg:col-span-5 order-1 lg:order-2"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#777777]">
              02 / Risk &amp; Blindspot Detection
            </p>
            <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-[-0.03em] leading-[1.1]">
              Discover hidden risks.
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[#777777] leading-relaxed">
              Our AI cross-checks your documents to find forgotten accounts, missing nominees, recurring leaks and more.
            </p>
            <div className="mt-8">
              <Link
                href="/login?demo=1"
                className="inline-flex items-center gap-2 rounded-full border border-[#111111] px-6 py-3 text-sm font-medium text-[#111111] hover:bg-[#111111] hover:text-white transition-colors"
              >
                See a Sample
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* SECTION 3 – Take Action and Stay Covered */}
      <section
        id="features"
        className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32 border-b border-[#E8E8E8]"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-14 items-center">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.6 }}
            className="lg:col-span-5"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#777777]">
              03 / Guided Resolution
            </p>
            <h2 className="mt-4 text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-[-0.03em] leading-[1.1]">
              Take action and stay covered.
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[#777777] leading-relaxed">
              Get clear, personalised next steps to fix gaps, update nominees and optimise your finances.
            </p>
            <div className="mt-8">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-[#090909] px-6 py-3 text-sm font-medium text-white hover:bg-neutral-800 transition-colors"
              >
                Start Now
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </div>
          </motion.div>

          {/* Floating Action Plan Card + Minimal Black Financial Card */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.7 }}
            className="lg:col-span-7"
          >
            <div className="relative rounded-3xl bg-[#F7F7F7] border border-[#E8E8E8] p-7 sm:p-10">
              {/* Minimal Black Financial Card */}
              <div className="mb-6 rounded-2xl bg-[#090909] text-white p-6 shadow-[0_18px_40px_rgba(0,0,0,0.16)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.16em] text-white/50">
                    ArthaLens Action Plan
                  </p>
                  <p className="mt-1 text-xl font-semibold">
                    {tasks.filter((t) => t.done).length} of {tasks.length} Steps Verified
                  </p>
                </div>
                <div className="text-left sm:text-right">
                  <p className="text-xs text-white/60">Projected Score</p>
                  <p className="text-2xl font-semibold tabular-nums">
                    {72 + tasks.filter((t) => t.done).length * 8}/100
                  </p>
                </div>
              </div>

              {/* Interactive Checklist */}
              <div className="space-y-3">
                {tasks.map((task) => (
                  <button
                    key={task.id}
                    type="button"
                    onClick={() => toggleTask(task.id)}
                    className="w-full flex items-center justify-between rounded-2xl border border-[#E8E8E8] bg-white px-5 py-4 text-left hover:border-[#111111]/40 transition-colors"
                  >
                    <div className="flex items-center gap-3.5">
                      <span
                        className={`flex h-5 w-5 items-center justify-center rounded-md border transition-colors ${
                          task.done
                            ? "bg-[#090909] border-[#090909] text-white"
                            : "border-[#CCCCCC] bg-white"
                        }`}
                      >
                        {task.done && <Check className="h-3.5 w-3.5" />}
                      </span>
                      <span
                        className={`text-sm font-medium ${
                          task.done ? "line-through text-[#777777]" : "text-[#111111]"
                        }`}
                      >
                        {task.label}
                      </span>
                    </div>
                    <span className="text-xs font-medium text-[#777777]">
                      {task.done ? "Completed" : "Action"}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* SECURITY SECTION */}
      <section id="security" className="mx-auto max-w-7xl px-6 py-24 lg:px-10">
        <div className="rounded-3xl bg-[#090909] text-white p-10 sm:p-14 lg:p-16">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/50">
              Security &amp; Evidence Integrity
            </p>
            <h2 className="mt-4 text-3xl sm:text-4xl font-semibold tracking-[-0.02em]">
              Zero assumptions. Every insight is backed by your documents.
            </h2>
          </div>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
              <Shield className="h-5 w-5 text-white mb-4" />
              <h3 className="text-base font-semibold">Strict Evidence Trail</h3>
              <p className="mt-2 text-sm text-white/65 leading-relaxed">
                Every finding cites the exact document name, page number, and extracted text snippet.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
              <Lock className="h-5 w-5 text-white mb-4" />
              <h3 className="text-base font-semibold">Read-Only Intelligence</h3>
              <p className="mt-2 text-sm text-white/65 leading-relaxed">
                ArthaLens never modifies your financial records or submits forms automatically without your action.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
              <Eye className="h-5 w-5 text-white mb-4" />
              <h3 className="text-base font-semibold">Verified Nominee Rules</h3>
              <p className="mt-2 text-sm text-white/65 leading-relaxed">
                Nominees are only marked GREEN when confirmed directly in an uploaded document or verified evidence.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-[#E8E8E8] bg-[#F7F7F7]">
        <div className="mx-auto max-w-7xl px-6 py-12 lg:px-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div>
            <ArthaLogo variant="light" />
            <p className="mt-3 text-sm text-[#777777]">
              Other apps track what you tell them. ArthaLens finds what you forgot.
            </p>
          </div>
          <div className="flex items-center gap-6 text-sm text-[#777777]">
            <Link href="/login" className="hover:text-[#111111]">
              Login
            </Link>
            <Link href="/signup" className="hover:text-[#111111]">
              Sign Up
            </Link>
            <Link href="/login?demo=1" className="hover:text-[#111111]">
              Live Demo
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
