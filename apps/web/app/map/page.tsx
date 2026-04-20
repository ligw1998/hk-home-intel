"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { MapFilterSidebar } from "./map-filter-sidebar";
import { MapSelectedSidebar } from "./map-selected-sidebar";
import type {
  DevelopmentDetailResponse,
  DevelopmentListResponse,
  DevelopmentSummary,
  LaunchWatchMapItem,
  LaunchWatchResponse,
  SearchPreset,
  SearchPresetCriteria,
  WatchlistItem,
} from "./map-types";
import {
  DEFAULT_SEGMENTS,
  SUGGESTED_BEDROOM_VALUES,
  applyPresetCriteria,
  buildCriteriaFromState,
} from "./map-utils";

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
        <MapFilterSidebar
          search={search}
          setSearch={setSearch}
          maxBudgetHkd={maxBudgetHkd}
          setMaxBudgetHkd={setMaxBudgetHkd}
          maxAgeYears={maxAgeYears}
          setMaxAgeYears={setMaxAgeYears}
          region={region}
          setRegion={setRegion}
          district={district}
          setDistrict={setDistrict}
          regions={regions}
          districts={districts}
          minBudgetHkd={minBudgetHkd}
          setMinBudgetHkd={setMinBudgetHkd}
          sourceFilter={sourceFilter}
          setSourceFilter={setSourceFilter}
          segments={segments}
          setSegments={setSegments}
          bedroomValues={bedroomValues}
          setBedroomValues={setBedroomValues}
          minSaleableAreaSqft={minSaleableAreaSqft}
          setMinSaleableAreaSqft={setMinSaleableAreaSqft}
          maxSaleableAreaSqft={maxSaleableAreaSqft}
          setMaxSaleableAreaSqft={setMaxSaleableAreaSqft}
          watchlistOnly={watchlistOnly}
          setWatchlistOnly={setWatchlistOnly}
          showLaunchWatch={showLaunchWatch}
          setShowLaunchWatch={setShowLaunchWatch}
          loading={loading}
          developmentsCount={developments.length}
          watchlistCount={watchlistCount}
          primaryMarketCount={primaryMarketCount}
          secondHandCount={secondHandCount}
          mixedCount={mixedCount}
          launchWatchCount={launchWatchCount}
          presetName={presetName}
          setPresetName={setPresetName}
          presetNote={presetNote}
          setPresetNote={setPresetNote}
          presets={presets}
          saveCurrentPreset={saveCurrentPreset}
          deletePreset={deletePreset}
          applySuggestedBuyerFocus={applySuggestedBuyerFocus}
          clearPreferenceFilters={clearPreferenceFilters}
          presetInfo={presetInfo}
        />

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

        <MapSelectedSidebar
          selected={selected}
          selectedLaunchWatch={selectedLaunchWatch}
          watchlistByDevelopment={watchlistByDevelopment}
          developments={developments}
          launchWatchItems={showLaunchWatch ? launchWatchItems : []}
          setSelectedId={setSelectedId}
          setSelectedLaunchWatchId={setSelectedLaunchWatchId}
        />
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
