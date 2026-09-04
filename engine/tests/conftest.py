"""Shared fixtures: in-process sandbox portal + clean store + seed reports."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "sandbox-portal"))

from portal.app import app as portal_app


def _proxy(client: TestClient, method: str, url: str, data: dict | None) -> httpx.Response:
    path = url.split("localhost:9100", 1)[1] if "localhost:9100" in url else url
    if method == "POST":
        resp = client.post(path, data=data)
    else:
        resp = client.get(path)
    return httpx.Response(
        status_code=resp.status_code,
        content=resp.content,
        headers={"content-type": resp.headers.get("content-type", "application/json")},
        request=httpx.Request(method, url),
    )


@pytest.fixture()
def portal_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Serve the mock portal in-process and point the channel at it."""
    client = TestClient(portal_app)
    monkeypatch.setattr(
        "app.channels.httpx.post",
        lambda url, data=None, timeout=None: _proxy(client, "POST", url, data),
    )
    monkeypatch.setattr(
        "app.channels.httpx.get",
        lambda url, timeout=None: _proxy(client, "GET", url, None),
    )
    return client


@pytest.fixture()
def clean_store():
    import app.store

    app.store._store = app.store.RunStore()
    yield app.store.get_store()
    app.store._store = None


@pytest.fixture()
def three_reports(clean_store) -> None:
    """Two nearby waste reports (~300m apart, same hotspot) + one pothole elsewhere."""
    from app.store import Report

    store = clean_store
    store.add_report(Report(category="waste", lat=9.010, lon=38.760, note="garbage pile on sidewalk"))
    store.add_report(Report(category="waste", lat=9.012, lon=38.758, note="trash not collected for days"))
    store.add_report(Report(category="pothole", lat=9.100, lon=38.700, note="deep pothole"))
