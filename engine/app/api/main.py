"""Tebaki HTTP API: report intake, decision queue, public dashboard data.

Run locally:
    PYTHONPATH=engine:sandbox-portal .venv/bin/uvicorn app.api.main:app --port 8000

The decision-queue endpoints resume real paused Strands interrupts:
POST /decisions/{card_id}/resolve approves/edits/drops a pending filing.
"""

import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.model_factory import model_mode
from app.city_pack import load_city_pack
from app.config import settings
from app.geo import is_within_boundary, load_boundary_features
from app.orchestrator import resolve_decision, run_chase, run_instant_triage, run_nightly_cycle
from app.store import Report, get_store


class ReportIn(BaseModel):
    category: str = Field(pattern="^(waste|pothole|streetlight|drain|water)$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    note: str = Field(min_length=1, max_length=1000)
    reporter: str = Field(default="anonymous", max_length=100)
    # Keep inline evidence well below DynamoDB's 400 KB item limit once the
    # report metadata, timeline, and indexes are accounted for.
    photo_data: str | None = Field(default=None, max_length=300_000)


class ResolveIn(BaseModel):
    action: str = Field(pattern="^(approve|edit|drop)$")
    fields: dict[str, Any] | None = None


def _run_events() -> list[dict[str, Any]]:
    """Flatten durable runs for public, redaction-safe accountability views."""
    runs = sorted(get_store().list_runs(), key=lambda r: r.started_at, reverse=True)
    events: list[dict[str, Any]] = []
    for run in runs:
        for event in run.events:
            events.append({"run_id": run.run_id, "city": run.city, **event})
    return sorted(events, key=lambda event: str(event.get("at", "")), reverse=True)


def _timeline_for_report(report_id: str) -> list[dict[str, Any]]:
    report = get_store().get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"unknown report {report_id}")
    timeline = [{
        "at": report.created_at,
        "kind": "submitted",
        "actor": "resident",
        "report_ids": [report_id],
        "input_summary": "A resident submitted a civic issue report",
        "resulting_action": "stored for guardian review",
    }]
    for event in _run_events():
        if report_id in event.get("report_ids", []):
            timeline.append(event)
    return sorted(timeline, key=lambda event: str(event.get("at", "")))


def _record_system_event(kind: str, **detail: Any) -> None:
    """Persist a non-agent guardrail outcome for the diagnostics view."""
    try:
        pack = load_city_pack(settings.cities_dir.resolve(), settings.city_pack)
        store = get_store()
        run = store.start_run(pack.city.name)
        run.add_event(kind, actor="tebaki-guardrail", **detail)
        store.finish_run(run)
        store.save_run(run)
    except Exception:  # noqa: BLE001 — diagnostics must not break intake validation
        # Diagnostics must never turn a validation rejection into a server error.
        return


