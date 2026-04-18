"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
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

function segmentColor(segment: string): string {
  if (segment === "new") {
    return "#a8741f";
  }
  if (segment === "first_hand_remaining") {
    return "#bb6126";
  }
  if (segment === "second_hand") {
    return "#517654";
  }
  if (segment === "mixed") {
    return "#355c70";
  }
  return "#7a7266";
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

export function DevelopmentLeafletMap({
  developments,
  selectedId,
  watchlistByDevelopment,
  onSelect,
}: {
  developments: DevelopmentSummary[];
  selectedId: string | null;
  watchlistByDevelopment: Record<string, string>;
  onSelect: (id: string) => void;
}) {
  const selected = developments.find((item) => item.id === selectedId) ?? null;
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
        <InvalidateOnFullscreen tick={fullscreenTick} />
        {developments.map((item) => {
          if (item.lat === null || item.lng === null) {
            return null;
          }
          const selectedItem = item.id === selectedId;
          const watchlistStage = watchlistByDevelopment[item.id];
          return (
            <CircleMarker
              key={item.id}
              center={[item.lat, item.lng]}
              radius={selectedItem ? 11 : watchlistStage ? 9 : 8}
              pathOptions={{
                color: selectedItem ? "#1f1b16" : watchlistStage ? "#1f1b16" : segmentColor(item.listing_segment),
                weight: selectedItem ? 3 : watchlistStage ? 3 : 2,
                fillColor: segmentColor(item.listing_segment),
                fillOpacity: 0.78,
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
      </MapContainer>
    </div>
  );
}
