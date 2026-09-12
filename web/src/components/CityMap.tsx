import { useEffect, useMemo, useRef, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { Crosshair, Plus } from "lucide-react";
import { api, type MapData } from "@/lib/api";
import { categoryLabel, statusInfo, statusMapColor } from "@/lib/strings";
import { useTheme } from "@/lib/theme";

const CITY_CENTER: [number, number] = [9.02, 38.76];

/** Fit bounds only when the point set materially changes — never on poll refreshes. */
function FitBounds({ data, recenterKey }: { data: MapData | null; recenterKey: number }) {
  const map = useMap();
  const lastPointCount = useRef(-1);
  useEffect(() => {
    if (recenterKey === 0) return; // initial state handled below
    const points = collectPoints(data);
    if (points.length === 0) return;
    applyBounds(map, points);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recenterKey]);

  useEffect(() => {
    const points = collectPoints(data);
    if (points.length === 0 || points.length === lastPointCount.current) return;
    lastPointCount.current = points.length;
    applyBounds(map, points);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  return null;
}

function collectPoints(data: MapData | null): Array<[number, number]> {
  return [
    ...(data?.reports ?? []).map((r) => [r.lat, r.lon] as [number, number]),
    ...(data?.complaints ?? [])
      .filter((c) => c.lat != null && c.lon != null)
      .map((c) => [c.lat!, c.lon!] as [number, number]),
  ];
}

function applyBounds(map: ReturnType<typeof useMap>, points: Array<[number, number]>) {
  if (points.length === 1) {
    map.setView(points[0], 14);
    return;
  }
  map.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
}

function RecenterButton({ onClick }: { onClick: () => void }) {
  const map = useMap();
  return (
    <div className="leaflet-top leaflet-right">
      <div className="leaflet-control leaflet-bar">
        <button
          type="button"
          aria-label="Recenter map on reports"
          onClick={() => {
            onClick();
            map.getContainer().focus();
          }}
          className="flex size-8 items-center justify-center"
        >
          <Crosshair className="size-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
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
  const [error, setError] = useState(false);
  return (
    <Popup>
      <div className="min-w-44 space-y-2">
        <p className="text-xs font-semibold">
          {categoryLabel(report.category)} · sev {report.severity}
        </p>
        <p className="text-[11px] text-muted-foreground">{statusInfo(report.status).label}</p>
        {report.triage_reason && (
          <p className="border-l-2 border-primary/60 pl-2 text-[11px] leading-4 text-muted-foreground">
            <span className="font-medium text-foreground">Guardian review: </span>
            {report.triage_reason}
            {report.triage_confidence != null && ` (${Math.round(report.triage_confidence * 100)}% confidence)`}
          </p>
        )}
        <p className="num text-[11px] text-muted-foreground">
          {count} neighbor{count === 1 ? "" : "s"} corroborated
        </p>
        {error && (
          <p className="text-[11px] text-status-escalated">
            Couldn't record your corroboration. Try again.
          </p>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            setError(false);
            api
              .plusOne(report.report_id)
              .then((r) => setCount(r.plus_ones))
              .catch(() => setError(true))
              .finally(() => {
                setBusy(false);
                onPlusOne(report.report_id);
              });
          }}
          className="flex w-full items-center justify-center gap-1 rounded border border-primary/60 bg-primary/10 px-2 py-1.5 text-[11px] font-medium text-primary transition-colors hover:bg-primary/20 disabled:opacity-50"
        >
          <Plus className="size-3" aria-hidden="true" /> I've seen this too
        </button>
      </div>
    </Popup>
  );
}

export function CityMap({ data, onDataStale }: { data: MapData | null; onDataStale?: () => void }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const [recenterKey, setRecenterKey] = useState(0);
  // OpenStreetMap tiles are keyless and keep the public dashboard usable in
  // a fresh deployment. The app's own status colors provide the visual
  // hierarchy in both themes, so a paid basemap is unnecessary here.
  const tiles = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

  const legend = useMemo(
    () => [
      { label: "new intake", shape: "dot", className: "bg-primary" },
      { label: "guardian reviewed", shape: "dot", className: "bg-accent" },
      { label: "filed", shape: "ring", className: "border-status-filed" },
      { label: "escalated", shape: "ring", className: "border-status-escalated" },
      { label: "resolved", shape: "ring", className: "border-status-filed opacity-60" },
    ],
    [],
  );
  const reportCount = data?.reports.length ?? 0;
  const triagedCount = (data?.reports ?? []).filter((report) => report.status === "triaged").length;
  const draftCount = (data?.complaints ?? []).filter((complaint) => complaint.status === "awaiting_approval").length;

  return (
    <div className="relative" role="region" aria-label="City map of reports and complaints">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[500] flex flex-wrap items-start justify-between gap-3 p-3">
        <div className="rounded-lg border border-white/10 bg-black/75 px-3 py-2 text-white shadow-xl backdrop-blur-md">
          <p className="micro-label text-white/60">live intake</p>
          <p className="mt-0.5 text-sm font-semibold">{reportCount} report{reportCount === 1 ? "" : "s"} on the map</p>
        </div>
        <div className="flex gap-1.5 rounded-lg border border-white/10 bg-black/75 p-1.5 text-[11px] font-medium text-white shadow-xl backdrop-blur-md">
          <span className="rounded bg-white/10 px-2 py-1">{triagedCount} reviewed</span>
          <span className="rounded bg-primary/25 px-2 py-1 text-primary">{draftCount} need approval</span>
        </div>
      </div>
      <MapContainer
        center={CITY_CENTER}
        zoom={12}
        className="h-[420px] w-full focus:outline-none"
        scrollWheelZoom={false}
        zoomControl
        attributionControl
      >
        <TileLayer
          className={dark ? "map-tiles-dark" : undefined}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url={tiles}
        />
        <FitBounds data={data} recenterKey={recenterKey} />
        <RecenterButton onClick={() => setRecenterKey((k) => k + 1)} />
        {(data?.reports ?? []).map((r) => (
          <CircleMarker
            key={r.report_id}
            center={[r.lat, r.lon]}
            radius={4 + r.severity}
            pathOptions={{
              color: statusMapColor(r.status, dark),
              weight: 1,
              fillColor: statusMapColor(r.status, dark),
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
                color: statusMapColor(c.status, dark),
                weight: c.status === "resolved" ? 2.5 : 1.5,
                fillOpacity: 0,
                dashArray: c.status === "resolved" ? undefined : "3 4",
                opacity: c.status === "resolved" ? 0.85 : 1,
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
      {/* legend — matches the marker encodings exactly */}
      <div
        className="pointer-events-none absolute bottom-2 left-2 rounded-md border border-border bg-surface-1/95 px-3 py-2"
        aria-hidden="true"
      >
        <ul className="space-y-1 text-[11px] text-muted-foreground">
          {legend.map((l) => (
            <li key={l.label} className="flex items-center gap-2">
              {l.shape === "dot" ? (
                <span className={`inline-block size-2 rounded-full ${l.className}`} />
              ) : (
                <span className={`inline-block size-2.5 rounded-full border ${l.className}`} />
              )}
              {l.label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
