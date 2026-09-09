import { useState } from "react";
import { Link } from "react-router-dom";
import { MoonStar, Siren, List, Map as MapIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CityMap } from "@/components/CityMap";
import { NightLog, NightLogHeader } from "@/components/NightLog";
import { StatusStamp } from "@/components/StatusStamp";
import { Skeleton } from "@/components/Skeleton";
import { api } from "@/lib/api";
import type { EngineData } from "@/lib/useEngineData";
import { categoryLabel, residentsLabel, timeAgo, statusKind } from "@/lib/strings";

interface RunSummary {
  events?: Array<{ kind: string; [k: string]: unknown }>;
}

type StatusFilter = "all" | "active" | "escalated" | "resolved" | "awaiting" | "dropped";

const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "escalated", label: "Escalated" },
  { value: "resolved", label: "Resolved" },
  { value: "awaiting", label: "Awaiting" },
  { value: "dropped", label: "Dropped" },
];

function matchesFilter(status: string, filter: StatusFilter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "active":
      return ["filed", "acknowledged", "escalated"].includes(statusKind(status));
    case "escalated":
      return statusKind(status) === "escalated";
    case "resolved":
      return statusKind(status) === "resolved";
    case "awaiting":
      return ["awaiting", "new"].includes(statusKind(status));
    case "dropped":
      return statusKind(status) === "dropped";
  }
}

function ShiftBar({
  busy,
  message,
  onNightly,
  onChase,
}: {
  busy: "nightly" | "chase" | null;
  message: string | null;
  onNightly: () => void;
  onChase: () => void;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface-1 px-4 py-3">
      <div>
        <p className="micro-label">the guardian's shift</p>
        <p className="text-sm text-muted-foreground">
          Files every night at 02:00 — or start it now.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <span
          role="status"
          aria-live="polite"
          className="max-w-72 text-right text-xs text-muted-foreground"
        >
          {message}
        </span>
        <Button onClick={onNightly} disabled={busy !== null}>
          <MoonStar className="size-4" aria-hidden="true" />
          {busy === "nightly" ? "Running…" : "Run tonight's cycle"}
        </Button>
        <Button variant="outline" onClick={onChase} disabled={busy !== null}>
          <Siren className="size-4" aria-hidden="true" />
          {busy === "chase" ? "Chasing…" : "Chase tickets"}
        </Button>
      </div>
    </div>
  );
}

function StatStrip({
  ledger,
  pendingCount,
  loading,
}: {
  ledger: Array<{ status: string }>;
  pendingCount: number;
  loading: boolean;
}) {
  const active = ledger.filter(
    (r) => ["filed", "acknowledged", "escalated"].includes(statusKind(r.status)),
  ).length;
  const escalated = ledger.filter((r) => statusKind(r.status) === "escalated").length;
  const resolved = ledger.filter((r) => statusKind(r.status) === "resolved").length;
  const stats = [
    { label: "complaints", value: ledger.length, tone: "text-foreground", to: "/ledger" },
    { label: "active", value: active, tone: "text-status-filed", to: "/ledger?f=active" },
    { label: "escalated", value: escalated, tone: "text-status-escalated", to: "/ledger?f=escalated" },
    { label: "resolved", value: resolved, tone: "text-status-filed", to: "/ledger?f=resolved" },
    {
      label: "awaiting you",
      value: pendingCount,
      tone: "text-primary",
      to: "/decisions",
    },
  ];
  return (
    <div className="mb-6 grid grid-cols-2 divide-border rounded-md border border-border bg-surface-1 sm:grid-cols-5 sm:divide-x">
      {stats.map((s) => (
        <Link
          to={s.to}
          key={s.label}
          className="px-4 py-4 transition-colors hover:bg-surface-2"
        >
          <p className="micro-label">{s.label}</p>
          {loading ? (
            <Skeleton className="mt-1 h-8 w-10" />
          ) : (
            <p className={`num mt-1 text-3xl font-bold ${s.tone}`}>{s.value}</p>
          )}
        </Link>
      ))}
    </div>
  );
}

function FilterChips({
  filter,
  onChange,
  shown,
  total,
}: {
  filter: StatusFilter;
  onChange: (f: StatusFilter) => void;
  shown: number;
  total: number;
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5"
      role="group"
      aria-label="Filter complaints by status"
    >
      {STATUS_FILTERS.map((f) => (
        <button
          key={f.value}
          type="button"
          aria-pressed={filter === f.value}
          onClick={() => onChange(f.value)}
          className={
            "rounded-full border px-3 py-1 text-xs transition-colors " +
            (filter === f.value
              ? "border-primary/60 bg-primary/10 font-medium text-primary"
              : "border-border text-muted-foreground hover:text-foreground")
          }
        >
          {f.label}
        </button>
      ))}
      <span className="num ml-auto text-[11px] text-muted-foreground" aria-live="polite">
        showing {shown} of {total}
      </span>
    </div>
  );
}

