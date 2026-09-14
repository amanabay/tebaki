# Tebaki camera-ready demo runbook

This runbook is the source of truth for the live recording. It uses the deployed browser and API, while keeping Addis claims and delivery status explicit.

## Live surfaces

- Web: <https://d20081fyuc7fwc.cloudfront.net/>
- API health: <https://pxgwrenfrk.execute-api.us-east-1.amazonaws.com/health>
- Proof: <https://pxgwrenfrk.execute-api.us-east-1.amazonaws.com/public/proof>
- Diagnostics: <https://pxgwrenfrk.execute-api.us-east-1.amazonaws.com/public/diagnostics>

The deployed runtime is AgentCore in `us-east-1`, using Nova Pro and DynamoDB. The Addis pack includes a verified Bole sub-city pilot polygon and retains a city-level fallback elsewhere. Gmail SMTP is authenticated and configured; real delivery occurs only after explicit human approval.

## Two-minute story

1. Open the dashboard and point out the Addis coverage label, model mode, and persistence proof.
2. Submit two nearby reports from different residents. Show the immediate `triage: queued` response, then the guardian confidence and reason.
3. Run the supervised cycle. Open the decision queue and select a case.
4. Open the evidence drawer: source reports, corroboration count, privacy redactions, regulation citation, evidence score, and coordinator recommendation.
5. Open Replay and let the judge see guardian → cluster → evidence → coordinator → drafter → human approval.
6. Approve one case only when you intend to send the email. Show the real SMTP delivery label and the `filed` event in the case timeline; otherwise keep this step in the deterministic sandbox.
7. Open Impact and Proof to show anonymized neighborhood outcomes and runtime counters.
8. For the deterministic sandbox recording, simulate a missed SLA, run Chase, and show the escalation trail. Make clear that this clock control is sandbox-only.

## Safety narration

- The coordinator proposes in-app next actions; it never sends email.
- External filing is blocked until a human approves or edits the decision card.
- Bole resolves to a verified sub-city polygon; all other Addis areas remain city-level fallback.
- SMTP delivery is real only when the operator approves a decision card; do not approve a case during a recording unless that email is intended to be sent.
- Every action, retry, failure, and escalation remains in the case timeline.

## Release gate

```bash
PYTHONPATH=engine .venv/bin/python cli/tebaki.py validate --strict
PYTHONPATH=engine .venv/bin/ruff check engine/app engine/tests
PYTHONPATH=engine .venv/bin/python -m compileall -q engine/app
PYTHONPATH=engine .venv/bin/python -m pytest engine/tests -q -p no:cacheprovider
cd web && npm run build
```

The Python 3.14 run intentionally skips tests marked `python314_runtime`, which exercise the known Strands sync-bridge/TestClient deadlock. Use Python 3.12 for the complete runtime-loop suite.
