"use client";

import type { SearchPreset } from "./map-types";
import { DEFAULT_SEGMENTS, applyPresetCriteria, toggleNumberValue, toggleStringValue } from "./map-utils";
import { SEGMENT_OPTIONS } from "../lib/segment";

const SOURCE_OPTIONS = [
  { value: "all", label: "All sources" },
  { value: "srpe", label: "Official / SRPE" },
  { value: "centanet", label: "Centanet" },
  { value: "ricacorp", label: "Ricacorp" },
];

type Props = {
  search: string;
  setSearch: (value: string) => void;
  maxBudgetHkd: string;
  setMaxBudgetHkd: (value: string) => void;
  maxAgeYears: string;
  setMaxAgeYears: (value: string) => void;
  region: string;
  setRegion: (value: string) => void;
  district: string;
  setDistrict: (value: string) => void;
  regions: string[];
  districts: string[];
  minBudgetHkd: string;
  setMinBudgetHkd: (value: string) => void;
  sourceFilter: string;
  setSourceFilter: (value: string) => void;
  segments: string[];
  setSegments: (value: string[]) => void;
  bedroomValues: number[];
  setBedroomValues: (value: number[]) => void;
  minSaleableAreaSqft: string;
  setMinSaleableAreaSqft: (value: string) => void;
  maxSaleableAreaSqft: string;
  setMaxSaleableAreaSqft: (value: string) => void;
  watchlistOnly: boolean;
  setWatchlistOnly: (value: boolean) => void;
  showLaunchWatch: boolean;
  setShowLaunchWatch: (value: boolean) => void;
  loading: boolean;
  developmentsCount: number;
  watchlistCount: number;
  primaryMarketCount: number;
  secondHandCount: number;
  mixedCount: number;
  launchWatchCount: number;
  presetName: string;
  setPresetName: (value: string) => void;
  presetNote: string;
  setPresetNote: (value: string) => void;
  presets: SearchPreset[];
  saveCurrentPreset: () => Promise<void>;
  deletePreset: (presetId: string) => Promise<void>;
  applySuggestedBuyerFocus: () => void;
  clearPreferenceFilters: () => void;
  presetInfo: string | null;
};

