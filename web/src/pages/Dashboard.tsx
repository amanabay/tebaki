import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CityMap } from "@/components/CityMap";
import { NightLog, NightLogHeader } from "@/components/NightLog";
import { StatusStamp } from "@/components/StatusStamp";
import { api, type ActivityEvent, type LedgerRow, type MapData, type ScoreboardRow } from "@/lib/api";
import { categoryLabel, timeAgo } from "@/lib/strings";

function StatStrip({ ledger, pendingCount }: { ledger: LedgerRow[]; pendingCount: number }) {
  const filed = ledger.filter((r) => r.status === "filed" || r.status.startsWith("escalated")).length;
  const escalated = ledger.filter((r) => r.status.startsWith("escalated")).length;
  const stats = [
    { label: "complaints", value: ledger.length, tone: "text-foreground" },
    { label: "filed", value: filed, tone: "text-status-filed" },
    { label: "escalated", value: escalated, tone: "text-status-escalated" },
    { label: "awaiting you", value: pendingCount, tone: "text-primary" },
  ];
  return (
    <div className="mb-6 grid grid-cols-2 divide-border rounded-md border border-border bg-surface-1 sm:grid-cols-4 sm:divide-x">
      {stats.map((s) => (
        <Link
          to={s.label === "awaiting you" && s.value > 0 ? "/decisions" : "/"}
          key={s.label}
          className="px-5 py-4 transition-colors hover:bg-surface-2"
        >
          <p className="micro-label">{s.label}</p>
          <p className={`num mt-1 text-3xl font-bold ${s.tone}`}>{s.value}</p>
        </Link>
      ))}
    </div>
  );
}

function LedgerTable({ ledger }: { ledger: LedgerRow[] }) {
  return (
    <section className="rounded-md border border-border bg-surface-1">
      <header className="flex items-baseline justify-between border-b border-border px-4 py-3">
        <div>
          <p className="micro-label">civic gazette</p>
          <h3 className="mt-0.5 font-semibold">Complaint ledger</h3>
        </div>
        <span className="num text-[11px] text-muted-foreground">{ledger.length} entries</span>
      </header>
      {ledger.length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">
          Nothing filed yet. Report an issue and tonight's cycle will draft a complaint for it.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                {["complaint", "ward", "category", "status", "ticket", "filed"].map((h) => (
                  <th key={h} className="micro-label px-4 py-2.5 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ledger.map((row) => (
                <tr
                  key={row.complaint_id}
                  className="border-b border-border/50 last:border-0 hover:bg-surface-2/50"
                >
                  <td className="max-w-64 px-4 py-3">
                    <p className="truncate">{row.subject ?? "—"}</p>
                    <p className="num text-[11px] text-muted-foreground">{row.complaint_id}</p>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{row.ward}</td>
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

function Scoreboard({ rows }: { rows: ScoreboardRow[] }) {
  const max = Math.max(1, ...rows.map((r) => r.complaints));
  return (
    <section className="rounded-md border border-border bg-surface-1">
      <header className="border-b border-border px-4 py-3">
        <p className="micro-label">responsiveness</p>
        <h3 className="mt-0.5 font-semibold">Ward scoreboard</h3>
      </header>
      {rows.length === 0 ? (
        <p className="p-6 text-sm text-muted-foreground">No ward data yet.</p>
      ) : (
        <ul className="divide-y divide-border/50">
          {rows.map((row) => (
            <li key={row.ward} className="px-4 py-3">
              <div className="flex items-baseline justify-between gap-4">
                <span className="truncate text-sm">{row.ward}</span>
                <span className="num text-[11px] text-muted-foreground">
                  {row.filed}/{row.complaints} filed
                  {row.escalated > 0 && (
                    <span className="text-status-escalated"> · {row.escalated} esc</span>
                  )}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary/70"
                  style={{ width: `${(row.complaints / max) * 100}%` }}
                >
                  <div
                    className="h-full bg-status-escalated/80"
                    style={{ width: `${(row.escalated / Math.max(1, row.complaints)) * 100}%` }}
                  />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Dashboard() {
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [scoreboard, setScoreboard] = useState<ScoreboardRow[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [pending, setPending] = useState(0);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      Promise.all([
        api.ledger().catch(() => [] as LedgerRow[]),
        api.scoreboard().catch(() => [] as ScoreboardRow[]),
        api.activity().catch(() => [] as ActivityEvent[]),
        api.mapData().catch(() => null),
        api.listDecisions().catch(() => null),
      ]).then(([l, s, a, m, d]) => {
        if (!alive) return;
        setOffline(d === null);
        setLedger(l);
        setScoreboard(s);
        setActivity(a);
        if (m) setMapData(m);
        setPending(d?.length ?? 0);
      });
    load();
    const t = setInterval(load, 6000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <div className="space-y-6">
      {offline && (
        <div className="rounded-md border border-primary/40 bg-primary/10 px-4 py-2.5 text-sm text-primary">
          Engine offline — start it with the API server, then this page comes alive.
        </div>
      )}
      <StatStrip ledger={ledger} pendingCount={pending} />
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="overflow-hidden rounded-md border border-border bg-surface-1 lg:col-span-2">
          <header className="flex items-baseline justify-between px-4 pt-4 pb-2">
            <div>
              <p className="micro-label">the city at night</p>
              <h3 className="mt-0.5 font-semibold">Watch map</h3>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="inline-block size-2 rounded-full bg-primary" /> reports
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block size-2.5 rounded-full border border-status-filed" />{" "}
                filed
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block size-2.5 rounded-full border border-status-escalated" />{" "}
                escalated
              </span>
            </div>
          </header>
          <CityMap data={mapData} />
        </section>
        <section className="flex flex-col rounded-md border border-border bg-surface-1">
          <NightLogHeader events={activity} />
          <div className="rule-dashed mx-4" />
          <NightLog events={activity} />
        </section>
      </div>
      <LedgerTable ledger={ledger} />
      <Scoreboard rows={scoreboard} />
    </div>
  );
}
