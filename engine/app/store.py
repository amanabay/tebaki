"""In-memory run store for Day 1 development.

Interface mirrors the future DynamoDB-backed store: reports, complaints,
decision cards, and agent-run logs. The orchestrator only talks to this
interface, so swapping in DynamoDB (Day 3+) is a drop-in change.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

# --- models -------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Report:
    def __init__(
        self,
        *,
        report_id: str | None = None,
        reporter: str = "anonymous",
        category: str = "waste",
        lat: float = 0.0,
        lon: float = 0.0,
        note: str = "",
        photo_key: str | None = None,
        status: str = "new",
        severity: int = 3,
        language: str = "en",
    ) -> None:
        self.report_id = report_id or f"R-{uuid4().hex[:8].upper()}"
        self.reporter = reporter
        self.category = category
        self.lat = lat
        self.lon = lon
        self.note = note
        self.photo_key = photo_key
        self.status = status  # new | triaged | rejected | filed
        self.severity = severity
        self.language = language
        self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "reporter": self.reporter,
            "category": self.category,
            "lat": self.lat,
            "lon": self.lon,
            "note": self.note,
            "photo_key": self.photo_key,
            "status": self.status,
            "severity": self.severity,
            "language": self.language,
            "created_at": self.created_at,
        }


class DecisionCard:
    def __init__(
        self,
        *,
        card_id: str | None = None,
        complaint_draft: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        self.card_id = card_id or f"D-{uuid4().hex[:8].upper()}"
        self.complaint_draft = complaint_draft
        self.context = context or {}
        self.status = "pending"  # pending | approved | edited | dropped
        self.response: dict[str, Any] | None = None
        self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "complaint_draft": self.complaint_draft,
            "context": self.context,
            "status": self.status,
            "response": self.response,
            "created_at": self.created_at,
        }


class Complaint:
    def __init__(
        self,
        *,
        complaint_id: str | None = None,
        report_refs: list[str] | None = None,
        ward: str = "",
        draft_text: str = "",
        status: str = "awaiting_approval",
        ticket_id: str | None = None,
        channel: str = "",
        draft_payload: dict[str, Any] | None = None,
        filed_at: str | None = None,
        escalation_level: int = 0,
        ticket_status: str | None = None,
        last_chased_at: str | None = None,
    ) -> None:
        self.complaint_id = complaint_id or f"C-{uuid4().hex[:8].upper()}"
        self.report_refs = report_refs or []
        self.ward = ward
        self.draft_text = draft_text
        self.status = status
        # draft -> awaiting_approval -> filed -> acknowledged -> resolved -> escalated_N
        # (or dropped / filing_failed)
        self.ticket_id = ticket_id
        self.channel = channel
        self.draft_payload = draft_payload
        self.filed_at = filed_at
        self.ack_deadline: str | None = None
        self.resolve_deadline: str | None = None
        self.escalation_level = escalation_level
        self.ticket_status = ticket_status
        self.last_chased_at = last_chased_at
        self.created_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "complaint_id": self.complaint_id,
            "report_refs": self.report_refs,
            "ward": self.ward,
            "draft_text": self.draft_text,
            "status": self.status,
            "ticket_id": self.ticket_id,
            "channel": self.channel,
            "filed_at": self.filed_at,
            "ack_deadline": self.ack_deadline,
            "resolve_deadline": self.resolve_deadline,
            "escalation_level": self.escalation_level,
            "ticket_status": self.ticket_status,
            "last_chased_at": self.last_chased_at,
            "created_at": self.created_at,
        }


class AgentRun:
    def __init__(self, city: str) -> None:
        self.run_id = f"RUN-{uuid4().hex[:8].upper()}"
        self.city = city
        self.started_at = _now()
        self.finished_at: str | None = None
        self.events: list[dict[str, Any]] = []
        self.token_totals: dict[str, int] = {"input": 0, "output": 0}
        self.tool_call_count = 0

    def add_event(self, kind: str, **detail: Any) -> None:
        self.events.append({"at": _now(), "kind": kind, **detail})

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "city": self.city,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "events": self.events,
            "token_totals": self.token_totals,
            "tool_call_count": self.tool_call_count,
        }


# --- store ----------------------------------------------------------------------


class RunStore:
    """In-memory implementation; DynamoDB-backed store implements the same surface."""

    def __init__(self) -> None:
        self.reports: dict[str, Report] = {}
        self.complaints: dict[str, Complaint] = {}
        self.decision_cards: dict[str, DecisionCard] = {}
        self.agent_runs: dict[str, AgentRun] = {}

    # reports
    def add_report(self, report: Report) -> Report:
        self.reports[report.report_id] = report
        return report

    def new_reports(self) -> list[Report]:
        return [r for r in self.reports.values() if r.status == "new"]

    def update_report_status(self, report_id: str, status: str) -> None:
        self.reports[report_id].status = status

    # complaints
    def add_complaint(self, complaint: Complaint) -> Complaint:
        self.complaints[complaint.complaint_id] = complaint
        return complaint

    def filed_complaints(self) -> list[Complaint]:
        return [c for c in self.complaints.values() if c.status == "filed"]

    # decision cards
    def add_decision_card(self, card: DecisionCard) -> DecisionCard:
        self.decision_cards[card.card_id] = card
        return card

    def pending_cards(self) -> list[DecisionCard]:
        return [c for c in self.decision_cards.values() if c.status == "pending"]

    def resolve_card(self, card_id: str, resolution: str, response: dict[str, Any] | None = None) -> DecisionCard:
        card = self.decision_cards[card_id]
        if card.status != "pending":
            raise ValueError(f"card {card_id} already resolved ({card.status})")
        if resolution not in {"approved", "edited", "dropped"}:
            raise ValueError(f"invalid resolution {resolution!r}: approved|edited|dropped")
        card.status = resolution
        card.response = response
        return card

    # agent runs
    def start_run(self, city: str) -> AgentRun:
        run = AgentRun(city)
        self.agent_runs[run.run_id] = run
        return run

    def finish_run(self, run: AgentRun) -> None:
        run.finished_at = _now()


_store: RunStore | None = None


def get_store() -> RunStore:
    global _store
    if _store is None:
        _store = RunStore()
    return _store
