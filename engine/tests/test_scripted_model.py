"""Smoke tests: real Strands Agent loop driven by ScriptedModel."""

from __future__ import annotations

import json

import pytest
from strands import Agent, tool

from app.agents.model_factory import get_model, model_mode
from app.agents.scripted_model import ScriptedModel


@tool
def submit_triage(results: list[dict]) -> str:
    """Submit triage results for a batch of resident reports.

    Args:
        results: One entry per report with report_id, category, severity,
            valid, reason, language keys.
    """
    first = results[0]
    return (
        f"triaged {first['report_id']}: {first['category']}/{first['severity']}/"
        f"{'ok' if first['valid'] else 'invalid'}"
    )


@pytest.fixture()
def capture():
    return []


def test_agent_loop_with_scripted_tool_call(capture: list) -> None:
    agent = Agent(
        model=ScriptedModel(),
        tools=[submit_triage],
        system_prompt="You are the triage agent. ROLE: TRIAGE",
        callback_handler=None,
    )
    payload = {
        "report": {
            "report_id": "R-TEST1",
            "category": "waste",
            "note": "garbage pile on sidewalk for weeks",
            "lat": 9.01,
            "lon": 38.76,
        }
    }
    result = agent(json.dumps(payload))
    # The scripted model called the real tool, got its result, and ended the turn.
    assert result.stop_reason == "end_turn"
    assert "triaged R-TEST1: waste" in str(result)


def test_scripted_model_rejects_missing_role() -> None:
    agent = Agent(model=ScriptedModel(), tools=[submit_triage], system_prompt="no role here", callback_handler=None)
    with pytest.raises(RuntimeError, match="no ROLE"):
        agent("hello")


def test_scripted_model_rejects_tool_contract_break() -> None:
    from strands import tool as strands_tool

    @strands_tool
    def unrelated(thing: str) -> str:
        """Unrelated tool."""
        return thing

    agent = Agent(
        model=ScriptedModel(),
        tools=[unrelated],
        system_prompt="You are the triage agent. ROLE: TRIAGE",
        callback_handler=None,
    )
    with pytest.raises(RuntimeError, match="wants tool 'submit_triage'"):
        agent(json.dumps({"report": {"report_id": "R-X", "category": "waste", "note": "x"}}))


def test_model_factory_mode() -> None:
    assert model_mode() == "scripted"
    assert isinstance(get_model(), ScriptedModel)
