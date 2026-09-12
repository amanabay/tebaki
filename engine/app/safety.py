"""Pre-filing safety: PII redaction and privacy flags.

Resident notes and drafted complaint text are untrusted free text. Before
a complaint is presented for human approval, emails, phone numbers and
long digit runs are redacted — what the approver sees (and what files)
is the redacted version. Flags describe what was found so the approver
knows to double-check.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,16}\d")
# Do not treat internal report IDs (for example, ``R-1234567A``) as resident
# PII. They are deliberately included in complaint evidence for traceability.
# A long run must be a standalone numeric token to be considered sensitive.
_LONG_DIGITS_RE = re.compile(r"(?<![A-Za-z0-9-])\d{7,}(?![A-Za-z0-9])")

_REDACTED = "[redacted]"
_PHONE_MIN_DIGITS = 9  # Ethiopian +251... and generic international numbers


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Redact obvious personal data from text.

    Returns (redacted_text, flags) where flags are human-readable
    descriptions of what was removed, e.g. ["email address", "possible phone number"].
    """
    flags: list[str] = []

    def _sub_email(_m: re.Match[str]) -> str:
        flags.append("email address")
        return _REDACTED

    def _sub_phone(m: re.Match[str]) -> str:
        matched = m.group(0)
        digit_count = sum(c.isdigit() for c in matched)
        if digit_count >= _PHONE_MIN_DIGITS:
            flags.append("possible phone number")
            return _REDACTED
        return matched

    def _sub_digits(_m: re.Match[str]) -> str:
        flags.append("long digit sequence (possible account/id number)")
        return _REDACTED

    out = _EMAIL_RE.sub(_sub_email, text)
    out = _PHONE_RE.sub(_sub_phone, out)
    out = _LONG_DIGITS_RE.sub(_sub_digits, out)
    return out, _dedupe(flags)


def _dedupe(flags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def redact_draft(draft: dict) -> tuple[dict, list[str]]:
    """Redact a complaint draft's free-text fields in place; return flags."""
    all_flags: list[str] = []
    for field in ("text", "subject"):
        value = draft.get(field)
        if isinstance(value, str):
            redacted, flags = redact_pii(value)
            if flags:
                draft[field] = redacted
                all_flags.extend(flags)
    return draft, _dedupe(all_flags)
