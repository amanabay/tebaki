"""Strands tools for the Tebaki agents.

Typed submit-tools act as structured outputs for the triage and drafter
agents; `file_complaint` is the real-world action tool. Every filing is
gated by a human decision card implemented as a Strands interrupt
raised from the filer agent's BeforeToolCallEvent hook (see
app.agents.roles.filing_approval_hook).
"""

from __future__ import annotations

from datetime import UTC
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
def cluster_triaged_reports() -> str:
    """Cluster all triaged reports into hotspots (H3 + DBSCAN) and map wards.

    Returns a JSON payload with clusters, the city regulation citation, and
    the city name — the drafter stage consumes it.
    """
    import json as _json

    from app.agents.registry import get_filing_context
    from app.config import settings as _settings
    from app.geo import GeoPoint, cluster_reports, load_boundary_features, map_ward

    store = get_store()
    accepted = [r for r in store.reports.values() if r.status == "triaged"]
    if not accepted:
        return _json.dumps({"clusters": [], "regulation": None, "city": get_filing_context().city})

    filing = get_filing_context()
    pack = filing.pack
    points = [
        GeoPoint(lat=r.lat, lon=r.lon, category=r.category, report_id=r.report_id, note=r.note, severity=r.severity)
        for r in accepted
    ]
    clusters = cluster_reports(points)
    features = load_boundary_features(_settings.cities_dir.resolve() / pack.boundary.geojson)
    payload_clusters = []
    for cluster in clusters:
        cluster.ward = map_ward(cluster.lat, cluster.lon, features, fallback=pack.city.name)
        payload_clusters.append(
            {
                "category": cluster.category,
                "report_refs": cluster.report_ids,
                "lat": cluster.lat,
                "lon": cluster.lon,
                "ward": cluster.ward,
                "notes": cluster.notes,
                "max_severity": cluster.max_severity,
            }
        )
    for r in accepted:
        store.update_report_status(r.report_id, "clustered")
    regulation = pack.regulations[0].cite if pack.regulations else None
    return _json.dumps({"clusters": payload_clusters, "regulation": regulation, "city": pack.city.name})


@tool
def submit_complaint_drafts(drafts: list[dict[str, Any]]) -> str:
    """Stage drafted complaints for a batch of hotspot clusters.

    Args:
        drafts: One entry per cluster: category, severity, report_refs,
            lat, lon, ward, subject, text, cite (optional), duplicates_note (optional).
    """
    store = get_store()
    staged: list[str] = []
    for draft in drafts:
        complaint = store.add_complaint(
            Complaint(
                report_refs=draft["report_refs"],
                ward=draft["ward"],
                draft_text=draft["text"],
                status="awaiting_approval",
                draft_payload=draft,
            )
        )
        draft["complaint_id"] = complaint.complaint_id
        staged.append(complaint.complaint_id)
    return f"staged {len(staged)} complaint drafts: {', '.join(staged)}"


@tool
def submit_chase_results(results: list[dict[str, Any]]) -> str:
    """Submit chase decisions for filed complaints (one entry per complaint).

    Args:
        results: Each entry: complaint_id (str), ticket_status (str),
            action ("none"|"escalate"), escalation_level (int, next rung),
            subject (str), text (str) — subject/text required when escalating.
    """
    store = get_store()
    escalated = 0
    for r in results:
        complaint = store.complaints.get(r["complaint_id"])
        if complaint is None:
            return f"error: unknown complaint_id {r['complaint_id']}"
        complaint.ticket_status = r.get("ticket_status")
        complaint.last_chased_at = _now_iso()
        if r.get("action") == "escalate":
            level = int(r.get("escalation_level", complaint.escalation_level + 1))
            complaint.escalation_level = level
            complaint.status = f"escalated_{level}"
            escalated += 1
            from app.agents.registry import get_filing_context

            filing = get_filing_context()
            rungs = filing.escalation_rungs or []
            rung = rungs[min(level - 1, len(rungs) - 1)] if rungs else {}
            complaint.escalation_log = getattr(complaint, "escalation_log", []) + [
                {
                    "level": level,
                    "target": rung.get("target", "city"),
                    "subject": r.get("subject", ""),
                    "text": r.get("text", ""),
                    "at": _now_iso(),
                }
            ]
    return f"chased {len(results)} complaints, escalated {escalated}"


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


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

    filing = get_filing_context()
    channel = filing.channel
    result: FilingResult = channel.file(
        {"category": category, "lat": lat, "lon": lon, "text": text, "subject": subject, "cite": cite}
    )
    store = get_store()
    complaint = store.complaints[complaint_id]
    if result.ok:
        from datetime import datetime, timedelta

        filed_at = datetime.now(UTC)
        ack_days = filing.sla["acknowledge_days"]
        resolve_days = filing.sla["resolve_days"]
        complaint.status = "filed"
        complaint.filed_at = filed_at.isoformat()
        complaint.ack_deadline = (filed_at + timedelta(days=ack_days)).isoformat()
        complaint.resolve_deadline = (filed_at + timedelta(days=resolve_days)).isoformat()
        complaint.ticket_id = result.ticket_id
        complaint.channel = result.channel
        for rid in complaint.report_refs:
            store.update_report_status(rid, "filed")
        return f"filed {complaint_id}: ticket {result.ticket_id or 'no-ticket-id'} via {result.channel}"
    complaint.status = "filing_failed"
    return f"filing failed for {complaint_id}: {result.detail}"
