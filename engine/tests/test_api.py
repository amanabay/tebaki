"""HTTP API tests: intake, decision queue (resume over HTTP), public data, ops."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_report_intake_roundtrip(portal_client, clean_store) -> None:
    client = _client()
    resp = client.post(
        "/reports",
        json={"category": "waste", "lat": 9.01, "lon": 38.76, "note": "garbage pile", "reporter": "selam"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["report_id"].startswith("R-")
    assert body["status"] == "new"

    listed = client.get("/reports").json()
    assert len(listed) == 1
    assert listed[0]["reporter"] == "selam"


def test_report_intake_validation(portal_client, clean_store) -> None:
    client = _client()
    assert client.post("/reports", json={"category": "crime", "lat": 9, "lon": 38, "note": "x"}).status_code == 422
    assert client.post("/reports", json={"category": "waste", "lat": 99, "lon": 38, "note": "x"}).status_code == 422
    assert client.post("/reports", json={"category": "waste", "lat": 9, "lon": 38, "note": ""}).status_code == 422


def test_decision_flow_over_http(portal_client, three_reports) -> None:
    client = _client()
    # run the cycle paused (no auto-approve) via the orchestrator directly
    from app.orchestrator import run_nightly_cycle

    run_nightly_cycle("sandbox", auto_approve=False)

    cards = client.get("/decisions").json()
    assert len(cards) == 2
    draft = cards[0]["draft"]
    assert draft["complaint_id"].startswith("C-")

    # approve the first card over HTTP
    resp = client.post(f"/decisions/{cards[0]['card_id']}/resolve", json={"action": "approve"})
    assert resp.status_code == 200
    outcome = resp.json()
    assert outcome["status"] == "filed"
    assert outcome["ticket_id"].startswith("SBX-")

    # drop the second
    resp = client.post(f"/decisions/{cards[1]['card_id']}/resolve", json={"action": "drop"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "dropped"

    # queue is empty now
    assert client.get("/decisions").json() == []


def test_decision_resolve_validation(portal_client, three_reports) -> None:
    client = _client()
    from app.orchestrator import run_nightly_cycle

    run_nightly_cycle("sandbox", auto_approve=False)
    card_id = client.get("/decisions").json()[0]["card_id"]

    assert (
        client.post(f"/decisions/{card_id}/resolve", json={"action": "maybe"}).status_code == 422
    )
    assert client.post("/decisions/D-NOPE/resolve", json={"action": "drop"}).status_code == 404

    # resolve then double-resolve -> 409
    assert client.post(f"/decisions/{card_id}/resolve", json={"action": "drop"}).status_code == 200
    assert client.post(f"/decisions/{card_id}/resolve", json={"action": "drop"}).status_code == 409


def test_public_ledger_scoreboard_activity(portal_client, three_reports) -> None:
    client = _client()
    from app.orchestrator import run_nightly_cycle

    run_nightly_cycle("sandbox")  # auto-approve: files 2 complaints

    ledger = client.get("/public/ledger").json()
    assert len(ledger) == 2
    assert all(row["status"] == "filed" for row in ledger)
    assert all(row["ticket_id"].startswith("SBX-") for row in ledger)

    scoreboard = client.get("/public/scoreboard").json()
    wards = {row["ward"]: row for row in scoreboard}
    # both waste reports fall inside the district polygon; the pothole fixture
    # sits outside it and falls back to the city name
    assert len(scoreboard) == 2
    assert wards["Sandbox District"]["filed"] == 1
    assert wards["Sandbox City"]["filed"] == 1

    activity = client.get("/public/activity").json()
    kinds = {e["kind"] for e in activity}
    assert {"cycle_start", "triage_done", "filed"} <= kinds
    assert all("run_id" in e for e in activity)

    map_data = client.get("/public/map").json()
    assert len(map_data["reports"]) == 3
    assert len(map_data["complaints"]) == 2


def test_admin_endpoints(portal_client, three_reports) -> None:
    client = _client()
    assert client.get("/health").json() == {"status": "ok"}

    nightly = client.post("/admin/nightly").json()
    assert nightly["city"] == "Sandbox City"

    chase = client.post("/admin/chase").json()
    assert chase["events"][-1]["kind"] == "chase_end"
    assert chase["events"][-1]["checked"] == 2