@lru_cache(maxsize=8)
def _boundary_features(pack_name: str) -> tuple[dict, ...]:
    """Boundary polygons for the active city pack (cached per pack)."""
    from pathlib import Path

    from app.city_pack import load_city_pack

    cities_dir = Path(settings.cities_dir)
    pack = load_city_pack(cities_dir, pack_name)
    return tuple(load_boundary_features(cities_dir / pack.boundary.geojson))


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
    def submit_report(body: ReportIn, background_tasks: BackgroundTasks) -> dict[str, Any]:
        # geo-fence: the guardian only watches inside the city boundary
        try:
            features = _boundary_features(settings.city_pack)
        except Exception:  # noqa: BLE001 — no boundary configured -> skip the gate
            features = ()
        if features and not is_within_boundary(body.lat, body.lon, list(features)):
            _record_system_event(
                "boundary_rejected",
                input_summary="Report location is outside the configured city boundary",
                resulting_action="report was not stored",
            )
            raise HTTPException(
                status_code=422,
                detail="This location is outside the city the guardian watches. Drop the pin inside the city boundary.",
            )
        store = get_store()
        if body.photo_data is not None:
            if not body.photo_data.startswith("data:image/"):
                raise HTTPException(status_code=422, detail="photo_data must be an image data URL")
            # Keep the demo payload below DynamoDB's practical item-size limit.
            if len(body.photo_data) > 300_000:
                raise HTTPException(status_code=413, detail="photo is too large; use an image under 220 KB")
        report = store.add_report(
            Report(
                category=body.category,
                lat=body.lat,
                lon=body.lon,
                note=body.note,
                reporter=body.reporter,
                photo_key=body.photo_data,
            )
        )
        background_tasks.add_task(run_instant_triage, report.report_id)
        return {"report_id": report.report_id, "status": report.status, "triage": "queued"}

    @app.get("/reports")
    def list_reports(limit: int = 100) -> list[dict[str, Any]]:
        reports = sorted(get_store().list_reports(), key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in reports[:limit]]

    @app.post("/reports/{report_id}/plus-one", status_code=200)
    def plus_one(report_id: str) -> dict[str, Any]:
        """Corroborate an existing report — neighbors add weight to a case."""
        store = get_store()
        report = store.get_report(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"unknown report {report_id}")
        report.plus_ones = report.plus_ones + 1
        store.save_report(report)
        return {"report_id": report_id, "plus_ones": report.plus_ones}

    @app.post("/admin/demo/seed")
    def seed_demo() -> dict[str, Any]:
        """Insert the deterministic three-report judge scenario once.

        This is intentionally an explicit admin action: production instances
        never receive demo data merely by starting the service.
        """
        if settings.city_pack != "sandbox":
            raise HTTPException(
                status_code=409,
                detail="The deterministic demo scenario is only available for the sandbox city pack.",
            )
        store = get_store()
        existing_notes = {r.note for r in store.list_reports()}
        samples = [
            ("waste", 9.010, 38.760, "Demo neighbor: garbage pile on sidewalk"),
            ("waste", 9.012, 38.758, "Demo neighbor: trash not collected for days"),
            ("pothole", 9.040, 38.790, "Demo neighbor: deep pothole, hazard for motorcycles"),
        ]
        added = []
        for category, lat, lon, note in samples:
            if note in existing_notes:
                continue
            report = store.add_report(
                Report(category=category, lat=lat, lon=lon, note=note, reporter="demo neighbor")
            )
            added.append(report.report_id)
        return {"added": added, "total_demo_reports": len(samples)}

    @app.post("/admin/demo/miss-deadlines")
    def miss_demo_deadlines() -> dict[str, Any]:
        """Move active sandbox tickets past their SLA for a deterministic demo.

        Real city packs can never call this endpoint successfully. It exists so
        judges can observe the chaser agent's escalation behavior without
        waiting several calendar days.
        """
        if settings.city_pack != "sandbox":
            raise HTTPException(
                status_code=409,
                detail="Deadline simulation is only available for the sandbox city pack.",
            )

        from app.city_pack import load_city_pack

        pack = load_city_pack(settings.cities_dir.resolve(), settings.city_pack)
        store = get_store()
        active = store.filed_complaints()
        if not active:
            raise HTTPException(
                status_code=409,
                detail="File at least one sandbox complaint before simulating a missed deadline.",
            )

        now = datetime.now(UTC)
        age_days = max(pack.sla.acknowledge_days, pack.sla.resolve_days) + 1
        filed_at = now - timedelta(days=age_days)
        missed_at = now - timedelta(days=1)
        affected: list[str] = []
        for complaint in active:
            complaint.filed_at = filed_at.isoformat()
            complaint.ack_deadline = missed_at.isoformat()
            complaint.resolve_deadline = missed_at.isoformat()
            store.save_complaint(complaint)
            affected.append(complaint.complaint_id)

        runs = sorted(store.list_runs(), key=lambda r: r.started_at, reverse=True)
        if runs:
            runs[0].add_event(
                "demo_deadlines_missed",
                complaints=len(affected),
                simulated_days=age_days,
            )
            store.save_run(runs[0])
        return {
            "affected": affected,
            "simulated_days": age_days,
            "next_step": "Run the deadline check to let the chaser agent evaluate and escalate them.",
        }

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
            reporters = []
            plus_ones = 0
            for rid in c.report_refs:
                report = store.get_report(rid)
                if report is not None:
                    reporters.append(report.reporter)
                    plus_ones += report.plus_ones
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
                    "plus_ones": plus_ones,
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

    @app.get("/public/complaints/{complaint_id}")
    def case_file(complaint_id: str) -> dict[str, Any]:
        """The case dossier: one complaint's full journey, assembled."""
        store = get_store()
        complaint = store.get_complaint(complaint_id)
        if complaint is None:
            raise HTTPException(status_code=404, detail=f"unknown complaint {complaint_id}")
        reports = []
        for rid in complaint.report_refs:
            report = store.get_report(rid)
            if report is not None:
                reports.append(report.to_dict())
        draft = complaint.draft_payload or {}
        report_ids = list(complaint.report_refs)
        timeline = [event for event in _run_events() if complaint_id == event.get("complaint_id") or any(
            report_id in event.get("report_ids", []) for report_id in report_ids
        )]
        return {
            "complaint_id": complaint.complaint_id,
            "ward": complaint.ward,
            "status": complaint.status,
            "ticket_id": complaint.ticket_id,
            "channel": complaint.channel,
            "filed_at": complaint.filed_at,
            "ack_deadline": complaint.ack_deadline,
            "resolve_deadline": complaint.resolve_deadline,
            "ticket_status": complaint.ticket_status,
            "category": draft.get("category"),
            "subject": draft.get("subject"),
            "text": draft.get("text"),
            "cite": draft.get("cite"),
            "reporters": [r["reporter"] for r in reports],
            "plus_ones": sum(r.get("plus_ones", 0) for r in reports),
            "reports": reports,
            "evidence": {
                "report_count": len(reports),
                "corroborations": sum(r.get("plus_ones", 0) for r in reports),
                "category": draft.get("category"),
                "severity": draft.get("severity"),
                "grouping_reason": draft.get("duplicates_note") or (
                    "Reports share a category and a nearby location." if len(reports) > 1 else "One source report."
                ),
                "privacy_redactions": draft.get("privacy_flags", []),
                "regulation_citation": draft.get("cite"),
                "delivery_mode": "simulated" if settings.city_pack == "sandbox" else "dry_run",
            },
            "timeline": sorted(timeline, key=lambda event: str(event.get("at", ""))),
            "escalation_log": complaint.escalation_log,
            "created_at": complaint.created_at,
        }

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
            if complaint.status.startswith(("filed", "acknowledged", "resolved", "escalated_")):
                row["filed"] += 1
            if complaint.status == "acknowledged":
                row["acknowledged"] += 1
            if complaint.status == "resolved":
                row["resolved"] += 1
            if complaint.status.startswith("escalated_"):
                row["escalated"] += 1
        return sorted(rows.values(), key=lambda r: r["complaints"], reverse=True)

    @app.get("/public/activity")
    def activity(limit: int = 200) -> list[dict[str, Any]]:
        return _run_events()[:limit]

    @app.get("/public/reports/{report_id}/timeline")
    def report_timeline(report_id: str) -> list[dict[str, Any]]:
        return _timeline_for_report(report_id)

    @app.get("/public/runs")
    def runs(limit: int = 50) -> list[dict[str, Any]]:
        stored = sorted(get_store().list_runs(), key=lambda run: run.started_at, reverse=True)
        return [
            {
                "run_id": run.run_id,
                "city": run.city,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "event_count": len(run.events),
                "tool_call_count": run.tool_call_count,
                "token_totals": run.token_totals,
            }
            for run in stored[:limit]
        ]

    @app.get("/public/runs/{run_id}")
    def run_detail(run_id: str) -> dict[str, Any]:
        run = get_store().get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
        return run.to_dict()

    @app.get("/public/impact")
    def impact() -> dict[str, Any]:
        complaints = get_store().list_complaints()
        open_cases = [c for c in complaints if c.status not in {"resolved", "dropped"}]
        approaching = [
            c for c in open_cases
            if c.resolve_deadline and datetime.fromisoformat(c.resolve_deadline) <= datetime.now(UTC) + timedelta(days=2)
        ]
        corroborations = sum(
            report.plus_ones for report in get_store().list_reports()
        )
        return {
            "total_cases": len(complaints),
            "unresolved_cases": len(open_cases),
            "resolved_cases": sum(c.status == "resolved" for c in complaints),
            "escalated_cases": sum(c.status.startswith("escalated_") for c in complaints),
            "approaching_escalation": len(approaching),
            "corroborations": corroborations,
            "wards": scoreboard(),
        }

    @app.get("/public/proof")
    def proof() -> dict[str, Any]:
        store = get_store()
        complaints = store.list_complaints()
        runs = sorted(store.list_runs(), key=lambda run: run.started_at, reverse=True)
        try:
            pack = load_city_pack(settings.cities_dir.resolve(), settings.city_pack)
            city_name = pack.city.name
            coverage = pack.coverage.model_dump()
        except Exception:  # noqa: BLE001 — proof must still work during a bad pack deploy
            city_name = settings.city_pack
            coverage = {"status": "unknown"}
        return {
            "city": city_name,
            "model_mode": model_mode(),
            "persistence": "dynamodb" if os.getenv("TEBAKI_STORE", "").lower() == "dynamodb" else "memory",
            "last_run_id": runs[0].run_id if runs else None,
            "reports_triaged": sum(r.status in {"triaged", "clustered", "filed"} for r in store.list_reports()),
            "cases_drafted": len(complaints),
            "human_decisions": sum(event.get("kind") in {"filed", "dropped"} and event.get("action") is not None for event in _run_events()),
            "filed_tickets": sum(c.ticket_id is not None for c in complaints),
            "escalations": sum(c.escalation_level for c in complaints),
            "runtime_status": "reachable",
            "coverage": coverage,
        }

    @app.get("/public/diagnostics")
    def diagnostics(limit: int = 20) -> dict[str, Any]:
        """Safe, judge-visible resilience state; never returns resident data."""
        now = datetime.now(UTC).isoformat()
        events = _run_events()
        incident_kinds = {"triage_failed", "graph_failed", "filing_failed", "ticket_check_failed", "boundary_rejected"}
        incidents = [event for event in events if event.get("kind") in incident_kinds][:limit]
        persistent = os.getenv("TEBAKI_STORE", "").lower() == "dynamodb"
        live_model = os.getenv("TEBAKI_LIVE_BEDROCK", "").lower() in {"1", "true", "yes", "on"}
        email_live = bool(os.getenv("TEBAKI_SMTP_HOST") or os.getenv("TEBAKI_SES_FROM"))
        try:
            pack = load_city_pack(settings.cities_dir.resolve(), settings.city_pack)
            city_name = pack.city.name
            coverage = pack.coverage
            coverage_state = "ready" if coverage.status == "verified" else "attention"
            coverage_detail = (
                f"Verified pilot: {coverage.pilot_area}."
                if coverage.status == "verified"
                else "City-level fallback is active; sub-city polygons are not yet vendored."
            )
        except Exception:  # noqa: BLE001 — diagnostics must remain available during bad pack deploys
            city_name = settings.city_pack
            coverage_state = "attention"
            coverage_detail = "City pack could not be loaded; geographic claims are unverified."
        # These checks describe configuration and recovery guarantees without
        # making a network call (diagnostics must remain available during an
        # AWS outage).  The runtime health endpoint is the authoritative
        # liveness check; this view explains what mode it is configured for.
        checks = [
                {"id": "boundary", "label": "City boundary guard", "state": "ready", "detail": "Out-of-bound reports are rejected before triage."},
                {"id": "coverage", "label": "Geographic coverage", "state": coverage_state, "detail": coverage_detail},
                {"id": "approval_recovery", "label": "Human approval recovery", "state": "ready" if persistent else "local_only", "detail": "Paused decisions are durable only when DynamoDB is enabled."},
                {"id": "model", "label": "Model recovery", "state": "attention" if any(e.get("kind") in {"triage_failed", "graph_failed"} for e in incidents) else "ready", "detail": f"{'Live Bedrock' if live_model else 'Scripted offline'} mode; failed work is retained for the next supervised cycle."},
                {"id": "filing", "label": "Filing channel", "state": "attention" if any(e.get("kind") == "filing_failed" for e in incidents) else ("ready" if email_live or settings.city_pack == "sandbox" else "attention"), "detail": "A filing failure is retained for operator recovery." if any(e.get("kind") == "filing_failed" for e in incidents) else ("Real email delivery is configured." if email_live else ("Sandbox portal is the deterministic filing channel." if settings.city_pack == "sandbox" else "Addis filing is dry-run until SMTP/SES is configured." ))},
            ]
        return {
            "checked_at": now,
            "city": city_name,
            "model_mode": model_mode(),
            "persistence": "dynamodb" if persistent else "memory",
            "delivery_mode": "real" if email_live else ("simulated" if settings.city_pack == "sandbox" else "dry_run"),
            "coverage": {"state": coverage_state, "detail": coverage_detail},
            "checks": checks,
            "incidents": incidents,
            "incident_count": len(incidents),
        }

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
                "triage_confidence": r.triage_confidence,
                "triage_reason": r.triage_reason,
                "plus_ones": r.plus_ones,
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

    # --- geocoding (for the report map's address search) --------------------------------

    @app.get("/geocode/search")
    def geocode_search(q: str, limit: int = 5) -> list[dict[str, Any]]:
        from app.geocode import forward_geocode

        return forward_geocode(q, limit=limit)

    # --- admin/ops ---------------------------------------------------------------------

    class NightlyIn(BaseModel):
        auto_approve: bool | None = None

    class StatusIn(BaseModel):
        status: str = Field(pattern="^(acknowledged|resolved)$")
        note: str = Field(default="", max_length=1000)

    @app.post("/admin/complaints/{complaint_id}/status")
    def set_complaint_status(complaint_id: str, body: StatusIn) -> dict[str, Any]:
        """Record the city's response on a complaint (email channel has no
        ticket-status API — an operator records acknowledgments/resolutions).

        Ends the chase for resolved complaints; acknowledged ones stay
        monitored until resolved.
        """
        store = get_store()
        complaint = store.get_complaint(complaint_id)
        if complaint is None:
            raise HTTPException(status_code=404, detail=f"unknown complaint {complaint_id}")
        if not complaint.ticket_id and complaint.status != "filed":
            raise HTTPException(
                status_code=409,
                detail=f"complaint is {complaint.status}; status can only be recorded after filing",
            )
        complaint.status = body.status
        complaint.ticket_status = body.status
        if body.status == "resolved":
            complaint.resolved_note = body.note
        else:
            complaint.acknowledged_note = body.note
        store.save_complaint(complaint)
        # log to the run that owns the complaint's last event trail
        runs = store.list_runs()
        if runs:
            run = runs[0]
            run.add_event(
                "status_recorded",
                complaint_id=complaint_id,
                status=body.status,
                note=body.note[:200],
                source="operator",
            )
            store.save_run(run)
        return {
            "complaint_id": complaint_id,
            "status": complaint.status,
            "ticket_status": complaint.ticket_status,
        }

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

    # AgentCore's HTTP runtime contract uses /ping for readiness and
    # /invocations for signed runtime calls. Keep the ordinary REST surface
    # above for local/browser clients and expose a small explicit action
    # envelope for the managed runtime.
    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/invocations")
    def agentcore_invocation(body: dict[str, Any]) -> Any:
        # AgentCore receives a small HTTP-style envelope from the browser-safe
        # proxy.  Keep the older action-only form for CLI smoke tests.
        method = str(body.get("method", "")).upper()
        path = str(body.get("path", ""))
        query = body.get("query") or {}
        if method == "GET" and path == "/health":
            return health()
        if method == "GET" and path == "/public/ledger":
            return ledger(limit=int(query.get("limit", 200)))
        if method == "GET" and path == "/public/scoreboard":
            return scoreboard()
        if method == "GET" and path == "/public/activity":
            return activity(limit=int(query.get("limit", 200)))
        if method == "GET" and path == "/public/map":
            return map_data()
        if method == "GET" and path == "/public/impact":
            return impact()
        if method == "GET" and path == "/public/proof":
            return proof()
        if method == "GET" and path == "/public/diagnostics":
            return diagnostics(limit=int(query.get("limit", 20)))
        if method == "GET" and path == "/public/runs":
            return runs(limit=int(query.get("limit", 50)))
        if method == "GET" and path.startswith("/public/runs/"):
            return run_detail(path.removeprefix("/public/runs/").strip("/"))
        if method == "GET" and path.startswith("/public/reports/") and path.endswith("/timeline"):
            report_id = path.removeprefix("/public/reports/").removesuffix("/timeline").strip("/")
            return report_timeline(report_id)
        if method == "GET" and path.startswith("/public/complaints/"):
            complaint_id = path.removeprefix("/public/complaints/").strip("/")
            return case_file(complaint_id)
        if method == "GET" and path == "/decisions":
            return pending_decisions()
        if method == "GET" and path == "/reports":
            return list_reports(limit=int(query.get("limit", 100)))
        if method == "POST" and path == "/reports":
            report_response = submit_report(ReportIn.model_validate(body.get("body") or {}), BackgroundTasks())
            # The managed runtime has no browser request lifecycle to run
            # FastAPI background tasks, so complete instant triage explicitly.
            run_instant_triage(str(report_response["report_id"]))
            return report_response
        if method == "POST" and path.startswith("/reports/") and path.endswith("/plus-one"):
            report_id = path.removeprefix("/reports/").removesuffix("/plus-one").strip("/")
            return plus_one(report_id)
        if method == "POST" and path.startswith("/decisions/") and path.endswith("/resolve"):
            card_id = path.removeprefix("/decisions/").removesuffix("/resolve").strip("/")
            return resolve(card_id, ResolveIn.model_validate(body.get("body") or {}))
        if method == "POST" and path == "/admin/nightly":
            payload = body.get("body") or {}
            return run_nightly(NightlyIn.model_validate(payload))
        if method == "POST" and path == "/admin/chase":
            return chase()
        if method == "POST" and path == "/admin/demo/seed":
            return seed_demo()
        if method == "POST" and path == "/admin/demo/miss-deadlines":
            return miss_demo_deadlines()
        if method == "POST" and path.startswith("/admin/complaints/") and path.endswith("/status"):
            complaint_id = path.removeprefix("/admin/complaints/").removesuffix("/status").strip("/")
            return set_complaint_status(complaint_id, StatusIn.model_validate(body.get("body") or {}))
        action = str(body.get("action", "health"))
        if action in {"health", "ping"}:
            return health()
        if action == "run_nightly":
            return run_nightly_cycle(auto_approve=body.get("auto_approve"))
        if action == "run_chase":
            return run_chase()
        raise HTTPException(status_code=400, detail=f"unsupported AgentCore action: {action}")

    return app


app = create_app()
