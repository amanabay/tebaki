const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Report {
  report_id: string;
  reporter: string;
  category: string;
  lat: number;
  lon: number;
  note: string;
  status: string;
  severity: number;
  language: string;
  created_at: string;
}

export interface LedgerRow {
  complaint_id: string;
  ward: string;
  status: string;
  ticket_id: string | null;
  channel: string;
  escalation_level: number;
  filed_at: string | null;
  ack_deadline?: string | null;
  resolve_deadline?: string | null;
  ticket_status?: string | null;
  category: string | null;
  subject: string | null;
  report_refs: string[];
  reporters?: string[];
  plus_ones?: number;
  escalation_log?: Array<{
    level: number | null;
    target: string | null;
    subject: string | null;
    at: string | null;
    delivered: boolean | null;
  }>;
  created_at: string;
}

export interface ScoreboardRow {
  ward: string;
  complaints: number;
  filed: number;
  resolved: number;
  escalated: number;
  acknowledged?: number;
}

export interface ActivityEvent {
  run_id: string;
  city: string;
  at: string;
  kind: string;
  [key: string]: unknown;
}

export interface RunSummary {
  run_id: string;
  city: string;
  started_at: string;
  finished_at: string | null;
  event_count: number;
  tool_call_count: number;
  token_totals: { input: number; output: number };
}

export interface AgentRun extends RunSummary {
  events: ActivityEvent[];
}

export interface ImpactData {
  total_cases: number;
  unresolved_cases: number;
  resolved_cases: number;
  escalated_cases: number;
  approaching_escalation: number;
  corroborations: number;
  wards: ScoreboardRow[];
}

export interface ProofData {
  city: string;
  model_mode: string;
  persistence: string;
  last_run_id: string | null;
  reports_triaged: number;
  cases_drafted: number;
  human_decisions: number;
  filed_tickets: number;
  escalations: number;
  runtime_status: string;
  coverage?: {
    status: string;
    pilot_area?: string | null;
    boundary_source?: string | null;
    boundary_verified_at?: string | null;
    contact_source?: string | null;
    contact_verified_at?: string | null;
  };
}

export interface DiagnosticsData {
  checks: Array<{ id: string; label: string; state: "ready" | "attention" | "local_only"; detail: string }>;
  incidents: ActivityEvent[];
  incident_count: number;
}

export interface MapData {
  reports: Array<{
    report_id: string;
    category: string;
    lat: number;
    lon: number;
    status: string;
    severity: number;
    plus_ones: number;
    triage_confidence?: number | null;
    triage_reason?: string | null;
  }>;
  complaints: Array<{
    complaint_id: string;
    lat: number | null;
    lon: number | null;
    status: string;
    category: string | null;
  }>;
}

export interface DecisionCard {
  card_id: string;
  created_at: string;
  draft: {
    complaint_id: string;
    category: string;
    severity: number;
    report_refs: string[];
    lat: number;
    lon: number;
    ward: string;
    subject: string;
    text: string;
    cite?: string | null;
    duplicates_note?: string | null;
  };
  context: Record<string, unknown>;
}

export interface ResolveOutcome {
  card_id: string;
  action: string;
  complaint_id: string;
  status: string;
  ticket_id: string | null;
  channel: string;
  stop_reason: string;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`${resp.status}: ${body.slice(0, 200)}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  submitReport: (r: { category: string; lat: number; lon: number; note: string; reporter: string; photo_data?: string }) =>
    json<{ report_id: string; status: string }>("/reports", { method: "POST", body: JSON.stringify(r) }),
  listReports: () => json<Report[]>("/reports"),
  plusOne: (reportId: string) =>
    json<{ report_id: string; plus_ones: number }>(`/reports/${reportId}/plus-one`, { method: "POST" }),
  geocodeSearch: (q: string) =>
    json<Array<{ name: string; lat: number; lon: number }>>(
      `/geocode/search?q=${encodeURIComponent(q)}`,
    ),
  listDecisions: () => json<DecisionCard[]>("/decisions"),
  resolveDecision: (cardId: string, action: "approve" | "edit" | "drop", fields?: Record<string, string>) =>
    json<ResolveOutcome>(`/decisions/${cardId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action, fields }),
    }),
  ledger: () => json<LedgerRow[]>("/public/ledger"),
  scoreboard: () => json<ScoreboardRow[]>("/public/scoreboard"),
  activity: () => json<ActivityEvent[]>("/public/activity"),
  reportTimeline: (reportId: string) => json<ActivityEvent[]>(`/public/reports/${reportId}/timeline`),
  runs: () => json<RunSummary[]>("/public/runs"),
  run: (runId: string) => json<AgentRun>(`/public/runs/${runId}`),
  impact: () => json<ImpactData>("/public/impact"),
  proof: () => json<ProofData>("/public/proof"),
  diagnostics: () => json<DiagnosticsData>("/public/diagnostics"),
  mapData: () => json<MapData>("/public/map"),
  runNightly: (autoApprove: boolean | null) =>
    json<Record<string, unknown>>("/admin/nightly", {
      method: "POST",
      body: JSON.stringify(autoApprove === null ? {} : { auto_approve: autoApprove }),
    }),
  runChase: () => json<Record<string, unknown>>("/admin/chase", { method: "POST" }),
  seedDemo: () =>
    json<{ added: string[]; total_demo_reports: number }>("/admin/demo/seed", { method: "POST" }),
  missDemoDeadlines: () =>
    json<{ affected: string[]; simulated_days: number; next_step: string }>(
      "/admin/demo/miss-deadlines",
      { method: "POST" },
    ),
  caseFile: (complaintId: string) => json<CaseFile>(`/public/complaints/${complaintId}`),
  setComplaintStatus: (complaintId: string, status: "acknowledged" | "resolved", note: string) =>
    json<{ complaint_id: string; status: string; ticket_status: string }>(
      `/admin/complaints/${complaintId}/status`,
      { method: "POST", body: JSON.stringify({ status, note }) },
    ),
};

export interface CaseFile {
  complaint_id: string;
  ward: string;
  status: string;
  ticket_id: string | null;
  channel: string;
  filed_at: string | null;
  ack_deadline: string | null;
  resolve_deadline: string | null;
  ticket_status: string | null;
  category: string | null;
  subject: string | null;
  text: string | null;
  cite: string | null;
  reporters: string[];
  plus_ones: number;
  reports: Array<{
    report_id: string;
    reporter: string;
    note: string;
    lat: number;
    lon: number;
    severity: number;
    language: string;
    plus_ones: number;
    created_at: string;
    status: string;
  }>;
  evidence: {
    report_count: number;
    corroborations: number;
    category: string | null;
    severity: number | null;
    grouping_reason: string;
    privacy_redactions: string[];
    regulation_citation: string | null;
    delivery_mode: "real" | "dry_run" | "simulated";
  };
  timeline: ActivityEvent[];
  escalation_log: Array<{
    level: number | null;
    target: string | null;
    address: string | null;
    subject: string | null;
    text: string | null;
    at: string | null;
    delivered: boolean | null;
  }>;
  created_at: string;
}
