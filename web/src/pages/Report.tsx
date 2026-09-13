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

const LOCAL_PLACES = [
  { name: "Shiro Meda, Addis Ababa", lat: 9.061, lon: 38.761 },
  { name: "Meskel Square, Addis Ababa", lat: 9.010, lon: 38.761 },
  { name: "Bole, Addis Ababa", lat: 8.999, lon: 38.787 },
  { name: "Piassa, Addis Ababa", lat: 9.034, lon: 38.752 },
  { name: "Merkato, Addis Ababa", lat: 9.030, lon: 38.742 },
];

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
  const [photoData, setPhotoData] = useState<string | null>(null);
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
      const normalized = query.trim().toLowerCase();
      const local = LOCAL_PLACES.filter((place) => place.name.toLowerCase().includes(normalized));
      const merged = found.length > 0 ? found : local;
      setResults(merged);
      setHighlighted(merged.length > 0 ? 0 : -1);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const attachPhoto = (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }
    if (file.size > 220_000) {
      setError("That image is too large. Choose one under 220 KB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPhotoData(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(file);
    setError(null);
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
        ...(photoData ? { photo_data: photoData } : {}),
      });
      setDoneId(out.report_id);
      // The dashboard owns the shared data poller. Notify it immediately so
      // the new report is visible on the map when the user returns home.
      window.dispatchEvent(new Event("tebaki-data-refresh"));
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
          Your report is now on the operations map. The guardian reviews it automatically;
          when related reports form a case, a draft appears in Decisions for human approval.
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
            <Link to="/">Open operations map</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="micro-label">
          report an issue
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
              className={theme === "dark" ? "map-tiles-dark" : undefined}
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
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

      {/* optional photo evidence */}
      <div>
        <label htmlFor="report-photo" className="micro-label mb-2 block">
          photo evidence (optional)
        </label>
        <Input
          id="report-photo"
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => attachPhoto(e.target.files?.[0])}
          className="text-sm file:mr-3 file:border-0 file:bg-transparent file:text-xs"
        />
        {photoData && (
          <div className="mt-2 flex items-center gap-3">
            <img src={photoData} alt="Attached report evidence" className="size-16 rounded object-cover" />
            <button type="button" className="text-xs text-primary underline-offset-4 hover:underline" onClick={() => setPhotoData(null)}>
              Remove photo
            </button>
          </div>
        )}
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
    if (!navigator.geolocation) {
      setError("Location access is not available in this browser. Search a place or tap the map instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => setPos([p.coords.latitude, p.coords.longitude]),
      () => setError("Couldn't read your location — allow location access or search a place instead."),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
    );
  }
}
