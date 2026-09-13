import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, Database, ShieldCheck } from "lucide-react";
import { api, type DiagnosticsData } from "@/lib/api";
import { Skeleton } from "@/components/Skeleton";
import { eventCopy, timeAgo } from "@/lib/strings";

export function Diagnostics() {
  const [data, setData] = useState<DiagnosticsData | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { api.diagnostics().then(setData).catch(() => setFailed(true)); }, []);
  if (!data && !failed) return <div className="mx-auto max-w-3xl"><Skeleton className="h-48 w-full" /></div>;
  if (failed) return <div className="mx-auto max-w-3xl rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">Unable to load diagnostics. Check the engine connection and try again.</div>;
  return <div className="mx-auto max-w-3xl space-y-6">
    <header><p className="micro-label">resilience checks</p><h1 className="mt-1 font-serif text-2xl font-bold">System diagnostics</h1><p className="mt-1.5 text-sm text-muted-foreground">Guardrails retain work, surface failures, and require an operator before external action.</p><div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground"><span className="rounded border border-border px-2 py-1">{data!.city ?? "active city"}</span><span className="rounded border border-border px-2 py-1">{data!.model_mode ?? "model unknown"}</span><span className="rounded border border-border px-2 py-1">{data!.persistence ?? "persistence unknown"}</span><span className="rounded border border-border px-2 py-1">delivery: {(data!.delivery_mode ?? "unknown").replace("_", " ")}</span></div></header>
    <section className="grid gap-3 sm:grid-cols-2">{data!.checks.map((check) => { const attention = check.state === "attention"; const local = check.state === "local_only"; const Icon = attention ? CircleAlert : local ? Database : ShieldCheck; return <article key={check.id} className="rounded-md border border-border bg-surface-1 p-4"><div className="flex items-center gap-2"><Icon className={(attention ? "text-status-escalated" : local ? "text-status-pending" : "text-status-filed") + " size-4"} aria-hidden="true" /><h2 className="text-sm font-semibold">{check.label}</h2></div><p className="mt-2 text-xs leading-relaxed text-muted-foreground">{check.detail}</p><p className="mt-3 text-xs font-semibold">{attention ? "Needs attention" : local ? "Local-only" : "Ready"}</p></article>; })}</section>
    <section className="rounded-md border border-border bg-surface-1"><header className="border-b border-border px-4 py-3"><p className="micro-label">recent guardrail events</p><h2 className="mt-0.5 font-serif text-lg font-semibold">Failures and recoveries</h2></header>{data!.incidents.length === 0 ? <p className="p-5 text-sm text-muted-foreground"><CheckCircle2 className="mr-2 inline size-4 text-status-filed" aria-hidden="true" />No recent guardrail incidents. New failures will remain visible here.</p> : <ol className="divide-y divide-border/50">{data!.incidents.map((incident, index) => <li key={`${incident.run_id}-${index}`} className="px-4 py-3"><p className="text-sm font-medium">{eventCopy(incident.kind, incident)}</p><p className="mt-1 text-xs text-muted-foreground">{String(incident.resulting_action ?? incident.detail ?? "Recorded for operator review")} · {timeAgo(incident.at)}</p></li>)}</ol>}</section>
  </div>;
}
