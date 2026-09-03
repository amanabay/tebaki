"""Tebaki nightly orchestrator (Day-1 skeleton).

A Strands agent drives the nightly cycle over the run store:
triage -> cluster -> draft -> file (with human-in-the-loop interrupt
on every filing) -> chase.

Day 1 scope: the full loop runs against the sandbox city pack with a
planner agent that emits structured ComplaintDrafts; filing is gated
by a decision card (approve/edit/drop) resolved out-of-band via the
store (the FastAPI decision queue in a later section resumes it).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from strands import Agent

from app.channels import channel_from_pack
from app.city_pack import load_city_pack
from app.config import settings
from app.store import Complaint, DecisionCard, Report, get_store


class ComplaintDraft(BaseModel):
    """Structured output of the drafter agent."""

    category: str = Field(description="waste|pothole|streetlight|drain|water")
    severity: int = Field(ge=1, le=5, description="1 (minor) to 5 (hazard)")
    report_refs: list[str] = Field(description="report ids included in this complaint")
    lat: float
    lon: float
    ward: str = Field(description="admin unit (sub-city) this complaint belongs to")
    subject: str
    text: str
    cite: str | None = Field(default=None, description="regulation citation from the city pack")
    duplicates_note: str | None = Field(default=None)


NIGHTLY_SYSTEM_PROMPT = """\
You are Tebaki, the city's guardian agent. You run at night, while the \
city sleeps. Your job: turn residents' raw issue reports into properly \
filed municipal complaints, and never file anything without a human \
decision card approval.

Working rules:
- Ward mapping: the city pack boundary defines the city. Use the ward \
name given in context; never invent one.
- Regulation: only cite the regulation given in context (or the city's \
regulation you find in the reports context). Never invent a law.
- Severity: 5 = immediate hazard (flooding, exposed wiring), 3 = \
degraded service, 1 = cosmetic.
- Text: plain, factual, first-person-plural ("residents report..."), \
no exaggeration, no invented details. If the city's languages include \
a local language, keep the text in English; translation happens later.
- Duplicates: mention in duplicates_note when multiple reports describe \
the same issue; do not silently merge conflicting categories.
"""


def triage_cluster_draft(reports: list[Report], pack: Any) -> list[dict[str, Any]]:
    """Deterministic Day-1 stand-in for the triage/cluster/drafter agents.

    Groups new reports by category + 0.01-degree proximity and emits one
    complaint-draft payload per cluster. The Strands sub-agents (Day 2)
    replace the internals; this signature stays.
    """
    clusters: list[dict[str, Any]] = []
    for report in reports:
        placed = False
        for cluster in clusters:
            if cluster["category"] == report.category and abs(cluster["lat"] - report.lat) < 0.01 and abs(cluster["lon"] - report.lon) < 0.01:
                cluster["report_refs"].append(report.report_id)
                cluster["notes"].append(f"{report.report_id}: {report.note}")
                placed = True
                break
        if not placed:
            clusters.append(
                {
                    "category": report.category,
                    "report_refs": [report.report_id],
                    "lat": report.lat,
                    "lon": report.lon,
                    "ward": getattr(pack.city, "name", "Sandbox City"),
                    "notes": [f"{report.report_id}: {report.note}"],
                }
            )
    return clusters


def draft_complaint_text(cluster: dict[str, Any], pack: Any) -> tuple[str, str, str | None]:
    """Render subject/text/cite for a cluster (Day-1 template)."""
    n = len(cluster["report_refs"])
    cite = pack.regulations[0].cite if pack.regulations else None
    subject = f"{cluster['category'].title()} issue in {cluster['ward']} ({n} report{'s' if n > 1 else ''})"
    text = (
        f"Residents report a {cluster['category']} issue at approximate location "
        f"({cluster['lat']:.4f}, {cluster['lon']:.4f}) in {cluster['ward']}.\n"
        f"Number of resident reports: {n}.\n"
        f"Details: {' | '.join(cluster['notes'])}\n"
        "We request acknowledgment and a resolution timeline as required by the applicable regulations."
    )
    return subject, text, cite


def run_nightly_cycle(city_pack_name: str | None = None, agent: Agent | None = None) -> dict[str, Any]:
    """Run the full nightly cycle for a city pack.

    Returns a run summary dict. The Strands agent (if provided) is used
    for drafting; Day-1 falls back to the deterministic template.
    """
    pack_name = city_pack_name or settings.city_pack
    cities_dir = settings.cities_dir.resolve()
    pack = load_city_pack(cities_dir, pack_name)

    store = get_store()
    run = store.start_run(pack.city.name)
    run.add_event("cycle_start", city=pack.city.name, pack=pack_name)

    new_reports = store.new_reports()
    run.add_event("triage", new_reports=len(new_reports))
    if not new_reports:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="no_new_reports")
        return run.to_dict()

    clusters = triage_cluster_draft(new_reports, pack)
    run.add_event("cluster", clusters=len(clusters))

    channel = channel_from_pack(pack)

    filed, awaiting, dropped = [], [], []
    for cluster in clusters:
        subject, text, cite = draft_complaint_text(cluster, pack)
        draft_payload = {
            **cluster,
            "subject": subject,
            "text": text,
            "cite": cite,
        }
        complaint = store.add_complaint(
            Complaint(
                report_refs=cluster["report_refs"],
                ward=cluster["ward"],
                draft_text=text,
                status="awaiting_approval",
            )
        )
        card = store.add_decision_card(
            DecisionCard(
                complaint_draft={**draft_payload, "complaint_id": complaint.complaint_id},
                context={"city": pack.city.name, "channel": channel.channel},
            )
        )
        run.add_event("decision_card_created", card_id=card.card_id, complaint_id=complaint.complaint_id)

        # Day-1 auto-approve policy for the sandbox city: resolve immediately
        # so the loop exercises filing end-to-end offline. Real runs keep the
        # card pending until the human answers via the decision queue API.
        if pack.city.name == "Sandbox City":
            store.resolve_card(card.card_id, "approved", response={"auto": "sandbox-policy"})
            outcome = _file_complaint(channel, complaint, draft_payload)
            if outcome.ok:
                complaint.status = "filed"
                complaint.ticket_id = outcome.ticket_id
                complaint.channel = outcome.channel
                filed.append(complaint.complaint_id)
                for rid in cluster["report_refs"]:
                    store.update_report_status(rid, "filed")
                run.add_event(
                    "filed",
                    complaint_id=complaint.complaint_id,
                    ticket_id=outcome.ticket_id,
                    channel=outcome.channel,
                )
            else:
                complaint.status = "filing_failed"
                run.add_event("filing_failed", complaint_id=complaint.complaint_id, detail=outcome.detail)
        else:
            awaiting.append(card.card_id)

    store.finish_run(run)
    run.add_event("cycle_end", filed=len(filed), awaiting_approval=len(awaiting), failed=len(dropped))
    return run.to_dict()


def _file_complaint(channel: Any, complaint: Complaint, draft_payload: dict[str, Any]) -> Any:
    return channel.file(
        {
            "category": draft_payload["category"],
            "lat": draft_payload["lat"],
            "lon": draft_payload["lon"],
            "text": draft_payload["text"],
            "subject": draft_payload["subject"],
            "cite": draft_payload.get("cite"),
        }
    )
