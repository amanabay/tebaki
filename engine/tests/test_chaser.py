"""Chaser agent tests: SLA clocks, ticket checks, escalation ladder."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.orchestrator import run_chase, run_nightly_cycle
from app.store import get_store


def _backdate(store, days: int) -> None:
    """Pretend all filed complaints were filed `days` days ago."""
    past = datetime.now(UTC) - timedelta(days=days)
    for complaint in store.list_complaints():
        if complaint.filed_at:
            complaint.filed_at = past.isoformat()


def test_chase_inside_sla_does_nothing(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")  # files 2 complaints
    summary = run_chase("sandbox")

    chase_end = next(e for e in summary["events"] if e["kind"] == "chase_end")
    assert chase_end["checked"] == 2
    assert chase_end["escalated"] == 0
    store = get_store()
    assert all(c.escalation_level == 0 for c in store.list_complaints())
    assert all(c.ticket_status == "pending" for c in store.filed_complaints())


def test_chase_escalates_past_ack_deadline(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")  # sandbox SLA: ack 2 days
    store = get_store()
    _backdate(store, days=5)  # 5 > 2 days, tickets still pending

    summary = run_chase("sandbox")
    chase_end = next(e for e in summary["events"] if e["kind"] == "chase_end")
    assert chase_end["checked"] == 2
    assert chase_end["escalated"] == 2

    for complaint in store.list_complaints():
        assert complaint.escalation_level == 1
        assert complaint.status == "escalated_1"
        log = getattr(complaint, "escalation_log", [])
        assert len(log) == 1
        assert log[0]["level"] == 1
        # sandbox pack's first escalation rung is the district grievance office
        assert log[0]["target"] == "District Grievance Office"
        assert complaint.ticket_id in log[0]["subject"]


def test_chase_escalates_acknowledged_past_resolve_deadline(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")  # sandbox SLA: resolve 7 days
    store = get_store()
    # Acknowledge both tickets in the portal, then age past resolve deadline
    for complaint in store.filed_complaints():
        portal_client.post(f"/complaints/{complaint.ticket_id}/ack")
    _backdate(store, days=10)

    summary = run_chase("sandbox")
    chase_end = next(e for e in summary["events"] if e["kind"] == "chase_end")
    assert chase_end["escalated"] == 2
    for complaint in store.list_complaints():
        assert complaint.status == "escalated_1"


def test_chase_ladder_goes_to_level_2(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")
    store = get_store()
    _backdate(store, days=5)
    run_chase("sandbox")  # level 1
    _backdate(store, days=20)  # even older now
    run_chase("sandbox")  # should reach level 2

    for complaint in store.list_complaints():
        assert complaint.escalation_level == 2
        log = getattr(complaint, "escalation_log", [])
        assert [entry["level"] for entry in log] == [1, 2]
        # second rung is the city council
        assert log[1]["target"] == "Sandbox City Council"


def test_chase_with_no_filed_complaints_is_noop(portal_client, clean_store) -> None:
    summary = run_chase("sandbox")
    assert summary["events"][-1]["outcome"] == "no_filed_complaints"


def test_resolved_tickets_not_escalated(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")
    store = get_store()
    for complaint in store.filed_complaints():
        portal_client.post(f"/complaints/{complaint.ticket_id}/resolve")
    _backdate(store, days=30)

    summary = run_chase("sandbox")
    chase_end = next(e for e in summary["events"] if e["kind"] == "chase_end")
    assert chase_end["escalated"] == 0
    for complaint in store.list_complaints():
        assert complaint.escalation_level == 0
