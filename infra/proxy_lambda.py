"""Browser-safe API Gateway proxy for the AgentCore runtime.

The browser sends ordinary REST requests. This function adds the HTTP-style
envelope expected by Tebaki's ``/invocations`` endpoint; boto3 performs SigV4
signing with the Lambda execution role.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from typing import Any

import boto3

client = boto3.client("bedrock-agentcore", region_name=os.getenv("AWS_REGION", "us-east-1"))
RUNTIME_ARN = os.environ["TEBAKI_AGENT_RUNTIME_ARN"]
OPERATOR_TOKEN = os.getenv("TEBAKI_OPERATOR_TOKEN", "")
PUBLIC_PATHS = {"/health", "/public/ledger", "/public/scoreboard", "/public/activity", "/public/map", "/public/impact", "/public/proof", "/public/diagnostics", "/public/runs", "/reports"}


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(("/public/runs/", "/public/reports/", "/public/complaints/"))


def _response(status: int, body: Any) -> dict[str, Any]:
    return {"statusCode": status, "headers": {"content-type": "application/json", "access-control-allow-origin": os.getenv("TEBAKI_WEB_ORIGIN", "*")}, "body": json.dumps(body, default=str)}


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    request = event.get("requestContext", {}).get("http", {})
    method = str(request.get("method", event.get("httpMethod", "GET"))).upper()
    path = str(event.get("rawPath") or event.get("path") or "/")
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": {"access-control-allow-origin": os.getenv("TEBAKI_WEB_ORIGIN", "*"), "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": "content-type,authorization"}, "body": ""}
    if method != "GET" and not _is_public(path):
        expected = f"Bearer {OPERATOR_TOKEN}" if OPERATOR_TOKEN else ""
        if not expected or event.get("headers", {}).get("authorization") != expected:
            return _response(401, {"detail": "operator authorization required"})
    raw_body = event.get("body")
    if raw_body and event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode()
    envelope = {"method": method, "path": path, "query": event.get("queryStringParameters") or {}, "body": json.loads(raw_body) if raw_body else None}
    try:
        result = client.invoke_agent_runtime(agentRuntimeArn=RUNTIME_ARN, runtimeSessionId=f"tebaki-{uuid.uuid4().hex[:24]}", payload=json.dumps(envelope).encode(), contentType="application/json", accept="application/json")
        payload = result.get("response")
        if hasattr(payload, "read"):
            payload = payload.read()
        decoded = json.loads(payload.decode() if isinstance(payload, bytes) else payload)
        return _response(200, decoded)
    except Exception as exc:  # noqa: BLE001 — proxy returns a safe structured error
        return _response(502, {"detail": "Agent runtime unavailable", "request_id": envelope.get("path"), "error": str(exc)[:160]})
