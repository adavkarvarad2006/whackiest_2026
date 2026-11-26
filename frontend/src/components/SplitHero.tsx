"use client";

import React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight, AlertCircle, TrendingUp, ShieldCheck } from "lucide-react";

export function SplitHero() {
  return (
    <section className="relative w-full overflow-hidden border-b border-[#E8E8E8]">
      <div className="grid grid-cols-1 lg:grid-cols-2 min-h-[calc(100vh-4rem)]">
        {/* LEFT SIDE: Black Background */}
        <div className="bg-[#090909] text-white flex flex-col justify-between px-8 py-16 sm:px-14 lg:px-16 xl:px-24 lg:py-24">
          <div className="max-w-xl my-auto">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-white/75 mb-8"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-white" />
              AI Financial Intelligence
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.08 }}
              className="text-4xl sm:text-5xl xl:text-[58px] font-semibold tracking-[-0.03em] leading-[1.06] text-white"
            >
              See the full picture of your finances.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.16 }}
              className="mt-6 text-base sm:text-lg text-white/65 leading-relaxed max-w-md"
            >
              Unify your financial documents, uncover blindspots, and take the right action.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.24 }}
              className="mt-10 flex flex-wrap items-center gap-4"
            >
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-full bg-white px-7 py-3.5 text-sm font-medium text-[#090909] hover:bg-neutral-200 transition-colors"
              >
                Get Started
                <ArrowUpRight className="h-4 w-4" />
              </Link>
              <Link
                href="/login?demo=1"
                className="inline-flex items-center gap-2 rounded-full border border-white/25 px-7 py-3.5 text-sm font-medium text-white hover:bg-white/10 transition-colors"
              >
                Explore Platform
              </Link>
            </motion.div>
          </div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.7, delay: 0.35 }}
            className="mt-14 text-xs tracking-wide text-white/45"
          >
            &ldquo;Other apps track what you tell them. ArthaLens finds what you forgot.&rdquo;
          </motion.p>
        </div>

        {/* RIGHT SIDE: White Background with Abstract 3D Organic Black Shape + Floating Widgets */}
        <div className="relative bg-white flex items-center justify-center px-6 py-16 sm:px-12 lg:px-14 min-h-[540px] overflow-hidden">
          {/* Subtle architectural grid backdrop */}
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.35]"
            style={{
              backgroundImage:
                "radial-gradient(#d4d4d4 1px, transparent 1px)",
              backgroundSize: "24px 24px",
            }}
          />

          {/* Abstract Black 3D Organic Sculptural Shape */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.85, ease: "easeOut" }}
            className="relative w-full max-w-[480px] aspect-square flex items-center justify-center"
          >
            <svg
              viewBox="0 0 500 500"
              className="w-[88%] h-[88%] drop-shadow-[0_36px_64px_rgba(0,0,0,0.22)]"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <defs>
                <radialGradient id="sculptGrad1" cx="35%" cy="30%" r="70%">
                  <stop offset="0%" stopColor="#3a3a3a" />
                  <stop offset="42%" stopColor="#141414" />
                  <stop offset="100%" stopColor="#050505" />
                </radialGradient>
                <linearGradient id="sculptRim" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.28" />
                  <stop offset="50%" stopColor="#ffffff" stopOpacity="0.02" />
                  <stop offset="100%" stopColor="#000000" stopOpacity="0.6" />
                </linearGradient>
              </defs>
              {/* Primary organic 3D torus-knot inspired form */}
              <path
                d="M250,48 C345,42 435,108 450,204 C465,302 405,405 308,438 C212,470 105,428 64,336 C22,242 58,130 142,78 C176,57 212,50 250,48 Z"
                fill="url(#sculptGrad1)"
              />
              <path
                d="M258,118 C322,118 378,168 380,234 C382,300 326,356 260,360 C194,364 134,312 132,246 C130,180 186,118 258,118 Z"
                fill="#ffffff"
              />
              <path
                d="M250,48 C345,42 435,108 450,204 C465,302 405,405 308,438 C212,470 105,428 64,336 C22,242 58,130 142,78 C176,57 212,50 250,48 Z"
                fill="none"
                stroke="url(#sculptRim)"
                strokeWidth="3"
              />
              {/* Inner floating obsidian sphere */}
              <circle cx="256" cy="240" r="54" fill="url(#sculptGrad1)" />
            </svg>

            {/* Floating Widget 1: Total Assets Mapped */}
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: [0, -6, 0] }}
              transition={{
                opacity: { duration: 0.6, delay: 0.2 },
                y: { duration: 5, repeat: Infinity, ease: "easeInOut" },
              }}
              className="absolute -top-2 left-0 sm:-left-6 rounded-2xl border border-[#E8E8E8] bg-white/95 backdrop-blur-sm px-5 py-4 shadow-[0_20px_45px_rgba(0,0,0,0.08)]"
            >
              <p className="text-[11px] font-medium uppercase tracking-wider text-[#777777]">
                Total Assets Mapped
              </p>
              <p className="mt-1 text-2xl font-semibold tracking-tight text-[#111111] tabular-nums">
                ₹3,84,575
              </p>
            </motion.div>

            {/* Floating Widget 2: 3 Blindspots Found */}
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: [0, 6, 0] }}
              transition={{
                opacity: { duration: 0.6, delay: 0.32 },
                y: { duration: 5.5, repeat: Infinity, ease: "easeInOut" },
              }}
              className="absolute top-12 -right-2 sm:-right-6 rounded-2xl border border-[#E8E8E8] bg-[#090909] px-4 py-3.5 text-white shadow-[0_20px_45px_rgba(0,0,0,0.18)]"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-500/20 text-amber-400">
                  <AlertCircle className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-xs font-semibold">3 Blindspots Found</p>
                  <p className="text-[11px] text-white/60">Nominee &amp; AIS gaps</p>
                </div>
              </div>
            </motion.div>

            {/* Floating Widget 3: Monthly Financial Flow */}
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: [0, -5, 0] }}
              transition={{
                opacity: { duration: 0.6, delay: 0.42 },
                y: { duration: 6, repeat: Infinity, ease: "easeInOut" },
              }}
              className="absolute bottom-8 -left-2 sm:-left-8 rounded-2xl border border-[#E8E8E8] bg-white/95 backdrop-blur-sm px-5 py-3.5 shadow-[0_20px_45px_rgba(0,0,0,0.08)]"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#F7F7F7] border border-[#E8E8E8]">
                  <TrendingUp className="h-4 w-4 text-[#111111]" />
                </div>
                <div>
                  <p className="text-[11px] font-medium text-[#777777]">
                    Monthly Financial Flow
                  </p>
                  <p className="text-base font-semibold text-[#111111] tabular-nums">
                    ₹1,42,000
                  </p>
                </div>
              </div>
            </motion.div>

            {/* Floating Widget 4: ArthaLens Score */}
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: [0, 5, 0] }}
              transition={{
                opacity: { duration: 0.6, delay: 0.52 },
                y: { duration: 4.8, repeat: Infinity, ease: "easeInOut" },
              }}
              className="absolute -bottom-3 right-0 sm:-right-4 rounded-2xl border border-[#E8E8E8] bg-white px-5 py-3.5 shadow-[0_20px_45px_rgba(0,0,0,0.09)]"
            >
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-5 w-5 text-[#111111]" />
                <div>
                  <p className="text-[11px] font-medium text-[#777777]">
                    ArthaLens Score
                  </p>
                  <p className="text-lg font-semibold text-[#111111] tabular-nums">
                    72<span className="text-xs font-normal text-[#777777]">/100</span>
                  </p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
