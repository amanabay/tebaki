"""Model factory: BedrockModel when credentials are live, ScriptedModel otherwise.

The agents, tools, hooks, and interrupts are identical in both modes;
only the brain differs. TEBAKI_LIVE_BEDROCK=1 opts in to the live model
(requires AWS credentials with Bedrock model access enabled).
"""

from __future__ import annotations

import os

from strands.models import BedrockModel, Model

from app.agents.scripted_model import ScriptedModel
from app.config import settings


def live_bedrock_enabled() -> bool:
    return os.getenv("TEBAKI_LIVE_BEDROCK", "").strip() == "1"


def get_model() -> Model:
    if live_bedrock_enabled():
        return BedrockModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.aws_region,
            # Tool calls are more reliable through Converse than the
            # streaming event path, especially for Nova's structured output.
            streaming=False,
            temperature=0,
        )
    return ScriptedModel()


def model_mode() -> str:
    return "bedrock" if live_bedrock_enabled() else "scripted"
