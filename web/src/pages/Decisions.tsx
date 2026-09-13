import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { MoonStar, Pencil, ShieldAlert, ThumbsDown, Stamp, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusStamp } from "@/components/StatusStamp";
import { Skeleton } from "@/components/Skeleton";
import { WatchButton } from "@/pages/Watchlist";
import {
  api,
  type DecisionCard as DecisionCardT,
  type ResolveOutcome,
} from "@/lib/api";
import { reportersLabel, timeAgo } from "@/lib/strings";
import type { EngineData } from "@/lib/useEngineData";

function SeverityDots({ level }: { level: number }) {
  return (
    <span
      className="inline-flex items-center gap-1"
      role="img"
      aria-label={`severity ${level} of 5`}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          className={"size-1.5 rounded-full " + (n <= level ? "bg-primary" : "bg-border")}
          aria-hidden="true"
        />
      ))}
    </span>
  );
}

type ResolvedState = { outcome: ResolveOutcome };

function ConfirmDrop({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div
      role="alertdialog"
      aria-labelledby="drop-title"
      aria-describedby="drop-body"
      className="rounded-md border border-status-escalated/40 bg-status-escalated/5 p-4"
    >
      <h3 id="drop-title" className="font-serif text-base font-semibold">
        Drop this complaint?
      </h3>
      <p id="drop-body" className="mt-1 text-sm text-muted-foreground">
        The draft is discarded and the case is closed. This can't be undone.
      </p>
      <div className="mt-3 flex gap-2">
        <Button
          variant="destructive"
          onClick={onConfirm}
          className="bg-destructive/10 text-destructive hover:bg-destructive/20"
        >
          Drop complaint
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function DecisionCardView({
  card,
  onResolved,
}: {
  card: DecisionCardT;
  onResolved: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(card.draft.subject);
  const [text, setText] = useState(card.draft.text);
  const [resolved, setResolved] = useState<ResolvedState | null>(null);
  const [confirmingDrop, setConfirmingDrop] = useState(false);

  const resolve = useCallback(
    async (action: "approve" | "edit" | "drop", fields?: Record<string, string>) => {
      setBusy(true);
      setError(null);
      setConfirmingDrop(false);
      try {
        const outcome = await api.resolveDecision(card.card_id, action, fields);
        setResolved({ outcome });
        onResolved();
      } catch {
        setError("Couldn't file the complaint. Check the engine is running and try again.");
        setBusy(false);
      }
    },
    [card.card_id, onResolved],
  );

  const dropped = resolved?.outcome.action === "drop";

  return (
    <article
      className={
        "relative rounded-md border border-border bg-surface-1 " +
        (resolved ? "opacity-90" : "")
      }
    >
      {/* document header */}
      <header className="flex items-baseline justify-between border-b border-border/60 px-5 py-3">
        <p className="micro-label">
          filing decision · <span className="num">{card.card_id}</span>
        </p>
        <p className="num text-[11px] text-muted-foreground">{timeAgo(card.created_at)}</p>
      </header>

      <div className="space-y-4 px-5 py-4">
        {editing ? (
          <div className="space-y-3">
            <div>
              <label htmlFor={`subject-${card.card_id}`} className="micro-label mb-1.5 block">
                subject
              </label>
              <Textarea
                id={`subject-${card.card_id}`}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                rows={1}
                className="resize-none text-sm"
              />
            </div>
            <div>
              <label htmlFor={`text-${card.card_id}`} className="micro-label mb-1.5 block">
                complaint text
              </label>
              <Textarea
                id={`text-${card.card_id}`}
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                className="resize-none text-sm"
              />
            </div>
          </div>
        ) : (
          <>
            <h2 className="text-lg leading-snug font-semibold text-balance">
              {card.draft.subject}
            </h2>
            <p className="text-sm leading-relaxed text-pretty text-muted-foreground">
              {card.draft.text}
            </p>
          </>
        )}

        {/* form fields */}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="micro-label">ward</dt>
            <dd className="mt-0.5 truncate" title={String(card.context.ward ?? "—")}>
              {String(card.context.ward ?? "—")}
            </dd>
          </div>
          <div>
            <dt className="micro-label">category</dt>
            <dd className="mt-0.5">
              {card.draft.category}
            </dd>
          </div>
          <div>
            <dt className="micro-label">severity</dt>
            <dd className="mt-1.5">
              <SeverityDots level={card.draft.severity} />
            </dd>
          </div>
          <div>
            <dt className="micro-label">reports</dt>
            <dd className="num mt-0.5 text-[12px]">{card.draft.report_refs.length} merged</dd>
          </div>
        </dl>

        {card.draft.cite && (
          <p className="border-l-2 border-primary/60 pl-3 text-xs text-muted-foreground italic">
            Legal basis: {card.draft.cite}
          </p>
        )}

        {Array.isArray(card.context.reporters) && (card.context.reporters as string[]).length > 0 && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Users className="size-3.5 text-primary" aria-hidden="true" />
            {reportersLabel(card.context.reporters as string[])} reported this
          </p>
        )}

        {Array.isArray(card.context.privacy_flags) &&
          (card.context.privacy_flags as string[]).length > 0 && (
            <p className="flex items-start gap-2 rounded border border-primary/40 bg-primary/10 px-3 py-2 text-xs text-primary">
              <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <span>
                Personal data found and redacted:{" "}
                {(card.context.privacy_flags as string[]).join(", ")}. The filing uses the
                redacted text — use Edit to restore anything the neighborhood consents to share.
              </span>
            </p>
          )}

        {error && (
          <p
            role="alert"
            className="rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
          >
            {error}
          </p>
        )}

        <div className="rule-dashed" />

        {resolved ? (
          <div className="flex min-h-16 items-center justify-between gap-4">
            {dropped ? <StatusStamp status="dropped" animate /> : <StatusStamp status="filed" animate />}
            <div className="flex items-center gap-3">
              {!dropped && resolved.outcome.ticket_id && (
                <p className="num text-xs text-muted-foreground">
                  ticket {resolved.outcome.ticket_id} · via {resolved.outcome.channel}
                </p>
              )}
              {!dropped && (
                <Link
                  to={`/case/${resolved.outcome.complaint_id}`}
                  className="text-xs text-primary underline-offset-4 hover:underline"
                >
                  Open the case file
                </Link>
              )}
              <WatchButton complaintId={resolved.outcome.complaint_id} />
            </div>
          </div>
        ) : confirmingDrop ? (
          <ConfirmDrop
            onConfirm={() => resolve("drop")}
            onCancel={() => setConfirmingDrop(false)}
          />
        ) : editing ? (
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy || !text.trim()}
              onClick={() => resolve("edit", { subject, text })}
            >
              {busy ? "Filing…" : "File as edited"}
            </Button>
            <Button variant="ghost" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button disabled={busy} onClick={() => resolve("approve")}>
              <Stamp className="size-4" aria-hidden="true" />
              {busy ? "Filing…" : "Approve & file"}
            </Button>
            <Button variant="outline" disabled={busy} onClick={() => setEditing(true)}>
              <Pencil className="size-4" aria-hidden="true" /> Edit
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => setConfirmingDrop(true)}
              className="text-destructive hover:text-destructive"
            >
              <ThumbsDown className="size-4" aria-hidden="true" /> Drop
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}

export function Decisions({ data }: { data: EngineData }) {
  // severity-first ordering: highest severity at the top
  const sorted = [...data.decisions].sort(
    (a, b) => (b.draft.severity ?? 3) - (a.draft.severity ?? 3),
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="micro-label">the one thing the guardian asks of you</p>
        <h1 className="mt-1 font-serif text-2xl font-bold">Filing decisions</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Everything else runs on its own. Complaints only go out after your word — highest
          severity first.
        </p>
      </div>

      {data.online === false && (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive"
        >
          Can't reach the guardian's engine. Check that it's running, then this page will
          reconnect on its own.
        </div>
      )}

      {data.decisionsError && /401|403|unauthori|forbidden/i.test(data.decisionsError) && (
        <div
          role="status"
          className="rounded-md border border-primary/30 bg-primary/5 px-4 py-3 text-sm"
        >
          <p className="font-semibold">Operator access is required to review filings.</p>
          <p className="mt-1 text-muted-foreground">
            Select the shield in the top bar, enter your operator token, then return here. The
            public map and case history remain available without it.
          </p>
        </div>
      )}

      {data.online === null ? (
        <div className="space-y-5">
          {[...Array(2)].map((_, i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : sorted.length === 0 ? (
        <div className="rounded-md border border-dashed border-border bg-surface-1 px-6 py-14 text-center">
          <MoonStar className="mx-auto size-8 text-primary" aria-hidden="true" />
          <h2 className="mt-3 font-serif text-lg font-semibold">Nothing waiting on you.</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            New reports are reviewed on the map first. Complaint drafts appear here only after a
            processing run groups nearby reports into one case.
          </p>
          <Link to="/" className="mt-4 inline-block text-sm font-semibold text-primary underline-offset-4 hover:underline">
            Go to the operations map
          </Link>
        </div>
      ) : (
        <div className="space-y-5">
          {sorted.map((card) => (
            <DecisionCardView key={card.card_id} card={card} onResolved={data.refresh} />
          ))}
        </div>
      )}
    </div>
  );
}
