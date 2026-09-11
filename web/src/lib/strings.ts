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

export function amCategory(value: string): string {
  return CATEGORIES.find((c) => c.value === value)?.am ?? "";
}

/* ------------------------------------------------------------------ *
 * Status taxonomy — the single source for labels, colors, and counts.
 * Every surface (stamps, map, filters, stats) renders from here.
 * ------------------------------------------------------------------ */

export type StatusKind =
  | "awaiting"
  | "dropped"
  | "filed"
  | "acknowledged"
  | "escalated"
  | "resolved"
  | "failed"
  | "other";

export interface StatusMeta {
  kind: StatusKind;
  label: string;
  /** status token class for text/stamps */
  className: string;
  /** hexes for Leaflet (one per theme, from the same token pairs) */
  mapLight: string;
  mapDark: string;
  /** filterable / stat-countable group */
  groupable: boolean;
}

export function statusKind(status: string): StatusKind {
  if (status === "resolved") return "resolved";
  if (status.startsWith("escalated")) return "escalated";
  if (status === "acknowledged") return "acknowledged";
  if (status === "filed") return "filed";
  if (status === "dropped") return "dropped";
  if (status === "filing_failed") return "failed";
  if (status === "awaiting_approval" || status === "drafted" || status === "new" || status === "triaged" || status === "clustered")
    return "awaiting";
  return "other";
}

export function statusInfo(status: string): { label: string; className: string } {
  const meta = STATUS_META[statusKind(status)];
  const label =
    status.startsWith("escalated")
      ? `ESCALATED L${status.split("_")[1]}`
      : meta.label;
  return { label, className: meta.className };
}

export const STATUS_META: Record<StatusKind, StatusMeta> = {
  awaiting: {
    kind: "awaiting",
    label: "AWAITING",
    className: "text-status-pending",
    mapLight: "#b57614",
    mapDark: "#f2a93b",
    groupable: true,
  },
  dropped: {
    kind: "dropped",
    label: "DROPPED",
    className: "text-status-dropped",
    mapLight: "#7d7468",
    mapDark: "#8a8177",
    groupable: true,
  },
  filed: {
    kind: "filed",
    label: "FILED",
    className: "text-status-filed",
    mapLight: "#2e7d4f",
    mapDark: "#69c98f",
    groupable: true,
  },
  acknowledged: {
    kind: "acknowledged",
    label: "ACKNOWLEDGED",
    className: "text-status-filed",
    mapLight: "#2e7d4f",
    mapDark: "#69c98f",
    groupable: true,
  },
  escalated: {
    kind: "escalated",
    label: "ESCALATED",
    className: "text-status-escalated",
    mapLight: "#b3442c",
    mapDark: "#e0654a",
    groupable: true,
  },
  resolved: {
    kind: "resolved",
    label: "RESOLVED",
    className: "text-status-filed",
    mapLight: "#1a6b3c",
    mapDark: "#3fae6d",
    groupable: true,
  },
  failed: {
    kind: "failed",
    label: "FAILED",
    className: "text-status-escalated",
    mapLight: "#b3442c",
    mapDark: "#e0654a",
    groupable: true,
  },
  other: {
    kind: "other",
    label: "UNKNOWN",
    className: "text-muted-foreground",
    mapLight: "#7d7468",
    mapDark: "#8a8177",
    groupable: false,
  },
};

/** Map colors resolved for the current theme (Leaflet needs literals). */
export function statusMapColor(status: string, dark: boolean): string {
  const meta = STATUS_META[statusKind(status)];
  return dark ? meta.mapDark : meta.mapLight;
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
    case "status_recorded":
      return `Response recorded — ${String(e.status)}`;
    case "chase_start":
      return `Chase round started`;
    case "chase_end":
      return `Chase done — ${String(e.checked)} checked, ${String(e.escalated)} escalated, ${String(e.resolved ?? 0)} resolved`;
    case "demo_deadlines_missed":
      return `Demo clock advanced — ${String(e.complaints)} cases now exceed their SLA`;
    case "cycle_end":
      return `Cycle ended`;
    default:
      return kind;
  }
}

const AMBER_KINDS = new Set(["filed", "escalated", "resolved", "decision_card", "chase_end", "status_recorded"]);

export function isAmberEvent(kind: string): boolean {
  return AMBER_KINDS.has(kind);
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

/** "5 residents" — reporters plus neighbor +1s. */
export function residentsLabel(names: string[] | undefined, plusOnes: number | undefined): string {
  const reporters = names?.length ?? 0;
  const total = reporters + (plusOnes ?? 0);
  if (total === 0) return "—";
  return `${total} resident${total === 1 ? "" : "s"}`;
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

/** Days until/past an ISO deadline; negative = overdue. */
export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.round((ms / 86400000) * 10) / 10;
}
