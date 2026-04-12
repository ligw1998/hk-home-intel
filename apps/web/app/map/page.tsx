"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

type DevelopmentSummary = {
  id: string;
  source_url: string | null;
  display_name: string | null;
  district: string | null;
  region: string | null;
  completion_year: number | null;
  listing_segment: string;
  lat: number | null;
  lng: number | null;
};

type DevelopmentListResponse = {
  items: DevelopmentSummary[];
  total: number;
};

type WatchlistItem = {
  development_id: string;
  decision_stage: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const DevelopmentLeafletMap = dynamic(
  () =>
    import("../components/development-leaflet-map").then((mod) => mod.DevelopmentLeafletMap),
  {
    ssr: false,
    loading: () => <p className="muted">Loading interactive map...</p>,
  },
);

function MapPageContent() {
  const searchParams = useSearchParams();
  const [developments, setDevelopments] = useState<DevelopmentSummary[]>([]);
  const [watchlistByDevelopment, setWatchlistByDevelopment] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("all");
  const [district, setDistrict] = useState("all");
  const [segment, setSegment] = useState("all");
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadDevelopments() {
      try {
        const [developmentResponse, watchlistResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/developments?lang=zh-Hant&limit=500&has_coordinates=true`),
          fetch(`${API_BASE}/api/v1/watchlist?lang=zh-Hant`),
        ]);
        if (!developmentResponse.ok) {
          throw new Error(`developments HTTP ${developmentResponse.status}`);
        }
        if (!watchlistResponse.ok) {
          throw new Error(`watchlist HTTP ${watchlistResponse.status}`);
        }
        const payload = (await developmentResponse.json()) as DevelopmentListResponse;
        const watchlistPayload = (await watchlistResponse.json()) as WatchlistItem[];
        if (!cancelled) {
          setDevelopments(payload.items);
          setWatchlistByDevelopment(
            Object.fromEntries(
              watchlistPayload.map((item) => [item.development_id, item.decision_stage]),
            ),
          );
          setSelectedId(searchParams.get("selected") ?? payload.items[0]?.id ?? null);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    loadDevelopments();
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  const regions = useMemo(() => {
    return Array.from(
      new Set(
        developments
          .map((item) => item.region)
          .filter((item): item is string => typeof item === "string" && item.length > 0),
      ),
    ).sort();
  }, [developments]);

  const districts = useMemo(() => {
    return Array.from(
      new Set(
        developments
          .map((item) => item.district)
          .filter((item): item is string => typeof item === "string" && item.length > 0),
      ),
    ).sort();
  }, [developments]);

  const filtered = useMemo(() => {
    return developments.filter((item) => {
      const matchesSearch =
        search.trim() === "" ||
        `${item.display_name ?? ""} ${item.district ?? ""} ${item.region ?? ""}`
          .toLowerCase()
          .includes(search.trim().toLowerCase());
      const matchesRegion = region === "all" || item.region === region;
      const matchesDistrict = district === "all" || item.district === district;
      const matchesSegment = segment === "all" || item.listing_segment === segment;
      const matchesWatchlist = !watchlistOnly || Boolean(watchlistByDevelopment[item.id]);
      return matchesSearch && matchesRegion && matchesDistrict && matchesSegment && matchesWatchlist;
    });
  }, [developments, district, region, search, segment, watchlistOnly, watchlistByDevelopment]);

  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0] ?? null;
  const watchlistCount = filtered.filter((item) => Boolean(watchlistByDevelopment[item.id])).length;
  const firstHandCount = filtered.filter((item) => item.listing_segment === "first_hand_remaining").length;

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Map View</p>
        <h1>Hong Kong Development Map</h1>
        <p className="lead">
          Phase 2 map workspace for SRPE-backed developments with real map tiles, coordinate-aware
          filtering, and direct detail handoff.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          {selected ? <Link href={`/developments/${selected.id}`}>Open selected detail</Link> : null}
          <Link href="/activity">Open activity</Link>
          <Link href="/watchlist">Open watchlist</Link>
          <Link href="/system">Open system</Link>
        </div>
      </section>

      <section className="map-layout">
        <aside className="panel filter-panel">
          <h2>Filters</h2>
          <label className="field">
            <span>Search</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Development / district"
            />
          </label>
          <label className="field">
            <span>Region</span>
            <select value={region} onChange={(event) => setRegion(event.target.value)}>
              <option value="all">All regions</option>
              {regions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>District</span>
            <select value={district} onChange={(event) => setDistrict(event.target.value)}>
              <option value="all">All districts</option>
              {districts.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Segment</span>
            <select value={segment} onChange={(event) => setSegment(event.target.value)}>
              <option value="all">All segments</option>
              <option value="first_hand_remaining">first_hand_remaining</option>
              <option value="mixed">mixed</option>
            </select>
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={watchlistOnly}
              onChange={(event) => setWatchlistOnly(event.target.checked)}
            />
            <span>Watchlist only</span>
          </label>
          <p className="muted">
            Showing {filtered.length} / {developments.length} developments with coordinates.
          </p>
          <dl className="kv-list compact-kv-list">
            <div>
              <dt>Watchlist</dt>
              <dd>{watchlistCount}</dd>
            </div>
            <div>
              <dt>First-hand</dt>
              <dd>{firstHandCount}</dd>
            </div>
            <div>
              <dt>Other</dt>
              <dd>{filtered.length - firstHandCount}</dd>
            </div>
          </dl>
          <div className="legend">
            <div>
              <span className="bubble bubble-primary legend-bubble" />
              <small>First-hand remaining</small>
            </div>
            <div>
              <span className="bubble bubble-muted legend-bubble" />
              <small>Mixed / other</small>
            </div>
            <div>
              <span className="legend-ring" />
              <small>In watchlist</small>
            </div>
          </div>
        </aside>

        <section className="panel map-panel">
          <h2>Map</h2>
          {error ? (
            <p className="muted">Map data unavailable: {error}</p>
          ) : filtered.length > 0 ? (
            <DevelopmentLeafletMap
              developments={filtered}
              selectedId={selected?.id ?? null}
              watchlistByDevelopment={watchlistByDevelopment}
              onSelect={setSelectedId}
            />
          ) : (
            <p className="muted">No coordinate-backed developments matched the current filters.</p>
          )}
        </section>

        <aside className="panel detail-panel">
          <h2>Selected</h2>
          {selected ? (
            <div className="selected-card">
              <strong>{selected.display_name ?? selected.id}</strong>
              <span>
                {selected.district ?? "Unknown district"}
                {selected.region ? ` / ${selected.region}` : ""}
              </span>
              <span>{selected.listing_segment}</span>
              {watchlistByDevelopment[selected.id] ? (
                <span>Watchlist / {watchlistByDevelopment[selected.id]}</span>
              ) : null}
              <span>
                {selected.completion_year ? `Completion ${selected.completion_year}` : "Year TBD"}
              </span>
              <span>
                {selected.lat?.toFixed(5)}, {selected.lng?.toFixed(5)}
              </span>
              <div className="hero-actions">
                <Link href={`/developments/${selected.id}`}>Open detail page</Link>
                <Link href={`/activity?development_id=${selected.id}`}>Recent activity</Link>
                {selected.source_url ? (
                  <a href={selected.source_url} target="_blank" rel="noreferrer">
                    Open source
                  </a>
                ) : null}
              </div>
            </div>
          ) : (
            <p className="muted">Select a point on the map.</p>
          )}

          <div className="map-list">
            {filtered.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`map-list-item ${item.id === selected?.id ? "map-list-item-active" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <strong>
                  {item.display_name ?? item.id}
                  {watchlistByDevelopment[item.id] ? " · saved" : ""}
                </strong>
                <span>{item.district ?? "Unknown district"}</span>
              </button>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}

export default function MapPage() {
  return (
    <Suspense fallback={<main className="page-shell"><p className="muted">Loading map...</p></main>}>
      <MapPageContent />
    </Suspense>
  );
}
