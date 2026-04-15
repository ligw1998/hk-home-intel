import Link from "next/link";

type CompareDevelopmentItem = {
  id: string;
  source: string | null;
  source_url: string | null;
  display_name: string | null;
  district: string | null;
  region: string | null;
  listing_segment: string;
  source_confidence: string;
  completion_year: number | null;
  age_years: number | null;
  developer_names: string[];
  address: string | null;
  active_listing_count: number;
  active_listing_min_price_hkd: number | null;
  active_listing_max_price_hkd: number | null;
  active_listing_bedroom_options: number[];
  active_listing_bedroom_mix: Record<string, number>;
  active_listing_source_counts: Record<string, number>;
  latest_listing_event_at: string | null;
  current_min_price_hkd: number | null;
  current_max_price_hkd: number | null;
  overall_min_price_hkd: number | null;
  overall_max_price_hkd: number | null;
  price_history_point_count: number;
};

type CompareDevelopmentsResponse = {
  focus_development_id: string | null;
  items: CompareDevelopmentItem[];
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

function formatBedroomMix(mix: Record<string, number>): string {
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

function formatSourceMix(mix: Record<string, number>): string {
  const parts = Object.entries(mix)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([source, count]) => `${source} × ${count}`);
  return parts.length > 0 ? parts.join(" / ") : "No active source rows";
}

async function fetchCompare(ids: string[]): Promise<CompareDevelopmentsResponse | null> {
  if (ids.length === 0) {
    return null;
  }
  const params = new URLSearchParams();
  for (const id of ids) {
    params.append("development_id", id);
  }
  const response = await fetch(`${API_BASE}/api/v1/compare/developments?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`compare HTTP ${response.status}`);
  }
  return (await response.json()) as CompareDevelopmentsResponse;
}

async function fetchSuggestions(id: string): Promise<CompareSuggestionsResponse | null> {
  const response = await fetch(`${API_BASE}/api/v1/compare/developments/${id}/suggestions?limit=6`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`suggestions HTTP ${response.status}`);
  }
  return (await response.json()) as CompareSuggestionsResponse;
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const rawIds = params.ids;
  const ids = Array.from(
    new Set(
      (Array.isArray(rawIds) ? rawIds.join(",") : rawIds ?? "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );

  const compare = ids.length > 0 ? await fetchCompare(ids) : null;
  const focusId = compare?.focus_development_id ?? ids[0] ?? null;
  const suggestions = focusId ? await fetchSuggestions(focusId) : null;

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Compare</p>
        <h1>Development Compare</h1>
        <p className="lead">
          Compare multiple developments side by side, then use the suggested comparables panel to
          add nearby or similarly priced stock into the same review workflow.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          <Link href="/map">Open map</Link>
          <Link href="/listings">Open listing feed</Link>
          <Link href="/watchlist">Open watchlist</Link>
        </div>
      </section>

      <section className="compare-layout">
        <article className="panel compare-main">
          <h2>Selected Developments</h2>
          {compare && compare.items.length > 0 ? (
            <div className="compare-grid">
              {compare.items.map((item) => (
                <article key={item.id} className="compare-card">
                  <div className="listing-event-head">
                    <strong>{item.display_name ?? item.id}</strong>
                    <span className="status-pill">{item.active_listing_count} active</span>
                  </div>
                  <span className="compare-card-meta">
                    {item.source ?? "unknown source"}
                    {" / "}
                    {item.district ?? "Unknown district"}
                    {item.region ? ` / ${item.region}` : ""}
                  </span>
                  <dl className="kv-list compact-kv-list">
                    <div>
                      <dt>Current Band</dt>
                      <dd>{formatPrice(item.current_min_price_hkd)} → {formatPrice(item.current_max_price_hkd)}</dd>
                    </div>
                    <div>
                      <dt>Observed Range</dt>
                      <dd>{formatPrice(item.overall_min_price_hkd)} → {formatPrice(item.overall_max_price_hkd)}</dd>
                    </div>
                    <div>
                      <dt>Bedroom Mix</dt>
                      <dd>{formatBedroomMix(item.active_listing_bedroom_mix)}</dd>
                    </div>
                    <div>
                      <dt>Source Mix</dt>
                      <dd>{formatSourceMix(item.active_listing_source_counts)}</dd>
                    </div>
                    <div>
                      <dt>Completion / Age</dt>
                      <dd>{item.completion_year ?? "TBD"} / {item.age_years ?? "TBD"}</dd>
                    </div>
                    <div>
                      <dt>Latest Event</dt>
                      <dd>{formatDateTime(item.latest_listing_event_at)}</dd>
                    </div>
                    <div>
                      <dt>Developers</dt>
                      <dd>{item.developer_names.length > 0 ? item.developer_names.join(" / ") : "TBD"}</dd>
                    </div>
                  </dl>
                  <div className="hero-actions">
                    <Link
                      href={
                        (() => {
                          const nextIds = compare.items
                            .map((row) => row.id)
                            .filter((developmentId) => developmentId !== item.id);
                          return nextIds.length > 0 ? `/compare?ids=${nextIds.join(",")}` : "/compare";
                        })()
                      }
                    >
                      Remove from compare
                    </Link>
                    <Link href={`/developments/${item.id}`}>Open detail</Link>
                    <Link href={`/listings?development_id=${item.id}`}>Focus listing feed</Link>
                    {item.source_url ? (
                      <a href={item.source_url} target="_blank" rel="noreferrer">
                        Open source page
                      </a>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted">
              Open this page with one or more development ids, for example
              {" "}
              <code>/compare?ids=&lt;development_id_1&gt;,&lt;development_id_2&gt;</code>.
            </p>
          )}
        </article>

        <aside className="compare-sidebar">
          <article className="panel">
            <h2>Suggested Comparables</h2>
            {suggestions && suggestions.items.length > 0 ? (
              <ul className="development-list">
                {suggestions.items.map((item) => {
                  const nextIds = Array.from(new Set([...(compare?.items.map((row) => row.id) ?? []), item.development.id]));
                  return (
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
                        <Link href={`/compare?ids=${nextIds.join(",")}`}>Add to compare</Link>
                        <Link href={`/developments/${item.development.id}`}>Open detail</Link>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted">
                No close comparables cleared the current scoring threshold. This usually means the
                available candidates are too far away in district, size, or asking-price band, so
                the compare engine is choosing not to show noisy matches.
              </p>
            )}
          </article>
        </aside>
      </section>
    </main>
  );
}
