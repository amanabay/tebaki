import { useEffect, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { Plus } from "lucide-react";
import { api, type MapData } from "@/lib/api";
import { categoryLabel, statusInfo } from "@/lib/strings";

const CITY_CENTER: [number, number] = [9.02, 38.76];

function FitBounds({ data }: { data: MapData | null }) {
  const map = useMap();
  useEffect(() => {
    const points: Array<[number, number]> = [
      ...(data?.reports ?? []).map((r) => [r.lat, r.lon] as [number, number]),
      ...(data?.complaints ?? [])
        .filter((c) => c.lat != null && c.lon != null)
        .map((c) => [c.lat!, c.lon!] as [number, number]),
    ];
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 14);
      return;
    }
    map.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
  }, [data, map]);
  return null;
}

function ReportPopup({
  report,
  onPlusOne,
}: {
  report: MapData["reports"][number];
  onPlusOne: (reportId: string) => void;
}) {
  const [count, setCount] = useState(report.plus_ones);
  const [busy, setBusy] = useState(false);
  return (
    <Popup className="tebaki-popup">
      <div className="min-w-44 space-y-2">
        <p className="text-xs font-semibold">
          {categoryLabel(report.category)} · sev {report.severity}
        </p>
        <p className="text-[11px] text-neutral-400">{statusInfo(report.status).label}</p>
        <p className="num text-[11px] text-neutral-400">
          {count} neighbor{count === 1 ? "" : "s"} corroborated
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            api
              .plusOne(report.report_id)
              .then((r) => setCount(r.plus_ones))
              .catch(() => {})
              .finally(() => {
                setBusy(false);
                onPlusOne(report.report_id);
              });
          }}
          className="flex w-full items-center justify-center gap-1 rounded border border-amber-400/60 bg-amber-400/10 px-2 py-1 text-[11px] font-medium text-amber-300 transition-colors hover:bg-amber-400/20 disabled:opacity-50"
        >
          <Plus className="size-3" /> I've seen this too
        </button>
      </div>
    </Popup>
  );
}

export function CityMap({ data, onDataStale }: { data: MapData | null; onDataStale?: () => void }) {
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
      <FitBounds data={data} />
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
          <ReportPopup report={r} onPlusOne={() => onDataStale?.()} />
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
                  : c.status === "resolved"
                    ? "#69c98f"
                    : c.status === "filed" || c.status === "acknowledged"
                      ? "#69c98f"
                      : "#f2a93b",
              weight: 1.5,
              fillOpacity: 0,
              dashArray: "3 4",
            }}
          >
            <Tooltip>
              <span className="text-xs">
                {c.category ? categoryLabel(c.category) : "complaint"} ·{" "}
                {statusInfo(c.status).label}
              </span>
            </Tooltip>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}
