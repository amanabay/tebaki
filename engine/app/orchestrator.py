"""Tebaki nightly orchestrator (Day-2: real Strands agents).

Pipeline per nightly run:
  1. TRIAGE   — Strands triage agent validates/classifies new reports
                (scripted model offline, Bedrock live).
  2. CLUSTER  — deterministic H3 + DBSCAN clustering, ward mapping
                against the city pack boundary.
  3. DRAFT    — Strands drafter agent emits one complaint per hotspot
                via typed submit_complaint_draft tool.
  4. FILE     — Strands filer agent calls file_complaint, which is gated
                by a Strands interrupt: the run pauses, a decision card
                is created. A human answers approve/edit/drop via
                resolve_decision() (CLI today, web queue on Day 4).
                Sandbox city auto-approves so the offline E2E loop works.

Model mode: TEBAKI_LIVE_BEDROCK=1 swaps every agent onto BedrockModel
with zero code changes (see app.agents.model_factory).
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.model_factory import model_mode
from app.agents.registry import pause_filing, resume_filing, set_filing_context
from app.agents.roles import decision_card_from_interrupt, drafter_agent, filer_agent, triage_agent
from app.channels import channel_from_pack
from app.city_pack import load_city_pack
from app.config import settings
from app.geo import GeoPoint, cluster_reports, load_boundary_features, map_ward
from app.store import get_store

_RESOLUTIONS = {"approve": "approved", "edit": "edited", "drop": "dropped"}


def run_nightly_cycle(
    city_pack_name: str | None = None,
    auto_approve: bool | None = None,
) -> dict[str, Any]:
    """Run the full nightly cycle for a city pack.

    auto_approve: None means "sandbox city auto-approves, others wait for
    a human" (the demo-friendly default). Explicit True/False overrides.
    """
    pack_name = city_pack_name or settings.city_pack
    cities_dir = settings.cities_dir.resolve()
    pack = load_city_pack(cities_dir, pack_name)

    store = get_store()
    run = store.start_run(pack.city.name)
    run.add_event("cycle_start", city=pack.city.name, pack=pack_name, model=model_mode())

    channel = channel_from_pack(pack)
    set_filing_context(pack.city.name, channel)

    if auto_approve is None:
        auto_approve = pack.city.name == "Sandbox City"

    new_reports = store.new_reports()
    if not new_reports:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="no_new_reports")
        return run.to_dict()
    run.add_event("triage_start", new_reports=len(new_reports))

    # 1) TRIAGE — Strands agent over the batch of new reports
    triage = triage_agent()
    triage(json.dumps({"reports": [r.to_dict() for r in new_reports]}))
    accepted = [r for r in store.reports.values() if r.status == "triaged"]
    rejected = [r for r in store.reports.values() if r.status == "rejected"]
    run.add_event("triage_done", accepted=len(accepted), rejected=len(rejected))
    if not accepted:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="all_rejected")
        return run.to_dict()

    # 2) CLUSTER — H3 + DBSCAN over triaged reports, ward mapping
    points = [
        GeoPoint(
            lat=r.lat,
            lon=r.lon,
            category=r.category,
            report_id=r.report_id,
            note=r.note,
            severity=r.severity,
        )
        for r in accepted
    ]
    clusters = cluster_reports(points)
    features = load_boundary_features(cities_dir / pack.boundary.geojson)
    for cluster in clusters:
        cluster.ward = map_ward(cluster.lat, cluster.lon, features, fallback=pack.city.name)
    run.add_event("cluster_done", clusters=len(clusters))

    # 3) DRAFT — drafter agent per hotspot cluster
    drafter = drafter_agent()
    regulation = pack.regulations[0].cite if pack.regulations else None
    for cluster in clusters:
        payload = {
            "cluster": {
                "category": cluster.category,
                "report_refs": cluster.report_ids,
                "lat": cluster.lat,
                "lon": cluster.lon,
                "ward": cluster.ward,
                "notes": cluster.notes,
                "max_severity": cluster.max_severity,
            },
            "regulation": regulation,
            "city": pack.city.name,
        }
        drafter(json.dumps(payload))
    drafts = [c for c in store.complaints.values() if c.status == "awaiting_approval"]
    run.add_event("drafts_ready", complaints=len(drafts))

    # 4) FILE — filer agent per complaint, interrupt-gated
    pending: list[str] = []
    filed_count = dropped_count = failed_count = 0
    for complaint in drafts:
        filer = filer_agent()
        result = filer(json.dumps({"draft": complaint.draft_payload}))
        if result.interrupts:
            interrupt = result.interrupts[0]
            card = decision_card_from_interrupt("tebaki-filer", interrupt)
            pause_filing(card.card_id, filer, interrupt.id)
            run.add_event("decision_card", card_id=card.card_id, complaint_id=complaint.complaint_id)
            if auto_approve:
                resolve_decision(card.card_id, "approve")
        if complaint.status == "filed":
            filed_count += 1
            run.add_event(
                "filed",
                complaint_id=complaint.complaint_id,
                ticket_id=complaint.ticket_id,
                channel=complaint.channel,
            )
        elif complaint.status == "filing_failed":
            failed_count += 1
            run.add_event("filing_failed", complaint_id=complaint.complaint_id)
        elif complaint.status == "dropped":
            dropped_count += 1
            run.add_event("dropped", complaint_id=complaint.complaint_id)
        else:
            pending.append(complaint.complaint_id)

    store.finish_run(run)
    run.add_event(
        "cycle_end",
        filed=filed_count,
        dropped=dropped_count,
        failed=failed_count,
        awaiting_approval=len(pending),
    )
    return run.to_dict()


def resolve_decision(
    card_id: str, action: str, fields: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Answer a pending filing decision card and resume the paused filer.

    action: "approve" files as drafted; "edit" merges `fields` into the
    tool input then files; "drop" cancels the filing.
    """
    if action not in _RESOLUTIONS:
        raise ValueError(f"invalid action {action!r}: approve|edit|drop")
    store = get_store()
    if card_id not in store.decision_cards:
        raise ValueError(f"unknown decision card {card_id!r}")
    card = store.decision_cards[card_id]
    if card.status != "pending":
        raise ValueError(f"card {card_id} already resolved ({card.status})")

    paused = resume_filing(card_id)
    response: Any = {"action": "edit", "fields": fields or {}} if action == "edit" else action
    result = paused.agent(
        [{"interruptResponse": {"interruptId": paused.interrupt_id, "response": response}}]
    )

    complaint = store.complaints[card.complaint_draft["complaint_id"]]
    if action == "drop" and complaint.status == "awaiting_approval":
        complaint.status = "dropped"
    store.resolve_card(
        card_id,
        _RESOLUTIONS[action],
        response={"action": action, "fields": fields} if fields else {"action": action},
    )
    return {
        "card_id": card_id,
        "action": action,
        "complaint_id": complaint.complaint_id,
        "status": complaint.status,
        "ticket_id": complaint.ticket_id,
        "channel": complaint.channel,
        "stop_reason": result.stop_reason,
    }
