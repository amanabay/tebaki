import { CATEGORIES } from "@/lib/strings";
import { Skeleton } from "@/components/Skeleton";
import { StatusStamp } from "@/components/StatusStamp";
import type { EngineData } from "@/lib/useEngineData";
import { statusKind, STATUS_META, type StatusKind } from "@/lib/strings";

function CategoryBars({ counts, total }: { counts: Record<string, number>; total: number }) {
  const max = Math.max(1, ...Object.values(counts));
  return (
    <section className="rounded-md border border-border bg-surface-1">
      <header className="border-b border-border px-4 py-3">
        <p className="micro-label">what the city hears about</p>
        <h2 className="mt-0.5 font-serif text-lg font-semibold">Category distribution</h2>
      </header>
      <ul className="divide-y divide-border/50">
        {CATEGORIES.map((c) => {
          const n = counts[c.value] ?? 0;
          return (
            <li key={c.value} className="flex items-center gap-4 px-4 py-3">
              <span className="w-24 shrink-0 text-sm">
                {c.en}
              </span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary/70"
                  style={{ width: `${(n / max) * 100}%` }}
                  aria-hidden="true"
                />
              </div>
              <span className="num w-8 shrink-0 text-right text-[12px] text-muted-foreground">
                {n}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="num px-4 pb-3 text-[11px] text-muted-foreground">{total} complaints total</p>
    </section>
  );
}

function StatusBreakdown({ ledger }: { ledger: EngineData["ledger"] }) {
  const kinds: StatusKind[] = ["awaiting", "filed", "acknowledged", "escalated", "resolved", "dropped"];
  const counts = kinds.map((k) => ({
    kind: k,
    count: ledger.filter((r) => statusKind(r.status) === k).length,
  }));
  return (
    <section className="rounded-md border border-border bg-surface-1">
      <header className="border-b border-border px-4 py-3">
        <p className="micro-label">where cases stand</p>
        <h2 className="mt-0.5 font-serif text-lg font-semibold">Status of all cases</h2>
      </header>
      <ul className="divide-y divide-border/50">
        {counts.map(({ kind, count }) => (
          <li key={kind} className="flex items-center justify-between gap-4 px-4 py-3">
            <StatusStamp status={kind === "escalated" ? "escalated_1" : kind === "awaiting" ? "awaiting_approval" : kind} />
            <span className="num text-sm font-semibold">{count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Scoreboard({ rows }: { rows: EngineData["scoreboard"] }) {
  const max = Math.max(1, ...rows.map((r) => r.complaints));
  return (
    <section className="rounded-md border border-border bg-surface-1">
      <header className="border-b border-border px-4 py-3">
        <p className="micro-label">responsiveness</p>
        <h2 className="mt-0.5 font-serif text-lg font-semibold">Ward scoreboard</h2>
      </header>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">No ward data yet.</p>
      ) : (
        <ul className="divide-y divide-border/50">
          {rows.map((row) => {
            const awaiting = row.complaints - row.filed;
            const active = row.filed - (row.resolved ?? 0) - row.escalated;
            return (
              <li key={row.ward} className="px-4 py-3">
                <div className="flex items-baseline justify-between gap-4">
                  <span className="truncate text-sm">{row.ward}</span>
                  <span className="num text-[11px] text-muted-foreground">
                    {row.filed}/{row.complaints} filed
                    {(row.resolved ?? 0) > 0 && (
                      <span className="text-status-filed"> · {row.resolved} resolved</span>
                    )}
                    {row.escalated > 0 && (
                      <span className="text-status-escalated"> · {row.escalated} esc</span>
                    )}
                  </span>
                </div>
                <div
                  className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-muted"
                  role="img"
                  aria-label={`${row.ward}: ${row.filed} of ${row.complaints} filed, ${row.resolved ?? 0} resolved, ${row.escalated} escalated`}
                >
                  <div
                    className="bg-status-filed"
                    style={{ width: `${((row.resolved ?? 0) / max) * 100}%` }}
                  />
                  <div
                    className="bg-status-escalated"
                    style={{ width: `${(row.escalated / max) * 100}%` }}
                  />
                  <div className="bg-primary/70" style={{ width: `${(active / max) * 100}%` }} />
                  <div className="bg-border" style={{ width: `${(awaiting / max) * 100}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function Stats({ data }: { data: EngineData }) {
  const loading = data.online === null;
  const counts: Record<string, number> = {};
  for (const row of data.ledger) {
    if (row.category) counts[row.category] = (counts[row.category] ?? 0) + 1;
  }
  void STATUS_META;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="micro-label">Service signals</p>
        <h1 className="mt-1 font-serif text-2xl font-bold">Statistics</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          What the neighborhood reports, how the city responds.
        </p>
      </div>
      {loading ? (
        <>
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </>
      ) : (
        <>
          <CategoryBars counts={counts} total={data.ledger.length} />
          <StatusBreakdown ledger={data.ledger} />
          <Scoreboard rows={data.scoreboard} />
        </>
      )}
    </div>
  );
}
