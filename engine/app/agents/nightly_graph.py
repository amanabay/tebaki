"""Nightly Strands Graph: triage -> cluster -> draft.

The deterministic stages of the nightly cycle run as a strands.multiagent
Graph: each node is a Strands agent whose tool calls mutate the run
store; conditional edges skip stages when there is nothing to do
(e.g. every report rejected at triage). The interrupt-gated filing and
the chase stage run after the graph via the registry/resume flow in
app.orchestrator (human-in-the-loop filings pause a run, not a graph
node), so the graph stays replayable and the HITL path stays simple.
"""

from __future__ import annotations

import json

from strands.multiagent import GraphBuilder

from app.agents.roles import clusterer_agent, drafter_agent, triage_agent
from app.store import get_store


def _has_triaged_reports(state: object) -> bool:
    return any(r.status == "triaged" for r in get_store().reports.values())


def _has_clusters(state: object) -> bool:
    return any(r.status == "clustered" for r in get_store().reports.values())


def build_nightly_graph() -> object:
    """Construct the triage -> cluster -> draft graph (fresh agents per run)."""
    triage = triage_agent()
    clusterer = clusterer_agent()
    drafter = drafter_agent()

    builder = GraphBuilder()
    builder.add_node(triage, node_id="triage")
    builder.add_node(clusterer, node_id="cluster")
    builder.add_node(drafter, node_id="drafter")
    builder.add_edge("triage", "cluster", condition=_has_triaged_reports)
    builder.add_edge("cluster", "drafter", condition=_has_clusters)
    builder.set_entry_point("triage")
    builder.set_max_node_executions(max_executions=10)
    return builder.build()


def run_graph_phase(reports_payload: dict) -> dict:
    """Execute the graph phase of the nightly cycle.

    reports_payload: {"reports": [report dicts]} — the graph task.
    Returns the GraphResult summary dict.
    """
    graph = build_nightly_graph()
    result = graph(json.dumps(reports_payload))
    return {
        "status": str(getattr(result.status, "value", result.status)),
        "completed": [n.node_id for n in result.execution_order],
        "completed_count": result.completed_nodes,
        "failed": result.failed_nodes,
        "interrupts": len(result.interrupts or []),
    }
