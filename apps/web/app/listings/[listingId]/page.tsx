"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { formatEventType, formatListingStatus } from "../../lib/listing-events";

type ListingDetail = {
  id: string;
  source: string;
  source_listing_id: string;
  source_url: string | null;
  development_id: string;
  development_name: string | null;
  development_source_url: string | null;
  title: string | null;
  asking_price_hkd: number | null;
  price_per_sqft: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  saleable_area_sqft: number | null;
  gross_area_sqft: number | null;
  status: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  address: string | null;
  update_date: string | null;
  monthly_payment_hkd: number | null;
  age_years: number | null;
  orientation: string | null;
  feature_tags: string[];
  description: string | null;
  developer_names: string[];
};

type ListingEvent = {
  id: string;
  event_type: string;
  event_at: string;
  old_price_hkd: number | null;
  new_price_hkd: number | null;
  old_status: string | null;
  new_status: string | null;
  listing_title: string | null;
};

type ListingPricePoint = {
  event_id: string | null;
  event_type: string;
  recorded_at: string;
  price_hkd: number;
};

type ListingPriceHistory = {
  listing_id: string;
  current_price_hkd: number | null;
  previous_price_hkd: number | null;
  lowest_price_hkd: number | null;
  highest_price_hkd: number | null;
  point_count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  points: ListingPricePoint[];
};

type ComparableListing = {
  id: string;
  source: string;
  source_url: string | null;
  development_id: string;
  development_name: string | null;
  district: string | null;
  region: string | null;
  title: string | null;
  asking_price_hkd: number | null;
  price_per_sqft: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  saleable_area_sqft: number | null;
  status: string;
  match_score: number;
  reasons: string[];
};

