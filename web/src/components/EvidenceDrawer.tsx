import { CheckCircle2, MapPin, ShieldAlert, Users } from "lucide-react";
import type { CaseFile } from "@/lib/api";

export function EvidenceDrawer({ file }: { file: CaseFile }) {
  const evidence = file.evidence;
  return (
    <details className="group rounded-md border border-border bg-surface-1">
      <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold marker:content-none">
        <span>Why this decision?</span>
        <span className="text-xs font-normal text-muted-foreground group-open:hidden">Open evidence</span>
        <span className="hidden text-xs font-normal text-muted-foreground group-open:inline">Close evidence</span>
      </summary>
      <div className="border-t border-border px-4 py-4">
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div><dt className="micro-label">sources</dt><dd className="mt-1 flex items-center gap-1.5"><Users className="size-4 text-primary" aria-hidden="true" />{evidence.report_count} reports · {evidence.corroborations} corroborations</dd></div>
          <div><dt className="micro-label">location</dt><dd className="mt-1 flex items-center gap-1.5"><MapPin className="size-4 text-primary" aria-hidden="true" />{file.ward}</dd></div>
          <div><dt className="micro-label">classification</dt><dd className="mt-1 capitalize">{evidence.category ?? "Unclassified"} · severity {evidence.severity ?? "—"}/5</dd></div>
          <div><dt className="micro-label">delivery</dt><dd className="mt-1 capitalize">{evidence.delivery_mode.replace("_", " ")}</dd></div>
          <div><dt className="micro-label">evidence gate</dt><dd className="mt-1 flex items-center gap-1.5 capitalize">{evidence.verification_state === "passed" ? <CheckCircle2 className="size-4 text-status-filed" aria-hidden="true" /> : <ShieldAlert className="size-4 text-primary" aria-hidden="true" />}{evidence.verification_state?.replace("_", " ") ?? "not run"}{typeof evidence.evidence_score === "number" && ` · ${Math.round(evidence.evidence_score * 100)}%`}</dd></div>
          <div className="sm:col-span-2"><dt className="micro-label">why grouped</dt><dd className="mt-1 leading-relaxed text-muted-foreground">{evidence.grouping_reason}</dd></div>
          <div className="sm:col-span-2"><dt className="micro-label">regulation</dt><dd className="mt-1 leading-relaxed text-muted-foreground">{evidence.regulation_citation ?? "No regulation citation was supplied."}</dd></div>
          {evidence.privacy_redactions.length > 0 && <div className="sm:col-span-2 rounded border border-primary/30 bg-primary/10 p-3 text-xs text-primary"><ShieldAlert className="mr-2 inline size-4" aria-hidden="true" />Redacted before drafting: {evidence.privacy_redactions.join(", ")}</div>}
          {(evidence.verification_flags?.length ?? 0) > 0 && <div className="sm:col-span-2 rounded border border-status-escalated/30 bg-status-escalated/10 p-3 text-xs text-status-escalated"><ShieldAlert className="mr-2 inline size-4" aria-hidden="true" />Review flags: {evidence.verification_flags?.join(", ")}</div>}
        </dl>
      </div>
    </details>
  );
}
