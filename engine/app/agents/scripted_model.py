"""Deterministic scripted model for dev/CI.

Exercises the REAL Strands agent event loop (tool specs, tool_use
emission, toolResult handling, end_turn) without a live LLM. Each agent
role embeds a ``ROLE: <name>`` marker in its system prompt; the model
dispatches on that marker and emits a scripted tool call derived from
the JSON payload embedded in the user prompt.

When Bedrock credentials are available, the factory
(`app.agents.model_factory.get_model`) swaps in a real
`BedrockModel` — the agents, tools, hooks, and interrupts are identical
in both modes.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterable, Callable
from typing import Any

from strands.models import Model
from strands.types.content import Message, Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

# Role dispatch: each agent offers exactly one tool; the tool name
# identifies the role. Prompts carry no dispatch markers.
_TOOL_ROLE = {
    "submit_triage": "TRIAGE",
    "cluster_triaged_reports": "CLUSTERER",
    "submit_complaint_drafts": "DRAFTER",
    "file_complaint": "FILER",
    "submit_chase_results": "CHASER",
}


def _role_from_tools(tool_names: list[str]) -> str | None:
    for name in tool_names:
        if name in _TOOL_ROLE:
            return _TOOL_ROLE[name]
    return None


Script = Callable[[dict[str, Any], list[ToolSpec]], tuple[str, dict[str, Any]]]


def _last_user_message(messages: Messages) -> Message | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None


def _message_text(message: Message) -> str:
    return "".join(
        block.get("text", "")
        for block in message.get("content", [])
        if isinstance(block, dict) and "text" in block
    )


def _extract_payload(messages: Messages) -> dict[str, Any]:
    """Return the last top-level JSON object in the last user message.

    Graph node inputs mix the original task JSON with dependency outputs;
    the last top-level object is the most recent stage's payload. Nested
    objects are skipped (only outermost objects count).
    """
    message = _last_user_message(messages)
    if message is None:
        return {}
    text = _message_text(message)
    decoder = json.JSONDecoder()
    candidates: list[Any] = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            candidates.append(obj)
        i = end  # skip past this object; nested objects are not candidates
    if not candidates:
        return {}
    payload = candidates[-1]
    return payload if isinstance(payload, dict) else {}


def _last_tool_result(messages: Messages) -> str | None:
    message = _last_user_message(messages)
    if message is None:
        return None
    for block in message.get("content", []):
        if isinstance(block, dict) and "toolResult" in block:
            content = block["toolResult"].get("content", [])
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    return part["text"]
            return ""
    return None


# --- role scripts ---------------------------------------------------------------

_SEVERITY_HIGH = ("flood", "hazard", "wire", "exposed", "sewage", "danger")
_SEVERITY_MED = ("deep", "weeks", "days", "broken", "blocked", "overflow")


def _severity(note: str) -> int:
    lowered = note.lower()
    if any(word in lowered for word in _SEVERITY_HIGH):
        return 5
    if any(word in lowered for word in _SEVERITY_MED):
        return 4
    return 3


def _is_amharic(text: str) -> bool:
    return any("\u1200" <= ch <= "\u137f" for ch in text)


def triage_script(payload: dict[str, Any], tool_specs: list[ToolSpec]) -> tuple[str, dict[str, Any]]:
    reports = payload.get("reports") or [payload["report"]]
    results = []
    for report in reports:
        note = report.get("note", "")
        category = report.get("category", "waste")
        if category not in {"waste", "pothole", "streetlight", "drain", "water"}:
            category = "waste"
        results.append(
            {
                "report_id": report.get("report_id", ""),
                "category": category,
                "severity": _severity(note),
                "valid": bool(note.strip()),
                "reason": "scripted triage: note present and category plausible"
                if note.strip()
                else "empty note",
                "language": "am" if _is_amharic(note) else "en",
            }
        )
    return ("submit_triage", {"results": results})


def drafter_script(payload: dict[str, Any], tool_specs: list[ToolSpec]) -> tuple[str, dict[str, Any]]:
    """Batch mode: payload {clusters: [...], regulation, city} -> one drafts call."""
    clusters = payload.get("clusters") or []
    cite = payload.get("regulation")
    city = payload.get("city", "Sandbox City")
    drafts = []
    for cluster in clusters:
        refs = cluster["report_refs"]
        residents = cluster.get("resident_count", len(refs))
        ward = cluster.get("ward", city)
        place = cluster.get("place")
        where = f"near {place}, {ward}" if place else f"in {ward}"
        subject = f"{cluster['category'].title()} issue {where} ({residents} residents)"
        notes = "; ".join(f'"{n}"' for n in cluster.get("notes", []))
        text = (
            f"{residents} residents report a {cluster['category']} issue "
            f"{where} (approximate location ({cluster['lat']:.4f}, {cluster['lon']:.4f})). "
            f"Resident notes: {notes or '—'}. "
            "We request acknowledgment and a resolution timeline as required by the applicable regulations."
        )
        drafts.append(
            {
                "category": cluster["category"],
                "severity": cluster.get("max_severity", 3),
                "report_refs": refs,
                "lat": cluster["lat"],
                "lon": cluster["lon"],
                "ward": ward,
                "place": place,
                "resident_count": residents,
                "subject": subject,
                "text": text,
                "cite": cite,
                "duplicates_note": f"{len(refs)} reports merged into one complaint" if len(refs) > 1 else None,
            }
        )
    return ("submit_complaint_drafts", {"drafts": drafts})


def filer_script(payload: dict[str, Any], tool_specs: list[ToolSpec]) -> tuple[str, dict[str, Any]]:
    draft = payload["draft"]
    return (
        "file_complaint",
        {
            "complaint_id": draft["complaint_id"],
            "category": draft["category"],
            "lat": draft["lat"],
            "lon": draft["lon"],
            "subject": draft["subject"],
            "text": draft["text"],
            "cite": draft.get("cite"),
        },
    )


def chaser_script(payload: dict[str, Any], tool_specs: list[ToolSpec]) -> tuple[str, dict[str, Any]]:
    results = []
    for c in payload.get("complaints", []):
        days = c["days_since_filing"]
        status = c["ticket_status"]
        ack_deadline = c["sla_ack_days"]
        resolve_deadline = c["sla_resolve_days"]
        level = c["escalation_level"]
        ticket = c.get("ticket_id") or "unknown ticket"
        stale_ack = status == "pending" and days > ack_deadline
        stale_resolve = status == "acknowledged" and days > resolve_deadline
        if not (stale_ack or stale_resolve):
            results.append(
                {"complaint_id": c["complaint_id"], "ticket_status": status, "action": "none"}
            )
            continue
        missed = (
            f"acknowledgment deadline ({ack_deadline} days)" if stale_ack
            else f"resolution deadline ({resolve_deadline} days)"
        )
        next_level = level + 1
        subject = f"Escalation {next_level}: complaint {c['complaint_id']} ({ticket}) unaddressed"
        text = (
            f"We are escalating complaint {c['complaint_id']} (ticket {ticket}), filed {days} days ago "
            f"regarding a {c['category']} issue in {c['ward']}. The {missed} has passed without "
            f"response. We request immediate attention and a written response."
        )
        results.append(
            {
                "complaint_id": c["complaint_id"],
                "ticket_status": status,
                "action": "escalate",
                "escalation_level": next_level,
                "subject": subject,
                "text": text,
            }
        )
    return ("submit_chase_results", {"results": results})


def clusterer_script(payload: dict[str, Any], tool_specs: list[ToolSpec]) -> tuple[str, dict[str, Any]]:
    return ("cluster_triaged_reports", {})


SCRIPTS: dict[str, Script] = {
    "TRIAGE": triage_script,
    "CLUSTERER": clusterer_script,
    "DRAFTER": drafter_script,
    "FILER": filer_script,
    "CHASER": chaser_script,
}


# --- the model ------------------------------------------------------------------

class ScriptedModel(Model):
    """Deterministic model: real Strands loop, scripted tool calls."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {}

    @property
    def stateful(self) -> bool:
        return False

    @property
    def context_window_limit(self) -> int | None:
        return None

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    def structured_output(
        self, output_model: Any, prompt: Messages, system_prompt: str | None = None, **kwargs: Any
    ) -> Any:
        raise NotImplementedError("ScriptedModel uses typed tools, not model-level structured_output")

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: Any = None,
        system_prompt_content: Any = None,
        invocation_state: dict[str, Any] | None = None,
        cancel_signal: Any = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        tool_specs = tool_specs or []
        tool_names = [spec["name"] for spec in tool_specs]

        # 1) If the previous turn produced tool results, finish the turn with text.
        tool_result = _last_tool_result(messages)
        if tool_result is not None:
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": f"Tool result received: {tool_result or 'ok'}."},
                }
            }
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return

        # 2) Otherwise dispatch the scripted tool call for this agent's role.
        #    Role is inferred from the tools the agent offers (each role has
        #    exactly one tool), so prompts stay free of dispatch markers.
        role = _role_from_tools(tool_names)
        if role is None:
            raise RuntimeError(
                f"ScriptedModel: no role mapped for tools {tool_names or '<none>'}"
            )

        payload = _extract_payload(messages)
        tool_name, tool_input = SCRIPTS[role](payload, tool_specs)
        if tool_name not in tool_names:
            available = ", ".join(tool_names) or "<none>"
            raise RuntimeError(
                f"ScriptedModel: role {role} wants tool {tool_name!r} but agent offers: {available}"
            )

        tool_use_id = f"script-{uuid.uuid4().hex[:12]}"
        input_json = json.dumps(tool_input)
        yield {"messageStart": {"role": "assistant"}}
        yield {
            "contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {"name": tool_name, "toolUseId": tool_use_id}},
            }
        }
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"toolUse": {"input": input_json}},
            }
        }
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "tool_use"}}

    async def count_tokens(self, prompt: Messages, tools: list[ToolSpec] | None = None) -> int:
        return sum(len(str(m)) for m in prompt)
