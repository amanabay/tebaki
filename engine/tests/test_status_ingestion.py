"""Status ingestion: operator records the city's response; the chase respects it."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.orchestrator import run_chase, run_nightly_cycle


def _client() -> TestClient:
    return TestClient(create_app())


def _file_one(store) -> None:
    from app.store import Report

    store.add_report(Report(category="waste", lat=9.01, lon=38.76, note="garbage pile"))
    run_nightly_cycle("sandbox")  # auto-approve


def test_operator_resolution_stops_the_chase(portal_client, clean_store) -> None:
    store = clean_store
    _file_one(store)
    (complaint,) = store.list_complaints()

    client = _client()
    resp = client.post(
        f"/admin/complaints/{complaint.complaint_id}/status",
        json={"status": "resolved", "note": "City collected the waste on Tuesday"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["ticket_status"] == "resolved"

    # even aged past SLA, nothing escalates: the chase set no longer contains it
    from datetime import UTC, datetime, timedelta

    past = datetime.now(UTC) - timedelta(days=30)
    complaint.filed_at = past.isoformat()
    store.save_complaint(complaint)

    summary = run_chase("sandbox")
    final = summary["events"][-1]
    # nothing left to chase: the resolution removed it from the monitoring set
    if final.get("outcome") == "no_filed_complaints":
        pass  # chase set empty — exactly what we want
    else:
        assert final["checked"] == 0
        assert final["escalated"] == 0
    assert store.get_complaint(complaint.complaint_id).status == "resolved"
    assert store.get_complaint(complaint.complaint_id).resolved_note.startswith("City collected")


def test_operator_acknowledgment_recorded_but_chaseable(portal_client, clean_store) -> None:
    store = clean_store
    _file_one(store)
    (complaint,) = store.list_complaints()

    client = _client()
    resp = client.post(
        f"/admin/complaints/{complaint.complaint_id}/status",
        json={"status": "acknowledged", "note": "Ward office confirmed receipt by email"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"

    complaint = store.get_complaint(complaint.complaint_id)
    assert complaint.acknowledged_note is not None
    # still monitored
    assert len(store.filed_complaints()) == 1


def test_status_validation(portal_client, clean_store) -> None:
    store = clean_store
    _file_one(store)
    (complaint,) = store.list_complaints()
    client = _client()

    # bad status
    assert (
        client.post(
            f"/admin/complaints/{complaint.complaint_id}/status", json={"status": "escalate"}
        ).status_code
        == 422
    )
    # unknown complaint
    assert (
        client.post("/admin/complaints/C-GHOST/status", json={"status": "resolved"}).status_code
        == 404
    )


def test_status_only_after_filing(portal_client, clean_store) -> None:
    store = clean_store
    from app.store import Complaint

    complaint = store.add_complaint(
        Complaint(complaint_id="C-DRAFT", report_refs=[], ward="W", draft_text="t", status="awaiting_approval")
    )
    client = _client()
    resp = client.post("/admin/complaints/C-DRAFT/status", json={"status": "resolved"})
    assert resp.status_code == 409
