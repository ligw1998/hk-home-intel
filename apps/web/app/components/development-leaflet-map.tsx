"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";

import { formatListingSegment } from "../lib/segment";

type DevelopmentSummary = {
  id: string;
  source_url: string | null;
  source_links: { source: string; url: string }[];
  display_name: string | null;
  district: string | null;
  region: string | null;
  completion_year: number | null;
  listing_segment: string;
  lat: number | null;
  lng: number | null;
};

type LaunchWatchMapItem = {
  id: string;
  display_name: string;
  district: string | null;
  region: string | null;
  expected_launch_window: string | null;
  launch_stage: string;
  official_site_url: string | null;
  source_url: string | null;
  linked_development_id: string | null;
  linked_development_name: string | null;
  note: string | null;
  lat: number | null;
  lng: number | null;
  coordinate_mode: string;
};

function segmentColor(segment: string): string {
  if (segment === "new") {
    return "#2563eb";
  }
  if (segment === "first_hand_remaining") {
    return "#f97316";
  }
  if (segment === "second_hand") {
    return "#2f855a";
  }
  if (segment === "mixed") {
    return "#64748b";
  }
  return "#6b7280";
}

function launchWatchColor(stage: string): string {
  if (stage === "selling" || stage === "watch-selling") {
    return "#be185d";
  }
  if (stage === "launch_watch") {
    return "#a21caf";
  }
  return "#9333ea";
}

const DEFAULT_MAP_CENTER: [number, number] = [22.2820, 114.1588];
const DEFAULT_MAP_ZOOM = 12;

function FitToDevelopments({
  items,
  enabled,
}: {
  items: DevelopmentSummary[];
  enabled: boolean;
}) {
  const map = useMap();

  useEffect(() => {
    if (!enabled) {
      map.setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM);
      return;
    }
    const points = items
      .filter((item) => item.lat !== null && item.lng !== null)
      .map((item) => [item.lat as number, item.lng as number] as [number, number]);

    if (points.length === 0) {
      map.setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM);
      return;
    }
    if (points.length === 1) {
      map.setView(points[0], 13);
      return;
    }
    map.fitBounds(points as LatLngBoundsExpression, { padding: [28, 28] });
  }, [items, map]);

  return null;
}

function PanToSelection({ item }: { item: DevelopmentSummary | null }) {
  const map = useMap();

  useEffect(() => {
    if (!item || item.lat === null || item.lng === null) {
      return;
    }
    map.flyTo([item.lat, item.lng], Math.max(map.getZoom(), 13), {
      duration: 0.8,
    });
  }, [item, map]);

  return null;
}

function PanToLaunchWatchSelection({ item }: { item: LaunchWatchMapItem | null }) {
  const map = useMap();

  useEffect(() => {
    if (!item || item.lat === null || item.lng === null) {
      return;
    }
    map.flyTo([item.lat, item.lng], Math.max(map.getZoom(), 13), {
      duration: 0.8,
    });
  }, [item, map]);

  return null;
}

function InvalidateOnFullscreen({ tick }: { tick: number }) {
  const map = useMap();

  useEffect(() => {
    const timer = window.setTimeout(() => {
      map.invalidateSize();
    }, 180);
    return () => {
      window.clearTimeout(timer);
    };
  }, [map, tick]);

  return null;
}

function buildDisplayCoordinateMap(
  developments: DevelopmentSummary[],
  launchWatchItems: LaunchWatchMapItem[],
): Record<string, [number, number]> {
  const grouped = new Map<string, Array<{ key: string; lat: number; lng: number }>>();
  const register = (key: string, lat: number | null, lng: number | null) => {
    if (lat === null || lng === null) {
      return;
    }
    const groupKey = `${lat.toFixed(4)}:${lng.toFixed(4)}`;
    const group = grouped.get(groupKey) ?? [];
    group.push({ key, lat, lng });
    grouped.set(groupKey, group);
  };
  developments.forEach((item) => register(item.id, item.lat, item.lng));
  launchWatchItems.forEach((item) => register(`launch-watch-${item.id}`, item.lat, item.lng));

  const positions: Record<string, [number, number]> = {};
  for (const group of grouped.values()) {
    const ordered = [...group].sort((left, right) => left.key.localeCompare(right.key));
    if (ordered.length === 1) {
      positions[ordered[0].key] = [ordered[0].lat, ordered[0].lng];
      continue;
    }
    ordered.forEach((item, index) => {
      const angle = (Math.PI * 2 * index) / ordered.length;
      const ring = Math.floor(index / 6);
      const distance = 0.00018 + ring * 0.00008;
      positions[item.key] = [
        item.lat + Math.sin(angle) * distance,
        item.lng + Math.cos(angle) * distance,
      ];
    });
  }
  return positions;
}

