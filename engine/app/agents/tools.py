"""Strands tools for the Tebaki agents.

Typed submit-tools act as structured outputs for the triage and drafter
agents; `file_complaint` is the real-world action tool. Every filing is
gated by a human decision card implemented as a Strands interrupt
raised from the filer agent's BeforeToolCallEvent hook (see
app.agents.roles.filing_approval_hook).

Batch tools are hardened against malformed model output: bad rows are
skipped and reported, never half-applied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from strands import tool

from app.channels import FilingResult
from app.store import Complaint, get_store

_VALID_CATEGORIES = {"waste", "pothole", "streetlight", "drain", "water"}
_RESOLVED_STATUSES = {"resolved", "closed"}
_ACKNOWLEDGED_STATUSES = {"acknowledged"}


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
    errors: list[str] = []
    seen: set[str] = set()
    for r in results:
        rid = str(r.get("report_id", "")).strip()
        report = store.get_report(rid) if rid else None
        if report is None:
            errors.append(f"unknown report_id {rid!r}")
            continue
        seen.add(rid)
        if not r.get("valid", False):
            report.status = "rejected"
        else:
            category = r.get("category", report.category)
            if category not in _VALID_CATEGORIES:
                report.status = "rejected"
                store.save_report(report)
                errors.append(f"{rid}: invalid category {category!r}")
                continue
            try:
                report.severity = max(1, min(5, int(r.get("severity", 3))))
            except (TypeError, ValueError):
                report.severity = 3
            report.category = category
            report.language = r.get("language", "en")
            try:
                report.triage_confidence = max(0.0, min(1.0, float(r.get("confidence", 0.7))))
            except (TypeError, ValueError):
                report.triage_confidence = 0.5
            report.triage_reason = str(r.get("reason", ""))[:300]
            report.status = "triaged"
            accepted += 1
        store.save_report(report)
    # A batch tool call is the triage stage's commit point. If a model omits a
    # report, reject it explicitly instead of leaving it in `new` forever and
    # reprocessing it on every nightly run.
    for report in store.new_reports():
        if report.report_id not in seen:
            report.status = "rejected"
            store.save_report(report)
            errors.append(f"{report.report_id}: missing triage result")
    summary = f"triaged {accepted}/{len(results)} reports accepted"
    if errors:
        summary += f"; skipped {len(errors)} bad rows ({'; '.join(errors[:3])})"
    return summary


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
    accepted = [r for r in store.list_reports() if r.status == "triaged"]
    if not accepted:
        return _json.dumps({"clusters": [], "regulation": None, "city": get_filing_context().city})

    filing = get_filing_context()
    pack = filing.pack
    points = [
        GeoPoint(
            lat=r.lat,
            lon=r.lon,
            category=r.category,
            report_id=r.report_id,
            note=r.note,
            severity=r.severity,
            plus_ones=r.plus_ones,
        )
        for r in accepted
    ]
    clusters = cluster_reports(points)
    features = load_boundary_features(_settings.cities_dir.resolve() / pack.boundary.geojson)
    from app.geocode import reverse_geocode

    payload_clusters = []
    for cluster in clusters:
        cluster.ward = map_ward(cluster.lat, cluster.lon, features, fallback=pack.city.name)
        place = reverse_geocode(cluster.lat, cluster.lon)
        payload_clusters.append(
            {
                "category": cluster.category,
                "report_refs": cluster.report_ids,
                "lat": cluster.lat,
                "lon": cluster.lon,
                "ward": cluster.ward,
                "place": place,
                "notes": cluster.notes,
                "max_severity": cluster.max_severity,
                "resident_count": cluster.residents,
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
    errors: list[str] = []
    for i, draft in enumerate(drafts):
        missing = [k for k in ("report_refs", "ward", "text") if not draft.get(k)]
        if missing:
            errors.append(f"draft #{i}: missing {', '.join(missing)}")
            continue
        refs = [str(r) for r in draft["report_refs"]]
        # Idempotency: a retried drafter call must not create a second civic
        # case for the same cluster of reports.
        existing = next(
            (
                c
                for c in store.list_complaints()
                if c.status != "dropped" and set(c.report_refs) == set(refs)
            ),
            None,
        )
        if existing is not None:
            staged.append(existing.complaint_id)
            continue
        complaint = Complaint(
            report_refs=refs,
            ward=str(draft["ward"]),
            draft_text=str(draft["text"]),
            status="awaiting_approval",
        )
        draft["complaint_id"] = complaint.complaint_id
        complaint.draft_payload = draft
        store.add_complaint(complaint)
        staged.append(complaint.complaint_id)
    summary = f"staged {len(staged)} complaint drafts: {', '.join(staged)}"
    if errors:
        summary += f"; skipped {len(errors)} bad drafts ({'; '.join(errors[:3])})"
    return summary


@tool
def submit_chase_results(results: list[dict[str, Any]]) -> str:
    """Submit chase decisions for filed complaints (one entry per complaint).

    Args:
        results: Each entry: complaint_id (str), ticket_status (str),
            action ("none"|"escalate"), subject (str), text (str) —
            subject/text required when escalating.
    """
    store = get_store()
    escalated = resolved = 0
    errors: list[str] = []
    for r in results:
        cid = str(r.get("complaint_id", "")).strip()
        complaint = store.get_complaint(cid) if cid else None
        if complaint is None:
            errors.append(f"unknown complaint_id {cid!r}")
            continue
        ticket_status = str(r.get("ticket_status") or "").lower()
        complaint.ticket_status = ticket_status or None
        complaint.last_chased_at = _now_iso()

        # closure loop: the city's own ticket state advances the complaint;
        # escalation still takes precedence over a mere acknowledgement
        if ticket_status in _RESOLVED_STATUSES and complaint.status != "resolved":
            complaint.status = "resolved"
            resolved += 1
        elif r.get("action") == "escalate":
            # one rung at a time — the store decides the next level, not the model
            level = complaint.escalation_level + 1
            complaint.escalation_level = level
            complaint.status = f"escalated_{level}"
            escalated += 1
            from app.agents.registry import get_filing_context

            filing = get_filing_context()
            rungs = filing.escalation_rungs or []
            rung = rungs[min(level - 1, len(rungs) - 1)] if rungs else {}
            delivery = _send_escalation(rung, r.get("subject", ""), r.get("text", ""))
            complaint.escalation_log = complaint.escalation_log + [
                {
                    "level": level,
                    "target": rung.get("target", "city"),
                    "address": delivery.get("address"),
                    "subject": r.get("subject", ""),
                    "text": r.get("text", ""),
                    "at": _now_iso(),
                    "delivered": delivery.get("delivered", False),
                    "delivery_detail": delivery.get("detail", ""),
                }
            ]
        elif ticket_status in _ACKNOWLEDGED_STATUSES and complaint.status == "filed":
            complaint.status = "acknowledged"
        store.save_complaint(complaint)
    summary = f"chased {len(results)} complaints, escalated {escalated}, resolved {resolved}"
    if errors:
        summary += f"; skipped {len(errors)} bad rows ({'; '.join(errors[:3])})"
    return summary


def _send_escalation(rung: dict[str, Any], subject: str, text: str) -> dict[str, Any]:
    """Send an escalation notice through the email channel.

    Target: the rung's email; falls back to the city pack's primary email
    address. In SES mode, placeholder addresses (the sandbox city) are
    redirected to the verified sender so the demo shows real delivery.
    """
    import os

    from app.agents.registry import get_filing_context
    from app.channels import EmailChannel, SESEmailChannel

    filing = get_filing_context()
    pack = filing.pack
    to = rung.get("email")
    if not to and pack is not None and pack.channels.email:
        to = pack.channels.email[0].address
    if not to:
        return {"delivered": False, "detail": "no escalation email configured; logged only", "address": None}

    ses_mode = os.getenv("TEBAKI_EMAIL_MODE", "").lower() == "ses"
    redirected = False
    if ses_mode and to.endswith((".invalid", "@placeholder.invalid")):
        to = os.getenv("TEBAKI_SES_FROM", "tebaki@localhost")
        redirected = True

    if ses_mode:
        channel = SESEmailChannel(to_address=to, from_address=os.getenv("TEBAKI_SES_FROM", "tebaki@localhost"))
    else:
        channel = EmailChannel(to_address=to)
    result: FilingResult = channel.file(
        {"category": "escalation", "lat": 0, "lon": 0, "text": text, "subject": subject, "cite": None}
    )
    detail = result.detail
    if redirected:
        detail = f"[sandbox redirect to sender] {detail}"
    return {"delivered": result.ok, "detail": detail, "address": to}


def _now_iso() -> str:
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
    from datetime import timedelta

    from app.agents.registry import get_filing_context

    filing = get_filing_context()
    channel = filing.channel
    result: FilingResult = channel.file(
        {"category": category, "lat": lat, "lon": lon, "text": text, "subject": subject, "cite": cite}
    )
    store = get_store()
    complaint = store.get_complaint(complaint_id)
    if complaint is None:
        return f"error: unknown complaint_id {complaint_id}"
    if result.ok:
        filed_at = datetime.now(UTC)
        ack_days = filing.sla["acknowledge_days"]
        resolve_days = filing.sla["resolve_days"]
        complaint.status = "filed"
        complaint.filed_at = filed_at.isoformat()
        complaint.ack_deadline = (filed_at + timedelta(days=ack_days)).isoformat()
        complaint.resolve_deadline = (filed_at + timedelta(days=resolve_days)).isoformat()
        complaint.ticket_id = result.ticket_id
        complaint.channel = result.channel
        store.save_complaint(complaint)
        for rid in complaint.report_refs:
            store.update_report_status(rid, "filed")
        return f"filed {complaint_id}: ticket {result.ticket_id or 'no-ticket-id'} via {result.channel}"
    complaint.status = "filing_failed"
    store.save_complaint(complaint)
    return f"filing failed for {complaint_id}: {result.detail}"
