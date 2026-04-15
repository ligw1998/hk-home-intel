import Link from "next/link";
import { notFound } from "next/navigation";

import { CompareToggleButton } from "../../components/compare-toggle-button";
import { WatchlistButton } from "../../components/watchlist-button";
import { formatEventType, formatListingStatus } from "../../lib/listing-events";
import { formatListingSegment } from "../../lib/segment";

type DocumentSummary = {
  id: string;
  source_doc_id: string;
  display_title: string;
  doc_type: string;
  source_url: string | null;
  published_at: string | null;
  file_path: string | null;
  mime_type: string | null;
};

type ListingSummary = {
  id: string;
  source: string;
  display_title: string | null;
  listing_type: string;
  asking_price_hkd: number | null;
  price_per_sqft: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  saleable_area_sqft: number | null;
  status: string;
  source_url: string | null;
};

type TransactionSummary = {
  id: string;
  transaction_date: string | null;
  price_hkd: number | null;
  transaction_type: string;
};

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

type DevelopmentDetail = {
  id: string;
  source_url: string | null;
  display_name: string | null;
  district: string | null;
  subdistrict: string | null;
  region: string | null;
  completion_year: number | null;
  listing_segment: string;
  source_confidence: string;
  lat: number | null;
  lng: number | null;
  active_listing_count: number;
  active_listing_min_price_hkd: number | null;
  active_listing_max_price_hkd: number | null;
  active_listing_bedroom_options: number[];
  active_listing_bedroom_mix: Record<string, number>;
  active_listing_source_counts: Record<string, number>;
  latest_listing_event_at: string | null;
  document_count: number;
  transaction_count: number;
  listings: ListingSummary[];
  documents: DocumentSummary[];
  transactions: TransactionSummary[];
};

type DevelopmentPriceHistoryPoint = {
  recorded_at: string;
  event_count: number;
  listing_count: number;
  min_price_hkd: number | null;
  max_price_hkd: number | null;
};

type DevelopmentPriceHistory = {
  development_id: string;
  point_count: number;
  latest_recorded_at: string | null;
  current_min_price_hkd: number | null;
  current_max_price_hkd: number | null;
  overall_min_price_hkd: number | null;
  overall_max_price_hkd: number | null;
  points: DevelopmentPriceHistoryPoint[];
};

type CompareDevelopmentItem = {
  id: string;
  source_url: string | null;
  display_name: string | null;
  district: string | null;
  region: string | null;
  listing_segment: string;
  current_min_price_hkd: number | null;
  current_max_price_hkd: number | null;
};

type CompareSuggestionItem = {
  development: CompareDevelopmentItem;
  match_score: number;
  reasons: string[];
};

type CompareSuggestionsResponse = {
  focus_development_id: string;
  items: CompareSuggestionItem[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function fetchDevelopmentDetail(developmentId: string): Promise<DevelopmentDetail | null> {
  const response = await fetch(`${API_BASE}/api/v1/developments/${developmentId}`, {
    cache: "no-store",
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`development HTTP ${response.status}`);
  }
  return (await response.json()) as DevelopmentDetail;
}

async function fetchDevelopmentListingEvents(
  developmentId: string,
): Promise<ListingFeedItem[]> {
  const response = await fetch(
    `${API_BASE}/api/v1/listings/feed?development_id=${developmentId}&limit=30`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`listing feed HTTP ${response.status}`);
  }
  return (await response.json()) as ListingFeedItem[];
}

async function fetchDevelopmentPriceHistory(
  developmentId: string,
): Promise<DevelopmentPriceHistory> {
  const response = await fetch(
    `${API_BASE}/api/v1/developments/${developmentId}/price-history`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`development price history HTTP ${response.status}`);
  }
  return (await response.json()) as DevelopmentPriceHistory;
}

async function fetchDevelopmentComparables(
  developmentId: string,
): Promise<CompareSuggestionsResponse> {
  const response = await fetch(
    `${API_BASE}/api/v1/compare/developments/${developmentId}/suggestions?limit=6`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`development comparables HTTP ${response.status}`);
  }
  return (await response.json()) as CompareSuggestionsResponse;
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