export function DevelopmentLeafletMap({
  developments,
  launchWatchItems,
  selectedId,
  selectedLaunchWatchId,
  watchlistByDevelopment,
  onSelect,
  onSelectLaunchWatch,
}: {
  developments: DevelopmentSummary[];
  launchWatchItems: LaunchWatchMapItem[];
  selectedId: string | null;
  selectedLaunchWatchId: string | null;
  watchlistByDevelopment: Record<string, string>;
  onSelect: (id: string) => void;
  onSelectLaunchWatch: (id: string) => void;
}) {
  const selected = developments.find((item) => item.id === selectedId) ?? null;
  const selectedLaunchWatch =
    launchWatchItems.find((item) => item.id === selectedLaunchWatchId) ?? null;
  const displayCoordinates = useMemo(
    () => buildDisplayCoordinateMap(developments, launchWatchItems),
    [developments, launchWatchItems],
  );
  const shellRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenTick, setFullscreenTick] = useState(0);

  useEffect(() => {
    function handleFullscreenChange() {
      const active = document.fullscreenElement === shellRef.current;
      setIsFullscreen(active);
      setFullscreenTick((current) => current + 1);
    }

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  async function toggleFullscreen() {
    if (!shellRef.current) {
      return;
    }
    if (document.fullscreenElement === shellRef.current) {
      await document.exitFullscreen();
      return;
    }
    await shellRef.current.requestFullscreen();
  }

  return (
    <div
      ref={shellRef}
      className={isFullscreen ? "leaflet-shell leaflet-shell-fullscreen" : "leaflet-shell"}
    >
      <button type="button" className="map-fullscreen-toggle" onClick={() => void toggleFullscreen()}>
        {isFullscreen ? "Exit fullscreen" : "Fullscreen"}
      </button>
      <MapContainer
        center={DEFAULT_MAP_CENTER}
        zoom={DEFAULT_MAP_ZOOM}
        scrollWheelZoom
        className="leaflet-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitToDevelopments items={developments} enabled={Boolean(selectedId)} />
        <PanToSelection item={selected} />
        <PanToLaunchWatchSelection item={selectedLaunchWatch} />
        <InvalidateOnFullscreen tick={fullscreenTick} />
        {developments.map((item) => {
          if (item.lat === null || item.lng === null) {
            return null;
          }
          const displayCenter = displayCoordinates[item.id] ?? [item.lat, item.lng];
          const selectedItem = item.id === selectedId;
          const watchlistStage = watchlistByDevelopment[item.id];
          return (
            <CircleMarker
              key={item.id}
              center={displayCenter}
              radius={selectedItem ? 10 : watchlistStage ? 8.5 : 7}
              pathOptions={{
                color: selectedItem ? "#1f1b16" : watchlistStage ? "#1f1b16" : segmentColor(item.listing_segment),
                weight: selectedItem ? 3 : watchlistStage ? 3 : 2,
                fillColor: segmentColor(item.listing_segment),
                fillOpacity: 0.82,
              }}
              eventHandlers={{
                click: () => onSelect(item.id),
              }}
            >
              <Popup>
                <div className="map-popup">
                  <strong>{item.display_name ?? item.id}</strong>
                  <span>
                    {item.district ?? "Unknown district"}
                    {item.region ? ` / ${item.region}` : ""}
                  </span>
                  <span>{formatListingSegment(item.listing_segment)}</span>
                  {watchlistStage ? <span>Watchlist / {watchlistStage}</span> : null}
                  <div className="map-popup-actions">
                    <Link href={`/developments/${item.id}`} className="action-link">
                      Detail
                    </Link>
                  </div>
                  {item.source_links.length === 1 ? (
                    <div className="map-popup-actions">
                      <a href={item.source_links[0].url} target="_blank" rel="noreferrer" className="action-link">
                        Open source
                      </a>
                    </div>
                  ) : null}
                  {item.source_links.length > 1 ? (
                    <details className="source-link-menu">
                      <summary>Open source</summary>
                      <div className="source-link-list">
                        {item.source_links.map((link) => (
                          <a key={link.source} href={link.url} target="_blank" rel="noreferrer">
                            {link.source}
                          </a>
                        ))}
                      </div>
                    </details>
                  ) : null}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
        {launchWatchItems.map((item) => {
          if (item.lat === null || item.lng === null) {
            return null;
          }
          const displayCenter = displayCoordinates[`launch-watch-${item.id}`] ?? [item.lat, item.lng];
          const selectedItem = item.id === selectedLaunchWatchId;
          return (
            <CircleMarker
              key={`launch-watch-${item.id}`}
              center={displayCenter}
              radius={selectedItem ? 9.5 : item.coordinate_mode === "approximate" ? 6.5 : 7.5}
              pathOptions={{
                color: selectedItem ? "#1f1b16" : launchWatchColor(item.launch_stage),
                weight: selectedItem ? 3 : item.coordinate_mode === "approximate" ? 2.5 : 2,
                fillColor: launchWatchColor(item.launch_stage),
                fillOpacity: item.coordinate_mode === "approximate" ? 0.3 : 0.56,
                dashArray: item.coordinate_mode === "approximate" ? "2 4" : "4 3",
              }}
              eventHandlers={{
                click: () => onSelectLaunchWatch(item.id),
              }}
            >
              <Popup>
                <div className="map-popup">
                  <strong>{item.display_name}</strong>
                  <span>
                    {item.district ?? "Unknown district"}
                    {item.region ? ` / ${item.region}` : ""}
                  </span>
                  <span>Launch watch / {item.launch_stage}</span>
                  {item.coordinate_mode === "approximate" ? <span>Approximate map position</span> : null}
                  {item.expected_launch_window ? <span>{item.expected_launch_window}</span> : null}
                  {item.linked_development_name ? <span>Linked / {item.linked_development_name}</span> : null}
                  {item.note ? <span>{item.note}</span> : null}
                  <div className="map-popup-actions">
                    <Link href="/launch-watch" className="action-link">
                      Launch watch
                    </Link>
                    {item.linked_development_id ? (
                      <Link href={`/developments/${item.linked_development_id}`} className="action-link">
                        Detail
                      </Link>
                    ) : null}
                  </div>
                  <div className="map-popup-actions">
                    {item.official_site_url ? (
                      <a href={item.official_site_url} target="_blank" rel="noreferrer" className="action-link">
                        Official site
                      </a>
                    ) : null}
                    {item.source_url ? (
                      <a href={item.source_url} target="_blank" rel="noreferrer" className="action-link">
                        Source signal
                      </a>
                    ) : null}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
      <div className="map-legend-overlay">
        <div>
          <span className="bubble bubble-new legend-bubble" />
          <small>New</small>
        </div>
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
    </div>
  );
}
