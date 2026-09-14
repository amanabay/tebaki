from app.agents.registry import set_filing_context
from app.agents.tools import coordinator_recommendation, file_complaint, verify_complaint_draft
from app.channels import EmailChannel
from app.store import Complaint, Report, RunStore


def _store_with_report() -> tuple[RunStore, Report]:
    store = RunStore()
    report = Report(
        category="waste",
        lat=9.03,
        lon=38.74,
        note="Overflowing bins block the footpath",
        reporter="resident",
    )
    store.add_report(report)
    return store, report


def test_evidence_gate_passes_provenance_and_privacy_safe_draft() -> None:
    store, report = _store_with_report()
    result = verify_complaint_draft(
        {
            "category": "waste",
            "severity": 3,
            "report_refs": [report.report_id],
            "lat": report.lat,
            "lon": report.lon,
            "ward": "Addis Ababa",
            "subject": "Waste issue near the footpath",
            "text": "One resident reports overflowing bins blocking the footpath.",
        },
        store,
    )
    assert result["verification_state"] == "passed"
    assert result["evidence_score"] == 1.0


def test_evidence_gate_flags_unknown_source_and_personal_data() -> None:
    store, report = _store_with_report()
    result = verify_complaint_draft(
        {
            "category": "waste",
            "severity": 9,
            "report_refs": [report.report_id, "R-missing"],
            "lat": report.lat,
            "lon": report.lon,
            "ward": "Addis Ababa",
            "subject": "Waste issue",
            "text": "Call me at +251 911 222 333 about this issue.",
        },
        store,
    )
    assert result["verification_state"] == "needs_review"
    assert "unknown source report (1)" in result["verification_flags"]
    assert "unredacted personal data" in result["verification_flags"]


def test_coordinator_prioritizes_connected_neighbors() -> None:
    _store, report = _store_with_report()
    complaint = Complaint(
        report_refs=[report.report_id],
        ward="Addis Ababa",
        draft_payload={"severity": 3, "resident_count": 2},
    )
    suggestion = coordinator_recommendation(complaint)
    assert "corroborate" in suggestion["recommendation"]


def test_filing_is_idempotent_after_a_committed_filing(monkeypatch) -> None:
    """A retried approval must not invoke the external channel twice."""
    store = RunStore()
    complaint = Complaint(status="filed", channel="email", filed_at="2026-09-14T00:00:00+00:00")
    store.save_complaint(complaint)
    calls = []

    class CountingChannel(EmailChannel):
        def file(self, payload):
            calls.append(payload)
            raise AssertionError("idempotent retry must not call the channel")

    monkeypatch.setattr("app.agents.tools.get_store", lambda: store)
    set_filing_context("Addis Ababa", CountingChannel("office@example.gov"))
    result = file_complaint._tool_func(
        complaint_id=complaint.complaint_id,
        category="waste",
        lat=9.03,
        lon=38.74,
        subject="Waste issue",
        text="Overflowing bins block the footpath.",
    )
    assert result.startswith("already filed")
    assert calls == []
