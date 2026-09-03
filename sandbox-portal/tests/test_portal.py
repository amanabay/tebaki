from fastapi.testclient import TestClient

from portal.app import app

client = TestClient(app)


def test_form_page_renders() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="category"' in resp.text
    assert 'id="description"' in resp.text


def test_file_complaint_returns_ticket_id() -> None:
    resp = client.post(
        "/complaints",
        data={"category": "waste", "location": "9.01, 38.76", "description": "Uncollected garbage for two weeks"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ticket_id"].startswith("SBX-")
    assert body["status"] == "pending"


def test_ticket_status_lookup() -> None:
    filed = client.post(
        "/complaints",
        data={"category": "pothole", "location": "9.02, 38.75", "description": "Deep pothole on main road"},
    ).json()
    resp = client.get(f"/complaints/{filed['ticket_id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_unknown_ticket_404() -> None:
    assert client.get("/complaints/SBX-NOPE123").status_code == 404


def test_force_acknowledge_and_resolve() -> None:
    filed = client.post(
        "/complaints",
        data={"category": "streetlight", "location": "9.00, 38.74", "description": "Streetlight out"},
    ).json()
    tid = filed["ticket_id"]
    acked = client.post(f"/complaints/{tid}/ack").json()
    assert acked["status"] == "acknowledged"
    assert acked["acknowledged_at"] is not None
    resolved = client.post(f"/complaints/{tid}/resolve").json()
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None


def test_form_selectors_match_city_pack() -> None:
    """The rendered form must match the selectors in cities/sandbox.yaml form_map."""
    import yaml
    from pathlib import Path

    pack = yaml.safe_load((Path(__file__).parents[2] / "cities/sandbox.yaml").read_text())
    form_map = pack["channels"]["browser"]["form_map"]
    html = client.get("/").text
    for field, selector in form_map.items():
        if selector.startswith("#"):
            assert f'id="{selector[1:]}"' in html, f"selector {selector} for {field} not found in form"
        elif selector.startswith("button"):
            assert "<button" in html
        elif "name=" in selector:
            name = selector.split("name=")[1].rstrip("]")
            assert f'name="{name}"' in html, f'form field name="{name}" ({field}) not found'
