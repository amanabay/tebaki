"""Sandbox mock municipal complaint portal.

Mimics a real city grievance portal for offline development, CI, and
agent evals. The form's field ids/selectors match the browser form_map
in cities/sandbox.yaml, so the AgentCore Browser channel (or any
headless client) can file against it exactly like a real portal.

Behavior:
- POST /complaints           -> creates ticket, returns ticket_id
- GET  /complaints/{id}      -> status (pending -> acknowledged -> resolved)
- POST /complaints/{id}/ack  -> force status change (test utility)
- GET  /                     -> human-facing complaint form
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Sandbox City Complaint Portal", version="0.1.0")

# In-memory ticket store: id -> record
TICKETS: dict[str, dict] = {}

# Auto-acknowledge: tickets acknowledge after N seconds (None = never).
AUTO_ACK_SECONDS: float | None = None

FORM_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sandbox City — File a Complaint</title>
  <style>
    body { font-family: system-ui; max-width: 480px; margin: 3rem auto; color: #222; }
    label { display: block; margin-top: 1rem; font-weight: 600; }
    select, textarea, input[type=text] { width: 100%; padding: 0.5rem; margin-top: 0.25rem; }
    button { margin-top: 1.5rem; padding: 0.6rem 1.5rem; }
  </style>
</head>
<body>
  <h1>Sandbox City Complaint Portal</h1>
  <form method="post" action="/complaints" enctype="multipart/form-data">
    <label for="category">Category</label>
    <select id="category" name="category">
      <option value="waste">Waste</option>
      <option value="pothole">Pothole</option>
      <option value="streetlight">Streetlight</option>
      <option value="drain">Blocked drain</option>
      <option value="water">Water</option>
    </select>

    <label for="location">Location</label>
    <input id="location" name="location" type="text" placeholder="Lat, Lon or landmark" required>

    <label for="description">Description</label>
    <textarea id="description" name="description" rows="4" required></textarea>

    <label for="photo">Photo (optional)</label>
    <input id="photo" name="photo" type="file" accept="image/*">

    <button type="submit">Submit complaint</button>
  </form>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def complaint_form() -> str:
    return FORM_HTML


@app.post("/complaints")
async def create_complaint(
    category: str = Form(...),
    location: str = Form(...),
    description: str = Form(...),
    photo: bytes | None = None,  # noqa: ARG001 — accepted but not stored
) -> JSONResponse:
    if not category or not location or not description:
        raise HTTPException(status_code=422, detail="category, location, description required")
    ticket_id = f"SBX-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    ack_at = now + timedelta(seconds=AUTO_ACK_SECONDS) if AUTO_ACK_SECONDS else None
    TICKETS[ticket_id] = {
        "ticket_id": ticket_id,
        "category": category,
        "location": location,
        "description": description[:500],
        "status": "pending",
        "filed_at": now.isoformat(),
        "acknowledged_at": None,
        "resolved_at": None,
        "auto_ack_at": ack_at.isoformat() if ack_at else None,
    }
    return JSONResponse(status_code=201, content={"ticket_id": ticket_id, "status": "pending"})


def _refresh(ticket: dict) -> dict:
    """Apply auto-acknowledge if enabled and due."""
    if ticket["status"] == "pending" and ticket["auto_ack_at"]:
        due = datetime.fromisoformat(ticket["auto_ack_at"])
        if datetime.now(timezone.utc) >= due:
            ticket["status"] = "acknowledged"
            ticket["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    return ticket


@app.get("/complaints/{ticket_id}")
def complaint_status(ticket_id: str) -> dict:
    if ticket_id not in TICKETS:
        raise HTTPException(status_code=404, detail=f"unknown ticket {ticket_id}")
    return _refresh(TICKETS[ticket_id])


@app.post("/complaints/{ticket_id}/ack")
def force_acknowledge(ticket_id: str) -> dict:
    if ticket_id not in TICKETS:
        raise HTTPException(status_code=404, detail=f"unknown ticket {ticket_id}")
    ticket = TICKETS[ticket_id]
    if ticket["status"] == "pending":
        ticket["status"] = "acknowledged"
        ticket["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    return ticket


@app.post("/complaints/{ticket_id}/resolve")
def force_resolve(ticket_id: str) -> dict:
    if ticket_id not in TICKETS:
        raise HTTPException(status_code=404, detail=f"unknown ticket {ticket_id}")
    ticket = TICKETS[ticket_id]
    ticket["status"] = "resolved"
    ticket["resolved_at"] = datetime.now(timezone.utc).isoformat()
    if not ticket["acknowledged_at"]:
        ticket["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    return ticket


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "tickets": len(TICKETS)}
