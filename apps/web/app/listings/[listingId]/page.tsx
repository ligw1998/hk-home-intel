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
        const [detailResponse, eventsResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/listings/${listingId}?lang=zh-Hant`),
          fetch(`${API_BASE}/api/v1/listings/${listingId}/events?lang=zh-Hant`),
        ]);
        if (!detailResponse.ok) {
          throw new Error(`listing detail HTTP ${detailResponse.status}`);
        }
        if (!eventsResponse.ok) {
          throw new Error(`listing events HTTP ${eventsResponse.status}`);
        }
        const detailPayload = (await detailResponse.json()) as ListingDetail;
        const eventsPayload = (await eventsResponse.json()) as ListingEvent[];
        if (!cancelled) {
          setDetail(detailPayload);
          setEvents(eventsPayload);
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
        <p className="eyebrow">Phase 3A</p>
        <h1>{detail?.title ?? "Listing Detail"}</h1>
        <p className="lead">
          Review the normalized commercial listing fields and recent change events for a single source listing.
        </p>
        <div className="hero-actions">
          <Link href="/listings">Back to listing feed</Link>
          {detail ? <Link href={`/developments/${detail.development_id}`}>Open development</Link> : null}
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

          <article className="panel detail-span-2">
            <h2>Recent Events</h2>
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
