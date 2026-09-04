"""Day-2 agent tests: real Strands loop, interrupt pause, resume approve/edit/drop."""

from __future__ import annotations

from app.channels import SandboxChannel
from app.orchestrator import resolve_decision, run_nightly_cycle
from app.store import Report, get_store


def test_auto_approve_sandbox_files_end_to_end(portal_client, three_reports) -> None:
    summary = run_nightly_cycle("sandbox")  # sandbox default: auto-approve
    store = get_store()

    kinds = [e["kind"] for e in summary["events"]]
    assert "triage_done" in kinds and "cluster_done" in kinds

    triage_done = next(e for e in summary["events"] if e["kind"] == "triage_done")
    assert triage_done["accepted"] == 3 and triage_done["rejected"] == 0
    assert triage_done["graph_nodes"] == ["triage", "cluster", "drafter"]
    cluster_done = next(e for e in summary["events"] if e["kind"] == "cluster_done")
    assert cluster_done["clustered"] == 3  # reports that made it through clustering

    filed_events = [e for e in summary["events"] if e["kind"] == "filed"]
    assert len(filed_events) == 2
    assert all(e["ticket_id"].startswith("SBX-") for e in filed_events)
    assert len(store.filed_complaints()) == 2
    assert all(c.status == "approved" for c in store.decision_cards.values())
    assert all(r.status == "filed" for r in store.reports.values())


def test_cycle_pauses_on_decision_cards(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()

    cards = store.pending_cards()
    assert len(cards) == 2
    assert all(c.status == "awaiting_approval" for c in store.complaints.values())
    assert store.filed_complaints() == []
    # reports passed the graph phase (triaged -> clustered) but nothing filed yet
    assert all(r.status == "clustered" for r in store.reports.values())


def test_resume_approve_files_with_ticket(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()
    card = store.pending_cards()[0]

    outcome = resolve_decision(card.card_id, "approve")
    assert outcome["status"] == "filed"
    assert outcome["ticket_id"].startswith("SBX-")
    assert outcome["stop_reason"] == "end_turn"

    complaint = store.complaints[outcome["complaint_id"]]
    assert complaint.status == "filed"
    assert card.status == "approved"
    # the other card is still pending
    assert len(store.pending_cards()) == 1


def test_resume_drop_cancels_filing(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()
    card = store.pending_cards()[0]

    outcome = resolve_decision(card.card_id, "drop")
    assert outcome["status"] == "dropped"
    assert outcome["ticket_id"] is None
    complaint = store.complaints[outcome["complaint_id"]]
    assert complaint.status == "dropped"
    assert card.status == "dropped"
    # nothing was filed for this complaint: no ticket in the portal for it
    assert store.filed_complaints() == []


def test_resume_edit_changes_filed_text(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()
    card = store.pending_cards()[0]

    outcome = resolve_decision(
        card.card_id, "edit", fields={"text": "EDITED BY HUMAN: drain overflowing near school"}
    )
    assert outcome["status"] == "filed"
    detail = SandboxChannel().check(outcome["ticket_id"])
    assert "EDITED BY HUMAN" in detail["description"]
    assert card.status == "edited"


def test_resolve_validates_action_and_state(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()
    card = store.pending_cards()[0]

    try:
        resolve_decision(card.card_id, "maybe")
    except ValueError as e:
        assert "approve|edit|drop" in str(e)
    else:
        raise AssertionError("expected ValueError")

    resolve_decision(card.card_id, "approve")
    try:
        resolve_decision(card.card_id, "drop")
    except ValueError as e:
        assert "already resolved" in str(e)
    else:
        raise AssertionError("expected ValueError on double resolve")


def test_triage_rejects_empty_notes(portal_client, clean_store) -> None:
    store = clean_store
    empty = store.add_report(Report(category="waste", lat=9.01, lon=38.76, note="   "))
    good = store.add_report(Report(category="pothole", lat=9.05, lon=38.70, note="deep pothole on main road"))

    summary = run_nightly_cycle("sandbox")  # auto-approve
    triage_done = next(e for e in summary["events"] if e["kind"] == "triage_done")
    assert triage_done["rejected"] == 1 and triage_done["accepted"] == 1
    assert store.reports[empty.report_id].status == "rejected"
    assert store.reports[good.report_id].status == "filed"


def test_graph_conditional_edge_skips_stages_when_all_rejected(portal_client, clean_store) -> None:
    """All-rejected -> the graph completes after triage only (edges untraversed)."""
    store = clean_store
    store.add_report(Report(category="waste", lat=9.01, lon=38.76, note="   "))
    store.add_report(Report(category="pothole", lat=9.05, lon=38.70, note=""))

    summary = run_nightly_cycle("sandbox")
    triage_done = next(e for e in summary["events"] if e["kind"] == "triage_done")
    assert triage_done["graph_nodes"] == ["triage"]  # cluster/drafter skipped
    assert summary["events"][-1]["outcome"] == "all_rejected"
    assert store.complaints == {}


def test_amharic_note_detected(portal_client, clean_store) -> None:
    store = clean_store
    am = store.add_report(Report(category="waste", lat=9.01, lon=38.76, note="ቆሻሻ ለብዙ ቀናት አልተሰበሰበም"))
    run_nightly_cycle("sandbox")
    assert store.reports[am.report_id].language == "am"
    assert store.reports[am.report_id].status == "filed"


def test_severity_from_notes(portal_client, clean_store) -> None:
    store = clean_store
    hazard = store.add_report(Report(category="drain", lat=9.01, lon=38.76, note="blocked drain causing flood hazard"))
    run_nightly_cycle("sandbox")
    assert store.reports[hazard.report_id].severity == 5
