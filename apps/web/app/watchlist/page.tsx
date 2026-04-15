"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { CompareToggleButton } from "../components/compare-toggle-button";
import { addCompareSelection, clearCompareSelections } from "../lib/compare-store";
import { formatListingSegment } from "../lib/segment";

type WatchlistItem = {
  id: string;
  development_id: string;
  development_name: string | null;
  source_url: string | null;
  district: string | null;
  region: string | null;
  completion_year: number | null;
  listing_segment: string | null;
  decision_stage: string;
  personal_score: number | null;
  note: string | null;
  tags: string[];
  updated_at: string;
  active_listing_count: number;
  active_listing_min_price_hkd: number | null;
  active_listing_max_price_hkd: number | null;
  latest_listing_event_at: string | null;
  recent_listing_event_count_7d: number;
  recent_price_move_count_7d: number;
  recent_status_move_count_7d: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const STAGES = [
  "all",
  "watching",
  "shortlisted",
  "visit_planned",
  "negotiating",
  "passed",
];

type DraftState = {
  stage: string;
  score: string;
  note: string;
};

function formatUpdatedAt(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

function formatPrice(amount: number | null): string {
  if (amount === null) {
    return "TBD";
  }
  return new Intl.NumberFormat("en-HK", {
    style: "currency",
    currency: "HKD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [filterStage, setFilterStage] = useState("all");
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadWatchlist() {
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE}/api/v1/watchlist?lang=zh-Hant`);
        if (!response.ok) {
          throw new Error(`watchlist HTTP ${response.status}`);
        }
        const payload = (await response.json()) as WatchlistItem[];
        if (!cancelled) {
          setItems(payload);
          setDrafts(
            Object.fromEntries(
              payload.map((item) => [
                item.id,
                {
                  stage: item.decision_stage,
                  score: item.personal_score?.toString() ?? "",
                  note: item.note ?? "",
                },
              ]),
            ),
          );
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

    loadWatchlist();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (filterStage === "all") {
      return items;
    }
    return items.filter((item) => item.decision_stage === filterStage);
  }, [filterStage, items]);

  async function saveItem(itemId: string) {
    const draft = drafts[itemId];
    if (!draft) {
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/watchlist/${itemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision_stage: draft.stage,
          personal_score: draft.score === "" ? null : Number(draft.score),
          note: draft.note,
        }),
      });
      if (!response.ok) {
        throw new Error(`watchlist update HTTP ${response.status}`);
      }
      const payload = (await response.json()) as WatchlistItem;
      setItems((current) => current.map((item) => (item.id === payload.id ? payload : item)));
      setDrafts((current) => ({
        ...current,
        [payload.id]: {
          stage: payload.decision_stage,
          score: payload.personal_score?.toString() ?? "",
          note: payload.note ?? "",
        },
      }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function removeItem(itemId: string) {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/watchlist/${itemId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`watchlist delete HTTP ${response.status}`);
      }
      setItems((current) => current.filter((item) => item.id !== itemId));
      setDrafts((current) => {
        const next = { ...current };
        delete next[itemId];
        return next;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function updateDraft(itemId: string, patch: Partial<DraftState>) {
    setDrafts((current) => ({
      ...current,
      [itemId]: {
        ...(current[itemId] ?? { stage: "watching", score: "", note: "" }),
        ...patch,
      },
    }));
  }

  function addFilteredToCompare() {
    for (const item of filtered) {
      addCompareSelection({
        id: item.development_id,
        name: item.development_name ?? item.development_id,
      });
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Phase 2</p>
        <h1>Watchlist Workspace</h1>
        <p className="lead">
          Review your shortlisted developments in one place, update stage, add notes, and
          keep a lightweight decision log before the richer comparison workflow lands.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/activity">Open activity</Link>
          <Link href="/map">Open map view</Link>
          <Link href="/compare">Open compare</Link>
          <Link href="/system">Open system monitor</Link>
          <button type="button" onClick={addFilteredToCompare}>
            Add filtered to compare
          </button>
          <button type="button" onClick={() => clearCompareSelections()}>
            Clear compare tray
          </button>
        </div>
      </section>

      <section className="watchlist-layout">
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
          <p className="muted">
            {loading ? "Saving or loading..." : `Showing ${filtered.length} / ${items.length} items`}
          </p>
          {error ? <p className="muted">Watchlist error: {error}</p> : null}
        </aside>

        <section className="watchlist-board">
          {filtered.length > 0 ? (
            filtered.map((item) => {
              const draft = drafts[item.id] ?? {
                stage: item.decision_stage,
                score: item.personal_score?.toString() ?? "",
                note: item.note ?? "",
              };
              return (
                <article key={item.id} className="panel watchlist-card">
                  <div className="watchlist-card-head">
                    <div>
                      <h2>{item.development_name ?? item.development_id}</h2>
                      <p className="muted">
                        {item.district ?? "Unknown district"}
                        {item.region ? ` / ${item.region}` : ""}
                        {item.listing_segment ? ` / ${formatListingSegment(item.listing_segment)}` : ""}
                      </p>
                    </div>
                    <span className="watchlist-updated">Updated {formatUpdatedAt(item.updated_at)}</span>
                  </div>

                  <div className="watchlist-meta">
                    <span>{item.completion_year ? `Completion ${item.completion_year}` : "Year TBD"}</span>
                    <span>{item.personal_score !== null ? `Score ${item.personal_score}/10` : "Score TBD"}</span>
                    <span>
                      {item.active_listing_count > 0
                        ? `${item.active_listing_count} active / ${formatPrice(item.active_listing_min_price_hkd)} → ${formatPrice(item.active_listing_max_price_hkd)}`
                        : "No active commercial listings yet"}
                    </span>
                    <span>
                      7d changes {item.recent_listing_event_count_7d}
                      {` / price ${item.recent_price_move_count_7d} / status ${item.recent_status_move_count_7d}`}
                    </span>
                    <span>
                      Latest listing event {item.latest_listing_event_at ? formatUpdatedAt(item.latest_listing_event_at) : "TBD"}
                    </span>
                  </div>

                  <div className="watchlist-editor">
                    <label className="field">
                      <span>Stage</span>
                      <select
                        value={draft.stage}
                        onChange={(event) => updateDraft(item.id, { stage: event.target.value })}
                      >
                        {STAGES.filter((value) => value !== "all").map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="field">
                      <span>Personal Score</span>
                      <input
                        type="number"
                        min="0"
                        max="10"
                        value={draft.score}
                        onChange={(event) => updateDraft(item.id, { score: event.target.value })}
                        placeholder="0-10"
                      />
                    </label>

                    <label className="field">
                      <span>Note</span>
                      <textarea
                        value={draft.note}
                        onChange={(event) => updateDraft(item.id, { note: event.target.value })}
                        rows={4}
                        placeholder="Record tradeoffs, site visit notes, pricing concerns..."
                      />
                    </label>
                  </div>

                  <div className="watchlist-actions">
                    <button
                      type="button"
                      className="action-button"
                      onClick={() => void saveItem(item.id)}
                      disabled={loading}
                    >
                      Save changes
                    </button>
                    <button
                      type="button"
                      className="action-button action-button-secondary"
                      onClick={() => void removeItem(item.id)}
                      disabled={loading}
                    >
                      Remove
                    </button>
                    <Link href={`/developments/${item.development_id}`} className="action-link">
                      Open detail
                    </Link>
                    <Link href={`/compare?ids=${item.development_id}`} className="action-link">
                      Compare
                    </Link>
                    <CompareToggleButton
                      developmentId={item.development_id}
                      developmentName={item.development_name ?? item.development_id}
                    />
                    <Link href={`/listings?development_id=${item.development_id}`} className="action-link">
                      Open listing feed
                    </Link>
                    {item.source_url ? (
                      <a href={item.source_url} target="_blank" rel="noreferrer" className="action-link">
                        Open source
                      </a>
                    ) : null}
                  </div>
                </article>
              );
            })
          ) : (
            <article className="panel">
              <h2>Watchlist Empty</h2>
              <p className="muted">
                Add developments from the detail page first. This page will then become your
                shortlist workspace.
              </p>
            </article>
          )}
        </section>
      </section>
    </main>
  );
}
