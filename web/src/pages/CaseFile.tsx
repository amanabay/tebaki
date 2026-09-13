import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Clock, HeartHandshake, Send, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusStamp } from "@/components/StatusStamp";
import { Skeleton } from "@/components/Skeleton";
import { CaseTimeline } from "@/components/CaseTimeline";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { api, type CaseFile } from "@/lib/api";
import {
  categoryLabel,
  daysUntil,
  reportersLabel,
  timeAgo,
} from "@/lib/strings";

function Deadline({ label, iso }: { label: string; iso: string | null }) {
  const days = daysUntil(iso);
  if (days === null) return null;
  const overdue = days < 0;
  const soon = days >= 0 && days < 2;
  return (
    <p
      className={
        "num flex items-center gap-1.5 text-[12px] " +
        (overdue ? "text-status-escalated" : soon ? "text-primary" : "text-muted-foreground")
      }
    >
      <Clock className="size-3.5" aria-hidden="true" />
      {label}:{" "}
      {overdue ? `${Math.abs(days)}d overdue` : `${days}d left`}
    </p>
  );
}

function StatusRecorder({ complaintId, onRecorded }: { complaintId: string; onRecorded: () => void }) {
  const [status, setStatus] = useState<"acknowledged" | "resolved">("resolved");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="rounded-md border border-border bg-surface-1 p-4">
      <p className="micro-label">the office replied?</p>
      <h3 className="mt-0.5 font-serif text-base font-semibold">Record the city's response</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Email filings have no ticket status — record what the office told you, and the chase
        respects it.
      </p>
      <div className="mt-3 flex gap-2" role="group" aria-label="Response type">
        {(["acknowledged", "resolved"] as const).map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={status === s}
            onClick={() => setStatus(s)}
            className={
              "rounded-full border px-3 py-1 text-xs transition-colors " +
              (status === s
                ? "border-primary/60 bg-primary/10 font-medium text-primary"
                : "border-border text-muted-foreground hover:text-foreground")
            }
          >
            {s === "acknowledged" ? "Acknowledged" : "Resolved"}
          </button>
        ))}
      </div>
      <label htmlFor="status-note" className="micro-label mt-3 mb-1.5 block">
        note
      </label>
      <Textarea
        id="status-note"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        maxLength={1000}
        placeholder="e.g. Ward office confirmed by phone, crew coming Thursday"
        className="resize-none text-sm"
      />
      {error && (
        <p className="mt-2 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}
      <Button
        className="mt-3"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError(null);
          api
            .setComplaintStatus(complaintId, status, note)
            .then(onRecorded)
            .catch(() =>
              setError("Couldn't record the response. Check the engine is running and try again."),
            )
            .finally(() => setBusy(false));
        }}
      >
        <Send className="size-4" aria-hidden="true" />
        {busy ? "Recording…" : `Mark as ${status}`}
      </Button>
    </div>
  );
}

