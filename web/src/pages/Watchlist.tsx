import { useMemo, useState, useEffect } from "react";
import { Link, Star } from "lucide-react";
import { StatusStamp } from "@/components/StatusStamp";
import { Skeleton } from "@/components/Skeleton";
import type { EngineData } from "@/lib/useEngineData";
import { categoryLabel, timeAgo } from "@/lib/strings";

const KEY = "tebaki-watchlist";

function loadWatch(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveWatch(ids: string[]) {
  localStorage.setItem(KEY, JSON.stringify(ids));
}

export function isWatched(id: string): boolean {
  return loadWatch().includes(id);
}

export function toggleWatch(id: string): void {
  const current = loadWatch();
  const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
  saveWatch(next);
}

/** Watch toggle button — used on ledger rows and the case file. */
export function WatchButton({ complaintId, className }: { complaintId: string; className?: string }) {
  const [watched, setWatched] = useState(isWatched(complaintId));
  useEffect(() => setWatched(isWatched(complaintId)), [complaintId]);
  return (
    <button
      type="button"
      aria-pressed={watched}
      aria-label={watched ? "Stop watching this case" : "Watch this case"}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleWatch(complaintId);
        setWatched(!watched);
        window.dispatchEvent(new Event("tebaki-watch-change"));
      }}
      className={
        "flex size-8 items-center justify-center rounded-md transition-colors " +
        (watched
          ? "text-primary"
          : "text-muted-foreground hover:bg-surface-2 hover:text-foreground ") +
        (className ?? "")
      }
    >
      <Star className="size-4" aria-hidden="true" fill={watched ? "currentColor" : "none"} />
    </button>
  );
}

export function Watchlist({ data }: { data: EngineData }) {
  const [ids, setIds] = useState<string[]>(loadWatch());

  useEffect(() => {
    const onUpdate = () => setIds(loadWatch());
    window.addEventListener("tebaki-watch-change", onUpdate);
    return () => window.removeEventListener("tebaki-watch-change", onUpdate);
  }, []);

  const watched = useMemo(
    () => data.ledger.filter((row) => ids.includes(row.complaint_id)),
    [data.ledger, ids],
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="micro-label">your cases</p>
        <h1 className="mt-1 font-serif text-2xl font-bold">Watchlist</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Cases you're following. Star any case in the ledger to track it here — status changes
          show up as they happen.
        </p>
      </div>

      {data.online === null ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : watched.length === 0 ? (
        <div className="rounded-md border border-dashed border-border bg-surface-1 px-6 py-14 text-center">
          <Star className="mx-auto size-8 text-primary" aria-hidden="true" />
          <h2 className="mt-3 font-serif text-lg font-semibold">Not following any cases yet.</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Star a case in the ledger — or the one you reported — and its journey lands here.
          </p>
          <Link
            to="/ledger"
            className="mt-4 inline-block text-sm text-primary underline-offset-4 hover:underline"
          >
            Browse the ledger
          </Link>
        </div>
      ) : (
        <ul className="space-y-3">
          {watched.map((row) => (
            <li key={row.complaint_id}>
              <Link
                to={`/case/${row.complaint_id}`}
                className="flex items-center gap-3 rounded-md border border-border bg-surface-1 p-4 transition-colors hover:bg-surface-2/60"
              >
                <WatchButton complaintId={row.complaint_id} className="-ml-1 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{row.subject ?? "—"}</p>
                  <p className="num mt-0.5 text-[11px] text-muted-foreground">
                    {row.complaint_id}
                    {row.filed_at && ` · filed ${timeAgo(row.filed_at)}`}
                    {row.category && ` · ${categoryLabel(row.category)}`}
                  </p>
                </div>
                <StatusStamp status={row.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
