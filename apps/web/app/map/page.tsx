"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { CompareToggleButton } from "../components/compare-toggle-button";
import { formatListingSegment, SEGMENT_OPTIONS } from "../lib/segment";

type DevelopmentSummary = {
  id: string;
  source_url: string | null;
  display_name: string | null;
  district: string | null;
  region: string | null;
  completion_year: number | null;
  age_years: number | null;
  listing_segment: string;
  lat: number | null;
  lng: number | null;
  active_listing_count: number;
  active_listing_min_price_hkd: number | null;
  active_listing_bedroom_options: number[];
};

type DevelopmentListResponse = {
  items: DevelopmentSummary[];
  total: number;
};

type WatchlistItem = {
  development_id: string;
  decision_stage: string;
};

type SearchPresetCriteria = {
  region: string | null;
  district: string | null;
  search: string | null;
  listing_segments: string[];
  max_budget_hkd: number | null;
  bedroom_values: number[];
  max_age_years: number | null;
  watchlist_only: boolean;
};

type SearchPreset = {
  id: string;
  name: string;
  scope: string;
  note: string | null;
  is_default: boolean;
  criteria: SearchPresetCriteria;
  updated_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const DEFAULT_SEGMENTS = ["new", "first_hand_remaining", "second_hand"];
const SUGGESTED_BEDROOM_VALUES = [2, 3, 1];

const DevelopmentLeafletMap = dynamic(
  () =>
    import("../components/development-leaflet-map").then((mod) => mod.DevelopmentLeafletMap),
  {
    ssr: false,
    loading: () => <p className="muted">Loading interactive map...</p>,
  },
);

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

function toggleStringValue(values: string[], value: string): string[] {
  if (values.includes(value)) {
    return values.filter((item) => item !== value);
  }
  return [...values, value];
}

function toggleNumberValue(values: number[], value: number): number[] {
  if (values.includes(value)) {
    return values.filter((item) => item !== value);
  }
  return [...values, value];
}

function buildCriteriaFromState(input: {
  region: string;
  district: string;
  search: string;
  segments: string[];
  maxBudgetHkd: string;
  bedroomValues: number[];
  maxAgeYears: string;
  watchlistOnly: boolean;
}): SearchPresetCriteria {
  return {
    region: input.region === "all" ? null : input.region,
    district: input.district === "all" ? null : input.district,
    search: input.search.trim() || null,
    listing_segments: input.segments,
    max_budget_hkd: input.maxBudgetHkd === "" ? null : Number(input.maxBudgetHkd),
    bedroom_values: input.bedroomValues,
    max_age_years: input.maxAgeYears === "" ? null : Number(input.maxAgeYears),
    watchlist_only: input.watchlistOnly,
  };
}

function applyPresetCriteria(
  criteria: SearchPresetCriteria,
  setters: {
    setRegion: (value: string) => void;
    setDistrict: (value: string) => void;
    setSearch: (value: string) => void;
    setSegments: (value: string[]) => void;
    setMaxBudgetHkd: (value: string) => void;
    setBedroomValues: (value: number[]) => void;
    setMaxAgeYears: (value: string) => void;
    setWatchlistOnly: (value: boolean) => void;
  },
) {
  setters.setRegion(criteria.region ?? "all");
  setters.setDistrict(criteria.district ?? "all");
  setters.setSearch(criteria.search ?? "");
  setters.setSegments(criteria.listing_segments.length > 0 ? criteria.listing_segments : DEFAULT_SEGMENTS);
  setters.setMaxBudgetHkd(criteria.max_budget_hkd !== null ? String(criteria.max_budget_hkd) : "");
  setters.setBedroomValues(criteria.bedroom_values);
  setters.setMaxAgeYears(criteria.max_age_years !== null ? String(criteria.max_age_years) : "");
  setters.setWatchlistOnly(criteria.watchlist_only);
}

function MapPageContent() {
  const searchParams = useSearchParams();
  const [developments, setDevelopments] = useState<DevelopmentSummary[]>([]);
  const [presets, setPresets] = useState<SearchPreset[]>([]);
  const [watchlistByDevelopment, setWatchlistByDevelopment] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("all");
  const [district, setDistrict] = useState("all");
  const [segments, setSegments] = useState<string[]>(DEFAULT_SEGMENTS);
  const [maxBudgetHkd, setMaxBudgetHkd] = useState("");
  const [bedroomValues, setBedroomValues] = useState<number[]>([]);
  const [maxAgeYears, setMaxAgeYears] = useState("");
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [presetName, setPresetName] = useState("Buyer Focus");
  const [presetNote, setPresetNote] = useState("2房優先、1600萬內、樓齡10年內為主。");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [presetInfo, setPresetInfo] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadStaticContext() {
      try {
        const [watchlistResponse, presetsResponse] = await Promise.all([
          fetch(`${API_BASE}/api/v1/watchlist?lang=zh-Hant`),
          fetch(`${API_BASE}/api/v1/search-presets?scope=development_map`),
        ]);
        if (!watchlistResponse.ok) {
          throw new Error(`watchlist HTTP ${watchlistResponse.status}`);
        }
        if (!presetsResponse.ok) {
          throw new Error(`search presets HTTP ${presetsResponse.status}`);
        }
        const watchlistPayload = (await watchlistResponse.json()) as WatchlistItem[];
        const presetsPayload = (await presetsResponse.json()) as SearchPreset[];
        if (!cancelled) {
          setWatchlistByDevelopment(
            Object.fromEntries(
              watchlistPayload.map((item) => [item.development_id, item.decision_stage]),
            ),
          );
          setPresets(presetsPayload);
          const defaultPreset = presetsPayload.find((item) => item.is_default);
          if (defaultPreset) {
            applyPresetCriteria(defaultPreset.criteria, {
              setRegion,
              setDistrict,
              setSearch,
              setSegments,
              setMaxBudgetHkd,
              setBedroomValues,
              setMaxAgeYears,
              setWatchlistOnly,
            });
            setPresetName(defaultPreset.name);
            setPresetNote(defaultPreset.note ?? "");
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    loadStaticContext();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadDevelopments() {
      try {
        setLoading(true);
        const params = new URLSearchParams({
          lang: "zh-Hant",
          limit: "500",
          has_coordinates: "true",
        });
        if (region !== "all") {
          params.set("region", region);
        }
        if (district !== "all") {
          params.set("district", district);
        }
        if (search.trim()) {
          params.set("q", search.trim());
        }
        if (segments.length > 0) {
          params.set("listing_segments", segments.join(","));
        }
        if (maxBudgetHkd !== "") {
          params.set("max_budget_hkd", maxBudgetHkd);
        }
        if (bedroomValues.length > 0) {
          params.set("bedroom_values", bedroomValues.join(","));
        }
        if (maxAgeYears !== "") {
          params.set("max_age_years", maxAgeYears);
        }
        const developmentResponse = await fetch(`${API_BASE}/api/v1/developments?${params.toString()}`);
        if (!developmentResponse.ok) {
          throw new Error(`developments HTTP ${developmentResponse.status}`);
        }
        const payload = (await developmentResponse.json()) as DevelopmentListResponse;
        if (!cancelled) {
          const filteredByWatchlist = watchlistOnly
            ? payload.items.filter((item) => Boolean(watchlistByDevelopment[item.id]))
            : payload.items;
          setDevelopments(filteredByWatchlist);
          const requestedSelectedId = searchParams.get("selected");
          setSelectedId((current) => {
            if (requestedSelectedId && filteredByWatchlist.some((item) => item.id === requestedSelectedId)) {
              return requestedSelectedId;
            }
            if (current && filteredByWatchlist.some((item) => item.id === current)) {
              return current;
            }
            return filteredByWatchlist[0]?.id ?? null;
          });
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

    loadDevelopments();
    return () => {
      cancelled = true;
    };
  }, [bedroomValues, district, maxAgeYears, maxBudgetHkd, region, search, searchParams, segments, watchlistByDevelopment, watchlistOnly]);

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

  const selected = developments.find((item) => item.id === selectedId) ?? developments[0] ?? null;
  const watchlistCount = developments.filter((item) => Boolean(watchlistByDevelopment[item.id])).length;
  const newCount = developments.filter((item) => item.listing_segment === "new").length;
  const firstHandCount = developments.filter((item) => item.listing_segment === "first_hand_remaining").length;
  const secondHandCount = developments.filter((item) => item.listing_segment === "second_hand").length;
  const mixedCount = developments.filter((item) => item.listing_segment === "mixed").length;

  function applySuggestedBuyerFocus() {
    setSegments(DEFAULT_SEGMENTS);
    setMaxBudgetHkd("16000000");
    setBedroomValues(SUGGESTED_BEDROOM_VALUES);
    setMaxAgeYears("10");
    setWatchlistOnly(false);
    setPresetInfo("Applied buyer-focus filter: <= 1600萬, 2房 > 3房 > 1房, age <= 10.");
  }

  function clearPreferenceFilters() {
    setSearch("");
    setRegion("all");
    setDistrict("all");
    setSegments(DEFAULT_SEGMENTS);
    setMaxBudgetHkd("");
    setBedroomValues([]);
    setMaxAgeYears("");
    setWatchlistOnly(false);
    setPresetInfo("Cleared filters. Showing broad live map view.");
  }

  async function reloadPresets() {
    const response = await fetch(`${API_BASE}/api/v1/search-presets?scope=development_map`);
    if (!response.ok) {
      throw new Error(`search presets HTTP ${response.status}`);
    }
    const payload = (await response.json()) as SearchPreset[];
    setPresets(payload);
  }

  async function saveCurrentPreset() {
    setPresetInfo("Saving current filter preset...");
    const criteria = buildCriteriaFromState({
      region,
      district,
      search,
      segments,
      maxBudgetHkd,
      bedroomValues,
      maxAgeYears,
      watchlistOnly,
    });
    try {
      const response = await fetch(`${API_BASE}/api/v1/search-presets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: presetName,
          scope: "development_map",
          note: presetNote || null,
          is_default: false,
          criteria,
        }),
      });
      if (!response.ok) {
        const message = response.status === 409
          ? "Preset name already exists. Rename it or replace later."
          : `search preset save HTTP ${response.status}`;
        throw new Error(message);
      }
      await reloadPresets();
      setPresetInfo(`Saved preset: ${presetName}`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setPresetInfo(null);
    }
  }

  async function deletePreset(presetId: string) {
    setPresetInfo("Deleting preset...");
    try {
      const response = await fetch(`${API_BASE}/api/v1/search-presets/${presetId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`search preset delete HTTP ${response.status}`);
      }
      await reloadPresets();
      setPresetInfo("Preset deleted.");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setPresetInfo(null);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Phase 3B</p>
        <h1>Preference Map Workspace</h1>
        <p className="lead">
          Start from your actual buying constraints: budget, bedroom preference, property segment,
          and age. Save repeatable presets instead of rebuilding the same shortlist filter every time.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          {selected ? <Link href={`/developments/${selected.id}`}>Open selected detail</Link> : null}
          <Link href="/activity">Open activity</Link>
          <Link href="/watchlist">Open watchlist</Link>
          <Link href="/system">Open system</Link>
          <button type="button" className="action-button action-button-secondary" onClick={applySuggestedBuyerFocus}>
            Apply buyer focus
          </button>
          <button type="button" className="action-button action-button-secondary" onClick={clearPreferenceFilters}>
            Clear filters
          </button>
        </div>
        {presetInfo ? <p className="muted">{presetInfo}</p> : null}
      </section>

      <section className="map-layout">
        <aside className="panel filter-panel">
          <h2>Preference Filters</h2>
          <label className="field">
            <span>Search</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Development / district"
            />
          </label>
          <label className="field">
            <span>Budget Ceiling (HKD)</span>
            <input
              type="number"
              min="0"
              value={maxBudgetHkd}
              onChange={(event) => setMaxBudgetHkd(event.target.value)}
              placeholder="16000000"
            />
          </label>
          <label className="field">
            <span>Max Age (Years)</span>
            <input
              type="number"
              min="0"
              value={maxAgeYears}
              onChange={(event) => setMaxAgeYears(event.target.value)}
              placeholder="10"
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

          <div className="field">
            <span>Segments</span>
            <div className="checkbox-stack">
              {SEGMENT_OPTIONS.filter((item) => item.value !== "all").map((item) => (
                <label key={item.value} className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={segments.includes(item.value)}
                    onChange={() => setSegments((current) => toggleStringValue(current, item.value))}
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="field">
            <span>Bedroom Preference</span>
            <div className="checkbox-stack">
              {[2, 3, 1, 4].map((value) => (
                <label key={value} className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={bedroomValues.includes(value)}
                    onChange={() => setBedroomValues((current) => toggleNumberValue(current, value))}
                  />
                  <span>{value === 4 ? "4+ rooms" : `${value} rooms`}</span>
                </label>
              ))}
            </div>
          </div>

          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={watchlistOnly}
              onChange={(event) => setWatchlistOnly(event.target.checked)}
            />
            <span>Watchlist only</span>
          </label>

          <p className="muted">
            {loading
              ? "Refreshing development candidates..."
              : `Showing ${developments.length} developments matched to the current preference set.`}
          </p>
          <p className="muted">
            Default view is broad live data. Use <code>Apply buyer focus</code> when you want the
            tighter 1600萬 / 2房優先 / 10年內 filter.
          </p>

          <dl className="kv-list compact-kv-list">
            <div>
              <dt>Watchlist</dt>
              <dd>{watchlistCount}</dd>
            </div>
            <div>
              <dt>New</dt>
              <dd>{newCount}</dd>
            </div>
            <div>
              <dt>First-hand</dt>
              <dd>{firstHandCount}</dd>
            </div>
            <div>
              <dt>Second-hand</dt>
              <dd>{secondHandCount}</dd>
            </div>
            <div>
              <dt>Mixed</dt>
              <dd>{mixedCount}</dd>
            </div>
          </dl>

          <div className="legend">
            <div>
              <span className="bubble bubble-primary legend-bubble" />
              <small>First-hand remaining</small>
            </div>
            <div>
              <span className="bubble bubble-secondary legend-bubble" />
              <small>Second-hand</small>
            </div>
            <div>
              <span className="bubble bubble-muted legend-bubble" />
              <small>Mixed</small>
            </div>
            <div>
              <span className="legend-ring" />
              <small>In watchlist</small>
            </div>
          </div>

          <div className="plan-editor">
            <strong>Save Preset</strong>
            <label className="field">
              <span>Name</span>
              <input
                value={presetName}
                onChange={(event) => setPresetName(event.target.value)}
                placeholder="Buyer Focus"
              />
            </label>
            <label className="field">
              <span>Note</span>
              <input
                value={presetNote}
                onChange={(event) => setPresetNote(event.target.value)}
                placeholder="2房優先、1600萬內、樓齡10年內為主。"
              />
            </label>
            <button type="button" className="action-button" onClick={() => void saveCurrentPreset()}>
              Save current filter
            </button>
          </div>

          {presets.length > 0 ? (
            <div className="plan-editor">
              <strong>Saved Presets</strong>
              <div className="preset-list">
                {presets.map((preset) => (
                  <div key={preset.id} className="preset-item">
                    <div>
                      <strong>{preset.name}</strong>
                      <p className="muted">{preset.note ?? "No note"}</p>
                    </div>
                    <div className="watchlist-actions">
                      <button
                        type="button"
                        className="action-button action-button-secondary"
                        onClick={() =>
                          applyPresetCriteria(preset.criteria, {
                            setRegion,
                            setDistrict,
                            setSearch,
                            setSegments,
                            setMaxBudgetHkd,
                            setBedroomValues,
                            setMaxAgeYears,
                            setWatchlistOnly,
                          })
                        }
                      >
                        Apply
                      </button>
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => void deletePreset(preset.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </aside>

        <section className="panel map-panel">
          <h2>Map</h2>
          {error ? (
            <p className="muted">Map data unavailable: {error}</p>
          ) : developments.length > 0 ? (
            <DevelopmentLeafletMap
              developments={developments}
              selectedId={selected?.id ?? null}
              watchlistByDevelopment={watchlistByDevelopment}
              onSelect={setSelectedId}
            />
          ) : (
            <div className="empty-state">
              <p className="muted">No coordinate-backed developments matched the current preference set.</p>
              <p className="muted">
                This usually means the current budget / bedroom / age filters are stricter than the
                imported live data coverage. Try <code>Clear filters</code> first.
              </p>
            </div>
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
              <span>{formatListingSegment(selected.listing_segment)}</span>
              <span>
                {selected.active_listing_count > 0
                  ? `${selected.active_listing_count} active listing(s) / from ${formatPrice(selected.active_listing_min_price_hkd)}`
                  : "No active listing rows yet"}
              </span>
              <span>
                {selected.active_listing_bedroom_options.length > 0
                  ? `Bedrooms ${selected.active_listing_bedroom_options.join(", ")}`
                  : "Bedrooms TBD"}
              </span>
              {watchlistByDevelopment[selected.id] ? (
                <span>Watchlist / {watchlistByDevelopment[selected.id]}</span>
              ) : null}
              <span>
                {selected.age_years !== null
                  ? `${selected.age_years} years`
                  : selected.completion_year
                    ? `Completion ${selected.completion_year}`
                    : "Age TBD"}
              </span>
              <span>
                {selected.lat?.toFixed(5)}, {selected.lng?.toFixed(5)}
              </span>
              <div className="hero-actions">
                <Link href={`/developments/${selected.id}`}>Open detail page</Link>
                <Link href={`/compare?ids=${selected.id}`}>Compare</Link>
                <CompareToggleButton
                  developmentId={selected.id}
                  developmentName={selected.display_name ?? selected.id}
                />
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
            {developments.map((item) => (
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
                <span>
                  {item.district ?? "Unknown district"} / {formatListingSegment(item.listing_segment)}
                </span>
                <span>
                  {formatPrice(item.active_listing_min_price_hkd)}
                  {" / "}
                  {item.active_listing_bedroom_options.length > 0
                    ? `${item.active_listing_bedroom_options.join(", ")} rooms`
                    : "rooms TBD"}
                </span>
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
