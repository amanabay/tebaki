"""Run-scoped wiring for the filer agents.

FilingContext carries the channel + city for the current nightly run
(tools read it at call time). PausedFiling keeps filer agents alive
across the interrupt pause so a decision answer can resume them.
In-memory for Day 2; DynamoDB/AgentCore sessions replace it later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from strands import Agent

from app.channels import SandboxChannel


@dataclass
class FilingContext:
    city: str
    channel: Any  # SandboxChannel | EmailChannel | ...


class _Registry:
    def __init__(self) -> None:
        self.context = FilingContext(city="Sandbox City", channel=SandboxChannel())
        self.paused: dict[str, PausedFiling] = {}

    def set_context(self, city: str, channel: Any) -> None:
        self.context = FilingContext(city=city, channel=channel)

    def pause(self, card_id: str, agent: Agent, interrupt_id: str) -> None:
        self.paused[card_id] = PausedFiling(agent=agent, interrupt_id=interrupt_id)

    def resume(self, card_id: str) -> PausedFiling:
        if card_id not in self.paused:
            raise KeyError(f"no paused filing for card {card_id!r}")
        return self.paused.pop(card_id)

    def pending_cards(self) -> list[str]:
        return list(self.paused)


@dataclass
class PausedFiling:
    agent: Agent
    interrupt_id: str


_registry = _Registry()


def get_filing_context() -> FilingContext:
    return _registry.context


def set_filing_context(city: str, channel: Any) -> None:
    _registry.set_context(city, channel)


def pause_filing(card_id: str, agent: Agent, interrupt_id: str) -> None:
    _registry.pause(card_id, agent, interrupt_id)


def resume_filing(card_id: str) -> PausedFiling:
    return _registry.resume(card_id)


def get_filing_city() -> str:
    return _registry.context.city
