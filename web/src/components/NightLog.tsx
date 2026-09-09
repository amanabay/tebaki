import { ScrollArea } from "@/components/ui/scroll-area";
import type { ActivityEvent } from "@/lib/api";
import { cityClock, eventCopy, isAmberEvent, timeAgo } from "@/lib/strings";

export function NightLog({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        No runs yet. The guardian files every night at 02:00 — or start a cycle from the
        dashboard.
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
                "absolute top-3.5 -left-[21px] size-1.5 rounded-full " +
                (isAmberEvent(e.kind) ? "bg-primary" : "bg-border")
              }
              aria-hidden="true"
            />
            <div className="flex items-baseline gap-2">
              <span className="num text-[11px] text-muted-foreground">
                {cityClock(e.at, e.city)}
              </span>
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
        <h2 className="mt-0.5 font-serif text-lg font-semibold">The guardian's log</h2>
      </div>
      {last && (
        <span className="num text-[11px] text-muted-foreground">
          last event {timeAgo(last.at)}
        </span>
      )}
    </div>
  );
}
