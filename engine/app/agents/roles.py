"""Tebaki agent roles and the human-in-the-loop filing gate.

Three Strands agents, each with a ROLE marker in its system prompt
(ScriptedModel dispatches on it; live prompts carry real instructions):

- TRIAGE: validates and classifies resident reports (vision-ready input).
- DRAFTER: turns hotspot clusters into factual complaint drafts.
- FILER: files approved drafts through the city channel. Every
  file_complaint call is gated by a Strands interrupt — the run pauses,
  a decision card is created, and a human answers approve/edit/drop
  before the tool executes or cancels.
"""

from __future__ import annotations

from typing import Any

from strands import Agent
from strands.hooks import BeforeToolCallEvent

from app.agents.model_factory import get_model
from app.agents.registry import get_filing_city
from app.agents.tools import file_complaint, submit_complaint_draft, submit_triage
from app.store import DecisionCard, get_store

TRIAGE_PROMPT = """\
ROLE: TRIAGE
You are Tebaki's triage agent. You run at night over residents' issue \
reports (photo + GPS + one line, sometimes in Amharic). For each report \
decide: is it a valid, actionable civic issue, which category is it \
(waste, pothole, streetlight, drain, water), and how severe (1 cosmetic \
to 5 immediate hazard like flooding or exposed wiring). Reject reports \
that are empty, unreadable, or not civic issues. Detect the note's \
language (am for Amharic, en for English). Submit one result per report \
with a one-line reason. Never invent details a report does not contain.
"""

DRAFTER_PROMPT = """\
ROLE: DRAFTER
You are Tebaki's drafter agent. You turn a hotspot cluster of triaged \
resident reports into one municipal complaint. Rules: plain factual \
text, first-person-plural ("residents report..."), no exaggeration, no \
invented details; cite ONLY the regulation given in context (never \
invent a law); use the ward given in context; severity is the maximum \
across merged reports; mention merged duplicates in duplicates_note. \
Submit exactly one draft per cluster.
"""

FILER_PROMPT = """\
ROLE: FILER
You are Tebaki's filer agent. You file approved complaint drafts through \
the city's official channel using the file_complaint tool. File each \
draft exactly as approved. If the tool reports a failure, report it \
back; do not retry more than once.
"""


def triage_agent() -> Agent:
    return Agent(
        model=get_model(),
        tools=[submit_triage],
        system_prompt=TRIAGE_PROMPT,
        callback_handler=None,
        name="tebaki-triage",
    )


def drafter_agent() -> Agent:
    return Agent(
        model=get_model(),
        tools=[submit_complaint_draft],
        system_prompt=DRAFTER_PROMPT,
        callback_handler=None,
        name="tebaki-drafter",
    )


def filer_agent() -> Agent:
    agent = Agent(
        model=get_model(),
        tools=[file_complaint],
        system_prompt=FILER_PROMPT,
        callback_handler=None,
        name="tebaki-filer",
        hooks=[filing_approval_hook],
    )
    return agent


# --- the human decision gate -----------------------------------------------------

APPROVE = "approve"
EDIT = "edit"
DROP = "drop"


def filing_approval_hook(event: BeforeToolCallEvent) -> None:
    """Pause every file_complaint call for a human approve/edit/drop decision.

    First pass: raises a Strands interrupt; the run stops and the caller
    finds the pending decision in AgentResult.interrupts.
    On resume: event.interrupt() returns the human's response instead of
    raising. "approve" lets the call through; "edit" applies the edited
    fields then lets it through; "drop" cancels the tool call.
    """
    if event.tool_use["name"] != "file_complaint":
        return
    tool_input = dict(event.tool_use["input"])
    response: Any = event.interrupt("filing_approval", reason={"draft": tool_input})
    if response == APPROVE:
        return
    if isinstance(response, dict) and response.get("action") == EDIT:
        event.tool_use["input"] = {**tool_input, **response.get("fields", {})}
        return
    action = response.get("action", "?") if isinstance(response, dict) else response
    event.cancel_tool = f"filing not approved (human said {action!r})"


def decision_card_from_interrupt(agent_name: str, interrupt: Any) -> DecisionCard:
    """Create a store decision card from a pending filing interrupt."""
    reason = interrupt.reason or {}
    draft = reason.get("draft", {})
    store = get_store()
    complaint = store.complaints.get(draft.get("complaint_id", ""))
    ward = complaint.ward if complaint is not None else draft.get("ward", "")
    card = store.add_decision_card(
        DecisionCard(
            complaint_draft=draft,
            context={
                "agent": agent_name,
                "interrupt_id": interrupt.id,
                "interrupt_name": interrupt.name,
                "ward": ward,
                "city": get_filing_city(),
            },
        )
    )
    if complaint is not None:
        complaint.status = "awaiting_approval"
    return card