function LedgerTable({
  ledger,
  filter,
  onFilter,
}: {
  ledger: EngineData["ledger"];
  filter: StatusFilter;
  onFilter: (f: StatusFilter) => void;
}) {
  const filtered = ledger.filter((row) => matchesFilter(row.status, filter));
  return (
    <section className="rounded-md border border-border bg-surface-1">
      <header className="flex items-baseline justify-between border-b border-border px-4 py-3">
        <div>
          <p className="micro-label">civic gazette</p>
          <h2 className="mt-0.5 font-serif text-lg font-semibold">Complaint ledger</h2>
        </div>
        <span className="num text-[11px] text-muted-foreground">{ledger.length} entries</span>
      </header>
      <FilterChips
        filter={filter}
        onChange={onFilter}
        shown={filtered.length}
        total={ledger.length}
      />
      {ledger.length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">
          Nothing filed yet. Report an issue and tonight's cycle will draft a complaint for it.
        </p>
      ) : filtered.length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">
          No complaints match this filter.{" "}
          <button
            type="button"
            className="text-primary underline-offset-4 hover:underline"
            onClick={() => onFilter("all")}
          >
            Clear filters
          </button>
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Complaints filed by the guardian</caption>
            <thead>
              <tr className="border-b border-border text-left">
                {["complaint", "neighbors", "ward", "category", "status", "ticket", "filed"].map(
                  (h) => (
                    <th key={h} scope="col" className="micro-label px-4 py-2.5 font-semibold">
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={row.complaint_id}
                  className="border-b border-border/50 last:border-0 hover:bg-surface-2/50"
                >
                  <td className="max-w-64 px-4 py-3">
                    <Link
                      to={`/case/${row.complaint_id}`}
                      className="block truncate font-medium underline-offset-4 hover:underline"
                    >
                      {row.subject ?? "—"}
                    </Link>
                    <p className="num text-[11px] text-muted-foreground">{row.complaint_id}</p>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    <span>{residentsLabel(row.reporters, row.plus_ones)}</span>
                    {(row.plus_ones ?? 0) > 0 && (
                      <span className="ml-1.5 text-[10px] text-primary">+{row.plus_ones}</span>
                    )}
                  </td>
                  <td className="max-w-32 truncate px-4 py-3 text-muted-foreground" title={row.ward}>
                    {row.ward}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {row.category ? categoryLabel(row.category) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusStamp status={row.status} />
                  </td>
                  <td className="num px-4 py-3 text-[12px] text-muted-foreground">
                    {row.ticket_id ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-[12px] text-muted-foreground">
                    {row.filed_at ? timeAgo(row.filed_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function Dashboard({
  data,
  initialView = "map",
}: {
  data: EngineData;
  initialView?: "map" | "ledger";
}) {
  const [view, setView] = useState<"map" | "ledger">(initialView);
  const [busy, setBusy] = useState<"nightly" | "chase" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const loading = data.online === null;

  const runNightly = async () => {
    setBusy("nightly");
    setMessage(null);
    try {
      const summary = (await api.runNightly(false)) as RunSummary;
      const events = summary.events ?? [];
      const cards = events.filter((e) => e.kind === "decision_card").length;
      const filed = events.filter((e) => e.kind === "filed").length;
      setMessage(
        cards > 0
          ? `${cards} draft${cards > 1 ? "s" : ""} waiting for your decision — open the Decisions tab.`
          : filed > 0
            ? `${filed} complaint${filed > 1 ? "s" : ""} filed.`
            : "Cycle done.",
      );
      data.refresh();
    } catch {
      setMessage("Couldn't run the cycle. Check that the engine is running and try again.");
    } finally {
      setBusy(null);
    }
  };

  const runChase = async () => {
    setBusy("chase");
    setMessage(null);
    try {
      const summary = (await api.runChase()) as RunSummary;
      const end = (summary.events ?? []).find((e) => e.kind === "chase_end");
      setMessage(
        end
          ? `Checked ${end.checked}, escalated ${end.escalated}, resolved ${end.resolved ?? 0}.`
          : "Chase done.",
      );
      data.refresh();
    } catch {
      setMessage("Couldn't run the chase. Check that the engine is running and try again.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      {data.online === false && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive"
        >
          Can't reach the guardian's engine. Check that it's running, then this page will
          reconnect on its own.
        </div>
      )}
      <ShiftBar busy={busy} message={message} onNightly={runNightly} onChase={runChase} />
      <StatStrip ledger={data.ledger} pendingCount={data.decisions.length} loading={loading} />

      {/* map / ledger view switch */}
      <div className="flex items-center justify-end gap-1" role="group" aria-label="View">
        <Button
          variant={view === "map" ? "default" : "outline"}
          size="sm"
          onClick={() => setView("map")}
          aria-pressed={view === "map"}
        >
          <MapIcon className="size-3.5" aria-hidden="true" /> Map
        </Button>
        <Button
          variant={view === "ledger" ? "default" : "outline"}
          size="sm"
          onClick={() => setView("ledger")}
          aria-pressed={view === "ledger"}
        >
          <List className="size-3.5" aria-hidden="true" /> List
        </Button>
      </div>

      {view === "map" ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="overflow-hidden rounded-md border border-border bg-surface-1 lg:col-span-2">
            <h2 className="sr-only">Watch map</h2>
            {loading ? (
              <Skeleton className="h-[420px] rounded-none border-0" />
            ) : (
              <CityMap data={data.mapData} onDataStale={data.refresh} />
            )}
          </section>
          <section className="flex flex-col rounded-md border border-border bg-surface-1">
            <NightLogHeader events={data.activity} />
            <div className="rule-dashed mx-4" />
            {loading ? (
              <div className="space-y-3 p-4">
                {[...Array(6)].map((_, i) => (
                  <Skeleton key={i} className="h-4 w-3/4" />
                ))}
              </div>
            ) : (
              <NightLog events={data.activity} />
            )}
          </section>
        </div>
      ) : (
        <LedgerTable ledger={data.ledger} filter={filter} onFilter={setFilter} />
      )}

      {view === "map" && <LedgerTable ledger={data.ledger} filter={filter} onFilter={setFilter} />}
    </div>
  );
}
