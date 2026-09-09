import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import {
  Construction,
  Crosshair,
  Droplets,
  Lightbulb,
  Check,
  MapPin,
  Search,
  Trash2,
  Waves,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { CATEGORIES, type CategoryValue } from "@/lib/strings";
import { useTheme } from "@/lib/theme";

const ICONS: Record<string, typeof Trash2> = {
  trash: Trash2,
  construction: Construction,
  lightbulb: Lightbulb,
  waves: Waves,
  droplets: Droplets,
};

const CITY_CENTER: [number, number] = [9.02, 38.76];

function usePinIcon(dark: boolean) {
  const color = dark ? "#f2a93b" : "#b57614";
  return L.divIcon({
    className: "",
    html: `<div style="width:14px;height:14px;border-radius:9999px;background:${color};box-shadow:0 0 0 4px ${color}55;transform:translate(-7px,-7px)"></div>`,
    iconSize: [0, 0],
  });
}

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
  const { theme } = useTheme();
  const pinIcon = usePinIcon(theme === "dark");
  const [category, setCategory] = useState<CategoryValue | null>(null);
  const [pos, setPos] = useState<[number, number] | null>(null);
  const [note, setNote] = useState("");
  const [reporter, setReporter] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [doneId, setDoneId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Array<{ name: string; lat: number; lon: number }>>([]);
  const [searching, setSearching] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const noteRef = useRef<HTMLTextAreaElement>(null);

  const searchAddress = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const found = await api.geocodeSearch(query);
      setResults(found);
      setHighlighted(found.length > 0 ? 0 : -1);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const pickResult = (r: { name: string; lat: number; lon: number }) => {
    setPos([r.lat, r.lon]);
    setResults([]);
    setQuery(r.name.split(",")[0]);
  };

  const submit = async () => {
    if (!category || !pos || !note.trim()) {
      setFieldError(
        !category
          ? "Pick a category first."
          : !pos
            ? "Drop a pin on the map (or search a place) first."
            : "Write a short note so the guardian knows what happened.",
      );
      if (!note.trim()) noteRef.current?.focus();
      return;
    }
    setFieldError(null);
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
      setError(
        String(e).includes("422")
          ? "That location is outside the city the guardian watches. Drop the pin inside the boundary."
          : "Couldn't submit the report. Check the connection and try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (doneId) {
    return (
      <div className="mx-auto max-w-lg rounded-md border border-border bg-surface-1 p-8 text-center">
        <div
          className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full border-2 border-primary text-primary"
          aria-hidden="true"
        >
          <Check className="size-6" />
        </div>
        <h1 className="font-serif text-xl font-semibold">Report received.</h1>
        <p className="num mt-2 text-sm text-primary">{doneId}</p>
        <div className="rule-dashed my-5" />
        <p className="text-sm leading-relaxed text-muted-foreground">
          The guardian takes it from here. Tonight's run will triage it, cluster it with nearby
          reports, and draft the complaint — you'll only be asked to approve the filing.
        </p>
        <div className="mt-5 flex justify-center gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setDoneId(null);
              setCategory(null);
              setPos(null);
              setNote("");
              setFieldError(null);
            }}
          >
            Report another
          </Button>
          <Button asChild>
            <Link to="/ledger">See the ledger</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="micro-label">
          report an issue · <span lang="am">ችግር ሪፖርት</span>
        </p>
        <h1 className="mt-1 font-serif text-2xl font-bold text-balance">
          Tell the guardian once.{" "}
          <span className="text-muted-foreground">It does the rest.</span>
        </h1>
      </div>

      {/* category tiles */}
      <fieldset>
        <legend className="micro-label mb-2">what is it</legend>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {CATEGORIES.map((c) => {
            const Icon = ICONS[c.icon];
            const active = category === c.value;
            return (
              <button
                key={c.value}
                type="button"
                aria-pressed={active}
                onClick={() => setCategory(c.value)}
                className={
                  "flex flex-col items-center gap-1.5 rounded-md border px-2 py-3.5 transition-all " +
                  (active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-surface-1 text-muted-foreground hover:text-foreground")
                }
              >
                <Icon className="size-5" aria-hidden="true" />
                <span className="text-xs font-medium">{c.en}</span>
                <span lang="am" className="font-ethiopic text-[10px] opacity-70">
                  {c.am}
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* location */}
      <fieldset>
        <div className="mb-2 flex items-center justify-between">
          <legend className="micro-label">where</legend>
          <Button variant="outline" size="sm" onClick={locateMe} className="h-7 text-xs">
            <Crosshair className="size-3.5" aria-hidden="true" /> Use my location
          </Button>
        </div>
        <div className="relative z-20 mb-2">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search
                className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <label htmlFor="place-search" className="sr-only">
                Search a place
              </label>
              <Input
                id="place-search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    if (highlighted >= 0 && results[highlighted]) {
                      pickResult(results[highlighted]);
                    } else {
                      searchAddress();
                    }
                  } else if (e.key === "Escape") {
                    setResults([]);
                    setHighlighted(-1);
                  } else if (e.key === "ArrowDown" && results.length > 0) {
                    e.preventDefault();
                    setHighlighted((h) => Math.min(h + 1, results.length - 1));
                  } else if (e.key === "ArrowUp" && results.length > 0) {
                    e.preventDefault();
                    setHighlighted((h) => Math.max(h - 1, 0));
                  }
                }}
                role="combobox"
                aria-expanded={results.length > 0}
                aria-controls="place-results"
                aria-autocomplete="list"
                placeholder="Search a place — e.g. Shiro Meda"
                className="h-9 pl-8 text-sm"
              />
            </div>
            <Button variant="outline" size="sm" onClick={searchAddress} disabled={searching} className="h-9">
              {searching ? "…" : "Find"}
            </Button>
          </div>
          {results.length > 0 && (
            <ul
              id="place-results"
              role="listbox"
              className="absolute inset-x-0 top-10 z-30 overflow-hidden rounded-md border border-border bg-surface-1 shadow-xl"
            >
              {results.map((r, i) => (
                <li key={`${r.lat}-${r.lon}`} role="option" aria-selected={i === highlighted}>
                  <button
                    type="button"
                    onClick={() => pickResult(r)}
                    className={
                      "flex w-full items-start gap-2 px-3 py-2 text-left text-xs " +
                      (i === highlighted ? "bg-surface-2" : "hover:bg-surface-2/60")
                    }
                  >
                    <MapPin className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden="true" />
                    <span className="line-clamp-2">{r.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="overflow-hidden rounded-md border border-border">
          <MapContainer
            center={CITY_CENTER}
            zoom={12}
            className="h-56 w-full focus:outline-none"
            attributionControl
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
              url={
                theme === "dark"
                  ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                  : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
              }
            />
            <MapClick onPick={(lat, lon) => setPos([lat, lon])} />
            {pos && (
              <Marker
                position={pos}
                icon={pinIcon}
                draggable
                eventHandlers={{
                  dragend: (e) => {
                    const p = e.target.getLatLng();
                    setPos([p.lat, p.lng]);
                  },
                }}
                aria-label="Report location — drag to adjust"
              />
            )}
          </MapContainer>
        </div>
        <p className="num mt-1.5 text-[11px] text-muted-foreground" aria-live="polite">
          {pos
            ? `${pos[0].toFixed(4)}, ${pos[1].toFixed(4)} — drag the pin to adjust`
            : "tap the map to drop a pin"}
        </p>
      </fieldset>

      {/* note */}
      <div>
        <label htmlFor="report-note" className="micro-label mb-2 block">
          what happened
        </label>
        <Textarea
          id="report-note"
          ref={noteRef}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="One or two sentences. Amharic or English — the guardian reads both."
          className="resize-none"
          aria-describedby={fieldError && !note.trim() ? "field-error" : undefined}
          aria-invalid={fieldError ? true : undefined}
        />
      </div>

      <div>
        <label htmlFor="reporter-name" className="micro-label mb-2 block">
          your name (optional)
        </label>
        <Input
          id="reporter-name"
          value={reporter}
          onChange={(e) => setReporter(e.target.value)}
          maxLength={100}
          placeholder="anonymous"
          autoComplete="name"
        />
      </div>

      {fieldError && (
        <p
          id="field-error"
          role="alert"
          className="rounded-md border border-primary/40 bg-primary/10 px-4 py-2.5 text-sm text-primary"
        >
          {fieldError}
        </p>
      )}
      {error && (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive"
        >
          {error}
        </p>
      )}

      <div className="rule-dashed" />

      <Button size="lg" className="w-full tracking-[0.08em] uppercase" onClick={submit} disabled={submitting}>
        {submitting ? "Submitting…" : "Hand it to the guardian"}
      </Button>
    </div>
  );

  function locateMe() {
    navigator.geolocation?.getCurrentPosition(
      (p) => setPos([p.coords.latitude, p.coords.longitude]),
      () => setError("Couldn't read your location — search a place or tap the map instead."),
    );
  }
}
