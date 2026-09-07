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
    case "checked":
      return `Ticket checked — ${String(e.status ?? "")}`;
    case "chase_start":
      return `Chase round started`;
    case "chase_end":
      return `Chase done — ${String(e.checked)} checked, ${String(e.escalated)} escalated`;
    case "cycle_end":
      return `Cycle ended`;
    default:
      return kind;
  }
}

export function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