export function MapFilterSidebar(props: Props) {
  const {
    search,
    setSearch,
    maxBudgetHkd,
    setMaxBudgetHkd,
    maxAgeYears,
    setMaxAgeYears,
    region,
    setRegion,
    district,
    setDistrict,
    regions,
    districts,
    minBudgetHkd,
    setMinBudgetHkd,
    sourceFilter,
    setSourceFilter,
    segments,
    setSegments,
    bedroomValues,
    setBedroomValues,
    minSaleableAreaSqft,
    setMinSaleableAreaSqft,
    maxSaleableAreaSqft,
    setMaxSaleableAreaSqft,
    watchlistOnly,
    setWatchlistOnly,
    showLaunchWatch,
    setShowLaunchWatch,
    loading,
    developmentsCount,
    watchlistCount,
    primaryMarketCount,
    secondHandCount,
    mixedCount,
    launchWatchCount,
    presetName,
    setPresetName,
    presetNote,
    setPresetNote,
    presets,
    saveCurrentPreset,
    deletePreset,
    applySuggestedBuyerFocus,
    clearPreferenceFilters,
    presetInfo,
  } = props;

  return (
    <aside className="panel filter-panel">
      <h2>Preference Filters</h2>
      <label className="field">
        <span>Search</span>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Development / district" />
      </label>
      <label className="field">
        <span>Budget Ceiling (HKD)</span>
        <input type="number" min="0" value={maxBudgetHkd} onChange={(event) => setMaxBudgetHkd(event.target.value)} placeholder="18000000" />
      </label>
      <label className="field">
        <span>Max Age (Years)</span>
        <input type="number" min="0" value={maxAgeYears} onChange={(event) => setMaxAgeYears(event.target.value)} placeholder="10" />
      </label>
      <label className="field">
        <span>Region</span>
        <select value={region} onChange={(event) => setRegion(event.target.value)}>
          <option value="all">All regions</option>
          {regions.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </label>
      <label className="field">
        <span>District</span>
        <select value={district} onChange={(event) => setDistrict(event.target.value)}>
          <option value="all">All districts</option>
          {districts.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Budget Floor (HKD)</span>
        <input type="number" min="0" value={minBudgetHkd} onChange={(event) => setMinBudgetHkd(event.target.value)} placeholder="8000000" />
      </label>
      <label className="field">
        <span>Source</span>
        <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}>
          {SOURCE_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
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
                onChange={() => setSegments(toggleStringValue(segments, item.value))}
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
                onChange={() => setBedroomValues(toggleNumberValue(bedroomValues, value))}
              />
              <span>{value === 0 ? "Studio" : `${value} rooms`}</span>
            </label>
          ))}
        </div>
      </div>

      <label className="field">
        <span>Min Saleable Area (sqft)</span>
        <input type="number" min="0" value={minSaleableAreaSqft} onChange={(event) => setMinSaleableAreaSqft(event.target.value)} />
      </label>
      <label className="field">
        <span>Max Saleable Area (sqft)</span>
        <input type="number" min="0" value={maxSaleableAreaSqft} onChange={(event) => setMaxSaleableAreaSqft(event.target.value)} />
      </label>

      <label className="checkbox-field">
        <input type="checkbox" checked={watchlistOnly} onChange={(event) => setWatchlistOnly(event.target.checked)} />
        <span>Watchlist only</span>
      </label>

      <label className="checkbox-field">
        <input type="checkbox" checked={showLaunchWatch} onChange={(event) => setShowLaunchWatch(event.target.checked)} />
        <span>Show launch-watch</span>
      </label>

      <p className="muted">
        {loading ? "Refreshing development candidates..." : `Showing ${developmentsCount} developments matched to the current preference set.`}
      </p>
      <p className="muted">
        Default view is broad live data. Use <code>Apply buyer focus</code> when you want the tighter 800萬-1800萬 / 400-750呎（約 37-70 平方米） / 2房優先 / 10年內 filter.
      </p>

      <dl className="kv-list compact-kv-list">
        <div><dt>Watchlist</dt><dd>{watchlistCount}</dd></div>
        <div><dt>Primary market</dt><dd>{primaryMarketCount}</dd></div>
        <div><dt>Second-hand</dt><dd>{secondHandCount}</dd></div>
        <div><dt>Mixed</dt><dd>{mixedCount}</dd></div>
        <div><dt>Launch-watch</dt><dd>{launchWatchCount}</dd></div>
      </dl>

      <div className="legend">
        <div><span className="legend-dual-bubbles"><span className="bubble bubble-new legend-bubble" /><span className="bubble bubble-primary legend-bubble" /></span><small>Primary market: new + first-hand remaining</small></div>
        <div><span className="bubble bubble-secondary legend-bubble" /><small>Second-hand</small></div>
        <div><span className="bubble bubble-muted legend-bubble" /><small>Mixed</small></div>
        <div><span className="bubble bubble-launch-watch legend-bubble" /><small>Launch watch</small></div>
        <div><span className="legend-dashed-ring" /><small>Approx. launch-watch</small></div>
        <div><span className="legend-ring" /><small>Selected / watchlist ring</small></div>
      </div>

      <div className="hero-actions">
        <button type="button" className="action-button action-button-secondary" onClick={applySuggestedBuyerFocus}>
          Apply buyer focus
        </button>
        <button type="button" className="action-button action-button-secondary" onClick={clearPreferenceFilters}>
          Clear filters
        </button>
      </div>
      {presetInfo ? <p className="muted">{presetInfo}</p> : null}

      <div className="plan-editor">
        <strong>Save Preset</strong>
        <label className="field">
          <span>Name</span>
          <input value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Buyer Focus" />
        </label>
        <label className="field">
          <span>Note</span>
          <input value={presetNote} onChange={(event) => setPresetNote(event.target.value)} placeholder="800萬-1800萬、400-750呎（約 37-70 平方米）、2房優先，再看3房、1房、開放式。" />
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
                  <button type="button" className="action-button" onClick={() => void deletePreset(preset.id)}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </aside>
  );
}
