"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CompareToggleButton } from "./components/compare-toggle-button";
import { formatListingSegment } from "./lib/segment";

type HealthResponse = {
  status: string;
  environment: string;
  app_name: string;
  app_version: string;
  api_prefix: string;
  database: {
    healthy: boolean;
    dialect: string;
    url_redacted: string;
  };
};

type DevelopmentSummary = {
  id: string;
  source_url: string | null;
  name_zh: string | null;
  name_en: string | null;
  name_translations: Record<string, string>;
  display_name: string | null;
  district: string | null;
  region: string | null;
  completion_year: number | null;
  listing_segment: string;
};

type DevelopmentListResponse = {
  items: DevelopmentSummary[];
  total: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [developments, setDevelopments] = useState<DevelopmentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [developmentError, setDevelopmentError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPageData() {
      try {
        const [healthResponse, developmentResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/health`),
          fetch(`${API_BASE}/api/v1/developments?limit=6`),
        ]);
        if (!healthResponse.ok) {
          throw new Error(`health HTTP ${healthResponse.status}`);
        }
        if (!developmentResponse.ok) {
          throw new Error(`developments HTTP ${developmentResponse.status}`);
        }
        const healthPayload = (await healthResponse.json()) as HealthResponse;
        const developmentPayload =
          (await developmentResponse.json()) as DevelopmentListResponse;
        if (!cancelled) {
          setHealth(healthPayload);
          setDevelopments(developmentPayload.items);
          setError(null);
          setDevelopmentError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setDevelopmentError(
            err instanceof Error ? err.message : "Unknown error",
          );
        }
      }
    }

    loadPageData();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Dashboard</p>
        <h1>HK Home Intel</h1>
        <p className="lead">
          Local-first Hong Kong residential property research workspace. The
          Track official and commercial-source housing data in one local workspace:
          map, watchlist, system monitor, activity feed, listing flow, and
          development compare.
        </p>
        <div className="hero-actions">
          <Link href="/map">Open map view</Link>
          <Link href="/activity">Open activity feed</Link>
          <Link href="/listings">Open listing feed</Link>
          <Link href="/watchlist">Open watchlist</Link>
          <Link href="/system">Open system monitor</Link>
        </div>
      </section>

      <section className="grid">
        <article className="panel">
          <h2>System Status</h2>
          {health ? (
            <dl className="kv-list">
              <div>
                <dt>API</dt>
                <dd>{health.status}</dd>
              </div>
              <div>
                <dt>Environment</dt>
                <dd>{health.environment}</dd>
              </div>
              <div>
                <dt>Version</dt>
                <dd>{health.app_version}</dd>
              </div>
              <div>
                <dt>Database</dt>
                <dd>
                  {health.database.dialect} /{" "}
                  {health.database.healthy ? "healthy" : "unhealthy"}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="muted">
              {error
                ? `API unavailable: ${error}`
                : "Waiting for API health response..."}
            </p>
          )}
        </article>

        <article className="panel">
          <h2>Workspace Overview</h2>
          <ul className="bullet-list">
            <li>Core canonical development, document, listing, and transaction tables</li>
            <li>Official SRPE index and selected development detail import</li>
            <li>Coordinate-backed Leaflet map with watchlist overlay</li>
            <li>Recent activity feed across refresh runs, snapshots, and watchlist updates</li>
            <li>System monitor with UI-triggered refresh plans</li>
            <li>Commercial listing event feed with canonical price events</li>
            <li>Three-language display fallback in the API layer</li>
          </ul>
        </article>

        <article className="panel">
          <h2>Developments</h2>
          {developmentError ? (
            <p className="muted">Development feed unavailable: {developmentError}</p>
          ) : developments.length > 0 ? (
            <ul className="development-list">
              {developments.map((item) => (
                <li key={item.id}>
                  <strong>
                    <Link href={`/developments/${item.id}`}>
                      {item.display_name ?? item.name_zh ?? item.name_en ?? item.id}
                    </Link>
                  </strong>
                  <span>
                    {item.district ?? "Unknown district"} / {formatListingSegment(item.listing_segment)}
                  </span>
                  <span>
                    {item.completion_year ? `Completion ${item.completion_year}` : "Year TBD"}
                  </span>
                  <div className="hero-actions">
                    <CompareToggleButton
                      developmentId={item.id}
                      developmentName={item.display_name ?? item.name_zh ?? item.name_en ?? item.id}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <p className="muted">No developments imported yet.</p>
              <code>conda run -n py311 hhi-worker import-srpe-index --lang en --limit 5</code>
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
