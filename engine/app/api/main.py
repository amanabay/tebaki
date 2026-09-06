"""Tebaki HTTP API: report intake, decision queue, public dashboard data.

Run locally:
    PYTHONPATH=engine:sandbox-portal .venv/bin/uvicorn app.api.main:app --port 8000

The decision-queue endpoints resume real paused Strands interrupts:
POST /decisions/{card_id}/resolve approves/edits/drops a pending filing.
"""

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.orchestrator import resolve_decision, run_chase, run_nightly_cycle
from app.store import Report, get_store


class ReportIn(BaseModel):
    category: str = Field(pattern="^(waste|pothole|streetlight|drain|water)$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    note: str = Field(min_length=1, max_length=1000)
    reporter: str = Field(default="anonymous", max_length=100)


class ResolveIn(BaseModel):
    action: str = Field(pattern="^(approve|edit|drop)$")
    fields: dict[str, Any] | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="Tebaki API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- intake -----------------------------------------------------------------

    @app.post("/reports", status_code=201)
    def submit_report(body: ReportIn) -> dict[str, Any]:
        store = get_store()
        report = store.add_report(
            Report(
                category=body.category,
                lat=body.lat,
                lon=body.lon,
                note=body.note,
                reporter=body.reporter,
            )
        )
        return {"report_id": report.report_id, "status": report.status}

    @app.get("/reports")
    def list_reports(limit: int = 100) -> list[dict[str, Any]]:
        reports = sorted(get_store().reports.values(), key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in reports[:limit]]

    # --- decision queue ------------------------------------------------------------

    @app.get("/decisions")
    def pending_decisions() -> list[dict[str, Any]]:
        store = get_store()
        return [
            {
                "card_id": card.card_id,
                "created_at": card.created_at,
                "draft": card.complaint_draft,
                "context": card.context,
            }
            for card in store.pending_cards()
        ]

    @app.post("/decisions/{card_id}/resolve")
    def resolve(card_id: str, body: ResolveIn) -> dict[str, Any]:
        try:
            return resolve_decision(card_id, body.action, body.fields)
        except ValueError as e:
            raise HTTPException(status_code=404 if "unknown" in str(e) else 409, detail=str(e)) from e

    # --- public dashboard data -------------------------------------------------------

    @app.get("/public/ledger")
    def ledger(limit: int = 200) -> list[dict[str, Any]]:
        complaints = sorted(get_store().complaints.values(), key=lambda c: c.created_at, reverse=True)
        return [
            {
                "complaint_id": c.complaint_id,
                "ward": c.ward,
                "status": c.status,
                "ticket_id": c.ticket_id,
                "channel": c.channel,
                "escalation_level": c.escalation_level,
                "filed_at": c.filed_at,
                "category": (c.draft_payload or {}).get("category"),
                "subject": (c.draft_payload or {}).get("subject"),
                "report_refs": c.report_refs,
                "created_at": c.created_at,
            }
            for c in complaints[:limit]
        ]

    @app.get("/public/scoreboard")
    def scoreboard() -> list[dict[str, Any]]:
        rows: dict[str, dict[str, int]] = {}
        for complaint in get_store().complaints.values():
            row = rows.setdefault(
                complaint.ward,
                {"ward": complaint.ward, "complaints": 0, "filed": 0, "resolved": 0, "escalated": 0},
            )
            row["complaints"] += 1
            if complaint.status.startswith("filed"):
                row["filed"] += 1
            if complaint.status.startswith("escalated_"):
                row["filed"] += 1
                row["escalated"] += 1
        return sorted(rows.values(), key=lambda r: r["complaints"], reverse=True)

    @app.get("/public/activity")
    def activity(limit: int = 200) -> list[dict[str, Any]]:
        runs = sorted(get_store().agent_runs.values(), key=lambda r: r.started_at, reverse=True)
        events: list[dict[str, Any]] = []
        for run in runs:
            for event in run.events:
                events.append({"run_id": run.run_id, "city": run.city, **event})
        return events[:limit]

    @app.get("/public/map")
    def map_data() -> dict[str, Any]:
        store = get_store()
        reports = [
            {
                "report_id": r.report_id,
                "category": r.category,
                "lat": r.lat,
                "lon": r.lon,
                "status": r.status,
                "severity": r.severity,
            }
            for r in store.reports.values()
        ]
        complaints = [
            {
                "complaint_id": c.complaint_id,
                "lat": (c.draft_payload or {}).get("lat"),
                "lon": (c.draft_payload or {}).get("lon"),
                "status": c.status,
                "category": (c.draft_payload or {}).get("category"),
            }
            for c in store.complaints.values()
        ]
        return {"reports": reports, "complaints": complaints}

    # --- admin/ops ---------------------------------------------------------------------

    @app.post("/admin/nightly")
    def run_nightly() -> dict[str, Any]:
        return run_nightly_cycle()

    @app.post("/admin/chase")
    def chase() -> dict[str, Any]:
        return run_chase()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
