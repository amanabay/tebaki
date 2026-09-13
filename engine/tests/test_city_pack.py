from pathlib import Path

import pytest

from app.city_pack import CityPackError, load_city_pack, validate_pack_file
from app.models.city_pack import SLA, Channels, CityMeta, CityPack

CITIES_DIR = Path(__file__).parents[2] / "cities"


def test_load_sandbox_pack() -> None:
    pack = load_city_pack(CITIES_DIR, "sandbox")
    assert pack.city.name == "Sandbox City"
    assert pack.channels.browser is not None
    assert pack.channels.browser.form_map.submit == "button[type=submit]"
    assert pack.sla.acknowledge_days == 2
    assert [e.level for e in pack.channels.escalation] == ["district", "city"]


def test_load_addis_and_chicago_packs() -> None:
    addis = load_city_pack(CITIES_DIR, "addis")
    assert addis.city.local_name == "አዲስ አበባ"
    assert addis.city.languages == ["am", "en"]
    assert addis.coverage.status == "city_fallback"
    assert addis.coverage.contact_source
    chicago = load_city_pack(CITIES_DIR, "chicago")
    assert chicago.channels.api is not None
    assert chicago.channels.api.type == "open311"


def test_unknown_pack_lists_available() -> None:
    with pytest.raises(CityPackError, match="available"):
        load_city_pack(CITIES_DIR, "narnia")


def test_pack_name_rejects_traversal() -> None:
    with pytest.raises(CityPackError, match="invalid pack name"):
        load_city_pack(CITIES_DIR, "../etc/passwd")


def test_missing_geojson_is_fatal() -> None:
    pack_data = load_city_pack(CITIES_DIR, "sandbox").model_dump()
    pack_data["boundary"]["geojson"] = "geojson/does-not-exist.geojson"
    bad_dir = CITIES_DIR.parent / "engine/tests/fixtures/bad_pack"
    bad_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (bad_dir / "broken.yaml").write_text(yaml.safe_dump(pack_data))
    (bad_dir / "does-not-exist.geojson").unlink(missing_ok=True)
    with pytest.raises(CityPackError, match="boundary geojson not found"):
        load_city_pack(bad_dir, "broken")


def test_invalid_timezone_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        CityMeta(
            name="X", local_name="X", languages=["en"], timezone="Not/AZone", locale="en-US"
        )


def test_sla_ordering_enforced() -> None:
    with pytest.raises(ValueError, match="resolve_days"):
        SLA(acknowledge_days=7, resolve_days=3)


def test_channels_require_a_filing_channel() -> None:
    with pytest.raises(ValueError, match="at least one filing channel"):
        Channels(email=[], browser=None, api=None, escalation=[
            __import__("app.models.city_pack", fromlist=["EscalationLevel"]).EscalationLevel(
                level="city", target="T", after_days=7
            )
        ])


def test_escalation_days_must_ascending() -> None:
    from app.models.city_pack import EscalationLevel

    with pytest.raises(ValueError, match="ascending"):
        Channels(
            email=[{"target": "T", "address": "a@b.co", "lang": "en"}],
            escalation=[
                EscalationLevel(level="city", target="T2", after_days=14),
                EscalationLevel(level="district", target="T1", after_days=7),
            ],
        )


def test_email_lang_must_be_city_language() -> None:

    with pytest.raises(Exception, match="not in city languages"):
        CityPack.model_validate(
            {
                "city": {
                    "name": "X",
                    "local_name": "X",
                    "languages": ["en"],
                    "timezone": "Africa/Addis_Ababa",
                    "locale": "en-US",
                },
                "boundary": {"geojson": "geojson/sandbox.geojson"},
                "admin": [{"level": "district"}],
                "channels": {
                    "email": [
                        {"target": "T", "address": "a@b.co", "lang": "am"}
                    ],
                    "escalation": [{"level": "city", "target": "T", "after_days": 7}],
                },
                "sla": {"acknowledge_days": 2, "resolve_days": 7},
                "pitch": {"number": "n", "source": "s"},
            }
        )


def test_strict_validation_passes_addis_source_linked_pack() -> None:
    issues = validate_pack_file(CITIES_DIR / "addis.yaml", strict=True)
    assert issues == []


def test_strict_validation_passes_sandbox() -> None:
    issues = validate_pack_file(CITIES_DIR / "sandbox.yaml", strict=True)
    assert issues == []
