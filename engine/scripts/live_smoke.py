"""Live Bedrock smoke test: one real Nova Pro triage call through Strands.

Run: PYTHONPATH=engine:sandbox-portal TEBAKI_LIVE_BEDROCK=1 \
     .venv/bin/python engine/scripts/live_smoke.py
"""

import json
import sys

from strands import Agent, tool

from app.agents.model_factory import get_model, model_mode


@tool
def submit_triage(results: list[dict]) -> str:
    """Submit triage results for a batch of resident reports.

    Args:
        results: One entry per report with report_id, category, severity, valid, reason, language keys.
    """
    print(f"TOOL CALLED: submit_triage with {len(results)} results:")
    for r in results:
        print(f"  {r}")
    return f"received {len(results)} triage results"


def main() -> int:
    print("model mode:", model_mode())
    agent = Agent(
        model=get_model(),
        tools=[submit_triage],
        system_prompt=(
            "You are Tebaki's triage agent. ROLE: TRIAGE\n"
            "The user message contains a JSON payload of resident issue reports. "
            "For each report decide category (waste|pothole|streetlight|drain|water), "
            "severity 1-5 (5 = immediate hazard), validity (empty/unreadable notes are "
            "invalid), language (am for Amharic, en for English), and a one-line reason. "
            "Call submit_triage exactly once with results for the whole batch."
        ),
        callback_handler=None,
    )
    payload = {
        "reports": [
            {"report_id": "R-1", "category": "waste", "note": "garbage pile on sidewalk for weeks", "lat": 9.01, "lon": 38.76},
            {"report_id": "R-2", "category": "streetlight", "note": "የከተማ መብራት አልተበራም", "lat": 9.05, "lon": 38.70},
            {"report_id": "R-3", "category": "pothole", "note": "", "lat": 9.02, "lon": 38.71},
        ]
    }
    result = agent(json.dumps(payload))
    print("stop_reason:", result.stop_reason)
    usage = result.metrics.accumulated_usage
    print("usage:", dict(usage) if usage else "n/a")
    print("output:", str(result)[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
