# Tebaki — submission brief

Tebaki is a civic follow-through agent for residents and the small community
teams who keep a neighborhood organized. A resident reports an issue once;
Tebaki turns nearby reports into one accountable case, asks a human to approve
the external action, and keeps pursuing the city after filing.

## The story in one sentence

Two neighbors report the same blocked walkway. Tebaki verifies and clusters the
reports, drafts a cited complaint, pauses for a human decision, files through
the configured city channel, and escalates when the response deadline passes.

## What is live

- **AgentCore Runtime:** deployed in `us-east-1` with Bedrock and DynamoDB.
- **Strands workflow:** guardian triage, spatial clusterer, drafter, filer,
  coordinator, and chaser agents, connected by a replayable graph.
- **Human control:** every external filing pauses as an approve / edit / drop
  decision card. Decisions and paused state survive a runtime restart.
- **Public proof:** timeline, evidence drawer, replay, impact dashboard, and
  diagnostics make agent work inspectable rather than implied.
- **Channels:** Gmail SMTP for the Addis demo, Open311 for the Chicago pack,
  and a deterministic sandbox portal for repeatable testing.
- **Geography:** Addis has a verified Bole sub-city pilot polygon; the
  published city boundary is used as an explicit fallback elsewhere.

## Why this fits Good Neighbor Agents

Tebaki reduces the invisible coordination work carried by residents, block
groups, and tiny civic teams. The agent consolidates duplicate reports,
preserves corroboration, writes the follow-up, tracks deadlines, and recommends
one practical neighborhood action. People remain in control of what leaves the
community; the system does the persistence work between updates.

## Judge path (two to three minutes)

1. Open the live dashboard and point out city, model, persistence, and coverage.
2. Submit two nearby reports from different residents; show immediate triage.
3. Run the supervised cycle and open the decision queue.
4. Inspect the evidence drawer: source reports, corroborations, redactions,
   citation, severity, and grouping reason.
5. Open Replay to show guardian → cluster → drafter → coordinator → filer.
6. Approve or edit one case and open its timeline. Use SMTP only when a real
   message is intentionally authorized.
7. Switch to the sandbox for the safe visual finale: miss the SLA, run Chase,
   and show the escalation trail.

## Safety and honesty

- Resident notes are untrusted data; agent prompts prohibit instruction
  following from report text.
- PII is redacted before the filing boundary and redaction is repeated on
  resumed edits.
- Boundary checks reject out-of-city reports before triage.
- The coordinator only recommends in-app actions; it never sends email.
- Addis coverage is labelled partial instead of implying full sub-city routing.
- Email delivery is labelled real, simulated, or dry-run in the case and proof
  views; no demo step silently contacts an office.

## Verification

```bash
PYTHONPATH=engine .venv/bin/python cli/tebaki.py validate --strict
PYTHONPATH=engine .venv/bin/ruff check engine/app engine/tests
PYTHONPATH=engine .venv/bin/python -m pytest engine/tests -q -p no:cacheprovider
cd web && npm run build
```

The Python 3.14 release check is finite and isolates the known Strands
sync-bridge/TestClient deadlock. Run the complete runtime-loop suite with
Python 3.12 before submission.

## Links

- Live web app: <https://d20081fyuc7fwc.cloudfront.net/>
- Public health: <https://pxgwrenfrk.execute-api.us-east-1.amazonaws.com/health>
- Proof endpoint: <https://pxgwrenfrk.execute-api.us-east-1.amazonaws.com/public/proof>
- Diagnostics endpoint: <https://pxgwrenfrk.execute-api.us-east-1.amazonaws.com/public/diagnostics>
- Architecture: [`architecture.svg`](architecture.svg)
