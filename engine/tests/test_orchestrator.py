"""End-to-end nightly cycle tests against the sandbox portal.

Runs the FastAPI mock portal via TestClient-based channel (monkeypatched
httpx transport) so no server process is needed.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.orchestrator import run_nightly_cycle
from app.store import Report, get_store

sys_path = Path(__file__).parents[2] / "sandbox-portal"
import sys

sys.path.insert(0, str(sys_path))
from portal.app import app as portal_app


@pytest.fixture()
def portal_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Serve the mock portal in-process and point the channel at it."""
    client = TestClient(portal_app)
    portal_app.dependency_overrides = {}
    monkeypatch.setattr(
        "app.channels.httpx.post",
        lambda url, data=None, timeout=None: _proxy(client, "POST", url, data),
    )
    monkeypatch.setattr(
        "app.channels.httpx.get",
        lambda url, timeout=None: _proxy(client, "GET", url, None),
    )
    return client


def _proxy(client: TestClient, method: str, url: str, data: dict | None) -> httpx.Response:
    path = url.split("localhost:9100", 1)[1] if "localhost:9100" in url else url
    if method == "POST":
        resp = client.post(path, data=data)
    else:
        resp = client.get(path)
    # Convert to a plain httpx.Response so channel code sees the same API
    return httpx.Response(
        status_code=resp.status_code,
        content=resp.content,
        headers={"content-type": resp.headers.get("content-type", "application/json")},
        request=httpx.Request(method, url),
    )


@pytest.fixture()
def clean_store():
    import app.store

    app.store._store = app.store.RunStore()
    yield app.store.get_store()
    app.store._store = None


@pytest.fixture()
def three_reports(clean_store) -> None:
    store = clean_store
    # two nearby waste reports + one pothole elsewhere
    store.add_report(Report(category="waste", lat=9.010, lon=38.760, note="garbage pile on sidewalk"))
    store.add_report(Report(category="waste", lat=9.015, lon=38.758, note="trash not collected for days"))
    store.add_report(Report(category="pothole", lat=9.100, lon=38.700, note="deep pothole"))


def test_nightly_cycle_files_and_produces_tickets(portal_client, three_reports) -> None:
    summary = run_nightly_cycle(city_pack_name="sandbox")

    # 2 clusters (waste x2 merged, pothole x1) -> 2 complaints, auto-approved and filed
    kinds = [e["kind"] for e in summary["events"]]
    assert "cycle_start" in kinds
    assert summary["events"][1] == {"at": summary["events"][1]["at"], "kind": "triage", "new_reports": 3}
    cluster_events = [e for e in summary["events"] if e["kind"] == "cluster"]
    assert cluster_events[0]["clusters"] == 2

    filed = [e for e in summary["events"] if e["kind"] == "filed"]
    assert len(filed) == 2
    assert all(e["ticket_id"] and e["ticket_id"].startswith("SBX-") for e in filed)

    store = get_store()
    assert len(store.filed_complaints()) == 2
    assert all(r.status == "filed" for r in store.reports.values())
    # decision cards resolved by sandbox auto-approve policy
    assert all(c.status == "approved" for c in store.decision_cards.values())


def test_nightly_cycle_empty_is_noop(portal_client, clean_store) -> None:
    summary = run_nightly_cycle(city_pack_name="sandbox")
    assert summary["events"][-1]["outcome"] == "no_new_reports"


def test_decision_card_rejects_double_resolution(portal_client, clean_store) -> None:
    store = clean_store
    from app.store import DecisionCard

    card = store.add_decision_card(DecisionCard(complaint_draft={"subject": "x"}))
    store.resolve_card(card.card_id, "approved")
    with pytest.raises(ValueError, match="already resolved"):
        store.resolve_card(card.card_id, "dropped")


def test_chaser_can_check_sandbox_ticket_status(portal_client, three_reports) -> None:
    run_nightly_cycle(city_pack_name="sandbox")
    store = get_store()
    for complaint in store.filed_complaints():
        assert complaint.ticket_id is not None
        from app.channels import SandboxChannel

        status = SandboxChannel().check(complaint.ticket_id)
        assert status["ticket_id"] == complaint.ticket_id
        assert status["status"] in {"pending", "acknowledged", "resolved"}