type ComparableListingsResponse = {
  focus_listing_id: string;
  focus_development_id: string;
  items: ComparableListing[];
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

function formatDateTime(value: string | null): string {
  if (!value) {
    return "TBD";
  }
  return new Intl.DateTimeFormat("zh-HK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function ListingDetailPage() {
  const params = useParams<{ listingId: string }>();
  const listingId = params.listingId ?? null;
  const [detail, setDetail] = useState<ListingDetail | null>(null);
  const [events, setEvents] = useState<ListingEvent[]>([]);
  const [priceHistory, setPriceHistory] = useState<ListingPriceHistory | null>(null);
  const [comparables, setComparables] = useState<ComparableListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!listingId) {
      return;
    }
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        const [detailResponse, eventsResponse, priceHistoryResponse, comparablesResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/listings/${listingId}?lang=zh-Hant`),
          fetch(`${API_BASE}/api/v1/listings/${listingId}/events?lang=zh-Hant`),
          fetch(`${API_BASE}/api/v1/listings/${listingId}/price-history`),
          fetch(`${API_BASE}/api/v1/compare/listings/${listingId}/comparables?limit=6`),
        ]);
        if (!detailResponse.ok) {
          throw new Error(`listing detail HTTP ${detailResponse.status}`);
        }
        if (!eventsResponse.ok) {
          throw new Error(`listing events HTTP ${eventsResponse.status}`);
        }
        if (!priceHistoryResponse.ok) {
          throw new Error(`listing price history HTTP ${priceHistoryResponse.status}`);
        }
        if (!comparablesResponse.ok) {
          throw new Error(`listing comparables HTTP ${comparablesResponse.status}`);
        }
        const detailPayload = (await detailResponse.json()) as ListingDetail;
        const eventsPayload = (await eventsResponse.json()) as ListingEvent[];
        const priceHistoryPayload = (await priceHistoryResponse.json()) as ListingPriceHistory;
        const comparablesPayload = (await comparablesResponse.json()) as ComparableListingsResponse;
        if (!cancelled) {
          setDetail(detailPayload);
          setEvents(eventsPayload);
          setPriceHistory(priceHistoryPayload);
          setComparables(comparablesPayload.items);
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

    load();
    return () => {
      cancelled = true;
    };
  }, [listingId]);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Listing Detail</p>
        <h1>{detail?.title ?? "Listing Detail"}</h1>
        <p className="lead">
          Review the normalized commercial listing fields and recent change events for a single source listing.
        </p>
        <div className="hero-actions">
          <Link href="/listings">Back to listing feed</Link>
          {detail ? <Link href={`/developments/${detail.development_id}`}>Open development</Link> : null}
          {detail ? <Link href={`/compare?ids=${detail.development_id}`}>Compare development</Link> : null}
          {detail?.source_url ? (
            <a href={detail.source_url} target="_blank" rel="noreferrer">
              Open source listing
            </a>
          ) : null}
        </div>
      </section>

      {loading ? <p className="muted">Loading listing detail...</p> : null}
      {error ? <p className="muted">Listing detail unavailable: {error}</p> : null}

      {detail ? (
        <section className="activity-layout">
          <article className="panel">
            <h2>Snapshot</h2>
            <dl className="kv-list compact-kv-list">
              <div><dt>Source</dt><dd>{detail.source}</dd></div>
              <div><dt>Status</dt><dd>{detail.status}</dd></div>
              <div><dt>Asking</dt><dd>{formatPrice(detail.asking_price_hkd)}</dd></div>
              <div><dt>Price / sqft</dt><dd>{detail.price_per_sqft ? formatPrice(detail.price_per_sqft) : "TBD"}</dd></div>
              <div><dt>Saleable</dt><dd>{detail.saleable_area_sqft ? `${detail.saleable_area_sqft} sqft` : "TBD"}</dd></div>
              <div><dt>Bedrooms</dt><dd>{detail.bedrooms ?? "TBD"}</dd></div>
              <div><dt>Bathrooms</dt><dd>{detail.bathrooms ?? "TBD"}</dd></div>
              <div><dt>Address</dt><dd>{detail.address ?? "TBD"}</dd></div>
              <div><dt>Updated</dt><dd>{detail.update_date ?? "TBD"}</dd></div>
              <div><dt>Monthly payment</dt><dd>{formatPrice(detail.monthly_payment_hkd)}</dd></div>
              <div><dt>Age</dt><dd>{detail.age_years !== null ? `${detail.age_years} years` : "TBD"}</dd></div>
              <div><dt>Orientation</dt><dd>{detail.orientation ?? "TBD"}</dd></div>
              <div><dt>First seen</dt><dd>{formatDateTime(detail.first_seen_at)}</dd></div>
              <div><dt>Last seen</dt><dd>{formatDateTime(detail.last_seen_at)}</dd></div>
            </dl>
            {detail.developer_names.length > 0 ? (
              <>
                <h3>Developers</h3>
                <div className="tag-group">
                  {detail.developer_names.map((item) => (
                    <span key={item} className="status-pill">{item}</span>
                  ))}
                </div>
              </>
            ) : null}
            {detail.feature_tags.length > 0 ? (
              <>
                <h3>Feature Tags</h3>
                <div className="tag-group">
                  {detail.feature_tags.map((item) => (
                    <span key={item} className="status-pill">{item}</span>
                  ))}
                </div>
              </>
            ) : null}
            {detail.description ? (
              <>
                <h3>Description</h3>
                <p className="muted">{detail.description}</p>
              </>
            ) : null}
          </article>

          <article className="panel">
            <h2>Price History</h2>
            {priceHistory ? (
              <>
                <dl className="kv-list compact-kv-list">
                  <div><dt>Current</dt><dd>{formatPrice(priceHistory.current_price_hkd)}</dd></div>
                  <div><dt>Previous</dt><dd>{formatPrice(priceHistory.previous_price_hkd)}</dd></div>
                  <div><dt>Lowest</dt><dd>{formatPrice(priceHistory.lowest_price_hkd)}</dd></div>
                  <div><dt>Highest</dt><dd>{formatPrice(priceHistory.highest_price_hkd)}</dd></div>
                  <div><dt>Points</dt><dd>{priceHistory.point_count}</dd></div>
                  <div><dt>First seen</dt><dd>{formatDateTime(priceHistory.first_seen_at)}</dd></div>
                  <div><dt>Last seen</dt><dd>{formatDateTime(priceHistory.last_seen_at)}</dd></div>
                </dl>
                {priceHistory.points.length > 0 ? (
                  <ul className="listing-event-list compact-listing-history">
                    {priceHistory.points
                      .slice()
                      .reverse()
                      .map((point) => (
                        <li key={point.event_id ?? `${point.event_type}-${point.recorded_at}`} className="listing-event-item">
                          <div className="listing-event-head">
                            <strong>{formatPrice(point.price_hkd)}</strong>
                            <span className={`listing-event-badge listing-event-badge-${point.event_type}`}>
                              {formatEventType(point.event_type)}
                            </span>
                          </div>
                          <span>{formatDateTime(point.recorded_at)}</span>
                        </li>
                      ))}
                  </ul>
                ) : (
                  <p className="muted">No price history points recorded yet.</p>
                )}
              </>
            ) : (
              <p className="muted">Price history unavailable.</p>
            )}
          </article>

          <article className="panel">
            <h2>Comparable Listings</h2>
            {comparables.length > 0 ? (
              <ul className="development-list">
                {comparables.map((item) => (
                  <li key={item.id}>
                    <strong>{item.title ?? item.development_name ?? "Comparable listing"}</strong>
                    <span>
                      Score {item.match_score}
                      {item.reasons.length > 0 ? ` / ${item.reasons.join(" / ")}` : ""}
                    </span>
                    <span>
                      {item.development_name ?? "Unknown development"}
                      {item.district ? ` / ${item.district}` : ""}
                    </span>
                    <span>
                      {formatPrice(item.asking_price_hkd)}
                      {item.saleable_area_sqft !== null ? ` / ${item.saleable_area_sqft} sqft` : ""}
                      {item.bedrooms !== null ? ` / ${item.bedrooms === 0 ? "開放式" : `${item.bedrooms}房`}` : ""}
                    </span>
                    <div className="hero-actions">
                      <Link href={`/listings/${item.id}`}>Open listing detail</Link>
                      <Link href={`/developments/${item.development_id}`}>Open development</Link>
                      {item.source_url ? (
                        <a href={item.source_url} target="_blank" rel="noreferrer">
                          Open source listing
                        </a>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No comparable listings matched the current listing yet.</p>
            )}
          </article>

          <article className="panel detail-span-2">
            <h2>Timeline</h2>
            {events.length > 0 ? (
              <ul className="listing-event-list">
                {events.map((item) => (
                  <li key={item.id} className="listing-event-item">
                    <div className="listing-event-head">
                      <strong>{item.listing_title ?? detail.title ?? "Listing event"}</strong>
                      <span className={`listing-event-badge listing-event-badge-${item.event_type}`}>
                        {formatEventType(item.event_type)}
                      </span>
                    </div>
                    <span>{formatDateTime(item.event_at)}</span>
                    <span>{formatPrice(item.old_price_hkd)} → {formatPrice(item.new_price_hkd)}</span>
                    <span>{formatListingStatus(item.old_status ?? "new")} → {formatListingStatus(item.new_status)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No listing events recorded yet.</p>
            )}
          </article>
        </section>
      ) : null}
    </main>
  );
}
