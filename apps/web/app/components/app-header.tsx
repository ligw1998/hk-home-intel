"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

type SystemOverview = {
  readiness_status: string;
  attention_monitor_count: number;
  latest_job: {
    status: string;
  } | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/shortlist", label: "Shortlist" },
  { href: "/map", label: "Map" },
  { href: "/listings", label: "Listings" },
  { href: "/compare", label: "Compare" },
  { href: "/launch-watch", label: "Launch Watch" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/activity", label: "Activity" },
  { href: "/system", label: "System" },
];

function readinessLabel(status: string | null): string {
  if (status === "ready") {
    return "Ready";
  }
  if (status === "attention") {
    return "Attention";
  }
  return "Loading";
}

export function AppHeader() {
  const pathname = usePathname();
  const [overview, setOverview] = useState<SystemOverview | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadOverview() {
      try {
        const response = await fetch(`${API_BASE}/api/v1/system/overview`);
        if (!response.ok) {
          throw new Error("overview unavailable");
        }
        const payload = (await response.json()) as SystemOverview;
        if (!cancelled) {
          setOverview(payload);
        }
      } catch {
        if (!cancelled) {
          setOverview(null);
        }
      }
    }

    void loadOverview();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link href="/" className="app-brand">
          HK Home Intel
        </Link>
        <nav className="app-nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? "app-nav-link app-nav-link-active" : "app-nav-link"}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <Link href="/system" className="app-status-pill">
          <strong>{readinessLabel(overview?.readiness_status ?? null)}</strong>
          <span>
            {overview
              ? `${overview.attention_monitor_count} attention / latest ${overview.latest_job?.status ?? "idle"}`
              : "system status"}
          </span>
        </Link>
      </div>
    </header>
  );
}
