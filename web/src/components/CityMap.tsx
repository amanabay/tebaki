import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { MapData } from "@/lib/api";
import { categoryLabel } from "@/lib/strings";

const CITY_CENTER: [number, number] = [9.02, 38.76];

export function CityMap({ data }: { data: MapData | null }) {
  return (
    <MapContainer
      center={CITY_CENTER}
      zoom={12}
      className="h-[420px] w-full"
      scrollWheelZoom
      attributionControl
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      {(data?.reports ?? []).map((r) => (
        <CircleMarker
          key={r.report_id}
          center={[r.lat, r.lon]}
          radius={4 + r.severity}
          pathOptions={{
            color: "#f2a93b",
            weight: 1,
            fillColor: "#f2a93b",
            fillOpacity: 0.55,
          }}
        >
          <Tooltip>
            <span className="text-xs">
              {categoryLabel(r.category)} · sev {r.severity} · {r.status}
            </span>
          </Tooltip>
        </CircleMarker>
      ))}
      {(data?.complaints ?? [])
        .filter((c) => c.lat != null && c.lon != null)
        .map((c) => (
          <CircleMarker
            key={c.complaint_id}
            center={[c.lat!, c.lon!]}
            radius={11}
            pathOptions={{
              color:
                c.status.startsWith("escalated")
                  ? "#e0654a"
                  : c.status === "filed"
                    ? "#69c98f"
                    : "#f2a93b",
              weight: 1.5,
              fillOpacity: 0,
              dashArray: "3 4",
            }}
          >
            <Tooltip>
              <span className="text-xs">
                {c.category ? categoryLabel(c.category) : "complaint"} · {c.status}
              </span>
            </Tooltip>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}
