import { useCallback, useEffect, useState } from "react";
import { MoonStar, Pencil, ThumbsDown, Stamp, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { StatusStamp } from "@/components/StatusStamp";
import {
  api,
  type DecisionCard as DecisionCardT,
  type ResolveOutcome,
} from "@/lib/api";
import { CATEGORIES, reportersLabel, timeAgo } from "@/lib/strings";

function SeverityDots({ level }: { level: number }) {
  return (
    <span className="inline-flex items-center gap-1" title={`severity ${level}/5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          className={"size-1.5 rounded-full " + (n <= level ? "bg-primary" : "bg-border")}
        />
      ))}
    </span>
  );
}

function amLabel(value: string): string {
  return CATEGORIES.find((c) => c.value === value)?.am ?? "";
}

type ResolvedState = { outcome: ResolveOutcome };

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

  const resolve = useCallback(
    async (action: "approve" | "edit" | "drop", fields?: Record<string, string>) => {
      setBusy(true);
      setError(null);
      try {
        const outcome = await api.resolveDecision(card.card_id, action, fields);
        setResolved({ outcome });
        window.setTimeout(onResolved, 2100);
      } catch (e) {
        setError(String(e));
        setBusy(false);
      }
    },
    [card.card_id, onResolved],
  );

  const dropped = resolved?.outcome.action === "drop";

  return (
    <article
      className={
        "relative rounded-md border border-border bg-surface-1 transition-opacity " +
        (resolved ? "pointer-events-none opacity-80" : "")
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
              <p className="micro-label mb-1.5">subject</p>
              <Textarea
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                rows={1}
                className="resize-none text-sm"
              />
            </div>
            <div>
              <p className="micro-label mb-1.5">complaint text</p>
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                className="resize-none text-sm"
              />
            </div>
          </div>
        ) : (
          <>
            <h3 className="text-lg leading-snug font-semibold">{card.draft.subject}</h3>
            <p className="text-sm leading-relaxed text-muted-foreground">{card.draft.text}</p>
          </>
        )}

        {/* form fields */}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="micro-label">ward</dt>
            <dd className="mt-0.5 truncate">{String(card.context.ward ?? "—")}</dd>
          </div>
          <div>
            <dt className="micro-label">category</dt>
            <dd className="mt-0.5">
              {card.draft.category} <span className="font-ethiopic text-xs text-muted-foreground">{amLabel(card.draft.category)}</span>
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
            <dd className="num mt-0.5 text-[12px]">
              {card.draft.report_refs.length} merged
            </dd>
          </div>
        </dl>

        {card.draft.cite && (
          <p className="border-l-2 border-primary/60 pl-3 text-xs text-muted-foreground italic">
            Legal basis: {card.draft.cite}
          </p>
        )}

        {Array.isArray(card.context.reporters) && (card.context.reporters as string[]).length > 0 && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Users className="size-3.5 text-primary" />
            {reportersLabel(card.context.reporters as string[])} reported this
          </p>
        )}

        {error && (
          <p className="rounded border border-status-escalated/40 bg-status-escalated/10 px-3 py-2 text-xs text-status-escalated">
            {error}
          </p>
        )}

        <div className="rule-dashed" />

        {resolved ? (
          <div className="flex min-h-16 items-center justify-between gap-4">
            {dropped ? (
              <StatusStamp status="dropped" animate />
            ) : (
              <StatusStamp status="filed" animate />
            )}
            {!dropped && resolved.outcome.ticket_id && (
              <p className="num text-xs text-muted-foreground">
                ticket {resolved.outcome.ticket_id} · via {resolved.outcome.channel}
              </p>
            )}
          </div>
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
              <Stamp className="size-4" />
              {busy ? "Filing…" : "Approve & file"}
            </Button>
            <Button variant="outline" disabled={busy} onClick={() => setEditing(true)}>
              <Pencil className="size-4" /> Edit
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => resolve("drop")}
              className="text-status-escalated hover:text-status-escalated"
            >
              <ThumbsDown className="size-4" /> Drop
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}

export function Decisions() {
  const [cards, setCards] = useState<DecisionCardT[] | null>(null);
  const [offline, setOffline] = useState(false);

  const refresh = useCallback(() => {
    api
      .listDecisions()
      .then((c) => {
        setCards(c);
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="micro-label">the one thing the guardian asks of you</p>
        <h2 className="mt-1 text-2xl font-bold">Filing decisions</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Everything else runs on its own. Complaints only go out after your word.
        </p>
      </div>

      {offline && (
        <div className="rounded-md border border-primary/40 bg-primary/10 px-4 py-2.5 text-sm text-primary">
          Can't reach the guardian's engine — is it running?
        </div>
      )}

      {cards === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : cards.length === 0 ? (
        <div className="rounded-md border border-dashed border-border bg-surface-1 px-6 py-14 text-center">
          <MoonStar className="mx-auto size-8 text-primary" />
          <h3 className="mt-3 font-semibold">Nothing waiting on you.</h3>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            The guardian is caught up. New complaint drafts pause here for your approval before
            they're filed.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {cards.map((card) => (
            <DecisionCardView key={card.card_id} card={card} onResolved={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}
