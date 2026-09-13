"""Run store: in-memory implementation + interface contract.

The store persists four entities: reports, complaints, decision cards,
and agent-run logs. RunStore is the in-memory implementation used for
offline dev and tests; DynamoDBStore (app.dynamodb_store) implements the
same surface for deployed/persistent use — selected via TEBAKI_STORE=dynamodb.

Interface contract (both implementations):
  reports:     add_report, get_report, list_reports, new_reports,
               update_report_status, save_report
  complaints:  add_complaint, get_complaint, list_complaints,
               filed_complaints, save_complaint
  cards:       add_decision_card, get_card, pending_cards, resolve_card, save_card
  runs:        start_run, get_run, list_runs, finish_run

Mutation rule: mutate a fetched object, then call its save_* method.
"""

import os
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
        triage_confidence: float | None = None,
        triage_reason: str | None = None,
        plus_ones: int = 0,
        created_at: str | None = None,
    ) -> None:
        self.report_id = report_id or f"R-{uuid4().hex[:8].upper()}"
        self.reporter = reporter
        self.category = category
        self.lat = lat
        self.lon = lon
        self.note = note
        self.photo_key = photo_key
        self.status = status  # new | triaged | clustered | rejected | filed
        self.severity = severity
        self.language = language
        self.triage_confidence = triage_confidence
        self.triage_reason = triage_reason
        self.plus_ones = plus_ones  # neighbor corroborations
        self.created_at = created_at or _now()

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
            "triage_confidence": self.triage_confidence,
            "triage_reason": self.triage_reason,
            "plus_ones": self.plus_ones,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Report":
        return cls(
            report_id=data["report_id"],
            reporter=data.get("reporter", "anonymous"),
            category=data.get("category", "waste"),
            lat=float(data.get("lat", 0.0)),
            lon=float(data.get("lon", 0.0)),
            note=data.get("note", ""),
            photo_key=data.get("photo_key"),
            status=data.get("status", "new"),
            severity=int(data.get("severity", 3)),
            language=data.get("language", "en"),
            triage_confidence=(float(data["triage_confidence"]) if data.get("triage_confidence") is not None else None),
            triage_reason=data.get("triage_reason"),
            plus_ones=int(data.get("plus_ones", 0)),
            created_at=data.get("created_at"),
        )


