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
  signal_bucket: string;
  signal_label: string;
  signal_rank: number;
  is_active: boolean;
  coordinate_mode: string;
  updated_at: string;
};

type LaunchWatchResponse = {
  items: LaunchWatchItem[];
  total: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const STAGES = ["all", "launch_watch", "watch_selling", "selling", "watching"];
const SIGNAL_BUCKETS = [
  "all",
  "landsd_pending",
  "landsd_issued",
  "recent_pricing",
  "recent_brochure",
  "srpe_active",
  "manual_watch",
  "other_watch",
];
const SIGNAL_BUCKET_DESCRIPTIONS: Record<string, string> = {
  landsd_pending: "Earliest official pre-sale pending signals.",
  landsd_issued: "Official consent-issued projects that are moving closer to sale.",
  recent_pricing: "Recent price list or sales arrangement activity on SRPE.",
  recent_brochure: "Recent brochure activity without stronger pricing signal yet.",
  srpe_active: "Still inside the official first-hand selling chain, but weaker than recent pricing.",
  manual_watch: "Manually seeded watch items and curated observations.",
  other_watch: "Residual watch items that do not fit the stronger official buckets.",
};

function formatUpdatedAt(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function stageLabel(value: string): string {
  if (value === "launch_watch") {
    return "Launch Watch";
  }
  if (value === "watch_selling") {
    return "Watch Selling";
  }
  if (value === "selling") {
    return "Selling";
  }
  return value;
}

function signalFilterLabel(value: string): string {
  if (value === "all") {
    return "All signals";
  }
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function LaunchWatchPage() {
  const [items, setItems] = useState<LaunchWatchItem[]>([]);
  const [filterStage, setFilterStage] = useState("all");
  const [filterSignal, setFilterSignal] = useState("all");
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
      if (filterSignal !== "all" && item.signal_bucket !== filterSignal) {
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
        item.signal_label,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(search.trim().toLowerCase());
    });
  }, [filterSignal, filterStage, items, search]);

  const groupedFiltered = useMemo(() => {
    const sorted = [...filtered].sort((left, right) => {
      if (left.signal_rank !== right.signal_rank) {
        return left.signal_rank - right.signal_rank;
      }
      if (left.signal_bucket !== right.signal_bucket) {
        return left.signal_bucket.localeCompare(right.signal_bucket);
      }
      if (left.updated_at !== right.updated_at) {
        return right.updated_at.localeCompare(left.updated_at);
      }
      return left.display_name.localeCompare(right.display_name, "zh-Hant");
    });

    const sections: Array<{
      bucket: string;
      label: string;
      description: string;
      rank: number;
      items: LaunchWatchItem[];
    }> = [];
    for (const item of sorted) {
      const current = sections[sections.length - 1];
      if (current && current.bucket === item.signal_bucket) {
        current.items.push(item);
        continue;
      }
      sections.push({
        bucket: item.signal_bucket,
        label: item.signal_label,
        description: SIGNAL_BUCKET_DESCRIPTIONS[item.signal_bucket] ?? "General launch-watch signal.",
        rank: item.signal_rank,
        items: [item],
      });
    }
    return sections;
  }, [filtered]);

  const stageCounts = useMemo(() => {
    return {
      total: items.length,
      watch: items.filter((item) => item.launch_stage === "launch_watch").length,
      selling: items.filter((item) => item.launch_stage === "selling" || item.launch_stage === "watch_selling").length,
    };
  }, [items]);

  const signalCounts = useMemo(() => {
    return {
      landsd: items.filter((item) => item.signal_bucket === "landsd_pending" || item.signal_bucket === "landsd_issued").length,
      pricing: items.filter((item) => item.signal_bucket === "recent_pricing").length,
      brochure: items.filter((item) => item.signal_bucket === "recent_brochure").length,
      active: items.filter((item) => item.signal_bucket === "srpe_active").length,
    };
  }, [items]);

  return (
    <main className="page-shell">
      <section className="hero-card hero-card-compact">
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
          <div className="dashboard-metric">
            <strong>{signalCounts.landsd}</strong>
            <span>LandsD signals</span>
          </div>
          <div className="dashboard-metric">
            <strong>{signalCounts.pricing}</strong>
            <span>Recent pricing</span>
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
            <span>Signal</span>
            <select value={filterSignal} onChange={(event) => setFilterSignal(event.target.value)}>
              {SIGNAL_BUCKETS.map((value) => (
                <option key={value} value={value}>
                  {signalFilterLabel(value)}
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
          <div className="launch-watch-signal-legend">
            <span className="workflow-chip launch-watch-signal-chip launch-watch-signal-landsd">LandsD</span>
            <span className="workflow-chip launch-watch-signal-chip launch-watch-signal-pricing">Recent pricing</span>
            <span className="workflow-chip launch-watch-signal-chip launch-watch-signal-brochure">Recent brochure</span>
            <span className="workflow-chip launch-watch-signal-chip launch-watch-signal-active">SRPE active</span>
          </div>
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
          {groupedFiltered.map((section) => (
            <div key={section.bucket} className="launch-watch-section">
              <div className="launch-watch-section-head">
                <div>
                  <h2>{section.label}</h2>
                  <p className="muted">{section.description}</p>
                </div>
                <span className="workflow-chip">{section.items.length} project(s)</span>
              </div>
              <div className="launch-watch-section-grid">
                {section.items.map((item) => (
                  <article key={item.id} className="panel launch-watch-card">
                    <div className="launch-watch-card-head">
                      <div>
                        <h2>{item.display_name}</h2>
                        <p className="muted">
                          {[item.district, item.region].filter(Boolean).join(" / ") || "Unknown district"}{" "}
                          {item.expected_launch_window ? `· ${item.expected_launch_window}` : ""}
                        </p>
                      </div>
                      <div className="launch-watch-badge-stack">
                        <span
                          className={`launch-watch-badge launch-watch-badge-signal launch-watch-badge-signal-${item.signal_bucket}`}
                        >
                          {item.signal_label}
                        </span>
                        <span className={`launch-watch-badge launch-watch-badge-${item.launch_stage.replace(/[^a-z]+/g, "-")}`}>
                          {stageLabel(item.launch_stage)}
                        </span>
                      </div>
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
              </div>
            </div>
          ))}
        </section>
      </section>
    </main>
  );
}
