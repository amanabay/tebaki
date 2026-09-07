import { useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import {
  Construction,
  Crosshair,
  Droplets,
  Lightbulb,
  Check,
  Trash2,
  Waves,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { CATEGORIES, type CategoryValue } from "@/lib/strings";

const ICONS: Record<string, typeof Trash2> = {
  trash: Trash2,
  construction: Construction,
  lightbulb: Lightbulb,
  waves: Waves,
  droplets: Droplets,
};

const CITY_CENTER: [number, number] = [9.02, 38.76];

const pinIcon = L.divIcon({
  className: "",
  html: `<div style="width:14px;height:14px;border-radius:9999px;background:#f2a93b;box-shadow:0 0 0 4px #f2a93b33;transform:translate(-7px,-7px)"></div>`,
  iconSize: [0, 0],
});

function MapClick({
  onPick,
}: {
  onPick: (lat: number, lon: number) => void;
}) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export function Report() {
  const [category, setCategory] = useState<CategoryValue | null>(null);
  const [pos, setPos] = useState<[number, number] | null>(null);
  const [note, setNote] = useState("");
  const [reporter, setReporter] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [doneId, setDoneId] = useState<string | null>(null);

  const locateMe = () => {
    navigator.geolocation?.getCurrentPosition(
      (p) => setPos([p.coords.latitude, p.coords.longitude]),
      () => setError("Couldn't read your location — tap the map instead."),
    );
  };

  const submit = async () => {
    if (!category || !pos || !note.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const out = await api.submitReport({
        category,
        lat: pos[0],
        lon: pos[1],
        note: note.trim(),
        reporter: reporter.trim() || "anonymous",
      });
      setDoneId(out.report_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (doneId) {
    return (
      <div className="mx-auto max-w-lg rounded-md border border-border bg-surface-1 p-8 text-center">
        <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full border-2 border-primary text-primary">
          <Check className="size-6" />
        </div>
        <h2 className="text-xl font-semibold">Report received.</h2>
        <p className="num mt-2 text-sm text-primary">{doneId}</p>
        <div className="rule-dashed my-5" />
        <p className="text-sm leading-relaxed text-muted-foreground">
          The guardian takes it from here. Tonight's run will triage it, cluster it with nearby
          reports, and draft the complaint — you'll only be asked to approve the filing.
        </p>
        <Button asChild className="mt-5">
          <Link to="/">See the ledger</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="micro-label">report an issue · ችግር ሪፖርት</p>
        <h2 className="mt-1 text-2xl font-bold">
          Tell the guardian once.{" "}
          <span className="text-muted-foreground">It does the rest.</span>
        </h2>
      </div>

      {/* category tiles */}
      <div>
        <p className="micro-label mb-2">what is it</p>
        <div className="grid grid-cols-5 gap-2">
          {CATEGORIES.map((c) => {
            const Icon = ICONS[c.icon];
            const active = category === c.value;
            return (
              <button
                key={c.value}
                type="button"
                onClick={() => setCategory(c.value)}
                className={
                  "flex flex-col items-center gap-1.5 rounded-md border px-2 py-3.5 transition-all " +
                  (active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-surface-1 text-muted-foreground hover:border-border hover:text-foreground")
                }
              >
                <Icon className="size-5" />
                <span className="text-xs font-medium">{c.en}</span>
                <span className="font-ethiopic text-[10px] opacity-70">{c.am}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* location */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="micro-label">where</p>
          <Button variant="outline" size="sm" onClick={locateMe} className="h-7 text-xs">
            <Crosshair className="size-3.5" /> Use my location
          </Button>
        </div>
        <div className="overflow-hidden rounded-md border border-border">
          <MapContainer
            center={CITY_CENTER}
            zoom={12}
            className="h-56 w-full"
            attributionControl={false}
          >
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
            <MapClick onPick={(lat, lon) => setPos([lat, lon])} />
            {pos && <Marker position={pos} icon={pinIcon} />}
          </MapContainer>
        </div>
        <p className="num mt-1.5 text-[11px] text-muted-foreground">
          {pos ? `${pos[0].toFixed(4)}, ${pos[1].toFixed(4)}` : "tap the map to drop a pin"}
        </p>
      </div>

      {/* note */}
      <div>
        <p className="micro-label mb-2">what happened</p>
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="One or two sentences. Amharic or English — the guardian reads both."
          className="resize-none"
        />
      </div>

      <div>
        <p className="micro-label mb-2">your name (optional)</p>
        <Input
          value={reporter}
          onChange={(e) => setReporter(e.target.value)}
          maxLength={100}
          placeholder="anonymous"
        />
      </div>

      {error && (
        <p className="rounded-md border border-status-escalated/40 bg-status-escalated/10 px-4 py-2.5 text-sm text-status-escalated">
          {error}
        </p>
      )}

      <div className="rule-dashed" />

      <Button
        size="lg"
        className="w-full tracking-[0.08em] uppercase"
        disabled={!category || !pos || !note.trim() || submitting}
        onClick={submit}
      >
        {submitting ? "Submitting…" : "Hand it to the guardian"}
      </Button>
    </div>
  );
}
