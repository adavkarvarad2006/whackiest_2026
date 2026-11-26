"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Network,
  ShieldCheck,
  AlertTriangle,
  SearchCheck,
  CheckSquare,
  MessageSquare,
  Settings,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { ArthaLogo } from "./ArthaLogo";
import { clearAuthSession, getStoredToken, getStoredUser } from "@/lib/api";
import { User } from "@/lib/types";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Documents", href: "/dashboard/documents", icon: FileText },
  { label: "Financial Map", href: "/dashboard/financial-map", icon: Network },
  { label: "Nominee Coverage", href: "/dashboard/nominees", icon: ShieldCheck },
  { label: "Findings", href: "/dashboard/findings", icon: AlertTriangle },
  { label: "Evidence", href: "/dashboard/evidence", icon: SearchCheck },
  { label: "Actions", href: "/dashboard/actions", icon: CheckSquare },
  { label: "Ask ArthaLens", href: "/dashboard/chat", icon: MessageSquare },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

export function DashboardShell({
  children,
  title,
  subtitle,
  hasDemoData = false,
}: {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  hasDemoData?: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setUser(getStoredUser());
  }, [router]);

  const handleLogout = () => {
    clearAuthSession();
    router.push("/login");
  };

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between bg-[#090909] text-white px-4 py-6">
      <div>
        <div className="px-2 mb-8 flex items-center justify-between">
          <Link href="/">
            <ArthaLogo variant="dark" />
          </Link>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="lg:hidden rounded-lg p-1 text-white/70 hover:text-white"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-[13px] font-medium transition-colors ${
                  active
                    ? "bg-white text-[#090909]"
                    : "text-white/65 hover:bg-white/10 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="border-t border-white/10 pt-4 px-2">
        {user && (
          <div className="mb-3">
            <p className="text-xs font-medium text-white truncate">{user.name}</p>
            <p className="text-[11px] text-white/50 truncate">{user.email}</p>
          </div>
        )}
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-[#F7F7F7] text-[#111111]">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 sticky top-0 h-screen">
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10 w-64 h-full">{sidebarContent}</div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-30 border-b border-[#E8E8E8] bg-white/95 backdrop-blur-sm px-5 sm:px-8 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="lg:hidden rounded-lg border border-[#E8E8E8] p-2 text-[#111111]"
              aria-label="Open sidebar"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div>
              <h1 className="text-lg sm:text-xl font-semibold tracking-tight text-[#111111]">
                {title}
              </h1>
              {subtitle && (
                <p className="text-xs text-[#777777]">{subtitle}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {hasDemoData && (
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#777777]">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                Includes Synthetic Demo Data
              </span>
            )}
            <Link
              href="/dashboard/documents"
              className="rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800 transition-colors"
            >
              Upload PDF
            </Link>
          </div>
        </header>

        <main className="flex-1 p-5 sm:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
