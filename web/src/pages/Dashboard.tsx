import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MoonStar, Siren } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CityMap } from "@/components/CityMap";
import { NightLog, NightLogHeader } from "@/components/NightLog";
import { StatusStamp } from "@/components/StatusStamp";
import {
  api,
  type ActivityEvent,
  type LedgerRow,
  type MapData,
  type ScoreboardRow,
} from "@/lib/api";
import { categoryLabel, reportersLabel, timeAgo } from "@/lib/strings";

interface RunSummary {
  events?: Array<{ kind: string; [k: string]: unknown }>;
}

function StatStrip({ ledger, pendingCount }: { ledger: LedgerRow[]; pendingCount: number }) {
  const active = ledger.filter(
    (r) => r.status === "filed" || r.status === "acknowledged" || r.status.startsWith("escalated"),
  ).length;
  const escalated = ledger.filter((r) => r.status.startsWith("escalated")).length;
  const resolved = ledger.filter((r) => r.status === "resolved").length;
  const stats = [
    { label: "complaints", value: ledger.length, tone: "text-foreground" },
    { label: "active", value: active, tone: "text-status-filed" },
    { label: "escalated", value: escalated, tone: "text-status-escalated" },
    { label: "resolved", value: resolved, tone: "text-status-filed" },
    { label: "awaiting you", value: pendingCount, tone: "text-primary" },
  ];
  return (
    <div className="mb-6 grid grid-cols-2 divide-border rounded-md border border-border bg-surface-1 sm:grid-cols-5 sm:divide-x">
      {stats.map((s) => (
        <Link
          to={s.label === "awaiting you" && s.value > 0 ? "/decisions" : "/"}
          key={s.label}
          className="px-4 py-4 transition-colors hover:bg-surface-2"
        >
          <p className="micro-label">{s.label}</p>
          <p className={`num mt-1 text-3xl font-bold ${s.tone}`}>{s.value}</p>
        </Link>
      ))}
    </div>
  );
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
        {message && (
          <span className="max-w-72 text-right text-xs text-muted-foreground">{message}</span>
        )}
        <Button onClick={onNightly} disabled={busy !== null}>
          <MoonStar className="size-4" />
          {busy === "nightly" ? "Running…" : "Run tonight's cycle"}
        </Button>
        <Button variant="outline" onClick={onChase} disabled={busy !== null}>
          <Siren className="size-4" />
          {busy === "chase" ? "Chasing…" : "Chase tickets"}
        </Button>
      </div>
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
                {["complaint", "neighbors", "ward", "category", "status", "ticket", "filed"].map(
                  (h) => (
                    <th key={h} className="micro-label px-4 py-2.5 font-semibold">
                      {h}
                    </th>
                  ),
                )}
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
                  <td className="px-4 py-3 text-muted-foreground">
                    {reportersLabel(row.reporters)}
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
          {rows.map((row) => {
            const awaiting = row.complaints - row.filed;
            const active = row.filed - row.resolved - row.escalated;
            return (
              <li key={row.ward} className="px-4 py-3">
                <div className="flex items-baseline justify-between gap-4">
                  <span className="truncate text-sm">{row.ward}</span>
                  <span className="num text-[11px] text-muted-foreground">
                    {row.filed}/{row.complaints} filed
                    {row.resolved > 0 && (
                      <span className="text-status-filed"> · {row.resolved} resolved</span>
                    )}
                    {row.escalated > 0 && (
                      <span className="text-status-escalated"> · {row.escalated} esc</span>
                    )}
                  </span>
                </div>
                <div className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="bg-status-filed"
                    style={{ width: `${(row.resolved / max) * 100}%` }}
                  />
                  <div
                    className="bg-status-escalated"
                    style={{ width: `${(row.escalated / max) * 100}%` }}
                  />
                  <div className="bg-primary/70" style={{ width: `${(active / max) * 100}%` }} />
                  <div
                    className="bg-border"
                    style={{ width: `${(awaiting / max) * 100}%` }}
                  />
                </div>
              </li>
            );
          })}
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
  const [busy, setBusy] = useState<"nightly" | "chase" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api.ledger().catch(() => [] as LedgerRow[]),
      api.scoreboard().catch(() => [] as ScoreboardRow[]),
      api.activity().catch(() => [] as ActivityEvent[]),
      api.mapData().catch(() => null),
      api.listDecisions().catch(() => null),
    ]).then(([l, s, a, m, d]) => {
      setOffline(d === null);
      setLedger(l);
      setScoreboard(s);
      setActivity(a);
      if (m) setMapData(m);
      setPending(d?.length ?? 0);
    });
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, [load]);

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
          ? `${cards} draft${cards > 1 ? "s" : ""} waiting for your decision →`
          : filed > 0
            ? `${filed} complaint${filed > 1 ? "s" : ""} filed.`
            : "Cycle done.",
      );
      load();
    } catch (e) {
      setMessage(`Couldn't run the cycle: ${String(e).slice(0, 100)}`);
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
      load();
    } catch (e) {
      setMessage(`Couldn't run the chase: ${String(e).slice(0, 100)}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      {offline && (
        <div className="rounded-md border border-primary/40 bg-primary/10 px-4 py-2.5 text-sm text-primary">
          Can't reach the guardian's engine — is it running?
        </div>
      )}
      <ShiftBar busy={busy} message={message} onNightly={runNightly} onChase={runChase} />
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
                active
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
