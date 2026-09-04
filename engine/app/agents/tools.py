"""Strands tools for the Tebaki agents.

Typed submit-tools act as structured outputs for the triage and drafter
agents; `file_complaint` is the real-world action tool. Every filing is
gated by a human decision card implemented as a Strands interrupt
raised from the filer agent's BeforeToolCallEvent hook (see
app.agents.roles.filing_approval_hook).
"""

from __future__ import annotations

from typing import Any

from strands import tool

from app.channels import FilingResult
from app.store import Complaint, get_store


@tool
def submit_triage(results: list[dict[str, Any]]) -> str:
    """Submit triage results for a batch of resident reports.

    Args:
        results: One entry per report, each with keys:
            report_id (str), category (waste|pothole|streetlight|drain|water),
            severity (int 1-5), valid (bool), reason (str), language (ISO code).
    """
    store = get_store()
    accepted = 0
    for r in results:
        report = store.reports.get(r["report_id"])
        if report is None:
            return f"error: unknown report_id {r['report_id']}"
        if not r.get("valid", False):
            store.update_report_status(r["report_id"], "rejected")
        else:
            report.category = r["category"]
            report.severity = int(r.get("severity", 3))
            report.language = r.get("language", "en")
            store.update_report_status(r["report_id"], "triaged")
            accepted += 1
    return f"triaged {accepted}/{len(results)} reports accepted"


@tool
def submit_complaint_draft(
    category: str,
    severity: int,
    report_refs: list[str],
    lat: float,
    lon: float,
    ward: str,
    subject: str,
    text: str,
    cite: str | None = None,
    duplicates_note: str | None = None,
) -> str:
    """Submit one drafted complaint for a hotspot cluster.

    Args:
        category: waste|pothole|streetlight|drain|water
        severity: 1 (minor) to 5 (hazard)
        report_refs: report ids backing this complaint
        lat: representative latitude
        lon: representative longitude
        ward: admin unit this complaint belongs to
        subject: short complaint subject line
        text: full factual complaint text
        cite: regulation citation from the city pack (never invented)
        duplicates_note: note about merged duplicate reports
    """
    store = get_store()
    draft = {
        "complaint_id": None,  # assigned below
        "category": category,
        "severity": severity,
        "report_refs": report_refs,
        "lat": lat,
        "lon": lon,
        "ward": ward,
        "subject": subject,
        "text": text,
        "cite": cite,
        "duplicates_note": duplicates_note,
    }
    complaint = store.add_complaint(
        Complaint(
            report_refs=report_refs,
            ward=ward,
            draft_text=text,
            status="awaiting_approval",
            draft_payload=draft,
        )
    )
    draft["complaint_id"] = complaint.complaint_id
    return f"draft staged: {complaint.complaint_id}"


@tool
def file_complaint(
    complaint_id: str,
    category: str,
    lat: float,
    lon: float,
    subject: str,
    text: str,
    cite: str | None = None,
) -> str:
    """File an approved complaint through the city's official channel.

    Args:
        complaint_id: The complaint being filed
        category: waste|pothole|streetlight|drain|water
        lat: representative latitude
        lon: representative longitude
        subject: complaint subject line
        text: full complaint text
        cite: regulation citation from the city pack
    """
    from app.agents.registry import get_filing_context

    channel = get_filing_context().channel
    result: FilingResult = channel.file(
        {"category": category, "lat": lat, "lon": lon, "text": text, "subject": subject, "cite": cite}
    )
    store = get_store()
    complaint = store.complaints[complaint_id]
    if result.ok:
        complaint.status = "filed"
        complaint.ticket_id = result.ticket_id
        complaint.channel = result.channel
        for rid in complaint.report_refs:
            store.update_report_status(rid, "filed")
        return f"filed {complaint_id}: ticket {result.ticket_id or 'no-ticket-id'} via {result.channel}"
    complaint.status = "filing_failed"
    return f"filing failed for {complaint_id}: {result.detail}"
