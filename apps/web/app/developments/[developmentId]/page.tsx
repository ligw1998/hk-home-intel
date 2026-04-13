import Link from "next/link";
import { notFound } from "next/navigation";

import { WatchlistButton } from "../../components/watchlist-button";

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
  display_title: string | null;
  listing_type: string;
  asking_price_hkd: number | null;
  status: string;
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
  document_count: number;
  transaction_count: number;
  listings: ListingSummary[];
  documents: DocumentSummary[];
  transactions: TransactionSummary[];
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
    `${API_BASE}/api/v1/listings/feed?development_id=${developmentId}&limit=10`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`listing feed HTTP ${response.status}`);
  }
  return (await response.json()) as ListingFeedItem[];
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

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-HK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default async function DevelopmentDetailPage({
  params,
}: {
  params: Promise<{ developmentId: string }>;
}) {
  const { developmentId } = await params;
  const [development, events] = await Promise.all([
    fetchDevelopmentDetail(developmentId),
    fetchDevelopmentListingEvents(developmentId),
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
          {development.listing_segment}
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href={`/map?selected=${development.id}`}>Open in map</Link>
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

      <section className="grid detail-grid">
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
          <h2>Listings</h2>
          {development.listings.length > 0 ? (
            <ul className="development-list">
              {development.listings.map((item) => (
                <li key={item.id}>
                  <strong>{item.display_title ?? "Untitled listing"}</strong>
                  <span>
                    {item.listing_type} / {item.status}
                  </span>
                  <span>{formatPrice(item.asking_price_hkd)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No active listing rows imported for this development yet.</p>
          )}
        </article>

        <article className="panel detail-span-2">
          <h2>Recent Listing Events</h2>
          {events.length > 0 ? (
            <ul className="listing-event-list">
              {events.map((item) => (
                <li key={item.id} className="listing-event-item">
                  <div className="listing-event-head">
                    <strong>{item.listing_title ?? item.development_name ?? "Listing event"}</strong>
                    <span className={`listing-event-badge listing-event-badge-${item.event_type}`}>
                      {item.event_type}
                    </span>
                  </div>
                  <span>
                    {item.source} / {formatDateTime(item.event_at)}
                  </span>
                  <span>
                    {formatPrice(item.old_price_hkd)} → {formatPrice(item.new_price_hkd)}
                  </span>
                  <span>
                    {item.old_status ?? "new"} → {item.new_status ?? "unknown"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No listing events recorded for this development yet.</p>
          )}
        </article>

        <article className="panel detail-span-2">
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

        <article className="panel detail-span-2">
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
      </section>
    </main>
  );
}
