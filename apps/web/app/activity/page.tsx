"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

type ActivityItem = {
  id: string;
  kind: string;
  timestamp: string;
  title: string;
  subtitle: string | null;
  detail: string | null;
  status: string | null;
  source: string | null;
  development_id: string | null;
  development_name: string | null;
  source_url: string | null;
  file_path: string | null;
};

type ActivityFeedResponse = {
  items: ActivityItem[];
  summary: {
    total_items: number;
    refresh_job_count: number;
    source_snapshot_count: number;
    watchlist_update_count: number;
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const KIND_OPTIONS = ["all", "refresh_job", "source_snapshot", "watchlist_update"];

function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(parsed);
}

function kindLabel(value: string): string {
  switch (value) {
    case "refresh_job":
      return "Refresh Job";
    case "source_snapshot":
      return "Source Snapshot";
    case "watchlist_update":
      return "Watchlist Update";
    default:
      return value;
  }
}

function ActivityPageContent() {
  const searchParams = useSearchParams();
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [kind, setKind] = useState(searchParams.get("kind") ?? "all");
  const [source, setSource] = useState(searchParams.get("source") ?? "all");
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ActivityFeedResponse["summary"] | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadActivity() {
      try {
        const params = new URLSearchParams({
          lang: "zh-Hant",
          limit: "40",
        });
        const developmentId = searchParams.get("development_id");
        if (kind !== "all") {
          params.set("kind", kind);
        }
        if (source !== "all") {
          params.set("source", source);
        }
        if (developmentId) {
          params.set("development_id", developmentId);
        }
        const response = await fetch(`${API_BASE}/api/v1/activity/recent?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`activity HTTP ${response.status}`);
        }
        const payload = (await response.json()) as ActivityFeedResponse;
        if (!cancelled) {
          setItems(payload.items);
          setSummary(payload.summary);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    void loadActivity();
    return () => {
      cancelled = true;
    };
  }, [kind, searchParams, source]);

  const sources = useMemo(() => {
    return Array.from(new Set(items.map((item) => item.source).filter((item): item is string => Boolean(item)))).sort();
  }, [items]);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Phase 2</p>
        <h1>Recent Activity</h1>
        <p className="lead">
          Review what changed recently across refresh runs, source snapshots, and watchlist updates
          before drilling into the map, detail pages, or system monitor.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/map">Open map</Link>
          <Link href="/watchlist">Open watchlist</Link>
          <Link href="/system">Open system</Link>
        </div>
      </section>

      <section className="activity-layout">
        <aside className="panel filter-panel">
          <h2>Feed Filter</h2>
          <label className="field">
            <span>Kind</span>
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {KIND_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Source</span>
            <select value={source} onChange={(event) => setSource(event.target.value)}>
              <option value="all">all</option>
              {sources.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          {searchParams.get("development_id") ? (
            <p className="muted">Filtered to development {searchParams.get("development_id")}</p>
          ) : null}
          <dl className="kv-list compact-kv-list">
            <div>
              <dt>Refresh Jobs</dt>
              <dd>{summary?.refresh_job_count ?? 0}</dd>
            </div>
            <div>
              <dt>Snapshots</dt>
              <dd>{summary?.source_snapshot_count ?? 0}</dd>
            </div>
            <div>
              <dt>Watchlist</dt>
              <dd>{summary?.watchlist_update_count ?? 0}</dd>
            </div>
            <div>
              <dt>Visible</dt>
              <dd>{summary?.total_items ?? items.length}</dd>
            </div>
          </dl>
          {error ? <p className="muted">Activity unavailable: {error}</p> : null}
        </aside>

        <section className="panel detail-span-2">
          <h2>Timeline</h2>
          {items.length > 0 ? (
            <ul className="activity-list">
              {items.map((item) => (
                <li key={item.id} className="activity-item">
                  <div className="activity-item-head">
                    <span className={`activity-badge activity-badge-${item.kind}`}>
                      {kindLabel(item.kind)}
                    </span>
                    <span className="activity-time">{formatDateTime(item.timestamp)}</span>
                  </div>
                  <strong>{item.title}</strong>
                  {item.subtitle ? <span>{item.subtitle}</span> : null}
                  {item.detail ? <p className="activity-detail">{item.detail}</p> : null}
                  <div className="hero-actions">
                    {item.development_id ? (
                      <Link href={`/developments/${item.development_id}`}>Open detail</Link>
                    ) : null}
                    {item.development_id ? (
                      <Link href={`/map?selected=${item.development_id}`}>Open in map</Link>
                    ) : null}
                    {item.source_url ? (
                      <a href={item.source_url} target="_blank" rel="noreferrer">
                        Open source
                      </a>
                    ) : null}
                    {item.file_path ? <code>{item.file_path}</code> : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No activity matched the current filter.</p>
          )}
        </section>
      </section>
    </main>
  );
}

export default function ActivityPage() {
  return (
    <Suspense fallback={<main className="page-shell"><p className="muted">Loading activity...</p></main>}>
      <ActivityPageContent />
    </Suspense>
  );
}
