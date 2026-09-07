import { ScrollArea } from "@/components/ui/scroll-area";
import type { ActivityEvent } from "@/lib/api";
import { eventCopy, timeAgo } from "@/lib/strings";

function clock(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const AMBER_KINDS = new Set(["filed", "escalated", "decision_card", "chase_end"]);

export function NightLog({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        No runs yet. The guardian files at 02:00 — or trigger a cycle from the admin API.
      </p>
    );
  }
  return (
    <ScrollArea className="h-[420px]">
      <ol className="relative m-2 space-y-0 border-l border-border pl-4">
        {events.map((e, i) => (
          <li key={`${e.run_id}-${e.at}-${i}`} className="relative py-2.5">
            <span
              className={
                "absolute -left-[21px] top-3.5 size-1.5 rounded-full " +
                (AMBER_KINDS.has(e.kind) ? "bg-primary" : "bg-border")
              }
            />
            <div className="flex items-baseline gap-2">
              <span className="num text-[11px] text-muted-foreground">{clock(e.at)}</span>
              <span className="text-sm">{eventCopy(e.kind, e)}</span>
            </div>
          </li>
        ))}
      </ol>
    </ScrollArea>
  );
}

export function NightLogHeader({ events }: { events: ActivityEvent[] }) {
  const last = events[0];
  return (
    <div className="flex items-baseline justify-between px-4 pt-4 pb-2">
      <div>
        <p className="micro-label">while the city slept</p>
        <h3 className="mt-0.5 font-semibold">The guardian's log</h3>
      </div>
      {last && (
        <span className="num text-[11px] text-muted-foreground">
          last event {timeAgo(last.at)}
        </span>
      )}
    </div>
  );
}
