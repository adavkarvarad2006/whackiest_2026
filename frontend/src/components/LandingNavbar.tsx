"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { ArthaLogo } from "./ArthaLogo";

export function LandingNavbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full bg-[#090909]/95 backdrop-blur-md border-b border-white/10">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 lg:px-10">
        <Link href="/" className="focus:outline-none">
          <ArthaLogo variant="dark" />
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-[13px] font-medium text-white/75">
          <a href="#product" className="hover:text-white transition-colors">
            Product
          </a>
          <a href="#how-it-works" className="hover:text-white transition-colors">
            How It Works
          </a>
          <a href="#features" className="hover:text-white transition-colors">
            Features
          </a>
          <a href="#security" className="hover:text-white transition-colors">
            Security
          </a>
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <Link
            href="/login"
            className="px-4 py-2 text-[13px] font-medium text-white/85 hover:text-white transition-colors"
          >
            Login
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-white px-5 py-2 text-[13px] font-medium text-[#090909] hover:bg-neutral-200 transition-colors"
          >
            Sign Up
          </Link>
        </div>

        <button
          type="button"
          onClick={() => setMobileOpen((prev) => !prev)}
          className="md:hidden inline-flex items-center justify-center rounded-lg p-2 text-white/80 hover:text-white hover:bg-white/10"
          aria-label="Toggle navigation menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t border-white/10 bg-[#090909] px-6 py-5 space-y-4">
          <div className="flex flex-col space-y-3 text-sm text-white/80">
            <a href="#product" onClick={() => setMobileOpen(false)} className="hover:text-white">
              Product
            </a>
            <a href="#how-it-works" onClick={() => setMobileOpen(false)} className="hover:text-white">
              How It Works
            </a>
            <a href="#features" onClick={() => setMobileOpen(false)} className="hover:text-white">
              Features
            </a>
            <a href="#security" onClick={() => setMobileOpen(false)} className="hover:text-white">
              Security
            </a>
          </div>
          <div className="flex items-center gap-3 pt-2 border-t border-white/10">
            <Link
              href="/login"
              className="flex-1 text-center rounded-full border border-white/25 py-2.5 text-sm font-medium text-white"
            >
              Login
            </Link>
            <Link
              href="/signup"
              className="flex-1 text-center rounded-full bg-white py-2.5 text-sm font-medium text-[#090909]"
            >
              Sign Up
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
