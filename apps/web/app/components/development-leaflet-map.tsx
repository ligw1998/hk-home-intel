"use client";

import Link from "next/link";
import { useEffect } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";

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

function segmentColor(segment: string): string {
  if (segment === "first_hand_remaining") {
    return "#bb6126";
  }
  if (segment === "mixed") {
    return "#355c70";
  }
  return "#517654";
}

function FitToDevelopments({ items }: { items: DevelopmentSummary[] }) {
  const map = useMap();

  useEffect(() => {
    const points = items
      .filter((item) => item.lat !== null && item.lng !== null)
      .map((item) => [item.lat as number, item.lng as number] as [number, number]);

    if (points.length === 0) {
      map.setView([22.3193, 114.1694], 10);
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

  return (
    <div className="leaflet-shell">
      <MapContainer
        center={[22.3193, 114.1694]}
        zoom={11}
        scrollWheelZoom
        className="leaflet-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitToDevelopments items={developments} />
        <PanToSelection item={selected} />
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
                  <span>{item.listing_segment}</span>
                  {watchlistStage ? <span>Watchlist / {watchlistStage}</span> : null}
                  <div className="map-popup-actions">
                    <button type="button" className="action-button" onClick={() => onSelect(item.id)}>
                      Select
                    </button>
                    <Link href={`/developments/${item.id}`} className="action-link">
                      Detail
                    </Link>
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
