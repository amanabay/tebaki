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
    # TestClient waits for FastAPI background tasks, so the response keeps its
    # intake contract while the persisted report already has instant triage.
    assert listed[0]["status"] == "triaged"
    assert listed[0]["triage_reason"]
    assert 0 <= listed[0]["triage_confidence"] <= 1


def test_public_map_exposes_instant_triage_metadata(portal_client, clean_store) -> None:
    client = _client()
    response = client.post(
        "/reports",
        json={"category": "drain", "lat": 9.01, "lon": 38.76, "note": "blocked drain"},
    )
    assert response.status_code == 201

    mapped = client.get("/public/map").json()["reports"]
    assert len(mapped) == 1
    assert mapped[0]["status"] == "triaged"
    assert mapped[0]["triage_reason"]
    assert mapped[0]["triage_confidence"] is not None


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


def test_accountability_and_proof_endpoints(clean_store) -> None:
    client = _client()
    from app.store import Complaint, Report

    report = clean_store.add_report(
        Report(report_id="R-TRACE", category="waste", lat=9.01, lon=38.76, note="overflowing bin")
    )
    complaint = clean_store.add_complaint(
        Complaint(
            complaint_id="C-TRACE",
            report_refs=[report.report_id],
            ward="Sandbox District",
            status="filed",
            ticket_id="SBX-TRACE",
            draft_payload={"category": "waste", "severity": 3, "cite": "Solid Waste rule"},
        )
    )
    run = clean_store.start_run("Sandbox City")
    run.add_event("triage_done", actor="tebaki-guardian", report_ids=[report.report_id], confidence=0.9)
    run.add_event("filed", actor="tebaki-filer", complaint_id=complaint.complaint_id, report_ids=[report.report_id])
    clean_store.finish_run(run)
    clean_store.save_run(run)

    timeline = client.get(f"/public/reports/{report.report_id}/timeline")
    assert timeline.status_code == 200
    assert [event["kind"] for event in timeline.json()] == ["submitted", "triage_done", "filed"]
    case = client.get(f"/public/complaints/{complaint.complaint_id}").json()
    assert case["evidence"]["report_count"] == 1
    assert case["timeline"]
    assert client.get("/public/runs").json()[0]["run_id"] == run.run_id
    assert client.get(f"/public/runs/{run.run_id}").json()["events"]
    assert client.get("/public/impact").json()["total_cases"] == 1
    assert client.get("/public/proof").json()["last_run_id"] == run.run_id
    assert client.get("/public/diagnostics").json()["checks"]


def test_agentcore_http_envelope_reads_public_data(clean_store) -> None:
    client = _client()
    response = client.post("/invocations", json={"method": "GET", "path": "/public/proof"})
    assert response.status_code == 200
    assert response.json()["runtime_status"] == "reachable"


def test_admin_endpoints(portal_client, three_reports) -> None:
    client = _client()
    assert client.get("/health").json() == {"status": "ok"}

    nightly = client.post("/admin/nightly").json()
    assert nightly["city"] == "Sandbox City"

    chase = client.post("/admin/chase").json()
    assert chase["events"][-1]["kind"] == "chase_end"
    assert chase["events"][-1]["checked"] == 2


def test_demo_seed_is_idempotent(portal_client, clean_store) -> None:
    client = _client()
    first = client.post("/admin/demo/seed")
    assert first.status_code == 200
    assert len(first.json()["added"]) == 3
    second = client.post("/admin/demo/seed")
    assert second.status_code == 200
    assert second.json()["added"] == []
    assert len(client.get("/reports").json()) == 3


def test_demo_can_simulate_missed_sla_then_escalate(portal_client, three_reports) -> None:
    client = _client()
    client.post("/admin/nightly")  # sandbox auto-approves and files two cases

    advanced = client.post("/admin/demo/miss-deadlines")
    assert advanced.status_code == 200
    assert len(advanced.json()["affected"]) == 2
    assert advanced.json()["simulated_days"] > 0

    chase = client.post("/admin/chase")
    assert chase.status_code == 200
    end = next(event for event in chase.json()["events"] if event["kind"] == "chase_end")
    assert end["checked"] == 2
    assert end["escalated"] == 2

    ledger = client.get("/public/ledger").json()
    assert {row["status"] for row in ledger} == {"escalated_1"}
    assert all(row["escalation_log"][0]["delivered"] is True for row in ledger)


def test_demo_deadline_simulation_requires_filed_cases(portal_client, clean_store) -> None:
    client = _client()
    response = client.post("/admin/demo/miss-deadlines")
    assert response.status_code == 409
    assert "File at least one" in response.text