export function CaseFilePage() {
  const { complaintId } = useParams<{ complaintId: string }>();
  const [file, setFile] = useState<CaseFile | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [supporting, setSupporting] = useState(false);
  const [ownerName, setOwnerName] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  const reload = () => {
    if (!complaintId) return;
    api
      .caseFile(complaintId)
      .then(setFile)
      .catch(() => setNotFound(true));
  };

  useEffect(reload, [complaintId]);

  if (notFound) {
    return (
      <div className="mx-auto max-w-lg py-16 text-center">
        <h1 className="font-serif text-2xl font-semibold">Case not found.</h1>
        <Link to="/ledger" className="mt-3 inline-block text-sm text-primary underline-offset-4 hover:underline">
          Back to the ledger
        </Link>
      </div>
    );
  }

  if (!file) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const active = ["filed", "acknowledged", "escalated"].includes(file.status) || file.status.startsWith("escalated");

  return (
    <article className="mx-auto max-w-3xl">
      <Link
        to="/ledger"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Back to the ledger
      </Link>

      <header className="border-b border-border pb-4">
        <p className="micro-label">
          case file · <span className="num">{file.complaint_id}</span>
        </p>
        <h1 className="mt-1 font-serif text-2xl leading-snug font-semibold text-balance">
          {file.subject ?? "Complaint"}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
          <StatusStamp status={file.status} />
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Users className="size-3.5 text-primary" aria-hidden="true" />
            {reportersLabel(file.reporters)} reported
            {file.plus_ones > 0 && ` · ${file.plus_ones} corroborated`}
          </span>
          {file.category && (
            <span className="text-xs text-muted-foreground">
              {categoryLabel(file.category)}
            </span>
          )}
          <span className="text-xs text-muted-foreground">{file.ward}</span>
        </div>
      </header>

      <div className="space-y-8 py-6">
        <section className="rounded-md border border-primary/30 bg-primary/5 p-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="micro-label text-primary">neighborhood action</p>
              <h2 className="mt-0.5 font-serif text-lg font-semibold">Keep this issue visible</h2>
              <p className="mt-1 text-sm text-muted-foreground">Corroborate this case so the team knows how many neighbors are affected.</p>
            </div>
            <Button
              variant="outline"
              disabled={supporting}
              onClick={() => { setSupporting(true); api.supportCase(file.complaint_id).then(reload).finally(() => setSupporting(false)); }}
            >
              <HeartHandshake className="size-4" aria-hidden="true" />
              {supporting ? "Adding…" : `Support · ${file.support_count ?? file.plus_ones}`}
            </Button>
          </div>
          {(file.owner_name || file.next_action) && (
            <div className="mt-4 grid gap-3 border-t border-primary/20 pt-3 text-sm sm:grid-cols-2">
              <p><span className="micro-label block">community steward</span>{file.owner_name ?? "Unassigned"}{file.owner_role ? ` · ${file.owner_role}` : ""}</p>
              <p><span className="micro-label block">next action</span>{file.next_action ?? "The guardian is preparing the next update."}</p>
            </div>
          )}
          <details className="mt-4 border-t border-primary/20 pt-3">
            <summary className="cursor-pointer text-xs font-semibold text-primary">Assign a community steward</summary>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <input aria-label="Steward name" value={ownerName} onChange={(e) => setOwnerName(e.target.value)} placeholder="Steward name" className="min-h-10 rounded-md border border-border bg-background px-3 text-sm" />
              <input aria-label="Next action" value={nextAction} onChange={(e) => setNextAction(e.target.value)} placeholder="Next action" className="min-h-10 rounded-md border border-border bg-background px-3 text-sm" />
            </div>
            {assignError && <p className="mt-2 text-xs text-destructive">{assignError}</p>}
            <Button className="mt-2" size="sm" disabled={assigning || !ownerName.trim() || !nextAction.trim()} onClick={() => {
              setAssigning(true); setAssignError(null);
              api.assignSteward(file.complaint_id, { owner_name: ownerName, owner_role: "community steward", next_action: nextAction })
                .then(reload).catch((err) => setAssignError(err instanceof Error ? err.message : "Operator access required"))
                .finally(() => setAssigning(false));
            }}>{assigning ? "Assigning…" : "Save assignment"}</Button>
          </details>
        </section>

        <CaseTimeline events={file.timeline} />

        {/* the complaint text */}
        <section aria-labelledby="complaint-heading">
          <h2 id="complaint-heading" className="micro-label mb-2">
            the complaint
          </h2>
          <div className="rounded-md border border-border bg-surface-1 p-4">
            <p className="text-sm leading-relaxed text-pretty">{file.text ?? "—"}</p>
            {file.cite && (
              <p className="mt-3 border-l-2 border-primary/60 pl-3 text-xs text-muted-foreground italic">
                Legal basis: {file.cite}
              </p>
            )}
            {file.filed_at && (
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-border/50 pt-3">
                <p className="num text-[12px] text-muted-foreground">
                  filed {timeAgo(file.filed_at)} via {file.channel}
                </p>
                <p className="num text-[12px] text-muted-foreground">
                  ticket {file.ticket_id ?? "—"} · {file.ticket_status ?? "pending"}
                </p>
                <Deadline label="ack deadline" iso={file.ack_deadline} />
                <Deadline label="resolve deadline" iso={file.resolve_deadline} />
              </div>
            )}
          </div>
        </section>

        <EvidenceDrawer file={file} />

        {/* the neighbors */}
        <section aria-labelledby="reports-heading">
          <h2 id="reports-heading" className="micro-label mb-2">
            the neighbors · {file.reports.length + file.plus_ones} residents
          </h2>
          <ul className="space-y-2">
            {file.reports.map((r) => (
              <li key={r.report_id} className="rounded-md border border-border bg-surface-1 p-3.5">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-sm font-medium">{r.reporter}</p>
                  <p className="num text-[11px] text-muted-foreground">
                    {r.report_id} · {timeAgo(r.created_at)}
                  </p>
                </div>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground text-pretty">
                  "{r.note}"
                </p>
                <p className="num mt-1.5 text-[11px] text-muted-foreground">
                  sev {r.severity}
                  {r.plus_ones > 0 && ` · ${r.plus_ones} corroborated`}
                  {r.language === "am" && " · Amharic report"}
                </p>
              </li>
            ))}
            {file.plus_ones > 0 && (
              <li className="rounded-md border border-dashed border-border p-3.5 text-sm text-muted-foreground">
                +{file.plus_ones} neighbors corroborated without filing separate reports.
              </li>
            )}
          </ul>
        </section>

        {/* escalation trail */}
        {file.escalation_log.length > 0 && (
          <section aria-labelledby="escalation-heading">
            <h2 id="escalation-heading" className="micro-label mb-2">
              the follow-up
            </h2>
            <ol className="relative space-y-3 border-l border-border pl-5">
              {file.escalation_log.map((e, i) => (
                <li key={i} className="relative">
                  <span
                    className="absolute top-2 -left-[26px] flex size-3 items-center justify-center rounded-full border border-primary bg-background"
                    aria-hidden="true"
                  />
                  <div className="rounded-md border border-border bg-surface-1 p-3.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="text-sm font-medium">
                        Level {e.level} → {e.target}
                      </p>
                      <p className="num text-[11px] text-muted-foreground">
                        {e.at ? timeAgo(e.at) : "—"} ·{" "}
                        {e.delivered ? (
                          <span className="text-status-filed">letter sent</span>
                        ) : (
                          <span className="text-status-escalated">not delivered</span>
                        )}
                      </p>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{e.subject}</p>
                    {e.text && (
                      <p className="mt-1 text-sm leading-relaxed text-muted-foreground text-pretty">
                        {e.text}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* record the response */}
        {active && <StatusRecorder complaintId={file.complaint_id} onRecorded={reload} />}
      </div>
    </article>
  );
}