function formatCompactMoney(amount: number | null): string {
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

function formatDayLabel(value: string): string {
  return new Intl.DateTimeFormat("zh-HK", {
    dateStyle: "full",
  }).format(new Date(value));
}

function formatCompactDateTime(value: string | null): string {
  if (!value) {
    return "TBD";
  }
  return new Intl.DateTimeFormat("zh-HK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatBedroomMix(mix: Record<string, number>): string {
  const knownCount = Object.values(mix).reduce((sum, count) => sum + count, 0);
  const parts = Object.entries(mix)
    .sort(([left], [right]) => Number(left) - Number(right))
    .map(([bedrooms, count]) => {
      if (bedrooms === "0") {
        return `開放式 × ${count}`;
      }
      return `${bedrooms}房 × ${count}`;
    });
  return parts.length > 0 ? parts.join(" / ") : "No bedroom signal yet";
}

function formatBedroomCoverage(mix: Record<string, number>, total: number): string {
  const knownCount = Object.values(mix).reduce((sum, count) => sum + count, 0);
  const unknownCount = Math.max(0, total - knownCount);
  if (total === 0) {
    return "No active listings";
  }
  if (unknownCount === 0) {
    return `All ${total} listings carry bedroom data`;
  }
  return `${knownCount} / ${total} listings carry bedroom data, ${unknownCount} still unknown`;
}

function formatSourceMix(mix: Record<string, number>): string {
  const parts = Object.entries(mix)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([source, count]) => `${source} × ${count}`);
  return parts.length > 0 ? parts.join(" / ") : "No active source rows";
}

function formatBedroomLabel(value: number | null): string {
  if (value === null) {
    return "戶型待補";
  }
  if (value === 0) {
    return "開放式";
  }
  return `${value}房`;
}

function summarizeEvents(items: ListingFeedItem[]): Array<{ label: string; value: number }> {
  const total = items.length;
  const newListings = items.filter((item) => item.event_type === "new_listing").length;
  const priceMoves = items.filter(
    (item) => item.event_type === "price_drop" || item.event_type === "price_raise",
  ).length;
  const statusMoves = items.filter(
    (item) => item.event_type === "withdrawn" || item.event_type === "relist" || item.event_type === "sold",
  ).length;
  return [
    { label: "Events", value: total },
    { label: "New listings", value: newListings },
    { label: "Price moves", value: priceMoves },
    { label: "Status moves", value: statusMoves },
  ];
}

function groupEventsByDay(items: ListingFeedItem[]): Array<{ dateKey: string; label: string; items: ListingFeedItem[] }> {
  const grouped = new Map<string, ListingFeedItem[]>();
  for (const item of items) {
    const key = item.event_at.slice(0, 10);
    const bucket = grouped.get(key) ?? [];
    bucket.push(item);
    grouped.set(key, bucket);
  }
  return Array.from(grouped.entries()).map(([dateKey, dayItems]) => ({
    dateKey,
    label: formatDayLabel(dayItems[0].event_at),
    items: dayItems,
  }));
}

export default async function DevelopmentDetailPage({
  params,
}: {
  params: Promise<{ developmentId: string }>;
}) {
  const { developmentId } = await params;
  const [development, events, priceHistory, comparables] = await Promise.all([
    fetchDevelopmentDetail(developmentId),
    fetchDevelopmentListingEvents(developmentId),
    fetchDevelopmentPriceHistory(developmentId),
    fetchDevelopmentComparables(developmentId),
  ]);
  if (!development) {
    notFound();
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Development Detail</p>
        <h1>{development.display_name ?? development.id}</h1>
        <p className="lead">
          {development.district ?? "Unknown district"}
          {development.region ? ` / ${development.region}` : ""}
          {" / "}
          {formatListingSegment(development.listing_segment)}
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href={`/map?selected=${development.id}`}>Open in map</Link>
          <Link href={`/compare?ids=${development.id}`}>Compare view</Link>
          <CompareToggleButton
            developmentId={development.id}
            developmentName={development.display_name ?? development.id}
          />
          <Link href={`/activity?development_id=${development.id}`}>Recent activity</Link>
          <Link href={`/listings?development_id=${development.id}`}>Listing event feed</Link>
          <Link href="/watchlist">Open watchlist</Link>
          {development.source_url ? (
            <a href={development.source_url} target="_blank" rel="noreferrer">
              Open source page
            </a>
          ) : null}
        </div>
      </section>

      <section className="development-detail-layout">
        <aside className="development-sidebar">
          <article className="panel">
            <h2>Summary</h2>
            <WatchlistButton developmentId={development.id} />
            <dl className="kv-list">
              <div>
                <dt>Completion</dt>
                <dd>{development.completion_year ?? "TBD"}</dd>
              </div>
              <div>
                <dt>Source Confidence</dt>
                <dd>{development.source_confidence}</dd>
              </div>
              <div>
                <dt>Active Listings</dt>
                <dd>{development.active_listing_count}</dd>
              </div>
              <div>
                <dt>Documents</dt>
                <dd>{development.document_count}</dd>
              </div>
              <div>
                <dt>Transactions</dt>
                <dd>{development.transaction_count}</dd>
              </div>
              <div>
                <dt>Coordinates</dt>
                <dd>
                  {development.lat !== null && development.lng !== null
                    ? `${development.lat.toFixed(5)}, ${development.lng.toFixed(5)}`
                    : "Pending geocode"}
                </dd>
              </div>
            </dl>
          </article>

          <article className="panel">
            <h2>Current Market Snapshot</h2>
            <dl className="kv-list">
              <div>
                <dt>Price Band</dt>
                <dd>
                  {development.active_listing_count > 0
                    ? `${formatPrice(development.active_listing_min_price_hkd)} → ${formatPrice(development.active_listing_max_price_hkd)}`
                    : "No active price rows yet"}
                </dd>
              </div>
              <div>
                <dt>Bedroom Mix</dt>
                <dd>{formatBedroomMix(development.active_listing_bedroom_mix)}</dd>
              </div>
              <div>
                <dt>Bedroom Coverage</dt>
                <dd>{formatBedroomCoverage(development.active_listing_bedroom_mix, development.active_listing_count)}</dd>
              </div>
              <div>
                <dt>Source Mix</dt>
                <dd>{formatSourceMix(development.active_listing_source_counts)}</dd>
              </div>
              <div>
                <dt>Latest Listing Event</dt>
                <dd>{formatCompactDateTime(development.latest_listing_event_at)}</dd>
              </div>
            </dl>
          </article>
        </aside>

        <div className="development-main-stack">
        <article className="panel">
          <h2>Price Trail</h2>
          {priceHistory.points.length > 0 ? (
            <>
              <div className="listing-feed-stats">
                <div className="listing-feed-stat">
                  <strong>{priceHistory.point_count}</strong>
                  <span>Recorded snapshots</span>
                </div>
                <div className="listing-feed-stat">
                  <strong>{formatPrice(priceHistory.overall_min_price_hkd)}</strong>
                  <span>Overall min</span>
                </div>
                <div className="listing-feed-stat">
                  <strong>{formatPrice(priceHistory.overall_max_price_hkd)}</strong>
                  <span>Overall max</span>
                </div>
                <div className="listing-feed-stat">
                  <strong>{formatCompactDateTime(priceHistory.latest_recorded_at)}</strong>
                  <span>Latest recorded</span>
                </div>
              </div>
              <ul className="listing-event-list compact-listing-history">
                {priceHistory.points
                  .slice()
                  .reverse()
                  .map((point) => (
                    <li key={point.recorded_at} className="listing-event-item">
                      <div className="listing-event-head">
                        <strong>
                          {formatPrice(point.min_price_hkd)} → {formatPrice(point.max_price_hkd)}
                        </strong>
                        <span className="status-pill">
                          {point.event_count} event{point.event_count === 1 ? "" : "s"}
                        </span>
                      </div>
                      <span>{formatDateTime(point.recorded_at)}</span>
                      <span>
                        {point.listing_count} listing{point.listing_count === 1 ? "" : "s"} touched
                      </span>
                    </li>
                  ))}
              </ul>
            </>
          ) : (
            <p className="muted">No development-level price trail recorded yet.</p>
          )}
        </article>

        <article className="panel">
          <h2>Listings</h2>
          {development.listings.length > 0 ? (
            <ul className="development-list">
              {development.listings.map((item) => (
                <li key={item.id}>
                  <strong>
                    <Link href={`/listings/${item.id}`}>{item.display_title ?? "Untitled listing"}</Link>
                  </strong>
                  <span>
                    {formatListingSegment(item.listing_type)} / {formatListingStatus(item.status)} / {item.source}
                  </span>
                  <span>
                    {formatBedroomLabel(item.bedrooms)}
                    {item.bathrooms !== null ? ` / ${item.bathrooms}浴` : ""}
                    {item.saleable_area_sqft !== null ? ` / ${item.saleable_area_sqft} sqft` : ""}
                  </span>
                  <span>
                    {formatCompactMoney(item.asking_price_hkd)}
                    {item.price_per_sqft !== null ? ` / ${formatCompactMoney(item.price_per_sqft)} psf` : ""}
                  </span>
                  <div className="hero-actions">
                    <Link href={`/listings/${item.id}`}>Open listing detail</Link>
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
            <p className="muted">No active listing rows imported for this development yet.</p>
          )}
        </article>

        <article className="panel">
          <h2>Suggested Comparables</h2>
          {comparables.items.length > 0 ? (
            <ul className="development-list">
              {comparables.items.map((item) => (
                <li key={item.development.id}>
                  <strong>{item.development.display_name ?? item.development.id}</strong>
                  <span>
                    Score {item.match_score}
                    {item.reasons.length > 0 ? ` / ${item.reasons.join(" / ")}` : ""}
                  </span>
                  <span>
                    {formatPrice(item.development.current_min_price_hkd)} → {formatPrice(item.development.current_max_price_hkd)}
                  </span>
                  <div className="hero-actions">
                    <Link href={`/compare?ids=${development.id},${item.development.id}`}>Add to compare</Link>
                    <Link href={`/developments/${item.development.id}`}>Open detail</Link>
                    <Link href={`/listings?development_id=${item.development.id}`}>Open listing feed</Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No suggested comparables available for this development yet.</p>
          )}
        </article>

        <article className="panel">
          <h2>Listing Timeline</h2>
          {events.length > 0 ? (
            <div className="listing-feed-stats">
              {summarizeEvents(events).map((item) => (
                <div key={item.label} className="listing-feed-stat">
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          ) : null}
          {events.length > 0 ? (
            <div className="timeline-day-groups">
              {groupEventsByDay(events).map((group) => (
                <section key={group.dateKey} className="timeline-day-group">
                  <div className="timeline-day-header">
                    <strong>{group.label}</strong>
                    <span>{group.items.length} events</span>
                  </div>
                  <ul className="listing-event-list">
                    {group.items.map((item) => (
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
                          {formatPrice(item.old_price_hkd)} → {formatPrice(item.new_price_hkd)}
                        </span>
                        <span>
                          {formatListingStatus(item.old_status ?? "new")} → {formatListingStatus(item.new_status)}
                        </span>
                        <div className="hero-actions">
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
                </section>
              ))}
            </div>
          ) : (
            <p className="muted">No listing events recorded for this development yet.</p>
          )}
        </article>

        <article className="panel">
          <h2>Documents</h2>
          {development.documents.length > 0 ? (
            <ul className="development-list">
              {development.documents.map((item) => (
                <li key={item.id}>
                  <strong>{item.display_title}</strong>
                  <span>
                    {item.doc_type}
                    {item.published_at ? ` / ${item.published_at.slice(0, 10)}` : ""}
                  </span>
                  <span>
                    {item.file_path ? "downloaded locally" : "metadata only"}
                    {item.mime_type ? ` / ${item.mime_type}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No documents imported yet.</p>
          )}
        </article>

        <article className="panel">
          <h2>Transactions</h2>
          {development.transactions.length > 0 ? (
            <ul className="development-list">
              {development.transactions.map((item) => (
                <li key={item.id}>
                  <strong>{item.transaction_date ?? "Undated transaction"}</strong>
                  <span>{item.transaction_type}</span>
                  <span>{formatPrice(item.price_hkd)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No transaction rows imported yet.</p>
          )}
        </article>
        </div>
      </section>
    </main>
  );
}
