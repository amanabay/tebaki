"""Closure loop, escalation delivery, and tool hardening tests."""

from __future__ import annotations

from app.orchestrator import run_chase, run_nightly_cycle
from app.store import get_store


def _backdate(store, days: int) -> None:
    from datetime import UTC, datetime, timedelta

    past = datetime.now(UTC) - timedelta(days=days)
    for complaint in store.list_complaints():
        if complaint.filed_at:
            complaint.filed_at = past.isoformat()
            store.save_complaint(complaint)


def test_resolved_ticket_closes_the_complaint(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")
    store = get_store()
    for complaint in store.filed_complaints():
        portal_client.post(f"/complaints/{complaint.ticket_id}/resolve")

    summary = run_chase("sandbox")
    chase_end = next(e for e in summary["events"] if e["kind"] == "chase_end")
    assert chase_end["resolved"] == 2
    for complaint in store.list_complaints():
        assert complaint.status == "resolved"
        assert complaint.ticket_status == "resolved"
    # resolved complaints leave the chase set
    assert store.filed_complaints() == []


def test_acknowledged_ticket_advances_status_but_stays_chaseable(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")
    store = get_store()
    for complaint in store.filed_complaints():
        portal_client.post(f"/complaints/{complaint.ticket_id}/ack")

    run_chase("sandbox")  # inside ack SLA -> no escalation
    for complaint in store.list_complaints():
        assert complaint.status == "acknowledged"
    # still chaseable until resolved
    assert len(store.filed_complaints()) == 2


def test_escalation_letter_recorded_with_delivery(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")
    store = get_store()
    _backdate(store, days=5)  # past ack SLA (2 days)

    run_chase("sandbox")
    for complaint in store.list_complaints():
        assert complaint.status == "escalated_1"
        (entry,) = complaint.escalation_log
        assert entry["target"] == "District Grievance Office"
        assert entry["delivered"] is True  # dry-run email channel reports ok
        assert entry["delivery_detail"]
        assert entry["subject"]
        assert entry["text"]


def test_escalation_goes_up_the_ladder_with_delivery(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox")
    store = get_store()
    _backdate(store, days=5)
    run_chase("sandbox")  # level 1
    _backdate(store, days=20)
    run_chase("sandbox")  # level 2

    for complaint in store.list_complaints():
        log = complaint.escalation_log
        assert [e["level"] for e in log] == [1, 2]
        assert log[1]["target"] == "Sandbox City Council"
        assert log[1]["delivered"] is True


def test_submit_triage_skips_bad_rows_without_half_applying(clean_store) -> None:
    from app.agents.tools import submit_triage
    from app.store import Report

    store = clean_store
    good = store.add_report(Report(category="waste", lat=9.01, lon=38.76, note="garbage pile"))
    store.add_report(Report(category="waste", lat=9.02, lon=38.77, note="more garbage"))

    out = submit_triage(
        [
            {"report_id": good.report_id, "category": "waste", "severity": 4, "valid": True, "reason": "ok", "language": "en"},
            {"report_id": "R-NOPE", "category": "waste", "severity": 3, "valid": True, "reason": "x", "language": "en"},
            {"report_id": good.report_id, "category": "nonsense", "severity": 3, "valid": True, "reason": "y", "language": "en"},
        ]
    )
    assert "skipped 2 bad rows" in out
    assert store.get_report(good.report_id).status == "triaged"
    assert store.get_report(good.report_id).category == "waste"


def test_submit_chase_results_clamps_level_to_next_rung(clean_store) -> None:
    from app.agents.tools import submit_chase_results
    from app.store import Complaint

    store = clean_store
    complaint = store.add_complaint(
        Complaint(
            complaint_id="C-CLAMP",
            report_refs=[],
            ward="W",
            draft_text="t",
            status="filed",
            ticket_id="T-1",
        )
    )
    # model tries to jump 3 rungs ahead
    out = submit_chase_results(
        [{"complaint_id": "C-CLAMP", "ticket_status": "pending", "action": "escalate", "escalation_level": 3, "subject": "s", "text": "x"}]
    )
    assert "escalated 1" in out
    assert complaint.escalation_level == 1  # clamped to next rung
    assert complaint.status == "escalated_1"


def test_submit_chase_results_skips_unknown_complaints(clean_store) -> None:
    from app.agents.tools import submit_chase_results

    out = submit_chase_results([{"complaint_id": "C-GHOST", "ticket_status": "pending", "action": "none"}])
    assert "skipped 1 bad rows" in out
