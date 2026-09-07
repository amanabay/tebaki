export const CATEGORIES = [
  { value: "waste", en: "Waste", am: "ቆሻሻ", icon: "trash" },
  { value: "pothole", en: "Pothole", am: "ጉድጓድ", icon: "construction" },
  { value: "streetlight", en: "Streetlight", am: "መብራት", icon: "lightbulb" },
  { value: "drain", en: "Drain", am: "መውረጃ", icon: "waves" },
  { value: "water", en: "Water", am: "ውሃ", icon: "droplets" },
] as const;

export type CategoryValue = (typeof CATEGORIES)[number]["value"];

export function categoryLabel(value: string): string {
  return CATEGORIES.find((c) => c.value === value)?.en ?? value;
}

export function statusInfo(status: string): { label: string; className: string } {
  if (status === "filed") return { label: "FILED", className: "text-status-filed" };
  if (status.startsWith("escalated_"))
    return { label: `ESCALATED L${status.split("_")[1]}`, className: "text-status-escalated" };
  if (status === "dropped") return { label: "DROPPED", className: "text-status-dropped" };
  if (status === "filing_failed") return { label: "FAILED", className: "text-status-escalated" };
  if (status === "awaiting_approval" || status === "drafted")
    return { label: "AWAITING YOU", className: "text-status-pending" };
  return { label: status.replace(/_/g, " ").toUpperCase(), className: "text-muted-foreground" };
}

export function eventCopy(kind: string, e: Record<string, unknown>): string {
  switch (kind) {
    case "cycle_start":
      return `Nightly cycle started — ${String(e.city)}`;
    case "triage_done":
      return `Triaged ${String(e.accepted)} reports (${String(e.rejected)} rejected)`;
    case "cluster_done":
      return `Clustered into ${String(e.clustered)} hotspots`;
    case "drafts_ready":
      return `${String(e.complaints)} complaint draft(s) ready`;
    case "decision_card":
      return `Filing decision card raised`;
    case "filed":
      return `Filed — ticket ${String(e.ticket_id ?? "—")}`;
    case "dropped":
      return `Dropped at human's request`;
    case "filing_failed":
      return `Filing failed`;
    case "escalated":
      return `Escalated to level ${String(e.level)}`;
    case "resolved":
      return `City resolved ticket ${String(e.ticket_id ?? "—")}`;
    case "checked":
      return `Ticket checked — ${String(e.status ?? "")}`;
    case "chase_start":
      return `Chase round started`;
    case "chase_end":
      return `Chase done — ${String(e.checked)} checked, ${String(e.escalated)} escalated, ${String(e.resolved ?? 0)} resolved`;
    case "cycle_end":
      return `Cycle ended`;
    default:
      return kind;
  }
}

/** "Selam + 3 others" style summary of who reported a complaint. */
export function reportersLabel(names: string[] | undefined): string {
  if (!names || names.length === 0) return "—";
  const real = names.filter((n) => n && n !== "anonymous");
  const anon = names.length - real.length;
  if (real.length === 0) {
    return `${anon} resident${anon === 1 ? "" : "s"}`;
  }
  const rest = real.length - 1 + anon;
  if (rest === 0) return real[0];
  return `${real[0]} + ${rest} other${rest === 1 ? "" : "s"}`;
}

const CITY_TZ: Record<string, string> = {
  "Addis Ababa": "Africa/Addis_Ababa",
  "Sandbox City": "Africa/Addis_Ababa",
  Chicago: "America/Chicago",
};

/** Clock string in the city's timezone (falls back to browser-local). */
export function cityClock(iso: string, city: string): string {
  const tz = CITY_TZ[city];
  try {
    return new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      ...(tz ? { timeZone: tz } : {}),
    }).format(new Date(iso));
  } catch {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }
}

export function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
