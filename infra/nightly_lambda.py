"""Server-side nightly trigger for the Tebaki AgentCore runtime.

EventBridge invokes this function; no browser token is involved.  The
runtime receives the same HTTP envelope as the public proxy, with human
approval explicitly left enabled.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import boto3


def handler(_event: dict[str, Any], _context: Any) -> dict[str, Any]:
    client = boto3.client("bedrock-agentcore", region_name=os.getenv("AWS_REGION", "us-east-1"))
    envelope = {
        "method": "POST",
        "path": "/admin/nightly",
        "query": {},
        "body": {"auto_approve": False},
    }
    response = client.invoke_agent_runtime(
        agentRuntimeArn=os.environ["TEBAKI_AGENT_RUNTIME_ARN"],
        runtimeSessionId=f"tebaki-schedule-{uuid.uuid4().hex}",
        payload=json.dumps(envelope).encode(),
        contentType="application/json",
        accept="application/json",
    )
    body = response.get("response")
    if hasattr(body, "read"):
        body = body.read()
    return {"statusCode": 200, "body": body.decode() if isinstance(body, bytes) else body}
