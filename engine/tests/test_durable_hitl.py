"""Durable human-in-the-loop: paused filings survive an engine restart."""

from __future__ import annotations

from app.agents.registry import reset_registry
from app.orchestrator import resolve_decision, run_nightly_cycle
from app.store import get_store


def test_paused_filing_survives_registry_restart(portal_client, three_reports) -> None:
    """Pause a filing, 'restart the engine' (drop in-memory agents), resolve."""
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()
    cards = store.pending_cards()
    assert len(cards) == 2
    card = cards[0]
    assert card.paused_state is not None
    # the persisted snapshot carries the SDK interrupt state
    assert card.paused_state["data"]["interrupt_state"]["activated"] is True

    # simulate restart: in-memory paused agents vanish; persisted cards remain
    reset_registry()

    outcome = resolve_decision(card.card_id, "approve")
    assert outcome["status"] == "filed"
    assert outcome["ticket_id"].startswith("SBX-")
    assert outcome["stop_reason"] == "end_turn"
    complaint = store.get_complaint(outcome["complaint_id"])
    assert complaint.status == "filed"


def test_paused_filing_drop_after_restart(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()
    card = store.pending_cards()[0]
    reset_registry()

    outcome = resolve_decision(card.card_id, "drop")
    assert outcome["status"] == "dropped"
    complaint = store.get_complaint(outcome["complaint_id"])
    assert complaint.status == "dropped"


def test_paused_filing_edit_after_restart(portal_client, three_reports) -> None:
    run_nightly_cycle("sandbox", auto_approve=False)
    store = get_store()
    card = store.pending_cards()[0]
    reset_registry()

    outcome = resolve_decision(
        card.card_id, "edit", fields={"text": "RESTARTED EDIT: drain overflowing near school"}
    )
    assert outcome["status"] == "filed"
    from app.channels import SandboxChannel

    detail = SandboxChannel().check(outcome["ticket_id"])
    assert "RESTARTED EDIT" in detail["description"]


def test_durable_pause_roundtrip_on_dynamodb(portal_client, clean_store, monkeypatch) -> None:
    """Full durability on the DynamoDB store: pause, new store instance, resolve."""
    import uuid

    import app.store as store_mod
    from app.dynamodb_store import DynamoDBStore

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "local")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "local")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("TEBAKI_AWS_REGION", "us-east-1")

    import socket

    try:
        with socket.create_connection(("localhost", 8000), timeout=1):
            pass
    except OSError:
        import pytest

        pytest.skip("DynamoDB Local not running on :8000")

    table = f"tebaki-dur-{uuid.uuid4().hex[:8]}"
    ddb = DynamoDBStore(table_name=table, endpoint_url="http://localhost:8000")
    monkeypatch.setattr(store_mod, "_store", ddb)

    from app.store import Report

    ddb.add_report(Report(category="waste", lat=9.010, lon=38.760, note="garbage pile"))
    run_nightly_cycle("sandbox", auto_approve=False)

    # fresh store instance (new process would do the same) + wiped registry
    ddb2 = DynamoDBStore(table_name=table, endpoint_url="http://localhost:8000")
    monkeypatch.setattr(store_mod, "_store", ddb2)
    reset_registry()

    card2 = ddb2.pending_cards()[0]
    assert card2.paused_state is not None  # snapshot persisted through DynamoDB

    outcome = resolve_decision(card2.card_id, "approve")
    assert outcome["status"] == "filed"
    assert outcome["ticket_id"].startswith("SBX-")
    ddb2.table.delete()
