"""Filing channel adapters.

Each adapter exposes `file(complaint) -> FilingResult`. City logic lives
in the city pack YAML; adapters are generic.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

import httpx


@dataclass
class FilingResult:
    ok: bool
    channel: str
    ticket_id: str | None = None
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class SandboxChannel:
    """Files against the local mock portal (sandbox-portal)."""

    def __init__(self, base_url: str = "http://localhost:9100") -> None:
        self.base_url = base_url.rstrip("/")
        self.channel = "sandbox"

    def file(self, complaint: dict[str, Any]) -> FilingResult:
        try:
            resp = httpx.post(
                f"{self.base_url}/complaints",
                data={
                    "category": complaint.get("category", "waste"),
                    "location": f"{complaint.get('lat', 0)}, {complaint.get('lon', 0)}",
                    "description": complaint.get("text", ""),
                },
                timeout=15,
            )
        except httpx.HTTPError as e:
            return FilingResult(ok=False, channel=self.channel, detail=f"portal unreachable: {e}")
        if resp.status_code != 201:
            return FilingResult(ok=False, channel=self.channel, detail=f"portal rejected: {resp.status_code} {resp.text[:200]}")
        body = resp.json()
        return FilingResult(ok=True, channel=self.channel, ticket_id=body["ticket_id"])

    def check(self, ticket_id: str) -> dict[str, Any]:
        resp = httpx.get(f"{self.base_url}/complaints/{quote(ticket_id)}", timeout=15)
        resp.raise_for_status()
        return resp.json()


class EmailChannel:
    """Files a complaint as an email via SMTP (dev) — SES swap-in later.

    In dev mode (dry_run=True, the default when no SMTP host is set),
    the message is rendered but not sent, so the nightly loop can be
    exercised end-to-end offline.
    """

    def __init__(
        self,
        to_address: str,
        from_address: str = "tebaki@localhost",
        smtp_host: str | None = None,
        smtp_port: int = 587,
        dry_run: bool = True,
    ) -> None:
        self.to_address = to_address
        self.from_address = from_address
        self.smtp_host = smtp_host or os.getenv("TEBAKI_SMTP_HOST")
        self.smtp_port = smtp_port
        self.dry_run = dry_run and self.smtp_host is None
        self.channel = "email"

    def _render(self, complaint: dict[str, Any]) -> EmailMessage:
        msg = EmailMessage()
        subject = complaint.get("subject") or f"Tebaki complaint: {complaint.get('category', 'issue')}"
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = self.to_address
        body = complaint.get("text", "")
        if complaint.get("cite"):
            body += f"\n\nLegal basis: {complaint['cite']}"
        msg.set_content(body)
        return msg

    def file(self, complaint: dict[str, Any]) -> FilingResult:
        msg = self._render(complaint)
        if self.dry_run:
            return FilingResult(
                ok=True,
                channel=self.channel,
                ticket_id=None,
                detail="dry-run (no SMTP configured); email rendered, not sent",
                extra={"preview": str(msg)[:500]},
            )
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as smtp:
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as e:
            return FilingResult(ok=False, channel=self.channel, detail=f"smtp error: {e}")
        return FilingResult(ok=True, channel=self.channel, ticket_id=None, detail=f"emailed {self.to_address}")


class Open311Channel:
    """Files complaints via the Open311 GeoReport v2 write API.

    Standard flow: POST /requests.json (service_code, lat, long,
    description [+ jurisdiction_id, api_key]) -> token or service_request_id;
    GET /requests/{ticket}.json to poll status. City category->service_code
    mapping comes from the city pack; unmapped categories fail cleanly.
    """

    def __init__(
        self,
        endpoint: str,
        jurisdiction_id: str | None = None,
        api_key: str | None = None,
        service_code_map: dict[str, str] | None = None,
    ) -> None:
        # Accept both base URLs and full .../requests.json URLs.
        self.endpoint = endpoint.rstrip("/")
        self.endpoint = self.endpoint.removesuffix("/requests.json")
        self.jurisdiction_id = jurisdiction_id
        self.api_key = api_key
        self.service_code_map = service_code_map or {}
        self.channel = "open311"

    def file(self, complaint: dict[str, Any]) -> FilingResult:
        category = complaint.get("category", "")
        service_code = self.service_code_map.get(category)
        if not service_code:
            return FilingResult(
                ok=False,
                channel=self.channel,
                detail=(
                    f"no service_code mapped for category {category!r} — "
                    "research the city's services list (see docs/chicago-research.md)"
                ),
            )
        data = {
            "service_code": service_code,
            "lat": str(complaint.get("lat", "")),
            "long": str(complaint.get("lon", "")),
            "description": complaint.get("text", ""),
        }
        if self.jurisdiction_id:
            data["jurisdiction_id"] = self.jurisdiction_id
        if self.api_key:
            data["api_key"] = self.api_key
        try:
            resp = httpx.post(f"{self.endpoint}/requests.json", data=data, timeout=20)
        except httpx.HTTPError as e:
            return FilingResult(ok=False, channel=self.channel, detail=f"open311 unreachable: {e}")
        if resp.status_code not in (200, 201):
            return FilingResult(
                ok=False,
                channel=self.channel,
                detail=f"open311 rejected: {resp.status_code} {resp.text[:200]}",
            )
        try:
            body = resp.json()
        except ValueError:
            return FilingResult(ok=False, channel=self.channel, detail="open311 returned non-JSON response")
        ticket_id: str | None = None
        if isinstance(body, dict) and "token" in body:
            ticket_id = str(body["token"])
        elif isinstance(body, list) and body and isinstance(body[0], dict) and "service_request_id" in body[0]:
            ticket_id = str(body[0]["service_request_id"])
        if ticket_id is None:
            return FilingResult(ok=False, channel=self.channel, detail="open311 response missing token/service_request_id")
        return FilingResult(ok=True, channel=self.channel, ticket_id=ticket_id)

    def check(self, ticket_id: str) -> dict[str, Any]:
        params = {"jurisdiction_id": self.jurisdiction_id} if self.jurisdiction_id else None
        resp = httpx.get(
            f"{self.endpoint}/requests/{quote(ticket_id)}.json", params=params, timeout=20
        )
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, list):
            if not body:
                raise ValueError(f"open311: empty response for ticket {ticket_id}")
            return body[0]
        return body


class SESEmailChannel:
    """Files a complaint as an email via Amazon SES v2 (UTF-8, Amharic-safe).

    Used when TEBAKI_EMAIL_MODE=ses; requires AWS credentials and a
    verified sender (see docs/aws-setup.md). Falls back nowhere: failures
    are reported as FilingResult(ok=False) for the agent to handle.
    """

    def __init__(
        self,
        to_address: str,
        from_address: str = "tebaki@localhost",
        region: str = "us-east-1",
    ) -> None:
        import boto3

        self.to_address = to_address
        self.from_address = from_address
        self.channel = "email"
        self.client = boto3.client("sesv2", region_name=region)

    def _content(self, complaint: dict[str, Any]) -> dict[str, Any]:
        subject = complaint.get("subject") or f"Tebaki complaint: {complaint.get('category', 'issue')}"
        body = complaint.get("text", "")
        if complaint.get("cite"):
            body += f"\n\nLegal basis: {complaint['cite']}"
        return {
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            }
        }

    def file(self, complaint: dict[str, Any]) -> FilingResult:
        try:
            resp = self.client.send_email(
                FromEmailAddress=self.from_address,
                Destination={"ToAddresses": [self.to_address]},
                Content=self._content(complaint),
            )
        except Exception as e:  # noqa: BLE001 — botocore raises many client errors
            return FilingResult(ok=False, channel=self.channel, detail=f"ses error: {e}")
        message_id = resp.get("MessageId", "unknown")
        return FilingResult(
            ok=True,
            channel=self.channel,
            ticket_id=None,
            detail=f"emailed {self.to_address} via SES (message {message_id})",
            extra={"message_id": message_id},
        )

    def check(self, ticket_id: str) -> dict[str, Any]:
        # Email has no ticket status API; the chase stage treats email
        # tickets as permanently "pending" until acknowledgment arrives.
        return {"ticket_id": ticket_id, "status": "pending", "channel": "email"}


def channel_from_pack(pack: Any) -> SandboxChannel | EmailChannel | Open311Channel | SESEmailChannel:
    """Build the primary filing channel from a loaded city pack."""
    if pack.city.name == "Sandbox City":
        return SandboxChannel()
    if pack.channels.api is not None:
        api = pack.channels.api
        api_key = os.getenv(api.api_key_env) if api.api_key_env else None
        return Open311Channel(
            endpoint=api.endpoint,
            jurisdiction_id=api.jurisdiction_id,
            api_key=api_key,
            service_code_map=api.service_code_map,
        )
    if pack.channels.email:
        primary = pack.channels.email[0]
        if os.getenv("TEBAKI_EMAIL_MODE", "").lower() == "ses":
            return SESEmailChannel(
                to_address=primary.address,
                from_address=os.getenv("TEBAKI_SES_FROM", "tebaki@localhost"),
            )
        return EmailChannel(to_address=primary.address)
    raise ValueError(f"no filing channel configured for {pack.city.name}")
