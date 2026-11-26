"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
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
  Bell,
  ChevronDown,
  RefreshCw,
} from "lucide-react";
import { ArthaLogo } from "./ArthaLogo";
import { api, clearAuthSession, getStoredToken, getStoredUser } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import { FindingItem, User } from "@/lib/types";

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
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [alerts, setAlerts] = useState<FindingItem[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState(false);
  const [istClock, setIstClock] = useState<string>("");
  const notifRef = useRef<HTMLDivElement | null>(null);
  const profileRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const syncClock = () => setIstClock(formatISTWithTz(new Date()));
    syncClock();
    const timer = setInterval(syncClock, 30000);
    return () => clearInterval(timer);
  }, []);

  const loadNotifications = useCallback(async () => {
    setLoadingAlerts(true);
    try {
      const items = await api.listFindings();
      setAlerts(items.filter((f) => f.status === "Open" || f.status === "In Review"));
    } catch {
      // ignore background notification poll failure
    } finally {
      setLoadingAlerts(false);
    }
  }, []);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setUser(getStoredUser());
    loadNotifications();
  }, [router, loadNotifications]);

  useEffect(() => {
    const onOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setNotifOpen(false);
        setProfileOpen(false);
      }
    };
    document.addEventListener("mousedown", onOutside);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onOutside);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

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

          <div className="flex items-center gap-2.5 sm:gap-3">
            {istClock && (
              <span className="hidden xl:inline-flex items-center rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#555555] tabular-nums">
                {istClock}
              </span>
            )}
            {hasDemoData && (
              <span className="hidden md:inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#777777]">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                Includes Synthetic Demo Data
              </span>
            )}

            {/* Notifications Dropdown */}
            <div className="relative" ref={notifRef}>
              <button
                type="button"
                onClick={() => {
                  setProfileOpen(false);
                  setNotifOpen((o) => !o);
                }}
                aria-label="Open notifications"
                className="relative rounded-full border border-[#E8E8E8] bg-white p-2 text-[#111111] hover:border-[#090909] transition-colors"
              >
                <Bell className="h-4 w-4" />
                {alerts.length > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#090909] px-1 text-[10px] font-semibold text-white tabular-nums">
                    {alerts.length}
                  </span>
                )}
              </button>

              {notifOpen && (
                <div className="absolute right-0 top-11 z-40 w-80 rounded-2xl border border-[#E8E8E8] bg-white p-3 shadow-2xl">
                  <div className="flex items-center justify-between border-b border-[#E8E8E8] pb-2 mb-2">
                    <span className="text-xs font-semibold text-[#111111]">
                      Notifications ({alerts.length})
                    </span>
                    <button
                      type="button"
                      onClick={loadNotifications}
                      disabled={loadingAlerts}
                      className="inline-flex items-center gap-1 text-[11px] text-[#777777] hover:text-[#111111]"
                    >
                      <RefreshCw className={`h-3 w-3 ${loadingAlerts ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                  </div>
                  {alerts.length === 0 ? (
                    <p className="py-4 text-center text-xs text-[#777777]">
                      All caught up — no open blindspots.
                    </p>
                  ) : (
                    <div className="max-h-64 overflow-y-auto space-y-1.5">
                      {alerts.slice(0, 6).map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => {
                            setNotifOpen(false);
                            router.push(`/dashboard/findings?findingId=${encodeURIComponent(item.id)}`);
                          }}
                          className="w-full text-left rounded-xl border border-[#E8E8E8]/80 bg-[#F7F7F7] px-3 py-2 hover:border-[#090909] transition-colors"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-[#777777]">
                              {item.severity} • {item.status}
                            </span>
                            <span className="text-[10px] text-[#777777]">
                              p.{item.evidence?.page_number ?? 1}
                            </span>
                          </div>
                          <p className="mt-0.5 text-xs font-medium text-[#111111] truncate">
                            {item.title}
                          </p>
                          {item.created_at && (
                            <p className="mt-0.5 text-[10px] text-[#777777]">
                              {formatISTWithTz(item.created_at)}
                            </p>
                          )}
                        </button>
                      ))}
                      <Link
                        href="/dashboard/findings"
                        onClick={() => setNotifOpen(false)}
                        className="block pt-1.5 text-center text-[11px] font-medium text-[#111111] hover:underline"
                      >
                        View all findings
                      </Link>
                    </div>
                  )}
                </div>
              )}
            </div>

            <Link
              href="/dashboard/documents"
              className="rounded-full bg-[#090909] px-4 py-2 text-xs font-medium text-white hover:bg-neutral-800 transition-colors"
            >
              Upload PDF
            </Link>

            {/* Profile Dropdown */}
            <div className="relative" ref={profileRef}>
              <button
                type="button"
                onClick={() => {
                  setNotifOpen(false);
                  setProfileOpen((o) => !o);
                }}
                aria-label="Open profile menu"
                className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-2.5 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909] transition-colors"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#090909] text-[10px] font-semibold text-white">
                  {(user?.name || "A").slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden sm:inline max-w-[100px] truncate">
                  {user?.name?.split(" ")[0] || "Account"}
                </span>
                <ChevronDown className="h-3 w-3 text-[#777777]" />
              </button>

              {profileOpen && (
                <div className="absolute right-0 top-11 z-40 w-56 rounded-2xl border border-[#E8E8E8] bg-white p-2 shadow-2xl">
                  {user && (
                    <div className="border-b border-[#E8E8E8] px-3 py-2 mb-1">
                      <p className="text-xs font-semibold text-[#111111] truncate">{user.name}</p>
                      <p className="text-[11px] text-[#777777] truncate">{user.email}</p>
                    </div>
                  )}
                  <Link
                    href="/dashboard/settings"
                    onClick={() => setProfileOpen(false)}
                    className="block rounded-xl px-3 py-2 text-xs text-[#111111] hover:bg-[#F7F7F7]"
                  >
                    Account Settings
                  </Link>
                  <Link
                    href="/dashboard/documents"
                    onClick={() => setProfileOpen(false)}
                    className="block rounded-xl px-3 py-2 text-xs text-[#111111] hover:bg-[#F7F7F7]"
                  >
                    Manage Documents
                  </Link>
                  <Link
                    href="/dashboard/chat"
                    onClick={() => setProfileOpen(false)}
                    className="block rounded-xl px-3 py-2 text-xs text-[#111111] hover:bg-[#F7F7F7]"
                  >
                    Ask ArthaLens
                  </Link>
                  <div className="my-1 h-px bg-[#E8E8E8]" />
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 p-5 sm:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
