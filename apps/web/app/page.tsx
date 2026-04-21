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

type SystemOverview = {
  readiness_status: string;
  readiness_notes: string[];
  active_monitor_count: number;
  attention_monitor_count: number;
  commercial_listing_count: number;
  price_event_count: number;
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

type ShortlistItem = {
  id: string;
  display_name: string | null;
  district: string | null;
  region: string | null;
  listing_segment: string;
  decision_score: number;
  decision_band: string;
  active_listing_min_price_hkd: number | null;
  active_listing_max_price_hkd: number | null;
  latest_listing_event_at: string | null;
};

type ShortlistResponse = {
  items: ShortlistItem[];
  total: number;
};

type ListingFeedItem = {
  id: string;
  event_type: string;
  event_at: string;
  source: string;
  development_id: string;
  development_name: string | null;
  listing_id: string | null;
  listing_title: string | null;
  new_price_hkd: number | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function formatDateTime(value: string | null): string {
  if (!value) {
    return "TBD";
  }
  return new Intl.DateTimeFormat("zh-HK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function bandLabel(value: string): string {
  switch (value) {
    case "strong_fit":
      return "Strong fit";
    case "possible_fit":
      return "Possible fit";
    case "needs_review":
      return "Needs review";
    default:
      return "Weak fit";
  }
}

function formatCompactPrice(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "TBD";
  }
  if (value >= 1_000_000) {
    return `HK$${(value / 1_000_000).toFixed(value >= 10_000_000 ? 1 : 2).replace(/\.0$/, "")}M`;
  }
  if (value >= 1_000) {
    return `HK$${Math.round(value / 1_000)}K`;
  }
  return `HK$${Math.round(value)}`;
}

export default function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [developments, setDevelopments] = useState<DevelopmentSummary[]>([]);
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);
  const [marketMoves, setMarketMoves] = useState<ListingFeedItem[]>([]);
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [developmentError, setDevelopmentError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPageData() {
      try {
        const [healthResponse, developmentResponse, shortlistResponse, marketMovesResponse, overviewResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/health`),
          fetch(`${API_BASE}/api/v1/developments?limit=6`),
          fetch(
            `${API_BASE}/api/v1/shortlist?lang=zh-Hant&min_budget_hkd=8000000&max_budget_hkd=18000000&bedroom_values=2,3,1,0&min_saleable_area_sqft=400&max_saleable_area_sqft=750&max_age_years=10&extended_age_years=15&listing_segments=new,first_hand_remaining,second_hand&limit=30`,
          ),
          fetch(`${API_BASE}/api/v1/listings/feed?days=7&limit=8`),
          fetch(`${API_BASE}/api/v1/system/overview`),
        ]);
        if (!healthResponse.ok) {
          throw new Error(`health HTTP ${healthResponse.status}`);
        }
        if (!developmentResponse.ok) {
          throw new Error(`developments HTTP ${developmentResponse.status}`);
        }
        if (!shortlistResponse.ok) {
          throw new Error(`shortlist HTTP ${shortlistResponse.status}`);
        }
        if (!marketMovesResponse.ok) {
          throw new Error(`listings HTTP ${marketMovesResponse.status}`);
        }
        if (!overviewResponse.ok) {
          throw new Error(`overview HTTP ${overviewResponse.status}`);
        }
        const healthPayload = (await healthResponse.json()) as HealthResponse;
        const developmentPayload =
          (await developmentResponse.json()) as DevelopmentListResponse;
        const shortlistPayload = (await shortlistResponse.json()) as ShortlistResponse;
        const marketMovesPayload = (await marketMovesResponse.json()) as ListingFeedItem[];
        const overviewPayload = (await overviewResponse.json()) as SystemOverview;
        if (!cancelled) {
          setHealth(healthPayload);
          setDevelopments(developmentPayload.items);
          setShortlist(shortlistPayload.items);
          setMarketMoves(marketMovesPayload);
          setSystemOverview(overviewPayload);
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
          Local-first Hong Kong residential property research workspace. Track
          official and commercial-source housing data in one local workspace:
          map, watchlist, system monitor, activity feed, listing flow, and
          development compare.
        </p>
        <div className="hero-actions">
          <Link href="/map">Map</Link>
          <Link href="/shortlist">Shortlist</Link>
          <Link href="/compare">Compare</Link>
          <Link href="/activity">Activity</Link>
          <Link href="/listings">Listings</Link>
          <Link href="/watchlist">Watchlist</Link>
          <Link href="/system">System</Link>
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
              {systemOverview ? (
                <>
                  <div>
                    <dt>Readiness</dt>
                    <dd>{systemOverview.readiness_status}</dd>
                  </div>
                  <div>
                    <dt>Commercial Listings</dt>
                    <dd>{systemOverview.commercial_listing_count}</dd>
                  </div>
                  <div>
                    <dt>Price Events</dt>
                    <dd>{systemOverview.price_event_count}</dd>
                  </div>
                  <div>
                    <dt>Monitor Attention</dt>
                    <dd>
                      {systemOverview.attention_monitor_count}
                      {" / "}
                      {systemOverview.active_monitor_count}
                    </dd>
                  </div>
                </>
              ) : null}
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
          <h2>Decision Pulse</h2>
          {shortlist.length > 0 ? (
            <div className="dashboard-stack">
              <div className="dashboard-metric-row">
                <Link href="/shortlist?band=strong_fit" className="dashboard-metric">
                  <strong>{shortlist.filter((item) => item.decision_band === "strong_fit").length}</strong>
                  <span>Strong fit</span>
                  <small className="muted">Open strong-fit shortlist</small>
                </Link>
                <Link href="/shortlist?band=possible_fit" className="dashboard-metric">
                  <strong>{shortlist.filter((item) => item.decision_band === "possible_fit").length}</strong>
                  <span>Possible fit</span>
                  <small className="muted">Open possible-fit shortlist</small>
                </Link>
                <Link href="/listings" className="dashboard-metric">
                  <strong>{marketMoves.length}</strong>
                  <span>Recent moves</span>
                  <small className="muted">Open listing moves</small>
                </Link>
              </div>
              <div className="dashboard-callout">
                <strong>Best current candidate</strong>
                <p>
                  {shortlist[0]?.display_name ?? "TBD"}
                  {" / "}
                  {bandLabel(shortlist[0]?.decision_band ?? "weak_fit")}
                  {" / score "}
                  {shortlist[0]?.decision_score ?? 0}
                </p>
                <span>
                  {shortlist[0]?.district ?? "Unknown district"}
                  {shortlist[0]?.region ? ` / ${shortlist[0].region}` : ""}
                  {" / "}
                  {formatListingSegment(shortlist[0]?.listing_segment ?? "mixed")}
                </span>
                <div className="hero-actions">
                  {shortlist[0] ? <Link href={`/developments/${shortlist[0].id}`}>Open candidate</Link> : null}
                  <Link href="/shortlist">Open full shortlist</Link>
                  <Link href="/shortlist?band=strong_fit">Open strong-fit set</Link>
                </div>
              </div>
              <div className="dashboard-callout">
                <strong>Top fits right now</strong>
                <ul className="development-list">
                  {shortlist.slice(0, 3).map((item) => (
                    <li key={item.id}>
                      <strong>
                        <Link href={`/developments/${item.id}`}>
                          {item.display_name ?? item.id}
                        </Link>
                      </strong>
                      <span>
                        {bandLabel(item.decision_band)}
                        {" / score "}
                        {item.decision_score}
                        {" / "}
                        {item.district ?? "Unknown district"}
                        {item.region ? ` / ${item.region}` : ""}
                      </span>
                      <span>
                        {formatCompactPrice(item.active_listing_min_price_hkd)}
                        {" → "}
                        {formatCompactPrice(item.active_listing_max_price_hkd)}
                        {" / "}
                        {formatListingSegment(item.listing_segment)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              {systemOverview?.readiness_notes?.length ? (
                <div className="dashboard-callout">
                  <strong>Preflight Notes</strong>
                  <span>{systemOverview.readiness_notes.join(" / ")}</span>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="muted">No shortlist candidates yet.</p>
          )}
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

      <section className="grid">
        <article className="panel detail-span-2">
          <h2>Shortlist Snapshot</h2>
          {shortlist.length > 0 ? (
            <ul className="development-list">
              {shortlist.slice(0, 4).map((item) => (
                <li key={item.id}>
                  <strong>
                    <Link href={`/developments/${item.id}`}>
                      {item.display_name ?? item.id}
                    </Link>
                  </strong>
                  <span>
                    {bandLabel(item.decision_band)}
                    {" / score "}
                    {item.decision_score}
                    {" / "}
                    {item.district ?? "Unknown district"}
                    {item.region ? ` / ${item.region}` : ""}
                  </span>
                  <span>
                    {formatCompactPrice(item.active_listing_min_price_hkd)}
                    {" → "}
                    {formatCompactPrice(item.active_listing_max_price_hkd)}
                    {" / "}
                    {formatListingSegment(item.listing_segment)}
                  </span>
                  <span>Latest event: {formatDateTime(item.latest_listing_event_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Shortlist is still empty.</p>
          )}
        </article>

        <article className="panel">
          <h2>Recent Market Moves</h2>
          {marketMoves.length > 0 ? (
            <ul className="development-list">
              {marketMoves.slice(0, 5).map((item) => (
                <li key={item.id}>
                  <strong>
                    <Link href={item.listing_id ? `/listings/${item.listing_id}` : `/developments/${item.development_id}`}>
                      {item.development_name ?? item.listing_title ?? item.id}
                    </Link>
                  </strong>
                  <span>{item.source} / {item.event_type.replaceAll("_", " ")}</span>
                  <span>{formatCompactPrice(item.new_price_hkd)}</span>
                  <span>{formatDateTime(item.event_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No recent listing moves yet.</p>
          )}
        </article>
      </section>
    </main>
  );
}
