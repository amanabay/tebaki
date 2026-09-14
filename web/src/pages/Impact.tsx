import { useEffect, useState } from "react";
import { ArrowUpRight, CheckCircle2, Clock3, Users } from "lucide-react";
import { Skeleton } from "@/components/Skeleton";
import { api, type CommunityDigest, type ImpactData, type ProofData } from "@/lib/api";

export function Impact() {
  const [impact, setImpact] = useState<ImpactData | null>(null);
  const [proof, setProof] = useState<ProofData | null>(null);
  const [digest, setDigest] = useState<CommunityDigest | null>(null);
  useEffect(() => { Promise.all([api.impact(), api.proof(), api.communityDigest()]).then(([i, p, d]) => { setImpact(i); setProof(p); setDigest(typeof d.residents_involved === "number" ? d : null); }).catch(() => undefined); }, []);
  if (!impact || !proof) return <div className="mx-auto max-w-3xl space-y-4"><Skeleton className="h-12 w-2/3" /><Skeleton className="h-40 w-full" /></div>;
  const metrics = [
    ["Unresolved cases", impact.unresolved_cases, Clock3],
    ["Resolved cases", impact.resolved_cases, CheckCircle2],
    ["Residents corroborating", impact.corroborations, Users],
    ["Near escalation", impact.approaching_escalation, ArrowUpRight],
  ] as const;
  return <div className="mx-auto max-w-3xl space-y-6">
    <header><p className="micro-label">public service view</p><h1 className="mt-1 font-serif text-2xl font-bold">What the city is hearing</h1><p className="mt-1.5 text-sm text-muted-foreground">A transparent view of issues, response, and the guardian’s work in {proof.city}.</p></header>
    {proof.coverage?.status !== "verified" && <section className="rounded-md border border-status-pending/40 bg-status-pending/10 p-4 text-sm"><p className="font-semibold">Partial sub-city coverage</p><p className="mt-1 text-muted-foreground">{proof.coverage?.pilot_area ?? "No verified sub-city pilot"}. Tebaki uses the verified pilot polygon where available and the published city boundary elsewhere; map and scoreboard labels outside the pilot remain city-level fallback.</p>{proof.coverage?.boundary_source && <a className="mt-2 inline-block text-xs text-primary underline-offset-4 hover:underline" href={proof.coverage.boundary_source} target="_blank" rel="noreferrer">View boundary source</a>}</section>}
    <section className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Impact summary">
      {metrics.map(([label, value, Icon]) => <div key={label} className="rounded-md border border-border bg-surface-1 p-4"><Icon className="size-4 text-primary" aria-hidden="true" /><p className="num mt-3 text-2xl font-bold">{value}</p><p className="mt-1 text-xs text-muted-foreground">{label}</p></div>)}
    </section>
    {digest && <section className="rounded-md border border-primary/30 bg-primary/5 p-4" aria-labelledby="neighbor-heading">
      <p className="micro-label text-primary">good neighbor pulse</p>
      <h2 id="neighbor-heading" className="mt-0.5 font-serif text-lg font-semibold">How the neighborhood is moving</h2>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <p><span className="num block text-xl font-bold">{digest.residents_involved}</span><span className="text-xs text-muted-foreground">residents involved</span></p>
        <p><span className="num block text-xl font-bold">{digest.steward_assigned}</span><span className="text-xs text-muted-foreground">stewards assigned</span></p>
        <p><span className="num block text-xl font-bold">{digest.needs_corroboration}</span><span className="text-xs text-muted-foreground">need corroboration</span></p>
        <p><span className="num block text-xl font-bold">{digest.resolved_cases}</span><span className="text-xs text-muted-foreground">resolved together</span></p>
      </div>
    </section>}
    <section className="rounded-md border border-border bg-surface-1"><header className="border-b border-border px-4 py-3"><p className="micro-label">where attention is needed</p><h2 className="mt-0.5 font-serif text-lg font-semibold">Sub-city scoreboard</h2></header><ul className="divide-y divide-border/50">{impact.wards.length === 0 ? <li className="p-6 text-sm text-muted-foreground">No cases have been filed yet.</li> : impact.wards.map((ward) => <li key={ward.ward} className="flex items-center justify-between gap-4 px-4 py-3"><span className="text-sm">{ward.ward}</span><span className="num text-xs text-muted-foreground">{ward.complaints} cases · {ward.resolved} resolved · {ward.escalated} escalated</span></li>)}</ul></section>
    <section className="rounded-md border border-primary/30 bg-primary/10 p-4"><p className="micro-label text-primary">proof of operation</p><p className="mt-1 text-sm">{proof.reports_triaged} reports triaged · {proof.cases_drafted} drafts · {proof.filed_tickets} filings · {proof.escalations} escalations</p><p className="num mt-2 text-[11px] text-muted-foreground">{proof.model_mode} model · {proof.persistence} persistence · runtime {proof.runtime_status}</p></section>
  </div>;
}
