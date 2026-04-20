"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { CompareToggleButton } from "../components/compare-toggle-button";
import { MoneyValue } from "../components/money-value";
import { formatListingSegment, SEGMENT_OPTIONS } from "../lib/segment";

type DevelopmentSummary = {
  id: string;
  source_url: string | null;
  available_sources: string[];
  source_links: { source: string; url: string }[];
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
  active_listing_saleable_area_values: number[];
  active_listing_bedroom_options: number[];
};

type LaunchWatchMapItem = {
  id: string;
  display_name: string;
  district: string | null;
  region: string | null;
  expected_launch_window: string | null;
  launch_stage: string;
  signal_bucket: string;
  signal_label: string;
  official_site_url: string | null;
  source_url: string | null;
  linked_development_id: string | null;
  linked_development_name: string | null;
  note: string | null;
  lat: number | null;
  lng: number | null;
  coordinate_mode: string;
};

type DevelopmentListResponse = {
  items: DevelopmentSummary[];
  total: number;
};

type LaunchWatchResponse = {
  items: LaunchWatchMapItem[];
  total: number;
};

type DevelopmentDetailResponse = DevelopmentSummary & {
  source_confidence: string;
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
  min_budget_hkd: number | null;
  max_budget_hkd: number | null;
  bedroom_values: number[];
  min_saleable_area_sqft: number | null;
  max_saleable_area_sqft: number | null;
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
const SUGGESTED_BEDROOM_VALUES = [2, 3, 1, 0];
const SOURCE_OPTIONS = [
  { value: "all", label: "All sources" },
  { value: "srpe", label: "Official / SRPE" },
  { value: "centanet", label: "Centanet" },
  { value: "ricacorp", label: "Ricacorp" },
];

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

function buildWhyNow(item: DevelopmentSummary): string {
  const reasons: string[] = [];
  if (item.active_listing_count >= 5) {
    reasons.push("盘面活跃");
  } else if (item.active_listing_count > 0) {
    reasons.push("已有在售盘源");
  }
  if (
    item.active_listing_min_price_hkd !== null &&
    item.active_listing_min_price_hkd >= 8_000_000 &&
    item.active_listing_min_price_hkd <= 18_000_000
  ) {
    reasons.push("最低叫价落在目标价值带内");
  }
  if (item.active_listing_bedroom_options.includes(2)) {
    reasons.push("有 2 房信号");
  } else if (item.active_listing_bedroom_options.includes(3)) {
    reasons.push("有 3 房信号");
  } else if (item.active_listing_bedroom_options.includes(1)) {
    reasons.push("有 1 房信号");
  } else if (item.active_listing_bedroom_options.includes(0)) {
    reasons.push("至少有开放式信号");
  }
  if (item.active_listing_saleable_area_values.some((value) => value >= 400 && value <= 750)) {
    reasons.push("已有 400-750 尺户型");
  }
  if (item.listing_segment === "new" || item.listing_segment === "first_hand_remaining") {
    reasons.push("属于新盘 / 一手范围");
  } else if (item.age_years !== null && item.age_years <= 10) {
    reasons.push("楼龄仍在优先窗口内");
  }
  return reasons.length > 0 ? reasons.slice(0, 3).join("，") + "。" : "目前更适合作为待观察地图点。";
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
  minBudgetHkd: string;
  maxBudgetHkd: string;
  bedroomValues: number[];
  minSaleableAreaSqft: string;
  maxSaleableAreaSqft: string;
  maxAgeYears: string;
  watchlistOnly: boolean;
}): SearchPresetCriteria {
  return {
    region: input.region === "all" ? null : input.region,
    district: input.district === "all" ? null : input.district,
    search: input.search.trim() || null,
    listing_segments: input.segments,
    min_budget_hkd: input.minBudgetHkd === "" ? null : Number(input.minBudgetHkd),
    max_budget_hkd: input.maxBudgetHkd === "" ? null : Number(input.maxBudgetHkd),
    bedroom_values: input.bedroomValues,
    min_saleable_area_sqft:
      input.minSaleableAreaSqft === "" ? null : Number(input.minSaleableAreaSqft),
    max_saleable_area_sqft:
      input.maxSaleableAreaSqft === "" ? null : Number(input.maxSaleableAreaSqft),
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
    setMinBudgetHkd: (value: string) => void;
    setMaxBudgetHkd: (value: string) => void;
    setBedroomValues: (value: number[]) => void;
    setMinSaleableAreaSqft: (value: string) => void;
    setMaxSaleableAreaSqft: (value: string) => void;
    setMaxAgeYears: (value: string) => void;
    setWatchlistOnly: (value: boolean) => void;
  },
) {
  setters.setRegion(criteria.region ?? "all");
  setters.setDistrict(criteria.district ?? "all");
  setters.setSearch(criteria.search ?? "");
  setters.setSegments(criteria.listing_segments.length > 0 ? criteria.listing_segments : DEFAULT_SEGMENTS);
  setters.setMinBudgetHkd(criteria.min_budget_hkd !== null ? String(criteria.min_budget_hkd) : "");
  setters.setMaxBudgetHkd(criteria.max_budget_hkd !== null ? String(criteria.max_budget_hkd) : "");
  setters.setBedroomValues(criteria.bedroom_values);
  setters.setMinSaleableAreaSqft(
    criteria.min_saleable_area_sqft !== null ? String(criteria.min_saleable_area_sqft) : "",
  );
  setters.setMaxSaleableAreaSqft(
    criteria.max_saleable_area_sqft !== null ? String(criteria.max_saleable_area_sqft) : "",
  );
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
  const [sourceFilter, setSourceFilter] = useState("all");
  const [minBudgetHkd, setMinBudgetHkd] = useState("");
  const [maxBudgetHkd, setMaxBudgetHkd] = useState("");
  const [bedroomValues, setBedroomValues] = useState<number[]>([]);
  const [minSaleableAreaSqft, setMinSaleableAreaSqft] = useState("");
  const [maxSaleableAreaSqft, setMaxSaleableAreaSqft] = useState("");
  const [maxAgeYears, setMaxAgeYears] = useState("");
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [showLaunchWatch, setShowLaunchWatch] = useState(true);
  const [launchWatchItems, setLaunchWatchItems] = useState<LaunchWatchMapItem[]>([]);
  const [selectedLaunchWatchId, setSelectedLaunchWatchId] = useState<string | null>(null);
  const [presetName, setPresetName] = useState("Buyer Focus");
  const [presetNote, setPresetNote] = useState("800萬-1800萬、400-750呎（約 37-70 平方米）、2房優先，再看3房、1房、開放式。");
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
              setMinBudgetHkd,
              setMaxBudgetHkd,
              setBedroomValues,
              setMinSaleableAreaSqft,
              setMaxSaleableAreaSqft,
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

    async function loadLaunchWatch() {
      if (!showLaunchWatch) {
        setLaunchWatchItems([]);
        setSelectedLaunchWatchId(null);
        return;
      }
      try {
        const response = await fetch(`${API_BASE}/api/v1/launch-watch?lang=zh-Hant`);
        if (!response.ok) {
          throw new Error(`launch-watch HTTP ${response.status}`);
        }
        const payload = (await response.json()) as LaunchWatchResponse;
        if (!cancelled) {
          const filtered = payload.items.filter((item) => item.lat !== null && item.lng !== null);
          setLaunchWatchItems(filtered);
          setSelectedLaunchWatchId((current) =>
            current && filtered.some((item) => item.id === current) ? current : null,
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    void loadLaunchWatch();
    return () => {
      cancelled = true;
    };
  }, [showLaunchWatch]);

  useEffect(() => {
    let cancelled = false;

    async function loadDevelopments() {
      try {
        setLoading(true);
        const requestedSelectedId = searchParams.get("selected");
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
        if (sourceFilter !== "all") {
          params.set("source", sourceFilter);
        }
        if (maxBudgetHkd !== "") {
          params.set("max_budget_hkd", maxBudgetHkd);
        }
        if (minBudgetHkd !== "") {
          params.set("min_budget_hkd", minBudgetHkd);
        }
        if (bedroomValues.length > 0) {
          params.set("bedroom_values", bedroomValues.join(","));
        }
        if (minSaleableAreaSqft !== "") {
          params.set("min_saleable_area_sqft", minSaleableAreaSqft);
        }
        if (maxSaleableAreaSqft !== "") {
          params.set("max_saleable_area_sqft", maxSaleableAreaSqft);
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
          let filteredByWatchlist = watchlistOnly
            ? payload.items.filter((item) => Boolean(watchlistByDevelopment[item.id]))
            : payload.items;
          if (
            requestedSelectedId &&
            !filteredByWatchlist.some((item) => item.id === requestedSelectedId)
          ) {
            const selectedResponse = await fetch(
              `${API_BASE}/api/v1/developments/${requestedSelectedId}?lang=zh-Hant`,
            );
            if (selectedResponse.ok) {
              const selectedPayload =
                (await selectedResponse.json()) as DevelopmentDetailResponse;
              if (
                selectedPayload.lat !== null &&
                selectedPayload.lng !== null
              ) {
                filteredByWatchlist = [selectedPayload, ...filteredByWatchlist];
              }
            }
          }
          setDevelopments(filteredByWatchlist);
          setSelectedId((current) => {
            if (requestedSelectedId && filteredByWatchlist.some((item) => item.id === requestedSelectedId)) {
              return requestedSelectedId;
            }
            if (current && filteredByWatchlist.some((item) => item.id === current)) {
              return current;
            }
            return null;
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
  }, [bedroomValues, district, maxAgeYears, maxBudgetHkd, maxSaleableAreaSqft, minBudgetHkd, minSaleableAreaSqft, region, search, searchParams, segments, sourceFilter, watchlistByDevelopment, watchlistOnly]);

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

  const selected = developments.find((item) => item.id === selectedId) ?? null;
  const selectedLaunchWatch =
    launchWatchItems.find((item) => item.id === selectedLaunchWatchId) ?? null;
  const watchlistCount = developments.filter((item) => Boolean(watchlistByDevelopment[item.id])).length;
  const primaryMarketCount = developments.filter(
    (item) => item.listing_segment === "new" || item.listing_segment === "first_hand_remaining",
  ).length;
  const secondHandCount = developments.filter((item) => item.listing_segment === "second_hand").length;
  const mixedCount = developments.filter((item) => item.listing_segment === "mixed").length;
  const launchWatchCount = launchWatchItems.length;

  function applySuggestedBuyerFocus() {
    setSegments(DEFAULT_SEGMENTS);
    setSourceFilter("all");
    setMinBudgetHkd("8000000");
    setMaxBudgetHkd("18000000");
    setBedroomValues(SUGGESTED_BEDROOM_VALUES);
    setMinSaleableAreaSqft("400");
    setMaxSaleableAreaSqft("750");
    setMaxAgeYears("10");
    setWatchlistOnly(false);
    setShowLaunchWatch(true);
    setPresetInfo("Applied buyer-focus filter: 800萬-1800萬, 400-750呎, 2房 > 3房 > 1房 > 開放式, age <= 10.");
  }

  function clearPreferenceFilters() {
    setSearch("");
    setRegion("all");
    setDistrict("all");
    setSegments(DEFAULT_SEGMENTS);
    setSourceFilter("all");
    setMinBudgetHkd("");
    setMaxBudgetHkd("");
    setBedroomValues([]);
    setMinSaleableAreaSqft("");
    setMaxSaleableAreaSqft("");
    setMaxAgeYears("");
    setWatchlistOnly(false);
    setShowLaunchWatch(true);
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
      minBudgetHkd,
      maxBudgetHkd,
      bedroomValues,
      minSaleableAreaSqft,
      maxSaleableAreaSqft,
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
        <p className="eyebrow">Map Workspace</p>
        <h1>Preference Map Workspace</h1>
        <p className="lead">
          Start from your actual buying constraints: budget, bedroom preference, property segment,
          and age. Save repeatable presets instead of rebuilding the same shortlist filter every time.
        </p>
        <div className="hero-actions">
          <Link href="/">Back to dashboard</Link>
          {selected ? <Link href={`/developments/${selected.id}`}>Selected detail</Link> : null}
          <Link href="/shortlist">Shortlist</Link>
          <Link href="/activity">Activity</Link>
          <Link href="/watchlist">Watchlist</Link>
          <Link href="/system">System</Link>
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
              placeholder="18000000"
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
          <label className="field">
            <span>Budget Floor (HKD)</span>
            <input
              type="number"
              min="0"
              value={minBudgetHkd}
              onChange={(event) => setMinBudgetHkd(event.target.value)}
              placeholder="8000000"
            />
          </label>
          <label className="field">
            <span>Source</span>
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}>
              {SOURCE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
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
              {[2, 3, 1, 0].map((value) => (
                <label key={value} className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={bedroomValues.includes(value)}
                    onChange={() => setBedroomValues((current) => toggleNumberValue(current, value))}
                  />
                  <span>{value === 0 ? "Studio" : `${value} rooms`}</span>
                </label>
              ))}
            </div>
          </div>

          <label className="field">
            <span>Min Saleable Area (sqft)</span>
            <input
              type="number"
              min="0"
              value={minSaleableAreaSqft}
              onChange={(event) => setMinSaleableAreaSqft(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Max Saleable Area (sqft)</span>
            <input
              type="number"
              min="0"
              value={maxSaleableAreaSqft}
              onChange={(event) => setMaxSaleableAreaSqft(event.target.value)}
            />
          </label>

          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={watchlistOnly}
              onChange={(event) => setWatchlistOnly(event.target.checked)}
            />
            <span>Watchlist only</span>
          </label>

          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={showLaunchWatch}
              onChange={(event) => setShowLaunchWatch(event.target.checked)}
            />
            <span>Show launch-watch</span>
          </label>

          <p className="muted">
            {loading
              ? "Refreshing development candidates..."
              : `Showing ${developments.length} developments matched to the current preference set.`}
          </p>
          <p className="muted">
            Default view is broad live data. Use <code>Apply buyer focus</code> when you want the
            tighter 800萬-1800萬 / 400-750呎（約 37-70 平方米） / 2房優先 / 10年內 filter.
          </p>

          <dl className="kv-list compact-kv-list">
            <div>
              <dt>Watchlist</dt>
              <dd>{watchlistCount}</dd>
            </div>
            <div>
              <dt>Primary market</dt>
              <dd>{primaryMarketCount}</dd>
            </div>
            <div>
              <dt>Second-hand</dt>
              <dd>{secondHandCount}</dd>
            </div>
            <div>
              <dt>Mixed</dt>
              <dd>{mixedCount}</dd>
            </div>
            <div>
              <dt>Launch-watch</dt>
              <dd>{launchWatchCount}</dd>
            </div>
          </dl>

          <div className="legend">
            <div>
              <span className="legend-dual-bubbles">
                <span className="bubble bubble-new legend-bubble" />
                <span className="bubble bubble-primary legend-bubble" />
              </span>
              <small>Primary market: new + first-hand remaining</small>
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
              <span className="bubble bubble-launch-watch legend-bubble" />
              <small>Launch watch</small>
            </div>
            <div>
              <span className="legend-dashed-ring" />
              <small>Approx. launch-watch</small>
            </div>
            <div>
              <span className="legend-ring" />
              <small>Selected / watchlist ring</small>
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
                placeholder="800萬-1800萬、400-750呎（約 37-70 平方米）、2房優先，再看3房、1房、開放式。"
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
                            setMinBudgetHkd,
                            setMaxBudgetHkd,
                            setBedroomValues,
                            setMinSaleableAreaSqft,
                            setMaxSaleableAreaSqft,
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
          ) : developments.length > 0 || launchWatchItems.length > 0 ? (
            <DevelopmentLeafletMap
              developments={developments}
              launchWatchItems={launchWatchItems}
              selectedId={selectedId}
              selectedLaunchWatchId={selectedLaunchWatchId}
              watchlistByDevelopment={watchlistByDevelopment}
              onSelect={(id) => {
                setSelectedLaunchWatchId(null);
                setSelectedId(id);
              }}
              onSelectLaunchWatch={(id) => {
                setSelectedId(null);
                setSelectedLaunchWatchId(id);
              }}
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
          <div className="detail-panel-scroll">
            {selectedLaunchWatch ? (
              <div className="selected-card">
                <strong>{selectedLaunchWatch.display_name}</strong>
                <span>
                  {selectedLaunchWatch.district ?? "Unknown district"}
                  {selectedLaunchWatch.region ? ` / ${selectedLaunchWatch.region}` : ""}
                </span>
                <span>{selectedLaunchWatch.signal_label} / {selectedLaunchWatch.launch_stage}</span>
                {selectedLaunchWatch.expected_launch_window ? (
                  <span>{selectedLaunchWatch.expected_launch_window}</span>
                ) : null}
                {selectedLaunchWatch.linked_development_name ? (
                  <span>Linked / {selectedLaunchWatch.linked_development_name}</span>
                ) : null}
                {selectedLaunchWatch.note ? <span className="decision-why-now">{selectedLaunchWatch.note}</span> : null}
                <span>
                  {selectedLaunchWatch.lat?.toFixed(5)}, {selectedLaunchWatch.lng?.toFixed(5)}
                </span>
                <div className="hero-actions">
                  <Link href="/launch-watch">Open launch watch</Link>
                  {selectedLaunchWatch.linked_development_id ? (
                    <Link href={`/developments/${selectedLaunchWatch.linked_development_id}`}>Open linked development</Link>
                  ) : null}
                  {selectedLaunchWatch.official_site_url ? (
                    <a href={selectedLaunchWatch.official_site_url} target="_blank" rel="noreferrer">
                      Official site
                    </a>
                  ) : null}
                  {selectedLaunchWatch.source_url ? (
                    <a href={selectedLaunchWatch.source_url} target="_blank" rel="noreferrer">
                      Source signal
                    </a>
                  ) : null}
                </div>
              </div>
            ) : selected ? (
              <div className="selected-card">
                <strong>{selected.display_name ?? selected.id}</strong>
                <span>
                  {selected.district ?? "Unknown district"}
                  {selected.region ? ` / ${selected.region}` : ""}
                </span>
                <span>{formatListingSegment(selected.listing_segment)}</span>
                <span>
                  {selected.active_listing_count > 0
                    ? (
                      <>
                        {selected.active_listing_count} active listing(s) / from{" "}
                        <MoneyValue amount={selected.active_listing_min_price_hkd} />
                      </>
                    )
                    : "No active listing rows yet"}
                </span>
                <span className="decision-why-now">Why now: {buildWhyNow(selected)}</span>
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
                  {selected.source_links.length === 1 ? (
                    <a href={selected.source_links[0].url} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                  ) : selected.source_url ? (
                    <a href={selected.source_url} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                  ) : null}
                </div>
                {selected.source_links.length > 1 ? (
                  <details className="source-link-menu">
                    <summary>Open source</summary>
                    <div className="source-link-list">
                      {selected.source_links.map((item) => (
                        <a key={item.source} href={item.url} target="_blank" rel="noreferrer">
                          {item.source}
                        </a>
                      ))}
                    </div>
                  </details>
                ) : null}
              </div>
            ) : (
              <p className="muted">Select a point on the map.</p>
            )}

            {showLaunchWatch && launchWatchItems.length > 0 ? (
              <div className="map-list">
                {launchWatchItems.map((item) => (
                  <button
                    key={`launch-watch-list-${item.id}`}
                    type="button"
                    className={`map-list-item ${item.id === selectedLaunchWatch?.id ? "map-list-item-active" : ""}`}
                    onClick={() => {
                      setSelectedId(null);
                      setSelectedLaunchWatchId(item.id);
                    }}
                  >
                    <strong>{item.display_name} · launch-watch</strong>
                    <span>
                      {item.district ?? "Unknown district"} / {item.signal_label}
                    </span>
                    <span>{item.expected_launch_window ?? "window TBD"}</span>
                  </button>
                ))}
              </div>
            ) : null}

            <div className="map-list">
              {developments.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`map-list-item ${item.id === selected?.id ? "map-list-item-active" : ""}`}
                  onClick={() => {
                    setSelectedLaunchWatchId(null);
                    setSelectedId(item.id);
                  }}
                >
                  <strong>
                    {item.display_name ?? item.id}
                    {watchlistByDevelopment[item.id] ? " · saved" : ""}
                  </strong>
                  <span>
                    {item.district ?? "Unknown district"} / {formatListingSegment(item.listing_segment)}
                  </span>
                  <span>
                    <MoneyValue amount={item.active_listing_min_price_hkd} interactive={false} />
                    {" / "}
                    {item.active_listing_bedroom_options.length > 0
                      ? `${item.active_listing_bedroom_options.join(", ")} rooms`
                      : "rooms TBD"}
                  </span>
                </button>
              ))}
            </div>
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
