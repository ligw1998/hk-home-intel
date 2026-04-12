"use client";

import { useEffect, useState } from "react";

type WatchlistItem = {
  id: string;
  decision_stage: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const STAGES = [
  "watching",
  "shortlisted",
  "visit_planned",
  "negotiating",
  "passed",
];

export function WatchlistButton({ developmentId }: { developmentId: string }) {
  const [item, setItem] = useState<WatchlistItem | null>(null);
  const [stage, setStage] = useState("watching");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadWatchlistState() {
      try {
        const response = await fetch(
          `${API_BASE}/api/v1/watchlist?development_id=${developmentId}`,
        );
        if (!response.ok) {
          throw new Error(`watchlist HTTP ${response.status}`);
        }
        const payload = (await response.json()) as WatchlistItem[];
        if (!cancelled) {
          setItem(payload[0] ?? null);
          setStage(payload[0]?.decision_stage ?? "watching");
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    loadWatchlistState();
    return () => {
      cancelled = true;
    };
  }, [developmentId]);

  async function saveItem() {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/watchlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          development_id: developmentId,
          decision_stage: stage,
          tags: [],
        }),
      });
      if (!response.ok) {
        throw new Error(`save HTTP ${response.status}`);
      }
      const payload = (await response.json()) as WatchlistItem;
      setItem(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function updateStage(nextStage: string) {
    setStage(nextStage);
    if (!item) {
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/watchlist/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision_stage: nextStage }),
      });
      if (!response.ok) {
        throw new Error(`update HTTP ${response.status}`);
      }
      const payload = (await response.json()) as WatchlistItem;
      setItem(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function removeItem() {
    if (!item) {
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/watchlist/${item.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`delete HTTP ${response.status}`);
      }
      setItem(null);
      setStage("watching");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="watchlist-box">
      <label className="field">
        <span>Watchlist Stage</span>
        <select value={stage} onChange={(event) => void updateStage(event.target.value)}>
          {STAGES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>
      <div className="watchlist-actions">
        <button type="button" className="action-button" onClick={() => void saveItem()} disabled={loading}>
          {item ? "Update watchlist" : "Add to watchlist"}
        </button>
        {item ? (
          <button
            type="button"
            className="action-button action-button-secondary"
            onClick={() => void removeItem()}
            disabled={loading}
          >
            Remove
          </button>
        ) : null}
      </div>
      <p className="muted">
        {item ? `Saved in watchlist as ${item.decision_stage}.` : "Not in watchlist yet."}
      </p>
      {error ? <p className="muted">Watchlist error: {error}</p> : null}
    </div>
  );
}
