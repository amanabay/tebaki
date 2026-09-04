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
from app.agents.roles import chaser_agent, decision_card_from_interrupt, filer_agent
from app.channels import channel_from_pack
from app.city_pack import load_city_pack
from app.config import settings
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
    set_filing_context(
        pack.city.name,
        channel,
        sla={"acknowledge_days": pack.sla.acknowledge_days, "resolve_days": pack.sla.resolve_days},
        escalation_rungs=[r.model_dump() for r in pack.channels.escalation],
        pack=pack,
    )

    if auto_approve is None:
        auto_approve = pack.city.name == "Sandbox City"

    new_reports = store.new_reports()
    if not new_reports:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="no_new_reports")
        return run.to_dict()
    run.add_event("triage_start", new_reports=len(new_reports))

    # 1-3) GRAPH PHASE — triage -> cluster -> draft as a Strands multiagent
    # graph with conditional edges (skips stages when nothing is left).
    from app.agents.nightly_graph import run_graph_phase

    graph_summary = run_graph_phase({"reports": [r.to_dict() for r in new_reports]})
    accepted = [r for r in store.reports.values() if r.status in ("triaged", "clustered")]
    rejected = [r for r in store.reports.values() if r.status == "rejected"]
    run.add_event(
        "triage_done",
        accepted=len(accepted),
        rejected=len(rejected),
        graph_nodes=graph_summary["completed"],
    )
    if not accepted:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="all_rejected")
        return run.to_dict()

    clustered = [r for r in store.reports.values() if r.status == "clustered"]
    run.add_event("cluster_done", clustered=len(clustered))

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


def run_chase(city_pack_name: str | None = None) -> dict[str, Any]:
    """Chase filed complaints: check tickets, evaluate SLA clocks, escalate stale cases.

    The chaser Strands agent decides escalate/none per complaint and drafts
    the escalation letters; the tool applies state changes and records the
    escalation log. Runs as part of the nightly cycle and on demand.
    """
    import json as _json
    from datetime import UTC, datetime

    pack_name = city_pack_name or settings.city_pack
    cities_dir = settings.cities_dir.resolve()
    pack = load_city_pack(cities_dir, pack_name)

    store = get_store()
    run = store.start_run(pack.city.name)
    run.add_event("chase_start", city=pack.city.name, pack=pack_name, model=model_mode())

    channel = channel_from_pack(pack)
    set_filing_context(
        pack.city.name,
        channel,
        sla={"acknowledge_days": pack.sla.acknowledge_days, "resolve_days": pack.sla.resolve_days},
        escalation_rungs=[r.model_dump() for r in pack.channels.escalation],
        pack=pack,
    )

    filed = [c for c in store.complaints.values() if c.ticket_id and c.status.startswith(("filed", "escalated"))]
    if not filed:
        store.finish_run(run)
        run.add_event("chase_end", outcome="no_filed_complaints")
        return run.to_dict()

    now = datetime.now(UTC)
    chase_payload = []
    for complaint in filed:
        try:
            ticket = channel.check(complaint.ticket_id)
            ticket_status = ticket.get("status", "unknown")
        except Exception as e:  # noqa: BLE001 — chase must survive one bad ticket
            run.add_event("ticket_check_failed", complaint_id=complaint.complaint_id, detail=str(e)[:120])
            ticket_status = "unknown"
        filed_at = datetime.fromisoformat(complaint.filed_at) if complaint.filed_at else now
        chase_payload.append(
            {
                "complaint_id": complaint.complaint_id,
                "ticket_id": complaint.ticket_id,
                "ticket_status": ticket_status,
                "days_since_filing": (now - filed_at).total_seconds() / 86400,
                "sla_ack_days": pack.sla.acknowledge_days,
                "sla_resolve_days": pack.sla.resolve_days,
                "escalation_level": complaint.escalation_level,
                "category": (complaint.draft_payload or {}).get("category", "civic"),
                "ward": complaint.ward,
            }
        )

    pre_levels = {c.complaint_id: c.escalation_level for c in filed}
    chaser = chaser_agent()
    chaser(_json.dumps({"complaints": chase_payload}))

    escalated_now = [
        c
        for c in store.complaints.values()
        if c.escalation_level > pre_levels.get(c.complaint_id, 0)
    ]
    for complaint in filed:
        if complaint.complaint_id in {c.complaint_id for c in escalated_now}:
            run.add_event(
                "escalated",
                complaint_id=complaint.complaint_id,
                level=complaint.escalation_level,
                ticket_status=complaint.ticket_status,
            )
        else:
            run.add_event(
                "checked", complaint_id=complaint.complaint_id, status=complaint.ticket_status
            )

    store.finish_run(run)
    run.add_event("chase_end", checked=len(chase_payload), escalated=len(escalated_now))
    return run.to_dict()
