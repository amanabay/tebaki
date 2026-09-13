import { Check, Circle, Clock3, FileText, ShieldCheck, Users } from "lucide-react";
import type { ActivityEvent } from "@/lib/api";
import { timeAgo } from "@/lib/strings";

const STAGES = [
  ["submitted", "Submitted", "Resident"],
  ["triage_done", "Triaged by guardian", "Guardian agent"],
  ["cluster_done", "Grouped with nearby reports", "Cluster agent"],
  ["drafts_ready", "Drafted with evidence", "Drafter agent"],
  ["decision_card", "Waiting for human approval", "Human approval boundary"],
  ["filed", "Filed with city", "Filer agent"],
  ["checked", "Tracked against SLA", "Chaser agent"],
  ["escalated", "Escalated if overdue", "Chaser agent"],
] as const;

const ICONS = [Users, ShieldCheck, Users, FileText, Circle, Check, Clock3, ShieldCheck];

function stageEvent(events: ActivityEvent[], kind: string) {
  return events.find((event) => event.kind === kind);
}

export function CaseTimeline({ events }: { events: ActivityEvent[] }) {
  return (
    <section aria-labelledby="journey-heading">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="micro-label">accountability trail</p>
          <h2 id="journey-heading" className="mt-0.5 font-serif text-lg font-semibold">What the agent did</h2>
        </div>
        <p className="text-xs text-muted-foreground">Every filing requires a human approval.</p>
      </div>
      <ol className="space-y-0 rounded-md border border-border bg-surface-1 p-4">
        {STAGES.map(([kind, label, defaultActor], index) => {
          const event = stageEvent(events, kind);
          const Icon = ICONS[index];
          const complete = Boolean(event);
          return (
            <li key={kind} className="relative flex gap-3 pb-4 last:pb-0">
              {index < STAGES.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-20px)] border-l border-border" aria-hidden="true" />}
              <span className={"relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border " + (complete ? "border-primary bg-primary/15 text-primary" : "border-border bg-surface-2 text-muted-foreground")}>
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <div className="min-w-0 pt-0.5">
                <p className={"text-sm font-semibold " + (complete ? "text-foreground" : "text-muted-foreground")}>{label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {event ? `${String(event.actor ?? defaultActor)} · ${timeAgo(event.at)}` : `${defaultActor} · pending`}
                </p>
                {event?.output_summary != null && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{String(event.output_summary)}</p>}
                {typeof event?.confidence === "number" && <p className="num mt-1 text-[11px] text-primary">confidence {Math.round(event.confidence * 100)}%</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
