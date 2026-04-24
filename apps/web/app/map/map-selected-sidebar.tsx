"use client";

import Link from "next/link";

import { CompareToggleButton } from "../components/compare-toggle-button";
import { MoneyValue } from "../components/money-value";
import { formatListingSegment } from "../lib/segment";
import type {
  DevelopmentLaunchWatchSignal,
  DevelopmentSummary,
  LaunchWatchMapItem,
} from "./map-types";
import { buildWhyNow, coverageLabel } from "./map-utils";

type Props = {
  selected: DevelopmentSummary | null;
  selectedLaunchWatch: LaunchWatchMapItem | null;
  linkedLaunchWatchSignals: DevelopmentLaunchWatchSignal[];
  watchlistByDevelopment: Record<string, string>;
  developments: DevelopmentSummary[];
  launchWatchItems: LaunchWatchMapItem[];
  setSelectedId: (id: string | null) => void;
  setSelectedLaunchWatchId: (id: string | null) => void;
};

function gapFlagLabel(flag: string): string {
  const labels: Record<string, string> = {
    missing_commercial_source: "Need commercial validation",
    srpe_only: "Official baseline only",
    missing_coordinates: "Missing map position",
    missing_completion_year: "Year proxy missing",
    missing_active_listing: "No active listings",
    missing_bedroom_coverage: "Bedroom mix incomplete",
    missing_saleable_area_coverage: "Area coverage incomplete",
  };
  return labels[flag] ?? flag.replaceAll("_", " ");
}

function gapFlagSeverity(flag: string): string {
  if (flag === "missing_coordinates" || flag === "missing_active_listing") {
    return "warning";
  }
  if (flag === "missing_commercial_source" || flag === "srpe_only") {
    return "info";
  }
  return "muted";
}

export function MapSelectedSidebar({
  selected,
  selectedLaunchWatch,
  linkedLaunchWatchSignals,
  watchlistByDevelopment,
  developments,
  launchWatchItems,
  setSelectedId,
  setSelectedLaunchWatchId,
}: Props) {
  return (
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
            {selectedLaunchWatch.expected_launch_window ? <span>{selectedLaunchWatch.expected_launch_window}</span> : null}
            {selectedLaunchWatch.linked_development_name ? <span>Linked / {selectedLaunchWatch.linked_development_name}</span> : null}
            {selectedLaunchWatch.note ? <span className="decision-why-now">{selectedLaunchWatch.note}</span> : null}
            <span>{selectedLaunchWatch.lat?.toFixed(5)}, {selectedLaunchWatch.lng?.toFixed(5)}</span>
            <div className="hero-actions">
              <Link href="/launch-watch">Open launch watch</Link>
              {selectedLaunchWatch.linked_development_id ? (
                <Link href={`/developments/${selectedLaunchWatch.linked_development_id}`}>Open linked development</Link>
              ) : null}
              {selectedLaunchWatch.official_site_url ? (
                <a href={selectedLaunchWatch.official_site_url} target="_blank" rel="noreferrer">Official site</a>
              ) : null}
              {selectedLaunchWatch.source_url ? (
                <a href={selectedLaunchWatch.source_url} target="_blank" rel="noreferrer">Source signal</a>
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
              {selected.active_listing_count > 0 ? (
                <>
                  {selected.active_listing_count} active listing(s) / from <MoneyValue amount={selected.active_listing_min_price_hkd} />
                </>
              ) : "No active listing rows yet"}
            </span>
            <span className="decision-why-now">Why now: {buildWhyNow(selected)}</span>
            <span className={`status-pill status-pill-${selected.coverage_status}`}>{coverageLabel(selected.coverage_status)}</span>
            {linkedLaunchWatchSignals.length > 0 ? (
              <>
                <span>
                  Launch watch / {linkedLaunchWatchSignals[0].signal_label}
                  {linkedLaunchWatchSignals.length > 1 ? ` +${linkedLaunchWatchSignals.length - 1}` : ""}
                </span>
                <div className="launch-watch-tag-row">
                  {linkedLaunchWatchSignals.map((signal) => (
                    <span key={signal.id} className="workflow-chip">
                      {signal.signal_label}
                    </span>
                  ))}
                </div>
                {linkedLaunchWatchSignals[0].expected_launch_window ? (
                  <span>{linkedLaunchWatchSignals[0].expected_launch_window}</span>
                ) : null}
              </>
            ) : null}
            {selected.coverage_notes.map((note) => <span key={note}>{note}</span>)}
            {selected.data_gap_flags.length > 0 ? (
              <div className="launch-watch-tag-row">
                {selected.data_gap_flags.map((flag) => (
                  <span key={flag} className={`gap-chip gap-chip-${gapFlagSeverity(flag)}`}>
                    {gapFlagLabel(flag)}
                  </span>
                ))}
              </div>
            ) : null}
            <span>
              {selected.active_listing_bedroom_options.length > 0
                ? `Bedrooms ${selected.active_listing_bedroom_options.join(", ")}`
                : "Bedrooms TBD"}
            </span>
            {watchlistByDevelopment[selected.id] ? <span>Watchlist / {watchlistByDevelopment[selected.id]}</span> : null}
            <span>
              {selected.age_years !== null ? `${selected.age_years} years` : selected.completion_year ? `Year proxy ${selected.completion_year}` : "Age TBD"}
            </span>
            <span>{selected.lat?.toFixed(5)}, {selected.lng?.toFixed(5)}</span>
            <div className="hero-actions">
              <Link href={`/developments/${selected.id}`}>Open detail page</Link>
              <Link href={`/compare?ids=${selected.id}`}>Compare</Link>
              <CompareToggleButton developmentId={selected.id} developmentName={selected.display_name ?? selected.id} />
              <Link href={`/activity?development_id=${selected.id}`}>Recent activity</Link>
              {linkedLaunchWatchSignals.length > 0 ? <Link href="/launch-watch">Launch watch</Link> : null}
              {selected.source_links.length === 1 ? (
                <a href={selected.source_links[0].url} target="_blank" rel="noreferrer">Open source</a>
              ) : selected.source_url ? (
                <a href={selected.source_url} target="_blank" rel="noreferrer">Open source</a>
              ) : null}
            </div>
            {selected.source_links.length > 1 ? (
              <details className="source-link-menu">
                <summary>Open source</summary>
                <div className="source-link-list">
                  {selected.source_links.map((item) => (
                    <a key={item.source} href={item.url} target="_blank" rel="noreferrer">{item.source}</a>
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        ) : (
          <p className="muted">Select a point on the map.</p>
        )}

        {launchWatchItems.length > 0 ? (
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
                <span>{item.district ?? "Unknown district"} / {item.signal_label}</span>
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
              <span>{item.district ?? "Unknown district"} / {formatListingSegment(item.listing_segment)}</span>
              <span>
                <MoneyValue amount={item.active_listing_min_price_hkd} interactive={false} />
                {" / "}
                {item.active_listing_bedroom_options.length > 0 ? `${item.active_listing_bedroom_options.join(", ")} rooms` : "rooms TBD"}
              </span>
              <span>{coverageLabel(item.coverage_status)}</span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
