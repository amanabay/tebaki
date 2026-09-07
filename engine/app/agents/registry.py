"""Run-scoped wiring for the filer agents.

FilingContext carries the channel + city for the current nightly run
(tools read it at call time). PausedFiling keeps filer agents alive
across the interrupt pause so a decision answer can resume them.

Durability: pausing also persists a full SDK snapshot of the filer agent
(messages, interrupt state, model state) onto the decision card. If the
engine restarts before the human answers, resume_filing rebuilds the
agent from that snapshot — the human-in-the-loop filing survives
restarts and works across serverless/AgentCore invocations.
"""

from dataclasses import dataclass
from typing import Any

from strands import Agent

from app.channels import SandboxChannel
from app.store import get_store


@dataclass
class FilingContext:
    city: str
    channel: Any  # SandboxChannel | EmailChannel | Open311Channel | SESEmailChannel
    sla: dict[str, int] | None = None  # {"acknowledge_days": n, "resolve_days": n}
    escalation_rungs: list[dict[str, Any]] | None = None  # [{level,target,email,after_days}]
    pack: Any = None  # loaded CityPack


@dataclass
class PausedFiling:
    agent: Agent
    interrupt_id: str


class _Registry:
    def __init__(self) -> None:
        self.context = FilingContext(city="Sandbox City", channel=SandboxChannel())
        self.paused: dict[str, PausedFiling] = {}

    def set_context(
        self,
        city: str,
        channel: Any,
        sla: dict[str, int] | None = None,
        escalation_rungs: list[dict[str, Any]] | None = None,
        pack: Any = None,
    ) -> None:
        self.context = FilingContext(
            city=city, channel=channel, sla=sla, escalation_rungs=escalation_rungs, pack=pack
        )

    def pause(self, card_id: str, agent: Agent, interrupt_id: str) -> None:
        self.paused[card_id] = PausedFiling(agent=agent, interrupt_id=interrupt_id)
        # Persist a snapshot so a restarted engine can rebuild this agent.
        try:
            snapshot = agent.take_snapshot(preset="session", include=["model_state"])
            store = get_store()
            card = store.get_card(card_id)
            if card is not None:
                card.paused_state = snapshot.to_dict()
                store.save_card(card)
        except Exception as e:  # noqa: BLE001 — pause must not fail the filing run
            # In-memory pause still works; durability is best-effort here.
            import logging

            logging.getLogger(__name__).warning("snapshot persistence failed: %s", e)

    def resume(self, card_id: str) -> PausedFiling:
        live = self.paused.pop(card_id, None)
        if live is not None:
            return live
        # Engine restarted (or another process paused the filing):
        # rebuild the agent from the persisted snapshot on the card.
        card = get_store().get_card(card_id)
        if card is None or not card.paused_state:
            raise KeyError(f"no paused filing for card {card_id!r}")
        from strands.types._snapshot import Snapshot

        from app.agents.roles import filer_agent

        agent = filer_agent()
        agent.load_snapshot(Snapshot.from_dict(card.paused_state))
        return PausedFiling(agent=agent, interrupt_id=str(card.context.get("interrupt_id", "")))

    def pending_cards(self) -> list[str]:
        return list(self.paused)


_registry = _Registry()


def get_filing_context() -> FilingContext:
    return _registry.context


def set_filing_context(
    city: str,
    channel: Any,
    sla: dict[str, int] | None = None,
    escalation_rungs: list[dict[str, Any]] | None = None,
    pack: Any = None,
) -> None:
    _registry.set_context(city, channel, sla=sla, escalation_rungs=escalation_rungs, pack=pack)


def pause_filing(card_id: str, agent: Agent, interrupt_id: str) -> None:
    _registry.pause(card_id, agent, interrupt_id)


def resume_filing(card_id: str) -> PausedFiling:
    return _registry.resume(card_id)


def reset_registry() -> None:
    """Drop all in-memory paused filings (test helper; persisted cards unaffected)."""
    _registry.paused = {}


def get_filing_city() -> str:
    return _registry.context.city
