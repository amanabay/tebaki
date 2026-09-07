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
        reports = sorted(get_store().list_reports(), key=lambda r: r.created_at, reverse=True)
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
        store = get_store()
        complaints = sorted(store.list_complaints(), key=lambda c: c.created_at, reverse=True)
        rows = []
        for c in complaints[:limit]:
            reporters = [
                store.get_report(rid).reporter
                for rid in c.report_refs
                if store.get_report(rid) is not None
            ]
            rows.append(
                {
                    "complaint_id": c.complaint_id,
                    "ward": c.ward,
                    "status": c.status,
                    "ticket_id": c.ticket_id,
                    "channel": c.channel,
                    "escalation_level": c.escalation_level,
                    "filed_at": c.filed_at,
                    "ack_deadline": c.ack_deadline,
                    "resolve_deadline": c.resolve_deadline,
                    "ticket_status": c.ticket_status,
                    "category": (c.draft_payload or {}).get("category"),
                    "subject": (c.draft_payload or {}).get("subject"),
                    "report_refs": c.report_refs,
                    "reporters": reporters,
                    "escalation_log": [
                        {
                            "level": e.get("level"),
                            "target": e.get("target"),
                            "subject": e.get("subject"),
                            "at": e.get("at"),
                            "delivered": e.get("delivered"),
                        }
                        for e in c.escalation_log
                    ],
                    "created_at": c.created_at,
                }
            )
        return rows

    @app.get("/public/scoreboard")
    def scoreboard() -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for complaint in get_store().list_complaints():
            row = rows.setdefault(
                complaint.ward,
                {
                    "ward": complaint.ward,
                    "complaints": 0,
                    "filed": 0,
                    "resolved": 0,
                    "escalated": 0,
                    "acknowledged": 0,
                },
            )
            row["complaints"] += 1
            if complaint.status.startswith(("filed", "acknowledged", "escalated_")):
                row["filed"] += 1
            if complaint.status == "acknowledged":
                row["acknowledged"] += 1
            if complaint.status == "resolved":
                row["filed"] += 1
                row["resolved"] += 1
            if complaint.status.startswith("escalated_"):
                row["filed"] += 1
                row["escalated"] += 1
        return sorted(rows.values(), key=lambda r: r["complaints"], reverse=True)

    @app.get("/public/activity")
    def activity(limit: int = 200) -> list[dict[str, Any]]:
        runs = sorted(get_store().list_runs(), key=lambda r: r.started_at, reverse=True)
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
            for r in store.list_reports()
        ]
        complaints = [
            {
                "complaint_id": c.complaint_id,
                "lat": (c.draft_payload or {}).get("lat"),
                "lon": (c.draft_payload or {}).get("lon"),
                "status": c.status,
                "category": (c.draft_payload or {}).get("category"),
            }
            for c in store.list_complaints()
        ]
        return {"reports": reports, "complaints": complaints}

    # --- admin/ops ---------------------------------------------------------------------

    class NightlyIn(BaseModel):
        auto_approve: bool | None = None

    @app.post("/admin/nightly")
    def run_nightly(body: NightlyIn | None = None) -> dict[str, Any]:
        auto_approve = body.auto_approve if body else None
        return run_nightly_cycle(auto_approve=auto_approve)

    @app.post("/admin/chase")
    def chase() -> dict[str, Any]:
        return run_chase()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
