"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Sparkles } from "lucide-react";
import { ArthaLogo } from "@/components/ArthaLogo";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("demo@arthalens.ai");
  const [password, setPassword] = useState("arthalens123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.login(email, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setError("");
    setLoading(true);
    try {
      await api.demoLogin();
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Demo login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-white">
      {/* Left black editorial panel */}
      <div className="hidden lg:flex flex-col justify-between bg-[#090909] text-white p-14">
        <Link href="/">
          <ArthaLogo variant="dark" />
        </Link>
        <div className="max-w-md">
          <p className="text-xs uppercase tracking-[0.16em] text-white/50">
            ArthaLens Intelligence
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight leading-tight">
            Other apps track what you tell them. ArthaLens finds what you forgot.
          </h1>
          <p className="mt-4 text-sm text-white/60 leading-relaxed">
            Sign in to inspect your unified financial map, nominee coverage rings, and evidence-backed findings.
          </p>
        </div>
        <p className="text-xs text-white/40">
          Read-only document intelligence • Zero automated record changes
        </p>
      </div>

      {/* Right login form */}
      <div className="flex flex-col justify-center px-6 py-12 sm:px-14 lg:px-20">
        <div className="mx-auto w-full max-w-md">
          <div className="lg:hidden mb-8">
            <Link href="/">
              <ArthaLogo variant="light" />
            </Link>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-[#111111]">
            Welcome back
          </h2>
          <p className="mt-2 text-sm text-[#777777]">
            Sign in to your ArthaLens workspace or explore with synthetic demo data.
          </p>

          <button
            type="button"
            onClick={handleDemo}
            disabled={loading}
            className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-xl border border-[#111111] bg-[#F7F7F7] px-4 py-3 text-sm font-medium text-[#111111] hover:bg-[#EFEFEF] transition-colors disabled:opacity-50"
          >
            <Sparkles className="h-4 w-4" />
            Explore Live Demo Account (Synthetic Data)
          </button>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-[#E8E8E8]" />
            <span className="text-xs text-[#777777]">or sign in with email</span>
            <div className="h-px flex-1 bg-[#E8E8E8]" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#111111] mb-1.5">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-[#E8E8E8] bg-white px-4 py-2.5 text-sm text-[#111111] focus:border-[#090909] focus:outline-none"
                placeholder="you@domain.com"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-[#111111] mb-1.5">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-[#E8E8E8] bg-white px-4 py-2.5 text-sm text-[#111111] focus:border-[#090909] focus:outline-none"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-[#090909] px-6 py-3 text-sm font-medium text-white hover:bg-neutral-800 transition-colors disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign In"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-[#777777]">
            New to ArthaLens?{" "}
            <Link href="/signup" className="font-medium text-[#111111] underline underline-offset-4">
              Create an account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
