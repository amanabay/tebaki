"""DynamoDBStore tests against DynamoDB Local (docker container).

Skipped automatically when no local endpoint is serving, so CI without
the container still runs the rest of the suite. Uses a uniquely named
table per session for isolation.

Start the container:
    docker run -d --name tebaki-dynamodb -p 8000:8000 amazon/dynamodb-local:latest
"""

from __future__ import annotations

import uuid

import pytest

from app.dynamodb_store import DynamoDBStore
from app.store import Complaint, DecisionCard, Report

pytestmark = pytest.mark.integration

ENDPOINT = "http://localhost:8000"
TABLE = f"tebaki-test-{uuid.uuid4().hex[:8]}"


def _local_available() -> bool:
    import socket

    try:
        with socket.create_connection(("localhost", 8000), timeout=1):
            return True
    except OSError:
        return False


if not _local_available():
    pytest.skip("DynamoDB Local not running on :8000", allow_module_level=True)


@pytest.fixture()
def ddb_store(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "local")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "local")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("TEBAKI_AWS_REGION", "us-east-1")
    store = DynamoDBStore(table_name=TABLE, endpoint_url=ENDPOINT)
    yield store
    store.table.delete()


def test_report_roundtrip_and_status_queries(ddb_store) -> None:
    r1 = store_report(ddb_store, "R-T1", "waste", 9.01, 38.76, "new")
    store_report(ddb_store, "R-T2", "pothole", 9.02, 38.77, "new")
    store_report(ddb_store, "R-T3", "drain", 9.03, 38.78, "triaged")

    new = ddb_store.new_reports()
    assert {r.report_id for r in new} == {"R-T1", "R-T2"}

    fetched = ddb_store.get_report("R-T1")
    assert fetched.note == r1.note
    assert fetched.lat == 9.01

    ddb_store.update_report_status("R-T1", "rejected")
    assert ddb_store.get_report("R-T1").status == "rejected"
    assert {r.report_id for r in ddb_store.new_reports()} == {"R-T2"}

    listed = ddb_store.list_reports()
    assert len(listed) == 3


def test_complaint_lifecycle_and_filed_queries(ddb_store) -> None:
    ddb_store.add_complaint(
        Complaint(
            complaint_id="C-T1",
            report_refs=["R-T1"],
            ward="Arada",
            draft_text="issue",
            status="awaiting_approval",
            draft_payload={"category": "waste", "lat": 9.01, "lon": 38.76, "ward": "Arada"},
        )
    )
    fetched = ddb_store.get_complaint("C-T1")
    assert fetched.ward == "Arada"
    assert fetched.draft_payload["category"] == "waste"

    assert ddb_store.filed_complaints() == []

    fetched.status = "filed"
    fetched.ticket_id = "SBX-1"
    fetched.filed_at = "2026-09-06T00:00:00+00:00"
    ddb_store.save_complaint(fetched)

    filed = ddb_store.filed_complaints()
    assert [x.complaint_id for x in filed] == ["C-T1"]

    fetched.status = "escalated_1"
    ddb_store.save_complaint(fetched)
    assert [x.complaint_id for x in ddb_store.filed_complaints()] == ["C-T1"]


def test_decision_card_lifecycle(ddb_store) -> None:
    ddb_store.add_decision_card(
        DecisionCard(
            card_id="D-T1",
            complaint_draft={"complaint_id": "C-T1", "subject": "x"},
            context={"city": "Addis Ababa"},
        )
    )
    pending = ddb_store.pending_cards()
    assert [c.card_id for c in pending] == ["D-T1"]
    assert pending[0].complaint_draft["subject"] == "x"

    resolved = ddb_store.resolve_card("D-T1", "approved", response={"action": "approve"})
    assert resolved.status == "approved"
    assert ddb_store.pending_cards() == []
    assert ddb_store.get_card("D-T1").status == "approved"

    with pytest.raises(ValueError, match="already resolved"):
        ddb_store.resolve_card("D-T1", "drop")
    with pytest.raises(ValueError, match="unknown decision card"):
        ddb_store.resolve_card("D-NOPE", "drop")


def test_agent_run_persistence(ddb_store) -> None:
    run = ddb_store.start_run("Addis Ababa")
    run.add_event("cycle_start", city="Addis Ababa")
    run.add_event("filed", complaint_id="C-1")
    ddb_store.finish_run(run)

    fetched = ddb_store.get_run(run.run_id)
    assert fetched is not None
    assert fetched.city == "Addis Ababa"
    assert [e["kind"] for e in fetched.events] == ["cycle_start", "filed"]
    assert fetched.finished_at is not None
    assert len(ddb_store.list_runs()) == 1


def test_full_nightly_cycle_and_chase_on_dynamodb(portal_client, ddb_store, monkeypatch) -> None:
    """The swap-in test: the whole engine runs against the DynamoDB store."""
    import app.store as store_mod

    monkeypatch.setattr(store_mod, "_store", ddb_store)

    from app.orchestrator import resolve_decision, run_chase, run_nightly_cycle

    ddb_store.add_report(Report(category="waste", lat=9.010, lon=38.760, note="garbage pile on sidewalk"))
    ddb_store.add_report(Report(category="waste", lat=9.012, lon=38.758, note="trash not collected for days"))
    ddb_store.add_report(Report(category="pothole", lat=9.100, lon=38.700, note="deep pothole"))

    # paused cycle: decision cards created, nothing filed
    run_nightly_cycle("sandbox", auto_approve=False)
    cards = ddb_store.pending_cards()
    assert len(cards) == 2
    assert ddb_store.filed_complaints() == []

    # approve one, drop the other — resuming paused agents through the store
    approved = resolve_decision(cards[0].card_id, "approve")
    assert approved["status"] == "filed"
    assert approved["ticket_id"].startswith("SBX-")
    dropped = resolve_decision(cards[1].card_id, "drop")
    assert dropped["status"] == "dropped"

    filed = ddb_store.filed_complaints()
    assert len(filed) == 1
    # reports referenced by the filed complaint are marked filed
    reports = {r.report_id: r for r in ddb_store.list_reports()}
    assert all(reports[rid].status == "filed" for rid in filed[0].report_refs)

    # age past the ack SLA (sandbox: 2 days) and chase
    from datetime import UTC, datetime, timedelta

    past = datetime.now(UTC) - timedelta(days=5)
    for complaint in ddb_store.list_complaints():
        if complaint.filed_at:
            complaint.filed_at = past.isoformat()
            ddb_store.save_complaint(complaint)

    chase_summary = run_chase("sandbox")
    chase_end = next(e for e in chase_summary["events"] if e["kind"] == "chase_end")
    assert chase_end["checked"] == 1
    assert chase_end["escalated"] == 1

    escalated = ddb_store.get_complaint(filed[0].complaint_id)
    assert escalated.status == "escalated_1"
    assert escalated.escalation_log[0]["target"] == "District Grievance Office"

    # run log persisted with the full event trail
    runs = ddb_store.list_runs()
    assert any(e["kind"] == "filed" for r in runs for e in r.events)
    assert any(e["kind"] == "escalated" for r in runs for e in r.events)


def store_report(store: DynamoDBStore, rid: str, category: str, lat: float, lon: float, status: str) -> Report:
    return store.add_report(
        Report(
            report_id=rid,
            category=category,
            lat=lat,
            lon=lon,
            note=f"note {rid}",
            status=status,
        )
    )
