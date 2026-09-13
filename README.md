# Tebaki (ጠባቂ) — The City's Guardian

> Every civic app makes the citizen do the follow-up. **Tebaki makes the government do the follow-up.**

Residents report an issue once. A Strands agent triages reports nightly, clusters them into hotspots, drafts bilingual complaints citing the city's own regulations, files them through real channels, tracks every ticket against SLA clocks, auto-escalates stale cases up the official ladder — and surfaces exactly one kind of human interaction: a decision card.

**Built for the Agents for Humans Hackathon (Good Neighbor Agents track).**

## Repo layout

```
tebaki/
├─ engine/           Python: Strands orchestrator, FastAPI, tools, agents
├─ web/              React 19 + Vite + TS SPA/PWA (intake, map, evidence, impact + replay)
├─ cities/           City Packs: addis.yaml, chicago.yaml, sandbox.yaml (+ geojson/)
├─ infra/            Container + AgentCore deployment helper
├─ sandbox-portal/   Mock city portal for offline dev/CI/eval
├─ cli/              tebaki validate / run / demo / chase
└─ tebaki.md         Full plan (pitch, architecture, schedule)
```

## Quickstart

The default city pack is Addis Ababa. Sandbox remains available for offline demos and CI:

```bash
# 1. mock city complaint portal (terminal 1)
cd sandbox-portal && ../.venv/bin/uvicorn portal.app:app --port 9100

# 2. Tebaki engine API (terminal 2, repo root)
TEBAKI_CITY_PACK=sandbox PYTHONPATH=engine:sandbox-portal .venv/bin/uvicorn app.api.main:app --port 8000

# 3. web app (terminal 3)
cd web && npm install && npm run dev   # http://localhost:5173
```

Try it: submit a report at `/report`, then hit **Process new reports** on the dashboard (or `curl -X POST localhost:8000/admin/nightly -H 'Content-Type: application/json' -d '{"auto_approve": false}'`). The draft appears under **Review** — approve it and the guardian files it with the mock portal and returns a real ticket id.

For a judge-ready seeded path, use the sandbox pack above and choose **Load sample reports**. It inserts two nearby waste reports from different neighbors plus one separate pothole. The visible flow is: **Load sample reports → Process new reports → Review → approve → ticket → Demo: miss SLA → Check deadlines**. The demo clock control is sandbox-only, idempotent for active tickets, and lets the chaser prove escalation without waiting several days.

## Architecture

![Tebaki architecture](docs/architecture.svg)

The production shape is a scheduled Strands workflow backed by DynamoDB and official city channels. Local development uses the same graph, a scripted offline model, an in-memory store, and the sandbox portal. The human approval interrupt is durable in the persistent store and every run emits an activity trail for the dashboard.

The operator UI makes the agent accountable: each case has a lifecycle timeline and evidence drawer, while **Replay** replays a persisted run and **Impact** presents anonymized neighborhood outcomes. The browser-safe production contract is `Browser → API proxy → AgentCore → DynamoDB/Bedrock/channels`; the browser never signs AWS requests. AgentCore also accepts the same REST operations through its `/invocations` HTTP-style envelope for proxy deployments.

Live endpoints (us-east-1): [HTTPS web demo](https://d20081fyuc7fwc.cloudfront.net/) · [public API](https://pxgwrenfrk.execute-api.us-east-1.amazonaws.com/health). The web build is served through CloudFront; the API proxy keeps AWS signing and operator credentials server-side.

For persistence, run DynamoDB Local (`docker run -d -p 8000:8000 amazon/dynamodb-local:latest` — use a port other than 8000 if the engine owns 8000) and start the engine with `TEBAKI_STORE=dynamodb TEBAKI_DDB_ENDPOINT=<url> TEBAKI_DYNAMODB_TABLE=tebaki`.

For a live Bedrock run: `TEBAKI_LIVE_BEDROCK=1` on the engine (requires AWS credentials with Nova access). For real email filing: `TEBAKI_EMAIL_MODE=ses TEBAKI_SES_FROM=<verified-sender>`.

### Browser-safe AgentCore proxy

`infra/proxy_lambda.py` is the thin API Gateway/Lambda bridge for a hosted web build. It signs requests with the Lambda role, forwards the existing REST contract as an AgentCore HTTP envelope, and keeps operator mutations behind a bearer token. Deploy it with `infra/template.yaml` after storing the runtime ARN, web origin, and operator token in SSM/Secrets Manager; set the resulting API URL as `VITE_API_URL` when building the web app.

The same template provisions an EventBridge-triggered nightly Lambda. It invokes `/admin/nightly` at 02:00 Africa/Addis_Ababa with human approval required; no browser token is used by the scheduler.

CLI: `.venv/bin/python cli/tebaki.py [validate|run|demo|chase] --city sandbox`.

### Environment variables

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Web app: engine API base URL (default `http://localhost:8000`) — set at build time for a deployed engine |
| `TEBAKI_STORE` | `dynamodb` to use the DynamoDB store (default: in-memory) |
| `TEBAKI_DDB_ENDPOINT` / `TEBAKI_DYNAMODB_TABLE` | DynamoDB endpoint (Local) / table name |
| `TEBAKI_LIVE_BEDROCK` | `1` to run agents on Bedrock (default: scripted offline model) |
| `TEBAKI_BEDROCK_MODEL_ID` | Live model override; defaults to cost-conscious `amazon.nova-lite-v1:0` (Nova Micro/Pro are supported) |
| `TEBAKI_EMAIL_MODE` / `TEBAKI_SES_FROM` | `ses` + verified sender to send email filings for real |
| `TEBAKI_SMTP_HOST` / `TEBAKI_SMTP_FROM` / `TEBAKI_SMTP_SECRET_ARN` | Optional Gmail SMTP demo path; store `username` and Gmail app `password` in Secrets Manager |
| `TEBAKI_SANDBOX_PORTAL_URL` | Sandbox filing portal base URL (default `http://localhost:9100`; useful when deployed separately) |
| `TEBAKI_CHICAGO_311_KEY` | Chicago Open311 API key |
| `TEBAKI_CORS_ORIGINS` | Allowed CORS origins for the engine (JSON list) |

### Accountability API

The public read surfaces are intentionally safe to expose to a resident-facing web app:

| Endpoint | Purpose |
|---|---|
| `/public/reports/{id}/timeline` | Report lifecycle from submission through filing/escalation |
| `/public/complaints/{id}` | Case dossier, source reports, evidence, citation, and timeline |
| `/public/runs` and `/public/runs/{id}` | Replayable agent runs and summarized tool activity |
| `/public/impact` | Aggregated neighborhood outcomes and SLA attention |
| `/public/proof` | Runtime, persistence, model, and workflow verification counters |

## Adding a city

Any city is a pull request: copy `cities/sandbox.yaml`, fill in boundary GeoJSON, channels (email / Open311 API / web form), regulations, and SLAs, then `.venv/bin/python cli/tebaki.py validate cities/<name>.yaml --strict`.

## License

MIT