class DecisionCard:
    def __init__(
        self,
        *,
        card_id: str | None = None,
        complaint_draft: dict[str, Any],
        context: dict[str, Any] | None = None,
        status: str = "pending",
        response: dict[str, Any] | None = None,
        paused_state: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> None:
        self.card_id = card_id or f"D-{uuid4().hex[:8].upper()}"
        self.complaint_draft = complaint_draft
        self.context = context or {}
        self.status = status  # pending | approved | edited | dropped
        self.response = response
        # Serialized SDK snapshot of the paused filer agent (messages +
        # interrupt state + model state) — lets a restarted engine resume
        # the human-in-the-loop filing instead of stranding the card.
        self.paused_state = paused_state
        self.created_at = created_at or _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "complaint_draft": self.complaint_draft,
            "context": self.context,
            "status": self.status,
            "response": self.response,
            "paused_state": self.paused_state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionCard":
        return cls(
            card_id=data["card_id"],
            complaint_draft=data.get("complaint_draft", {}),
            context=data.get("context"),
            status=data.get("status", "pending"),
            response=data.get("response"),
            paused_state=data.get("paused_state"),
            created_at=data.get("created_at"),
        )


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
        ack_deadline: str | None = None,
        resolve_deadline: str | None = None,
        escalation_level: int = 0,
        ticket_status: str | None = None,
        last_chased_at: str | None = None,
        escalation_log: list[dict[str, Any]] | None = None,
        acknowledged_note: str | None = None,
        resolved_note: str | None = None,
        owner_name: str | None = None,
        owner_role: str | None = None,
        next_action: str | None = None,
        next_action_due: str | None = None,
        community_status: str = "needs_attention",
        support_count: int = 0,
        community_updates: list[dict[str, Any]] | None = None,
        evidence_score: float | None = None,
        verification_state: str = "unverified",
        verification_flags: list[str] | None = None,
        verified_at: str | None = None,
        coordinator_recommendation: str | None = None,
        coordinator_reason: str | None = None,
        coordinator_due: str | None = None,
        created_at: str | None = None,
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
        self.ack_deadline = ack_deadline
        self.resolve_deadline = resolve_deadline
        self.escalation_level = escalation_level
        self.ticket_status = ticket_status
        self.last_chased_at = last_chased_at
        self.escalation_log = escalation_log or []
        self.acknowledged_note = acknowledged_note
        self.resolved_note = resolved_note
        self.owner_name = owner_name
        self.owner_role = owner_role
        self.next_action = next_action
        self.next_action_due = next_action_due
        self.community_status = community_status
        self.support_count = support_count
        self.community_updates = community_updates or []
        self.evidence_score = evidence_score
        self.verification_state = verification_state
        self.verification_flags = verification_flags or []
        self.verified_at = verified_at
        self.coordinator_recommendation = coordinator_recommendation
        self.coordinator_reason = coordinator_reason
        self.coordinator_due = coordinator_due
        self.created_at = created_at or _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "complaint_id": self.complaint_id,
            "report_refs": self.report_refs,
            "ward": self.ward,
            "draft_text": self.draft_text,
            "status": self.status,
            "ticket_id": self.ticket_id,
            "channel": self.channel,
            "draft_payload": self.draft_payload,
            "filed_at": self.filed_at,
            "ack_deadline": self.ack_deadline,
            "resolve_deadline": self.resolve_deadline,
            "escalation_level": self.escalation_level,
            "ticket_status": self.ticket_status,
            "last_chased_at": self.last_chased_at,
            "escalation_log": self.escalation_log,
            "acknowledged_note": self.acknowledged_note,
            "resolved_note": self.resolved_note,
            "owner_name": self.owner_name,
            "owner_role": self.owner_role,
            "next_action": self.next_action,
            "next_action_due": self.next_action_due,
            "community_status": self.community_status,
            "support_count": self.support_count,
            "community_updates": self.community_updates,
            "evidence_score": self.evidence_score,
            "verification_state": self.verification_state,
            "verification_flags": self.verification_flags,
            "verified_at": self.verified_at,
            "coordinator_recommendation": self.coordinator_recommendation,
            "coordinator_reason": self.coordinator_reason,
            "coordinator_due": self.coordinator_due,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Complaint":
        return cls(
            complaint_id=data["complaint_id"],
            report_refs=data.get("report_refs", []),
            ward=data.get("ward", ""),
            draft_text=data.get("draft_text", ""),
            status=data.get("status", "awaiting_approval"),
            ticket_id=data.get("ticket_id"),
            channel=data.get("channel", ""),
            draft_payload=data.get("draft_payload"),
            filed_at=data.get("filed_at"),
            ack_deadline=data.get("ack_deadline"),
            resolve_deadline=data.get("resolve_deadline"),
            escalation_level=int(data.get("escalation_level", 0)),
            ticket_status=data.get("ticket_status"),
            last_chased_at=data.get("last_chased_at"),
            escalation_log=data.get("escalation_log", []),
            acknowledged_note=data.get("acknowledged_note"),
            resolved_note=data.get("resolved_note"),
            owner_name=data.get("owner_name"),
            owner_role=data.get("owner_role"),
            next_action=data.get("next_action"),
            next_action_due=data.get("next_action_due"),
            community_status=data.get("community_status", "needs_attention"),
            support_count=int(data.get("support_count", 0)),
            community_updates=data.get("community_updates", []),
            evidence_score=(float(data["evidence_score"]) if data.get("evidence_score") is not None else None),
            verification_state=data.get("verification_state", "unverified"),
            verification_flags=data.get("verification_flags", []),
            verified_at=data.get("verified_at"),
            coordinator_recommendation=data.get("coordinator_recommendation"),
            coordinator_reason=data.get("coordinator_reason"),
            coordinator_due=data.get("coordinator_due"),
            created_at=data.get("created_at"),
        )


class AgentRun:
    def __init__(
        self,
        city: str,
        run_id: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        events: list[dict[str, Any]] | None = None,
        token_totals: dict[str, int] | None = None,
        tool_call_count: int = 0,
    ) -> None:
        self.run_id = run_id or f"RUN-{uuid4().hex[:8].upper()}"
        self.city = city
        self.started_at = started_at or _now()
        self.finished_at = finished_at
        self.events = events or []
        self.token_totals = token_totals or {"input": 0, "output": 0}
        self.tool_call_count = tool_call_count

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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRun":
        return cls(
            city=data["city"],
            run_id=data["run_id"],
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            events=data.get("events", []),
            token_totals=data.get("token_totals"),
            tool_call_count=int(data.get("tool_call_count", 0)),
        )


# --- store ----------------------------------------------------------------------


class RunStore:
    """In-memory implementation; DynamoDBStore implements the same surface."""

    def __init__(self) -> None:
        self.reports: dict[str, Report] = {}
        self.complaints: dict[str, Complaint] = {}
        self.decision_cards: dict[str, DecisionCard] = {}
        self.agent_runs: dict[str, AgentRun] = {}

    # reports
    def add_report(self, report: Report) -> Report:
        self.reports[report.report_id] = report
        return report

    def get_report(self, report_id: str) -> Report | None:
        return self.reports.get(report_id)

    def list_reports(self) -> list[Report]:
        return list(self.reports.values())

    def new_reports(self) -> list[Report]:
        return [r for r in self.reports.values() if r.status == "new"]

    def update_report_status(self, report_id: str, status: str) -> None:
        self.reports[report_id].status = status

    def save_report(self, report: Report) -> None:
        self.reports[report.report_id] = report

    # complaints
    def add_complaint(self, complaint: Complaint) -> Complaint:
        self.complaints[complaint.complaint_id] = complaint
        return complaint

    def get_complaint(self, complaint_id: str) -> Complaint | None:
        return self.complaints.get(complaint_id)

    def list_complaints(self) -> list[Complaint]:
        return list(self.complaints.values())

    def filed_complaints(self) -> list[Complaint]:
        """Complaints with a ticket in the active chase set (filed/acknowledged/escalated)."""
        return [
            c
            for c in self.complaints.values()
            if c.ticket_id and c.status.startswith(("filed", "acknowledged", "escalated"))
        ]

    def save_complaint(self, complaint: Complaint) -> None:
        self.complaints[complaint.complaint_id] = complaint

    # decision cards
    def add_decision_card(self, card: DecisionCard) -> DecisionCard:
        self.decision_cards[card.card_id] = card
        return card

    def get_card(self, card_id: str) -> DecisionCard | None:
        return self.decision_cards.get(card_id)

    def list_cards(self) -> list[DecisionCard]:
        return list(self.decision_cards.values())

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

    def save_card(self, card: DecisionCard) -> None:
        self.decision_cards[card.card_id] = card

    # agent runs
    def start_run(self, city: str) -> AgentRun:
        run = AgentRun(city)
        self.agent_runs[run.run_id] = run
        return run

    def get_run(self, run_id: str) -> AgentRun | None:
        return self.agent_runs.get(run_id)

    def list_runs(self) -> list[AgentRun]:
        return list(self.agent_runs.values())

    def save_run(self, run: AgentRun) -> None:
        self.agent_runs[run.run_id] = run

    def finish_run(self, run: AgentRun) -> None:
        run.finished_at = _now()


_store: RunStore | None = None


def get_store() -> RunStore:
    global _store
    if _store is None:
        if os.getenv("TEBAKI_STORE", "").lower() == "dynamodb":
            from app.dynamodb_store import DynamoDBStore

            _store = DynamoDBStore()
        else:
            _store = RunStore()
    return _store
