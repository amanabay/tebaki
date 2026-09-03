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
├─ infra/            Terraform: DynamoDB, S3, SES, EventBridge, AgentCore, CloudFront
├─ sandbox-portal/   Mock city portal for offline dev/CI/eval
├─ cli/              tebaki init / validate
└─ tebaki.md         Full plan (pitch, architecture, schedule)
```

## Quickstart

_(placeholder — populated as build progresses)_

## License

MIT
