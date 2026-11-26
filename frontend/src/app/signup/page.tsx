"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { ArthaLogo } from "@/components/ArthaLogo";
import { api } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.signup(name, email, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-white">
      <div className="hidden lg:flex flex-col justify-between bg-[#090909] text-white p-14">
        <Link href="/">
          <ArthaLogo variant="dark" />
        </Link>
        <div className="max-w-md">
          <p className="text-xs uppercase tracking-[0.16em] text-white/50">
            Start Your Audit
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight leading-tight">
            See the full picture of your finances.
          </h1>
          <p className="mt-4 text-sm text-white/60 leading-relaxed">
            Create your private ArthaLens workspace. New accounts start with labeled synthetic demo documents so you can test every workflow immediately, plus upload your own PDFs.
          </p>
        </div>
        <p className="text-xs text-white/40">
          Bank statements • AIS • Form 16 • Insurance • Loans • FDs
        </p>
      </div>

      <div className="flex flex-col justify-center px-6 py-12 sm:px-14 lg:px-20">
        <div className="mx-auto w-full max-w-md">
          <div className="lg:hidden mb-8">
            <Link href="/">
              <ArthaLogo variant="light" />
            </Link>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-[#111111]">
            Create your account
          </h2>
          <p className="mt-2 text-sm text-[#777777]">
            Begin mapping assets, nominees, and hidden financial leaks.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#111111] mb-1.5">
                Full Name
              </label>
              <input
                type="text"
                required
                minLength={2}
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-xl border border-[#E8E8E8] bg-white px-4 py-2.5 text-sm text-[#111111] focus:border-[#090909] focus:outline-none"
                placeholder="Aarav Mehta"
              />
            </div>

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
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-[#E8E8E8] bg-white px-4 py-2.5 text-sm text-[#111111] focus:border-[#090909] focus:outline-none"
                placeholder="Minimum 6 characters"
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
              {loading ? "Creating workspace..." : "Get Started"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-[#777777]">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-[#111111] underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
