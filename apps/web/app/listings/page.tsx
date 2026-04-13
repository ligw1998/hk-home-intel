"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { formatEventType, formatListingStatus } from "../lib/listing-events";

type ListingFeedItem = {
  id: string;
  event_type: string;
  event_at: string;
  source: string;
  development_id: string;
  development_name: string | null;
  development_source_url: string | null;
  listing_id: string | null;
  listing_title: string | null;
  listing_source_url: string | null;
  old_price_hkd: number | null;
  new_price_hkd: number | null;
  price_delta_hkd: number | null;
  old_status: string | null;
  new_status: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-HK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function ListingFeedPageContent() {
  const searchParams = useSearchParams();
  const [items, setItems] = useState<ListingFeedItem[]>([]);
  const [source, setSource] = useState(searchParams.get("source") ?? "all");
  const [eventType, setEventType] = useState(searchParams.get("event_type") ?? "all");
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [changesOnly, setChangesOnly] = useState(searchParams.get("changes_only") === "true");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const developmentId = searchParams.get("development_id") ?? "";

  useEffect(() => {
    let cancelled = false;

    async function loadFeed() {
      try {
        setLoading(true);
        const params = new URLSearchParams({ limit: "50", lang: "zh-Hant" });
        if (developmentId) {
          params.set("development_id", developmentId);
        }
        if (source !== "all") {
          params.set("source", source);
        }
        if (eventType !== "all") {
          params.set("event_type", eventType);
        }
        if (search.trim()) {
          params.set("q", search.trim());
        }
        if (changesOnly) {
          params.set("changes_only", "true");
        }
        const response = await fetch(`${API_BASE}/api/v1/listings/feed?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`listings feed HTTP ${response.status}`);
        }
        const payload = (await response.json()) as ListingFeedItem[];
        if (!cancelled) {
          setItems(payload);
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

    loadFeed();
    return () => {
      cancelled = true;
    };
  }, [changesOnly, developmentId, eventType, search, source]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (!search.trim()) {
        return true;
      }
      const haystack = `${item.listing_title ?? ""} ${item.development_name ?? ""} ${item.source}`.toLowerCase();
      return haystack.includes(search.trim().toLowerCase());
    });
  }, [items, search]);

  const summary = useMemo(() => {
    const byType = filteredItems.reduce<Record<string, number>>((acc, item) => {
      acc[item.event_type] = (acc[item.event_type] ?? 0) + 1;
      return acc;
    }, {});
    return byType;
  }, [filteredItems]);

  const newListingCount = filteredItems.filter((item) => item.event_type === "new_listing").length;
  const priceDropCount = filteredItems.filter((item) => item.event_type === "price_drop").length;
  const withdrawnCount = filteredItems.filter((item) => item.event_type === "withdrawn").length;
  const relistCount = filteredItems.filter((item) => item.event_type === "relist").length;

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Phase 3A</p>
        <h1>Listing Event Feed</h1>
        <p className="lead">
          Review recent commercial listing events before they are folded into the fuller comparison
          and monitoring workspace.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/activity">Open activity</Link>
          <Link href="/map">Open map</Link>
          <Link href="/watchlist">Open watchlist</Link>
        </div>
      </section>

      <section className="activity-layout">
        <article className="panel filter-panel">
          <h2>Filters</h2>
          <label className="field">
            <span>Search</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Listing / development / source"
            />
          </label>
          <label className="field">
            <span>Source</span>
            <select value={source} onChange={(event) => setSource(event.target.value)}>
              <option value="all">all</option>
              <option value="centanet">centanet</option>
              <option value="ricacorp">ricacorp</option>
            </select>
          </label>
          <label className="field">
            <span>Event Type</span>
            <select value={eventType} onChange={(event) => setEventType(event.target.value)}>
              <option value="all">all</option>
              <option value="new_listing">new_listing</option>
              <option value="price_drop">price_drop</option>
              <option value="price_raise">price_raise</option>
              <option value="relist">relist</option>
              <option value="sold">sold</option>
              <option value="withdrawn">withdrawn</option>
              <option value="status_change">status_change</option>
            </select>
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={changesOnly}
              onChange={(event) => setChangesOnly(event.target.checked)}
            />
            <span>Changes only</span>
          </label>
          <dl className="kv-list compact-kv-list">
            <div>
              <dt>Total events</dt>
              <dd>{filteredItems.length}</dd>
            </div>
            <div>
              <dt>New listings</dt>
              <dd>{newListingCount}</dd>
            </div>
            <div>
              <dt>Price drops</dt>
              <dd>{priceDropCount}</dd>
            </div>
            <div>
              <dt>Withdrawn</dt>
              <dd>{withdrawnCount}</dd>
            </div>
            <div>
              <dt>Relists</dt>
              <dd>{relistCount}</dd>
            </div>
            {Object.entries(summary).map(([key, value]) => (
              <div key={key}>
                <dt>{formatEventType(key)}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </article>

        <article className="panel detail-span-2">
          <h2>Recent Events</h2>
          {!loading && !error ? (
            <div className="listing-feed-stats">
            <div className="listing-feed-stat">
              <strong>{filteredItems.length}</strong>
              <span>Events in view</span>
            </div>
            <div className="listing-feed-stat">
              <strong>{newListingCount}</strong>
              <span>New listings</span>
            </div>
            <div className="listing-feed-stat">
              <strong>{priceDropCount}</strong>
              <span>Price drops</span>
            </div>
            <div className="listing-feed-stat">
              <strong>{withdrawnCount + relistCount}</strong>
              <span>Status moves</span>
            </div>
          </div>
          ) : null}
          {loading ? (
            <p className="muted">Loading listing events...</p>
          ) : error ? (
            <p className="muted">Listing feed unavailable: {error}</p>
          ) : filteredItems.length > 0 ? (
            <ul className="listing-event-list">
              {filteredItems.map((item) => (
                <li key={item.id} className="listing-event-item">
                  <div className="listing-event-head">
                    <strong>{item.listing_title ?? item.development_name ?? "Listing event"}</strong>
                    <span className={`listing-event-badge listing-event-badge-${item.event_type}`}>
                      {formatEventType(item.event_type)}
                    </span>
                  </div>
                  <span>
                    {item.source} / {formatDateTime(item.event_at)}
                  </span>
                  <span>
                    {item.development_name ?? "Unknown development"}
                  </span>
                  <span>
                    {formatPrice(item.old_price_hkd)} → {formatPrice(item.new_price_hkd)}
                    {item.price_delta_hkd !== null ? ` (${formatPrice(item.price_delta_hkd)})` : ""}
                  </span>
                  <span>
                    {formatListingStatus(item.old_status ?? "new")} → {formatListingStatus(item.new_status)}
                  </span>
                  <div className="hero-actions">
                    <Link href={`/developments/${item.development_id}`}>Open development</Link>
                    {item.listing_id ? <Link href={`/listings/${item.listing_id}`}>Open listing detail</Link> : null}
                    {item.listing_source_url ? (
                      <a href={item.listing_source_url} target="_blank" rel="noreferrer">
                        Open source listing
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No listing events matched the current filter.</p>
          )}
          {!loading && !error && changesOnly && filteredItems.length === 0 ? (
            <p className="muted">
              No price or status changes matched the current scope. Try disabling
              {" "}
              <code>Changes only</code>
              {" "}
              to inspect new listings as well.
            </p>
          ) : null}
        </article>
      </section>
    </main>
  );
}

export default function ListingFeedPage() {
  return (
    <Suspense fallback={<main className="page-shell"><p className="muted">Loading listing feed...</p></main>}>
      <ListingFeedPageContent />
    </Suspense>
  );
}
