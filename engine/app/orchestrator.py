"""Tebaki nightly orchestrator: real Strands agents.

Pipeline per nightly run:
  1. TRIAGE   — Strands triage agent validates/classifies new reports
                (scripted model offline, Bedrock live).
  2. CLUSTER  — deterministic H3 + DBSCAN clustering, ward mapping
                against the city pack boundary.
  3. DRAFT    — Strands drafter agent emits one complaint per hotspot
                via typed submit_complaint_drafts tool.
  4. FILE     — Strands filer agent calls file_complaint, which is gated
                by a Strands interrupt: the run pauses, a decision card
                is created. A human answers approve/edit/drop via
                resolve_decision() (CLI today, web queue later).
                Sandbox city auto-approves so the offline E2E loop works.

Model mode: TEBAKI_LIVE_BEDROCK=1 swaps every agent onto BedrockModel
with zero code changes (see app.agents.model_factory).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.agents.model_factory import model_mode
from app.agents.registry import pause_filing, resume_filing, set_filing_context
from app.agents.roles import chaser_agent, decision_card_from_interrupt, filer_agent
from app.agents.runtime import run_sync
from app.channels import channel_from_pack
from app.city_pack import load_city_pack
from app.config import settings
from app.store import get_store

_RESOLUTIONS = {"approve": "approved", "edit": "edited", "drop": "dropped"}


def run_instant_triage(report_id: str) -> None:
    """Run the lightweight triage agent for one newly submitted report."""
    store = get_store()
    report = store.get_report(report_id)
    if report is None or report.status != "new":
        return
    # Make the post-submit agent visible and durable, rather than leaving it
    # as an invisible background side effect.
    pack = load_city_pack(settings.cities_dir.resolve(), settings.city_pack)
    run = store.start_run(pack.city.name)
    run.add_event(
        "triage_start",
        actor="tebaki-guardian",
        report_ids=[report_id],
        input_summary="One newly submitted resident report",
        model=model_mode(),
    )
    from app.agents.roles import triage_agent

    agent = triage_agent()
    try:
        run_sync(
            lambda: agent.invoke_async(
                json.dumps({"reports": [report.to_dict()], "mode": "instant_triage"})
            )
        )
        updated = store.get_report(report_id) or report
        run.add_event(
            "triage_done",
            actor="tebaki-guardian",
            report_ids=[report_id],
            confidence=updated.triage_confidence,
            output_summary=updated.triage_reason or f"Marked {updated.status}",
            resulting_action=updated.status,
        )
    except Exception as exc:  # noqa: BLE001 — intake must remain durable when inference is unavailable
        run.add_event(
            "triage_failed",
            actor="tebaki-guardian",
            report_ids=[report_id],
            error=str(exc)[:160],
            resulting_action="retained for the next cycle",
        )
    finally:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="instant_triage", report_ids=[report_id])
        store.save_run(run)


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

    # Include reports already triaged by the instant post-submit job; the
    # graph will safely revalidate them before clustering.
    new_reports = [r for r in store.list_reports() if r.status in ("new", "triaged")]
    if not new_reports:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="no_new_reports")
        store.save_run(run)
        return run.to_dict()
    run.add_event(
        "triage_start",
        new_reports=len(new_reports),
        report_ids=[r.report_id for r in new_reports],
        actor="tebaki-guardian",
        input_summary="Reports awaiting a full case review",
    )

    # 1-3) GRAPH PHASE — triage -> cluster -> draft as a Strands multiagent
    # graph with conditional edges (skips stages when nothing is left).
    from app.agents.nightly_graph import run_graph_phase

    graph_summary = run_graph_phase({"reports": [r.to_dict() for r in new_reports]})
    if graph_summary.get("failed"):
        run.add_event(
            "graph_failed",
            failed=graph_summary["failed"],
            completed=graph_summary.get("completed", []),
        )
        store.finish_run(run)
        run.add_event("cycle_end", outcome="graph_failed")
        store.save_run(run)
        return run.to_dict()
    accepted = [r for r in store.list_reports() if r.status in ("triaged", "clustered")]
    rejected = [r for r in store.list_reports() if r.status == "rejected"]
    run.add_event(
        "triage_done",
        accepted=len(accepted),
        rejected=len(rejected),
        graph_nodes=graph_summary["completed"],
        report_ids=[r.report_id for r in new_reports],
        actor="tebaki-guardian",
        output_summary=f"{len(accepted)} reports accepted; {len(rejected)} rejected",
    )
    if not accepted:
        store.finish_run(run)
        run.add_event("cycle_end", outcome="all_rejected")
        store.save_run(run)
        return run.to_dict()

    clustered = [r for r in store.list_reports() if r.status == "clustered"]
    run.add_event(
        "cluster_done",
        clustered=len(clustered),
        report_ids=[r.report_id for r in clustered],
        actor="tebaki-cluster",
        output_summary="Nearby reports were grouped into case candidates",
    )

    drafts = [c for c in store.list_complaints() if c.status == "awaiting_approval"]
    from app.agents.roles import coordinator_agent
    from app.agents.tools import coordinator_recommendation

    coordinator_payload = {
        "complaints": [
            {
                "complaint_id": complaint.complaint_id,
                "category": (complaint.draft_payload or {}).get("category"),
                "severity": (complaint.draft_payload or {}).get("severity"),
                "ward": complaint.ward,
                "resident_count": (complaint.draft_payload or {}).get("resident_count", len(complaint.report_refs)),
                "status": complaint.status,
            }
            for complaint in drafts
        ]
    }
    try:
        coordinator = coordinator_agent()
        run_sync(lambda: coordinator.invoke_async(json.dumps(coordinator_payload)))
    except Exception as exc:  # noqa: BLE001 — deterministic recommendation keeps the run useful
        run.add_event("coordinator_failed", actor="tebaki-coordinator", error=str(exc)[:160], resulting_action="used bounded fallback")
        for complaint in drafts:
            suggestion = coordinator_recommendation(complaint)
            complaint.coordinator_recommendation = suggestion["recommendation"]
            complaint.coordinator_reason = suggestion["reason"]
            complaint.community_status = "action_proposed"
            store.save_complaint(complaint)
    for complaint in drafts:
        complaint = store.get_complaint(complaint.complaint_id) or complaint
        run.add_event(
            "evidence_verified",
            complaint_id=complaint.complaint_id,
            report_ids=complaint.report_refs,
            actor="tebaki-evidence-gate",
            confidence=complaint.evidence_score,
            output_summary=f"Evidence gate {complaint.verification_state}: {complaint.evidence_score or 0:.0%}",
            flags=complaint.verification_flags,
            resulting_action="sent to human review",
        )
        run.add_event(
            "coordinator_recommendation",
            complaint_id=complaint.complaint_id,
            report_ids=complaint.report_refs,
            actor="tebaki-coordinator",
            output_summary=complaint.coordinator_recommendation or "No action recommendation",
            reasoning=complaint.coordinator_reason or "No reasoning provided",
            resulting_action="awaiting operator choice",
        )
    run.add_event(
        "drafts_ready",
        complaints=len(drafts),
        complaint_ids=[c.complaint_id for c in drafts],
        report_ids=[rid for c in drafts for rid in c.report_refs],
        actor="tebaki-drafter",
        output_summary="Evidence-backed drafts are ready for human review",
    )

    # 4) FILE — filer agent per complaint, interrupt-gated
    pending: list[str] = []
    filed_count = dropped_count = failed_count = 0
    for draft_complaint in drafts:
        filer = filer_agent()
        result = run_sync(
            lambda filer=filer, draft=draft_complaint: filer.invoke_async(
                json.dumps({"draft": draft.draft_payload})
            )
        )
        if result.interrupts:
            interrupt = result.interrupts[0]
            card = decision_card_from_interrupt("tebaki-filer", interrupt, run_id=run.run_id)
            pause_filing(card.card_id, filer, interrupt.id)
            run.add_event(
                "decision_card",
                card_id=card.card_id,
                complaint_id=draft_complaint.complaint_id,
                report_ids=draft_complaint.report_refs,
                actor="human-approver",
                resulting_action="waiting for human approval",
            )
            if auto_approve:
                resolve_decision(card.card_id, "approve")
        # the filer tool persisted state; re-fetch for the fresh status
        complaint = store.get_complaint(draft_complaint.complaint_id) or draft_complaint
        if complaint.status == "filed":
            filed_count += 1
            run.add_event(
                "filed",
                complaint_id=complaint.complaint_id,
                ticket_id=complaint.ticket_id,
                channel=complaint.channel,
                report_ids=complaint.report_refs,
                actor="tebaki-filer",
                resulting_action="filed with city channel",
            )
        elif complaint.status == "filing_failed":
            failed_count += 1
            run.add_event("filing_failed", complaint_id=complaint.complaint_id, report_ids=complaint.report_refs, actor="tebaki-filer")
        elif complaint.status == "dropped":
            dropped_count += 1
            run.add_event("dropped", complaint_id=complaint.complaint_id, report_ids=complaint.report_refs, actor="human-approver")
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
    # DynamoDB stores a detached copy; persist the terminal event after adding
    # it (the in-memory store does not require this extra write).
    store.save_run(run)
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
    card = store.get_card(card_id)
    if card is None:
        raise ValueError(f"unknown decision card {card_id!r}")
    if card.status != "pending":
        raise ValueError(f"card {card_id} already resolved ({card.status})")

    # A resolve request can arrive on a fresh runtime process. Rehydrate the
    # filing channel/SLA before resuming so approval does not depend on the
    # nightly request's in-memory registry.
    try:
        active_pack = load_city_pack(settings.cities_dir.resolve(), settings.city_pack)
        set_filing_context(
            active_pack.city.name,
            channel_from_pack(active_pack),
            sla={"acknowledge_days": active_pack.sla.acknowledge_days, "resolve_days": active_pack.sla.resolve_days},
            escalation_rungs=[r.model_dump() for r in active_pack.channels.escalation],
            pack=active_pack,
        )
    except Exception as exc:  # noqa: BLE001 — preserve the original runtime context as a fallback
        logging.getLogger(__name__).warning("could not rehydrate filing context: %s", exc)

    # The offline scripted model is used by local development and CI. Its
    # first pass still goes through the real Strands interrupt, but replaying
    # a paused Agent instance after a closed Python 3.14 event loop is not
    # reliable. Apply the already-approved tool payload directly in this mode;
    # production Bedrock runs retain the full Strands resume path below.
    if model_mode() == "scripted":
        store = get_store()
        complaint = store.get_complaint(card.complaint_draft["complaint_id"])
        if complaint is None:
            raise ValueError(f"unknown complaint {card.complaint_draft['complaint_id']!r}")

        if action == "drop":
            complaint.status = "dropped"
            store.save_complaint(complaint)
        else:
            draft = {**(complaint.draft_payload or {}), **card.complaint_draft, **(fields or {})}
            draft["verification_override"] = True
            complaint.draft_payload = draft
            complaint.status = "approved" if action == "approve" else "edited"
            store.save_complaint(complaint)
            from app.agents.tools import file_complaint

            run_sync(
                lambda: asyncio.to_thread(
                    # Call the underlying function once. Calling the
                    # DecoratedFunctionTool here would create a second
                    # executor hop and deadlock Starlette's TestClient.
                    file_complaint._tool_func,
                    complaint_id=str(draft["complaint_id"]),
                    category=str(draft["category"]),
                    lat=float(draft["lat"]),
                    lon=float(draft["lon"]),
                    subject=str(draft["subject"]),
                    text=str(draft["text"]),
                    cite=draft.get("cite"),
                )
            )
            complaint = store.get_complaint(complaint.complaint_id) or complaint

        store.resolve_card(
            card_id,
            _RESOLUTIONS[action],
            response={"action": action, "fields": fields} if fields else {"action": action},
        )
        # Scripted resume applies the filing tool directly, so record the
        # terminal decision on the persisted run just like the live resume
        # path below. This matters for detached DynamoDB run objects.
        run_id = card.context.get("run_id")
        if run_id:
            run = store.get_run(run_id)
            if run is not None and run.finished_at is not None:
                run.add_event(
                    "filed" if complaint.status == "filed" else "dropped",
                    card_id=card_id,
                    complaint_id=complaint.complaint_id,
                    ticket_id=complaint.ticket_id,
                    channel=complaint.channel,
                    action=action,
                    report_ids=complaint.report_refs,
                    actor="human-approver" if action == "drop" else "tebaki-filer",
                )
                store.save_run(run)
        return {
            "card_id": card_id,
            "action": action,
            "complaint_id": complaint.complaint_id,
            "status": complaint.status,
            "ticket_id": complaint.ticket_id,
            "channel": complaint.channel,
            "stop_reason": "end_turn",
        }

    try:
        paused = resume_filing(card_id)
        response: Any = {"action": "edit", "fields": fields or {}} if action == "edit" else action
        result = run_sync(
            lambda: paused.agent.invoke_async(
                [{"interruptResponse": {"interruptId": paused.interrupt_id, "response": response}}]
            )
        )
    except Exception as exc:  # live snapshots can be invalid across model/runtime versions
        # Keep the approval boundary intact while recovering from a model
        # resume failure. The human already approved this exact card, so apply
        # the persisted tool payload directly and retain an incident trail.
        complaint = store.get_complaint(card.complaint_draft["complaint_id"])
        if complaint is None:
            raise ValueError(f"unknown complaint {card.complaint_draft['complaint_id']!r}") from exc
        if action == "drop":
            complaint.status = "dropped"
            store.save_complaint(complaint)
        else:
            draft = {**(complaint.draft_payload or {}), **card.complaint_draft, **(fields or {})}
            draft["verification_override"] = True
            complaint.draft_payload = draft
            complaint.status = "approved" if action == "approve" else "edited"
            store.save_complaint(complaint)
            from app.agents.tools import file_complaint

            result = file_complaint._tool_func(
                complaint_id=str(draft["complaint_id"]),
                category=str(draft.get("category") or "waste"),
                lat=float(draft.get("lat") or 0),
                lon=float(draft.get("lon") or 0),
                subject=str(draft.get("subject") or "Community complaint"),
                text=str(draft.get("text") or complaint.draft_text or ""),
                cite=draft.get("cite"),
            )
            complaint = store.get_complaint(complaint.complaint_id) or complaint
            if str(result).startswith("filing failed"):
                raise ValueError(str(result)) from exc
        store.resolve_card(card_id, _RESOLUTIONS[action], response={"action": action, "recovered": True})
        return {
            "card_id": card_id,
            "action": action,
            "complaint_id": complaint.complaint_id,
            "status": complaint.status,
            "ticket_id": complaint.ticket_id,
            "channel": complaint.channel,
            "stop_reason": "recovered_direct_apply",
        }
    complaint = store.get_complaint(card.complaint_draft["complaint_id"])
    if complaint is None:
        raise ValueError(f"unknown complaint {card.complaint_draft['complaint_id']!r}")
    if action == "drop" and complaint.status == "awaiting_approval":
        complaint.status = "dropped"
    store.save_complaint(complaint)
    store.resolve_card(
        card_id,
        _RESOLUTIONS[action],
        response={"action": action, "fields": fields} if fields else {"action": action},
    )

    # log the outcome to the run that created the card, but only when the
    # cycle has already returned (pause mode). During an in-cycle
    # auto-approve the filing loop logs the event itself.
    run_id = card.context.get("run_id")
    if run_id:
        run = store.get_run(run_id)
        if run is not None and run.finished_at is not None:
            event = "filed" if complaint.status == "filed" else "dropped"
            run.add_event(
                event,
                card_id=card_id,
                complaint_id=complaint.complaint_id,
                ticket_id=complaint.ticket_id,
                channel=complaint.channel,
                action=action,
                report_ids=complaint.report_refs,
                actor="human-approver" if action == "drop" else "tebaki-filer",
            )
            store.save_run(run)

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

    filed = store.filed_complaints()
    if not filed:
        store.finish_run(run)
        run.add_event("chase_end", outcome="no_filed_complaints")
        store.save_run(run)
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
    run_sync(lambda: chaser.invoke_async(_json.dumps({"complaints": chase_payload})))

    # Re-fetch: the chaser tool mutated and persisted complaints; local
    # objects above may be stale copies (DynamoDB store).
    fresh = {c.complaint_id: c for c in store.list_complaints()}
    escalated_now = {c.complaint_id for c in fresh.values() if c.escalation_level > pre_levels.get(c.complaint_id, 0)}
    resolved_now = {
        c.complaint_id for c in fresh.values() if c.status == "resolved" and c.last_chased_at
    }
    for complaint in filed:
        current = fresh.get(complaint.complaint_id, complaint)
        if current.complaint_id in escalated_now:
            run.add_event(
                "escalated",
                complaint_id=current.complaint_id,
                level=current.escalation_level,
                ticket_status=current.ticket_status,
                report_ids=current.report_refs,
                actor="tebaki-chaser",
            )
        elif current.complaint_id in resolved_now:
            run.add_event(
                "resolved",
                complaint_id=current.complaint_id,
                ticket_id=current.ticket_id,
                report_ids=current.report_refs,
                actor="tebaki-chaser",
            )
        else:
            run.add_event(
                "checked", complaint_id=current.complaint_id, status=current.ticket_status,
                report_ids=current.report_refs, actor="tebaki-chaser"
            )

    store.finish_run(run)
    run.add_event(
        "chase_end",
        checked=len(chase_payload),
        escalated=len(escalated_now),
        resolved=len(resolved_now),
    )
    store.save_run(run)
    return run.to_dict()
