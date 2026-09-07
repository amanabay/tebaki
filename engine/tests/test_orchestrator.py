"""Nightly cycle integration tests (sandbox portal, in-process)."""

from __future__ import annotations

from app.channels import SandboxChannel
from app.orchestrator import run_nightly_cycle
from app.store import get_store


def test_nightly_cycle_files_and_produces_tickets(portal_client, three_reports) -> None:
    summary = run_nightly_cycle(city_pack_name="sandbox")

    filed = [e for e in summary["events"] if e["kind"] == "filed"]
    assert len(filed) == 2
    assert all(e["ticket_id"].startswith("SBX-") for e in filed)

    store = get_store()
    assert len(store.filed_complaints()) == 2
    assert all(r.status == "filed" for r in store.list_reports())


def test_nightly_cycle_empty_is_noop(portal_client, clean_store) -> None:
    summary = run_nightly_cycle(city_pack_name="sandbox")
    assert summary["events"][-1]["outcome"] == "no_new_reports"


def test_decision_card_rejects_double_resolution(portal_client, clean_store) -> None:
    store = clean_store
    from app.store import DecisionCard

    card = store.add_decision_card(DecisionCard(complaint_draft={"subject": "x"}))
    store.resolve_card(card.card_id, "approved")
    try:
        store.resolve_card(card.card_id, "dropped")
    except ValueError as e:
        assert "already resolved" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_chaser_can_check_sandbox_ticket_status(portal_client, three_reports) -> None:
    run_nightly_cycle(city_pack_name="sandbox")
    store = get_store()
    for complaint in store.filed_complaints():
        assert complaint.ticket_id is not None
        status = SandboxChannel().check(complaint.ticket_id)
        assert status["ticket_id"] == complaint.ticket_id
        assert status["status"] in {"pending", "acknowledged", "resolved"}
