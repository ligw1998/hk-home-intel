"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type LaunchWatchItem = {
  id: string;
  source: string;
  project_name: string;
  project_name_en: string | null;
  display_name: string;
  district: string | null;
  region: string | null;
  expected_launch_window: string | null;
  launch_stage: string;
  official_site_url: string | null;
  source_url: string | null;
  srpe_url: string | null;
  linked_development_id: string | null;
  linked_development_name: string | null;
  note: string | null;
  tags: string[];
  is_active: boolean;
  coordinate_mode: string;
  updated_at: string;
};

type LaunchWatchResponse = {
  items: LaunchWatchItem[];
  total: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const STAGES = ["all", "launch_watch", "watch-selling", "selling", "watching"];

function formatUpdatedAt(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function stageLabel(value: string): string {
  if (value === "launch_watch") {
    return "Launch Watch";
  }
  if (value === "watch-selling") {
    return "Watch Selling";
  }
  if (value === "selling") {
    return "Selling";
  }
  return value;
}

export default function LaunchWatchPage() {
  const [items, setItems] = useState<LaunchWatchItem[]>([]);
  const [filterStage, setFilterStage] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadItems() {
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE}/api/v1/launch-watch`);
        if (!response.ok) {
          throw new Error(`launch-watch HTTP ${response.status}`);
        }
        const payload = (await response.json()) as LaunchWatchResponse;
        if (!cancelled) {
          setItems(payload.items);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadItems();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    return items.filter((item) => {
      if (filterStage !== "all" && item.launch_stage !== filterStage) {
        return false;
      }
      if (!search.trim()) {
        return true;
      }
      const haystack = [
        item.display_name,
        item.project_name,
        item.project_name_en,
        item.linked_development_name,
        item.district,
        item.region,
        item.expected_launch_window,
        item.launch_stage,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(search.trim().toLowerCase());
    });
  }, [filterStage, items, search]);

  const stageCounts = useMemo(() => {
    return {
      total: items.length,
      watch: items.filter((item) => item.launch_stage === "launch_watch").length,
      selling: items.filter((item) => item.launch_stage === "selling" || item.launch_stage === "watch-selling").length,
    };
  }, [items]);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Launch Watch</p>
        <h1>Upcoming New Launch Watch</h1>
        <p className="lead">
          Track near-term first-hand projects before they fully settle into the regular development and
          listing pipelines. This page is for projects that are still in launch-watch, draw-lot, or
          early selling phases.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/map">Open map</Link>
          <Link href="/shortlist">Open shortlist</Link>
          <Link href="/watchlist">Open watchlist</Link>
          <Link href="/system">Open system monitor</Link>
        </div>
        <div className="dashboard-metric-row">
          <div className="dashboard-metric">
            <strong>{stageCounts.total}</strong>
            <span>Tracked projects</span>
          </div>
          <div className="dashboard-metric">
            <strong>{stageCounts.watch}</strong>
            <span>Launch watch</span>
          </div>
          <div className="dashboard-metric">
            <strong>{stageCounts.selling}</strong>
            <span>Already selling / watch selling</span>
          </div>
        </div>
      </section>

      <section className="launch-watch-layout">
        <aside className="panel filter-panel">
          <h2>Filter</h2>
          <label className="field">
            <span>Stage</span>
            <select value={filterStage} onChange={(event) => setFilterStage(event.target.value)}>
              {STAGES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Search</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Project / district / region"
            />
          </label>
          <p className="muted">
            This pool is intentionally earlier and noisier than normal development coverage. It is meant
            to answer which projects need closer tracking before SRPE and commercial listing coverage are complete.
          </p>
          {error ? <p className="muted">Launch watch error: {error}</p> : null}
        </aside>

        <section className="launch-watch-grid">
          {loading ? <p className="muted">Loading launch-watch projects...</p> : null}
          {!loading && filtered.length === 0 ? (
            <article className="panel">
              <h2>No launch-watch projects</h2>
              <p className="muted">
                Sync `configs/launch_watch_projects.toml` first, or widen the current filter.
              </p>
            </article>
          ) : null}
          {filtered.map((item) => (
            <article key={item.id} className="panel launch-watch-card">
              <div className="launch-watch-card-head">
                <div>
                  <h2>{item.display_name}</h2>
                  <p className="muted">
                    {[item.district, item.region].filter(Boolean).join(" / ") || "Unknown district"}{" "}
                    {item.expected_launch_window ? `· ${item.expected_launch_window}` : ""}
                  </p>
                </div>
                <span className={`launch-watch-badge launch-watch-badge-${item.launch_stage.replace(/[^a-z]/g, "-")}`}>
                  {stageLabel(item.launch_stage)}
                </span>
              </div>
              <div className="development-summary-grid">
                <div className="development-summary-card">
                  <strong>Source</strong>
                  <span>{item.source}</span>
                </div>
                <div className="development-summary-card">
                  <strong>Linked Development</strong>
                  <span>{item.linked_development_name ?? "Not linked yet"}</span>
                </div>
              </div>
              {item.note ? <p className="muted">{item.note}</p> : null}
              {item.tags.length > 0 ? (
                <div className="launch-watch-tag-row">
                  {item.tags.map((tag, index) => (
                    <span key={`${item.id}-${tag}-${index}`} className="workflow-chip">
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}
              <div className="hero-actions">
                {item.official_site_url ? (
                  <a href={item.official_site_url} target="_blank" rel="noreferrer">
                    Official site
                  </a>
                ) : null}
                {item.source_url ? (
                  <a href={item.source_url} target="_blank" rel="noreferrer">
                    Source signal
                  </a>
                ) : null}
                {item.srpe_url ? (
                  <a href={item.srpe_url} target="_blank" rel="noreferrer">
                    SRPE / SRPA
                  </a>
                ) : null}
                {item.linked_development_id ? (
                  <Link href={`/developments/${item.linked_development_id}`}>Open development</Link>
                ) : null}
              </div>
              <p className="muted">Updated {formatUpdatedAt(item.updated_at)}</p>
              {item.coordinate_mode === "approximate" ? (
                <p className="muted">Map position is approximate.</p>
              ) : null}
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
