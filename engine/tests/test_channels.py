"""Channel adapter tests: Open311 (GeoReport v2) and SES email."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.channels import (
    EmailChannel,
    Open311Channel,
    SESEmailChannel,
    channel_from_pack,
)
from app.city_pack import load_city_pack, validate_pack_file

CITIES_DIR = Path(__file__).parents[2] / "cities"

_CODE_MAP = {"waste": "SVC-WASTE", "pothole": "SVC-POTHOLE", "streetlight": "SVC-LIGHT", "drain": "SVC-DRAIN", "water": "SVC-WATER"}


# --- Open311 ---------------------------------------------------------------------


def test_open311_files_with_service_code(open311_stub) -> None:
    channel = Open311Channel(
        endpoint="http://stub/v2", jurisdiction_id="test.gov", api_key="k-1", service_code_map=_CODE_MAP
    )
    result = channel.file(
        {"category": "pothole", "lat": 41.88, "lon": -87.63, "text": "big pothole", "subject": "Pothole"}
    )
    assert result.ok
    assert result.channel == "open311"
    assert result.ticket_id == "311-000001"
    record = open311_stub.store["311-000001"]
    assert record["service_code"] == "SVC-POTHOLE"
    assert record["jurisdiction_id"] == "test.gov"
    assert record["description"] == "big pothole"


def test_open311_check_returns_status(open311_stub) -> None:
    channel = Open311Channel(endpoint="http://stub/v2", service_code_map=_CODE_MAP)
    filed = channel.file({"category": "waste", "lat": 41.9, "lon": -87.6, "text": "overflowing bin"})
    status = channel.check(filed.ticket_id)
    assert status["service_request_id"] == filed.ticket_id
    assert status["status"] == "open"
    open311_stub.client.post(f"/v2/requests/{filed.ticket_id}/ack")
    assert channel.check(filed.ticket_id)["status"] == "acknowledged"


def test_open311_unmapped_category_fails_cleanly(open311_stub) -> None:
    channel = Open311Channel(endpoint="http://stub/v2", service_code_map={"waste": "SVC-WASTE"})
    result = channel.file({"category": "water", "lat": 41.9, "lon": -87.6, "text": "leak"})
    assert not result.ok
    assert "no service_code mapped" in result.detail
    assert "service-code map" in result.detail
    assert open311_stub.store == {}  # nothing was sent


def test_open311_endpoint_normalization() -> None:
    channel = Open311Channel(endpoint="https://311api.example.gov/open311/v2/requests.json")
    assert channel.endpoint == "https://311api.example.gov/open311/v2"


def test_open311_token_or_service_request_id(open311_stub) -> None:
    """A response returning a full service_request object also yields a ticket id."""
    open311_stub.set_format("service_request")
    channel = Open311Channel(endpoint="http://stub/v2", service_code_map=_CODE_MAP)
    result = channel.file({"category": "waste", "lat": 41.9, "lon": -87.6, "text": "x"})
    assert result.ok and result.ticket_id == "311-000001"
    assert open311_stub.store["311-000001"]["service_code"] == "SVC-WASTE"


# --- channel_from_pack -------------------------------------------------------------


def test_channel_from_pack_prefers_open311_for_chicago(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEBAKI_CHICAGO_311_KEY", "test-key")
    pack = load_city_pack(CITIES_DIR, "chicago")
    channel = channel_from_pack(pack)
    assert isinstance(channel, Open311Channel)
    assert channel.api_key == "test-key"
    assert channel.jurisdiction_id == "cityofchicago.org"
    assert channel.service_code_map["pothole"] == "4fd3b656e750846c53000004"
    assert set(channel.service_code_map) == {"waste", "pothole", "streetlight", "drain", "water"}


def test_channel_from_pack_uses_ses_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    pack = load_city_pack(CITIES_DIR, "addis")
    assert isinstance(channel_from_pack(pack), EmailChannel)  # default: dry-run
    monkeypatch.setenv("TEBAKI_EMAIL_MODE", "ses")
    monkeypatch.setenv("TEBAKI_SES_FROM", "tebaki@example.com")
    channel = channel_from_pack(pack)
    assert isinstance(channel, SESEmailChannel)


def test_strict_validation_passes_chicago_with_service_codes() -> None:
    issues = validate_pack_file(CITIES_DIR / "chicago.yaml", strict=True)
    assert issues == []


def test_open311_pack_without_codes_fails_strict(tmp_path, monkeypatch) -> None:
    """A pack with an open311 channel but no service codes must be flagged."""
    import shutil

    import yaml

    pack = load_city_pack(CITIES_DIR, "chicago")
    data = pack.model_dump()
    data["channels"]["api"]["service_code_map"] = None
    bad_dir = tmp_path / "cities"
    bad_dir.mkdir()
    geo_dir = bad_dir / "geojson"
    geo_dir.mkdir()
    shutil.copy(CITIES_DIR / "geojson/chicago.geojson", geo_dir / "chicago.geojson")
    (bad_dir / "chi-test.yaml").write_text(yaml.safe_dump(data))
    issues = validate_pack_file(bad_dir / "chi-test.yaml", strict=True)
    assert any("service_code_map" in i for i in issues)


# --- SES --------------------------------------------------------------------------


def test_ses_sends_utf8_email_with_message_id() -> None:
    from botocore.stub import Stubber

    channel = SESEmailChannel(to_address="office@city.gov", from_address="noreply@tebaki.dev")
    stubber = Stubber(channel.client)
    stubber.add_response(
        "send_email",
        {"MessageId": "msg-42"},
        expected_params={
            "FromEmailAddress": "noreply@tebaki.dev",
            "Destination": {"ToAddresses": ["office@city.gov"]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": "የቆሻሻ ቅሬታ / Waste complaint", "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": "ቆሻሻ አልተሰበሰበም።\n\nLegal basis: Proclamation 513/2007", "Charset": "UTF-8"}},
                }
            },
        },
    )
    stubber.activate()
    result = channel.file(
        {
            "category": "waste",
            "lat": 9.01,
            "lon": 38.76,
            "text": "ቆሻሻ አልተሰበሰበም።",
            "subject": "የቆሻሻ ቅሬታ / Waste complaint",
            "cite": "Proclamation 513/2007",
        }
    )
    stubber.assert_no_pending_responses()
    stubber.deactivate()
    assert result.ok
    assert result.extra["message_id"] == "msg-42"
    assert "msg-42" in result.detail


def test_ses_failure_reported_not_raised() -> None:
    from botocore.stub import Stubber

    channel = SESEmailChannel(to_address="office@city.gov")
    stubber = Stubber(channel.client)
    stubber.add_client_error("send_email", service_error_code="MessageRejected")
    stubber.activate()
    result = channel.file({"category": "waste", "lat": 9.0, "lon": 38.7, "text": "x", "subject": "s"})
    stubber.assert_no_pending_responses()
    stubber.deactivate()
    assert not result.ok
    assert "ses error" in result.detail


def test_ses_check_is_always_pending() -> None:
    channel = SESEmailChannel(to_address="office@city.gov")
    status = channel.check("any-message")
    assert status["status"] == "pending"  # no status API for email; chaser treats as unacked


# --- chicago nightly cycle with unmapped codes --------------------------------------


def test_chicago_cycle_files_through_open311(clean_store, open311_stub, monkeypatch) -> None:
    """Full nightly cycle on the Chicago pack files through the Open311 channel."""
    from app.orchestrator import run_nightly_cycle
    from app.store import Report

    monkeypatch.setenv("TEBAKI_CHICAGO_311_KEY", "test-key")
    store = clean_store
    store.add_report(Report(category="pothole", lat=41.88, lon=-87.63, note="big pothole on Clark St"))

    summary = run_nightly_cycle("chicago", auto_approve=True)
    filed = [e for e in summary["events"] if e["kind"] == "filed"]
    assert len(filed) == 1
    ticket = filed[0]["ticket_id"]
    assert ticket.startswith("311-")
    assert store.filed_complaints()[0].channel == "open311"
    # the stub received the mapped service code, not our category name
    record = open311_stub.store[ticket]
    assert record["service_code"] == "4fd3b656e750846c53000004"
    assert record["jurisdiction_id"] == "cityofchicago.org"
