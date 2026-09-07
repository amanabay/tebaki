# Tebaki (ጠባቂ) — The City's Guardian

> Every civic app makes the citizen do the follow-up. **Tebaki makes the government do the follow-up.**

Residents report an issue once. A Strands agent triages reports nightly, clusters them into hotspots, drafts bilingual complaints citing the city's own regulations, files them through real channels, tracks every ticket against SLA clocks, auto-escalates stale cases up the official ladder — and surfaces exactly one kind of human interaction: a decision card.

**Built for the Agents for Humans Hackathon (Good Neighbor Agents track).**

## Repo layout

```
tebaki/
├─ engine/           Python: Strands orchestrator, FastAPI, tools, agents
├─ web/              React 19 + Vite + TS SPA/PWA (intake + dashboard + decision queue)
├─ cities/           City Packs: addis.yaml, chicago.yaml, sandbox.yaml (+ geojson/)
├─ infra/            Deployment configuration (populated during the build week)
├─ sandbox-portal/   Mock city portal for offline dev/CI/eval
├─ cli/              tebaki validate / run / demo / chase
└─ tebaki.md         Full plan (pitch, architecture, schedule)
```

## Quickstart

Everything runs offline against the sandbox city pack (mock portal + scripted model):

```bash
# 1. mock city complaint portal (terminal 1)
cd sandbox-portal && ../.venv/bin/uvicorn portal.app:app --port 9100

# 2. Tebaki engine API (terminal 2, repo root)
PYTHONPATH=engine:sandbox-portal .venv/bin/uvicorn app.api.main:app --port 8000

# 3. web app (terminal 3)
cd web && npm install && npm run dev   # http://localhost:5173
```

Try it: submit a report at `/report`, then hit **Run tonight's cycle** on the dashboard (or `curl -X POST localhost:8000/admin/nightly -H 'Content-Type: application/json' -d '{"auto_approve": false}'`). The draft appears under **Decisions** — approve it and the guardian files it with the mock portal and returns a real ticket id.

For persistence, run DynamoDB Local (`docker run -d -p 8000:8000 amazon/dynamodb-local:latest` — use a port other than 8000 if the engine owns 8000) and start the engine with `TEBAKI_STORE=dynamodb TEBAKI_DDB_ENDPOINT=<url> TEBAKI_DYNAMODB_TABLE=tebaki`.

For a live Bedrock run: `TEBAKI_LIVE_BEDROCK=1` on the engine (requires AWS credentials with Nova access). For real email filing: `TEBAKI_EMAIL_MODE=ses TEBAKI_SES_FROM=<verified-sender>`.

CLI: `.venv/bin/python cli/tebaki.py [validate|run|demo|chase] --city sandbox`.

### Environment variables

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Web app: engine API base URL (default `http://localhost:8000`) — set at build time for a deployed engine |
| `TEBAKI_STORE` | `dynamodb` to use the DynamoDB store (default: in-memory) |
| `TEBAKI_DDB_ENDPOINT` / `TEBAKI_DYNAMODB_TABLE` | DynamoDB endpoint (Local) / table name |
| `TEBAKI_LIVE_BEDROCK` | `1` to run agents on Bedrock (default: scripted offline model) |
| `TEBAKI_EMAIL_MODE` / `TEBAKI_SES_FROM` | `ses` + verified sender to send email filings for real |
| `TEBAKI_CHICAGO_311_KEY` | Chicago Open311 API key |
| `TEBAKI_CORS_ORIGINS` | Allowed CORS origins for the engine (JSON list) |

## Adding a city

Any city is a pull request: copy `cities/sandbox.yaml`, fill in boundary GeoJSON, channels (email / Open311 API / web form), regulations, and SLAs, then `.venv/bin/python cli/tebaki.py validate cities/<name>.yaml --strict`.

## License

MIT
