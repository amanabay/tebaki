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
import re
import uuid
from collections.abc import AsyncIterable, Callable
from typing import Any

from strands.models import Model
from strands.types.content import Message, Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

_ROLE_RE = re.compile(r"ROLE:\s*([A-Z_]+)")
_PAYLOAD_RE = re.compile(r"\{.*\}", re.DOTALL)

Script = Callable[[dict[str, Any], list[ToolSpec]], tuple[str, dict[str, Any]]]


def _last_user_message(messages: Messages) -> Message | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message
    return None


def _extract_payload(messages: Messages) -> dict[str, Any]:
    message = _last_user_message(messages)
    if message is None:
        return {}
    for block in message.get("content", []):
        if isinstance(block, dict) and "text" in block:
            match = _PAYLOAD_RE.search(block["text"])
            if match:
                return json.loads(match.group(0))
    return {}


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
    cluster = payload["cluster"]
    refs = cluster["report_refs"]
    n = len(refs)
    cite = payload.get("regulation")
    ward = cluster.get("ward", payload.get("city", "Sandbox City"))
    subject = f"{cluster['category'].title()} issue in {ward} ({n} report{'s' if n > 1 else ''})"
    text = (
        f"Residents report a {cluster['category']} issue at approximate location "
        f"({cluster['lat']:.4f}, {cluster['lon']:.4f}) in {ward}. "
        f"Number of resident reports: {n}. "
        "We request acknowledgment and a resolution timeline as required by the applicable regulations."
    )
    return (
        "submit_complaint_draft",
        {
            "category": cluster["category"],
            "severity": cluster.get("severity", 3),
            "report_refs": refs,
            "lat": cluster["lat"],
            "lon": cluster["lon"],
            "ward": ward,
            "subject": subject,
            "text": text,
            "cite": cite,
            "duplicates_note": f"{n} reports merged into one complaint" if n > 1 else None,
        },
    )


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


SCRIPTS: dict[str, Script] = {
    "TRIAGE": triage_script,
    "DRAFTER": drafter_script,
    "FILER": filer_script,
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

        # 2) Otherwise dispatch the role's scripted tool call.
        match = _ROLE_RE.search(system_prompt or "")
        if not match:
            raise RuntimeError("ScriptedModel: no ROLE: marker in system prompt")
        role = match.group(1)
        if role not in SCRIPTS:
            raise RuntimeError(f"ScriptedModel: unknown role {role!r}")

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
