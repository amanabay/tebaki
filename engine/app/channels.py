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


def channel_from_pack(pack: Any) -> SandboxChannel | EmailChannel:
    """Build the primary filing channel from a loaded city pack."""
    if pack.city.name == "Sandbox City":
        return SandboxChannel()
    if pack.channels.email:
        primary = pack.channels.email[0]
        return EmailChannel(to_address=primary.address)
    raise ValueError(f"no filing channel configured for {pack.city.name}")
