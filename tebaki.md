# Tebaki (ጠባቂ) — The City's Guardian

**Agents for Humans Hackathon** · Strands Agents SDK · Deadline Sep 14, 2026 @ 5pm PDT
Track: **Good Neighbor Agents** · Language: Python (engine) + React/Vite/TS (web)

> **Implementation status — 14 Sep 2026:** This document preserves the original
> product plan. Claims marked optional, roadmap, or deferred are not part of
> the deployed surface. For current behavior and live links, use `README.md`
> and `docs/demo-runbook.md`.

> **Pitch:** Every civic app makes the citizen do the follow-up. **Tebaki makes the government do the follow-up.** Residents report an issue once; a Strands guardian triages it immediately, then a supervised graph clusters reports, drafts evidence-backed complaints citing the city's regulations, files them through a configured channel, tracks SLA clocks, and escalates stale cases — with every external action paused behind one human decision card. *Any city is a pull request.*

---

## 1. Problem & who it's for

- Civic complaints in most cities vanish into a void: no acknowledgment, no tracking, no deadline, no escalation.
- Municipal administrations are legally obliged to act (e.g., Ethiopia's **Solid Waste Management Proclamation No. 513/2007**) — but nobody chases them.
- Residents pay the cost in time, health, and environment (blocked drains → flooding; uncollected waste; dead streetlights → safety).
- **Audience:** neighbors and resident groups in Addis Ababa first; then any city via City Packs.

### Reference stat (Day-1 research, must be citable — never guessed)
`pitch: {number: <Addis waste/day>, source: <World Bank What a Waste / city report>}`

---

## 2. Inspiration

Tebaki is inspired by the lack of effective civic reporting systems in my city.

## 3. Product concept

Residents submit issue reports via the **web app** (optional photo + GPS + one line). A lightweight guardian triages each report immediately; the supervised Strands graph runs on demand locally and nightly in production:

1. **Triage** — vision model classifies & validates each report (waste / pothole / streetlight / drain / water), severity score, dup-check.
2. **Cluster** — H3 + DBSCAN geospatial clustering → hotspots; dedupe across reports.
3. **Draft** — language-aware, ward-mapped complaint citing the regulation supplied by the City Pack.
4. **File** — send through the configured channel (Gmail SMTP/SES, Open311 API, or sandbox; Browser is an extension point and is not configured for Addis).
5. **Chase** — per-ticket SLA clocks (acknowledge/resolve), auto-escalation up the official ladder (sub-city → city → federal).
6. **Surface** — exactly one human interaction: a decision card — *"Complaint #4312 goes to the ward officer tomorrow — approve, edit, or drop?"*

Public dashboard: live map, complaint ledger, **sub-city responsiveness scoreboard** (am/en), "what the agent did last night" activity feed, decision queue.

---

## 4. Architecture (AWS)

```
Web PWA (React+Vite) on S3 + CloudFront
        │ report (photo→S3 presign, GPS, text)
        ▼
FastAPI (Python 3.12, uv) — single backend surface; hosts Strands engine
  ├─ /reports   intake
  ├─ /decisions decision queue (approve/edit/drop → resumes interrupts)
  ├─ /public    ledger, scoreboard, activity feed, map data
  └─ /health
        ▼
Strands orchestrator (graph + agents-as-tools)
  ├─ triage / cluster / drafter / filer / chaser agents
  ├─ interrupts → decision cards (DynamoDB queue)
  ├─ tools: deterministic spatial clustering, SMTP/SES, Open311, sandbox
  ├─ hooks: PII scrub, geo-fence, evidence gate, durable HITL
  └─ deploy: Bedrock AgentCore Runtime (Docker → ECR)
        ▲
Optional EventBridge Scheduler (02:00 EAT nightly)
DynamoDB (state) · City Packs (regulations, contacts, boundaries)
```

Deployment today: Docker/BuildKit → ECR → AgentCore Runtime via `infra/deploy_agentcore.py`; the browser-safe proxy and nightly trigger are defined in the optional SAM template. CloudFront serves the deployed SPA.

---

## 5. Stack decision

| Layer | Choice | Why |
|---|---|---|
| Agent engine | **Python** (Strands Agents SDK) | Graph orchestration, tool calls, durable interrupts, and a shared scripted/live model seam |
| Backend API | **FastAPI** | Hosts Strands engine; all AWS data-plane access in one place |
| Frontend | **React 19 + Vite + TS** | Pure SPA — no SSR needed; `vite-plugin-pwa` for installability + offline report drafts; Leaflet map; static S3+CloudFront deploy |
| Infra | Docker + AgentCore helper; optional SAM template | DynamoDB, ECR, AgentCore, API Gateway/Lambda proxy, EventBridge, CloudFront |

Note: Next.js-only was rejected because the Python runtime is the tested path for Strands interrupts and durable resume behavior.

---

## 6. Plug-and-play: Tebaki Engine + City Packs

Engine is **code**; cities are **data**. A City Pack is one validated YAML:

```yaml
city: {name, local_name, languages: [am, en], timezone, locale}
boundary: {geojson: ...}                        # OSM-extractable polygon
admin: [{level: sub-city, source: geojson}, {level: woreda}]   # arbitrary depth
channels:                                       # any mix, all optional
  email:    [{target, address, lang}]           # universal fallback
  browser:  {url, form_map}                     # AgentCore Browser, recorded
  api:      {type: open311, endpoint, key}      # Chicago, Toronto, SF, DC...
  escalation: [level1, level2, federal]
regulations: [{cite, doc}]                      # per-city legal teeth
sla: {acknowledge_days, resolve_days}
pitch: {number, source}
```

**Ships with 3 packs:**
- `addis` — flagship: Amharic/English intake, Proclamation 513/2007, sub-city → federal grievance ladder, human-approved Gmail SMTP, and a verified Bole pilot polygon with city fallback elsewhere.
- `chicago` — real **Open311 GeoReport v2** public server (the API channel actually files).
- `sandbox` — mock portal + LocalStack: offline dev/CI.

**CLI:** `tebaki init --city=X` (scaffold from OSM boundary + templates) and `tebaki validate cities/*.yaml` (schema, geo-fence, channel reachability, regulation docs, stat citation).

**Channel adapters (generic, zero city logic in code):** `EmailChannel` (SMTP), `SESEmailChannel`, `Open311Channel`, and `SandboxChannel`. Browser form maps remain an extension point.

---

## 7. Strands design (max "Technological Implementation")

- Nightly orchestrator as a **Graph** (deterministic DAG + conditional edges) delegating to five **agents-as-tools** — not a single model call.
- **Interrupts (HITL)** on `file_complaint`: every filing pauses for approve/edit/drop; resumed from the web queue. The hackathon thesis implemented as architecture.
- **Hooks:** pre-file PII redaction, geo-fence check (inside city polygon), ward-field validation.
- **Safety:** PII redaction, city boundary checks, evidence gates, and a durable human approval interrupt protect the external filing boundary.
- **Durability:** DynamoDB persists reports, complaints, decision cards, and run activity across restarts; the same store carries SLA state between chases.
- **Verification:** focused regression tests cover clustering, geo-fencing, evidence gates, channel behavior, durable HITL, and sandbox escalation. A full Python 3.12 runtime-loop pass remains a release task; Python 3.14 isolates the known TestClient/Strands deadlock.
- **ContextInjector** (run clock/city context), **structured output** (Pydantic complaint objects), retry strategies, per-run **metrics** (tokens/tool calls) surfaced on the dashboard.

---

## 8. Data model (DynamoDB single table)

`Report` (id, reporter, photo S3, geo, category, severity, embedding)
`Complaint` (report refs, ward, draft, status: draft→awaiting_approval→filed→acknowledged→resolved→escalated_1..3, ticket_id, channel, SLA clocks)
`DecisionCard` · `AgentRun` (nightly log: tool calls, tokens, outcomes) · `Ward` (contacts, boundaries, scoreboard cache)

---

## 9. Scoring alignment

| Criterion | How Tebaki addresses it |
|---|---|
| Technological Implementation | Strands graph on AgentCore Runtime; five agents-as-tools; durable interrupts; SMTP/SES/Open311/Sandbox channels; geo/privacy/evidence guardrails; live demo URL |
| Design | One coherent web app: resident intake, public impact view, case dossier, replay, and operator decision queue |
| Impact | One honest Addis pilot with human-approved filing and a public neighborhood view, plus City Packs that make new cities portable |
| Creativity & Originality | The inversion: agent nags government so citizens don't; framework-not-app shape |
| Presentation | 5-min story-led demo; problem, agent evidence, human approval, and measurable follow-through are visible in the UI |

---

## 10. Deliverables

Public repo (MIT) · architecture diagram · ≤5-min demo video · **live demo URL** · AWS Builder ID · **builder.aws.com build-story post** (bonus points) · README with pitch + "any city is a PR" + Telegram extension guide.

---

## 11. Build schedule — 6 coding/testing days (started Sep 3, due Sep 14 5pm PDT)

| Day | Work |
|---|---|
| **1** | Repo scaffold · City Pack schema + addis/sandbox/chicago YAML · sandbox mock portal + LocalStack · Addis research (stat, GeoJSON, emails, proclamation PDF) · Strands orchestrator skeleton |
| **2** | Triage (vision, Amharic-aware) / cluster (H3+DBSCAN) / drafter (bilingual, KB-backed) agents · interrupt decision-card loop · full nightly cycle green E2E on sandbox |
| **3** | Filer channels: SES email + AgentCore Browser (recording on) + Chicago Open311 adapter · AgentCore Runtime deploy · EventBridge nightly cron live |
| **4** | Web app: PWA report intake (photo+GPS+one line) · public map/ledger/scoreboard/activity feed · admin decision queue — one deploy on CloudFront |
| **5** | Testing: real Addis filing E2E · Chicago live-API test · evals in CI · recruit neighbors for real reports · bug fixes · *if clean: build Telegram adapter* |
| **6** | Story-led screen recording · architecture diagram · README · submit early · builder.aws.com post |

### Workflow discipline
- Every completed section: **git commit + check in with the user** before proceeding.

---

## 12. Committed vs deferred scope

**Committed:** Tebaki Engine (Strands graph + agents-as-tools + durable interrupts + guardrails) · 3 City Packs (Addis flagship) · React/Vite web app (intake + public dashboard + admin queue) · SMTP/SES/Open311/Sandbox adapters · `tebaki validate` CLI · focused regression tests · live demo URL on AgentCore.

**Deferred (documented, not built):** Telegram bot (extension guide — `IntakeAdapter` interface stubbed), VitePress docs, red-team beyond 3 cases, additional proof packs.

---

## 13. Open decisions made along the way

- City anchor: **Addis Ababa** (user's home turf → "built what you know" authenticity) with global plug-and-play via City Packs.
- Intake: **web app first**, Telegram as extension point (post-hackathon / buffer permitting).
- Chicago Open311 proof pack: **committed**.
- Stack: **Python/FastAPI + Strands** backend; **React+Vite** frontend (Next.js rejected — TS SDK lacks interrupts + evals).
