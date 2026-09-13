import { useEffect, useMemo, useState } from "react";
import { Play, RotateCcw } from "lucide-react";
import { api, type AgentRun, type RunSummary } from "@/lib/api";
import { eventCopy, timeAgo } from "@/lib/strings";
import { Skeleton } from "@/components/Skeleton";

export function Replay() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<AgentRun | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { api.runs().then(setRuns).catch(() => undefined); }, []);
  useEffect(() => {
    if (!playing || !selected) return;
    const timer = window.setInterval(() => setCursor((value) => {
      if (value >= selected.events.length) { setPlaying(false); return value; }
      return value + 1;
    }), 700);
    return () => window.clearInterval(timer);
  }, [playing, selected]);
  const visible = useMemo(() => selected?.events.slice(0, cursor) ?? [], [selected, cursor]);
  return <div className="mx-auto max-w-3xl space-y-6">
    <header><p className="micro-label">agent run replay</p><h1 className="mt-1 font-serif text-2xl font-bold">Watch the guardian work</h1><p className="mt-1.5 text-sm text-muted-foreground">Replay a recorded run with the tool results and human approval boundary intact.</p></header>
    {!selected ? <section className="rounded-md border border-border bg-surface-1"><header className="border-b border-border px-4 py-3"><h2 className="font-serif text-lg font-semibold">Recorded runs</h2></header>{runs.length === 0 ? <Skeleton className="m-4 h-16" /> : <ul className="divide-y divide-border/50">{runs.map((run) => <li key={run.run_id} className="flex items-center justify-between gap-3 px-4 py-3"><div><p className="num text-sm font-semibold">{run.run_id}</p><p className="text-xs text-muted-foreground">{run.city} · {timeAgo(run.started_at)} · {run.event_count} events</p></div><button type="button" className="min-h-10 rounded-md border border-border px-3 text-xs font-semibold hover:bg-surface-2" onClick={() => { api.run(run.run_id).then((detail) => { setSelected(detail); setCursor(0); }).catch(() => undefined); }}>Open replay</button></li>)}</ul>}</section> : <section className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="num text-sm font-semibold">{selected.run_id}</p><p className="text-xs text-muted-foreground">{selected.city} · {visible.length}/{selected.events.length} events</p></div><div className="flex gap-2"><button type="button" className="inline-flex min-h-10 items-center gap-2 rounded-md bg-primary px-3 text-xs font-bold text-primary-foreground" onClick={() => setPlaying((value) => !value)}><Play className="size-4" aria-hidden="true" />{playing ? "Pause" : "Replay"}</button><button type="button" aria-label="Restart replay" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold" onClick={() => { setCursor(0); setPlaying(false); }}><RotateCcw className="size-4" aria-hidden="true" />Restart</button><button type="button" className="min-h-10 rounded-md px-3 text-xs text-muted-foreground hover:bg-surface-2" onClick={() => setSelected(null)}>All runs</button></div></div><ol className="space-y-2">{visible.map((event, index) => <li key={`${event.at}-${index}`} className="rounded-md border border-border bg-surface-1 p-3"><div className="flex flex-wrap items-baseline justify-between gap-2"><p className="text-sm font-semibold">{eventCopy(event.kind, event)}</p><p className="num text-[11px] text-muted-foreground">{event.at}</p></div><p className="mt-1 text-xs text-muted-foreground">{String(event.actor ?? "agent")} {event.output_summary ? `· ${String(event.output_summary)}` : ""}</p>{event.tool != null && <p className="num mt-1 text-[11px] text-primary">tool: {String(event.tool)}</p>}</li>)}</ol></section>}
  </div>;
}
