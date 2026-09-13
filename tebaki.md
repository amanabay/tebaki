# Tebaki (ጠባቂ) — The City's Guardian

**Agents for Humans Hackathon** · Strands Agents SDK · Deadline Sep 14, 2026 @ 5pm PDT
Track: **Good Neighbor Agents** · Language: Python (engine) + React/Vite/TS (web)

> **Pitch:** Every civic app makes the citizen do the follow-up. **Tebaki makes the government do the follow-up.** Residents report an issue once; a Strands agent triages reports nightly, clusters them into hotspots, drafts bilingual complaints citing the city's own regulations, files them through real channels, tracks every ticket against SLA clocks, auto-escalates stale cases up the official ladder — and surfaces exactly one kind of human interaction: a decision card. *Any city is a pull request.*

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

Residents submit issue reports via the **web app** (photo + GPS + one line). A Strands agent runs **every night**:

1. **Triage** — vision model classifies & validates each report (waste / pothole / streetlight / drain / water), severity score, dup-check.
2. **Cluster** — H3 + DBSCAN geospatial clustering → hotspots; dedupe across reports.
3. **Draft** — bilingual (Amharic/English) complaint, ward-mapped, citing the city's regulations via a Bedrock Knowledge Base.
4. **File** — send through real channels (email/SES, municipal web form via AgentCore Browser, Open311 API, sandbox).
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
  ├─ tools: H3/DBSCAN, SES email, AgentCore Browser (recorded), Open311, sandbox
  ├─ hooks: PII scrub, geo-fence, Cedar permissions · OTel → CloudWatch
  └─ deploy: Bedrock AgentCore Runtime (ECR via CodeBuild)
        ▲
Amazon EventBridge Scheduler (02:00 EAT nightly)
DynamoDB (state) · S3 (photos/recordings) · Bedrock KB (regulations/ward dir)
```

IaC: Terraform. CI/CD: GitHub Actions → CodeBuild → ECR → AgentCore Runtime. Custom domain + HTTPS.

---

## 5. Stack decision

| Layer | Choice | Why |
|---|---|---|
| Agent engine | **Python** (Strands Agents SDK) | Interrupts/HITL (decision cards) fully implemented; Evals SDK Python-first; deepest graph/steering/memory support; AgentCore Python deploy documented |
| Backend API | **FastAPI** | Hosts Strands engine; all AWS data-plane access in one place |
| Frontend | **React 19 + Vite + TS** | Pure SPA — no SSR needed; `vite-plugin-pwa` for installability + offline report drafts; Leaflet map; static S3+CloudFront deploy |
| Infra | Terraform | DynamoDB, S3, SES, EventBridge, AgentCore, CloudFront |

Note: Next.js-only rejected — Strands TS SDK lists interrupt support as "coming soon" (the centerpiece of this product), and Evals SDK is Python-only.

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
- `addis` — flagship: Amharic/English, Proclamation 513/2007, sub-city → federal grievance ladder, email + browser channels, real neighbors recruited.
- `chicago` — real **Open311 GeoReport v2** public server (the API channel actually files).
- `sandbox` — mock portal + LocalStack: offline dev/CI.

**CLI:** `tebaki init --city=X` (scaffold from OSM boundary + templates) and `tebaki validate cities/*.yaml` (schema, geo-fence, channel reachability, regulation docs, stat citation).

**Channel adapters (generic, zero city logic in code):** `EmailChannel` (SES), `BrowserChannel` (form-map), `ApiChannel` (Open311), `SandboxChannel`.

---

## 7. Strands design (max "Technological Implementation")

- Nightly orchestrator as a **Graph** (deterministic DAG + conditional edges) delegating to five **agents-as-tools** — not a single model call.
- **Interrupts (HITL)** on `file_complaint`: every filing pauses for approve/edit/drop; resumed from the web queue. The hackathon thesis implemented as architecture.
- **Hooks:** pre-file PII redaction, geo-fence check (inside city polygon), ward-field validation.
- **Cedar policy** limiting which tools the filer may invoke.
- **Memory:** AgentCore Memory + DynamoDB for SLA state across runs; Bedrock Knowledge Base for regs + ward directory.
- **Evals SDK suite in CI** (sandbox portal): TrajectoryEvaluator (right tools/order), goal-success, faithfulness on drafts, deterministic checks on ticket extraction, ~3 red-team cases (prompt injection via report text — show the guardrail works).
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
| Technological Implementation | Nightly autonomous Strands graph on AgentCore Runtime; interrupts; 4 channel adapters; evals in CI; hooks/Cedar/OTel; live demo URL |
| Design | Single Next-level web app: PWA intake + public dashboard + admin decision queue = complete product |
| Impact | One city done deeply (Addis, real filings, Amharic) + "any city is a pull request" portability multiplier |
| Creativity & Originality | The inversion: agent nags government so citizens don't; framework-not-app shape |
| Presentation | 5-min video; browser session recordings auto-capture the agent filing live; problem→who→why in first minute |

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
| **6** | Video (browser session recordings = footage) · architecture diagram · README · submit early · builder.aws.com post |

### Workflow discipline
- Every completed section: **git commit + check in with the user** before proceeding.

---

## 12. Committed vs deferred scope

**Committed:** Tebaki Engine (Strands graph + agents-as-tools + interrupts + hooks + OTel) · 3 City Packs (addis flagship) · React/Vite web app (PWA intake + public dashboard + admin queue) · 4 channel adapters (Email/Browser/Open311/Sandbox) · `tebaki init` + `tebaki validate` CLI · evals in CI · live demo URL on AgentCore.

**Deferred (documented, not built):** Telegram bot (extension guide — `IntakeAdapter` interface stubbed), VitePress docs, red-team beyond 3 cases, additional proof packs.

---

## 13. Open decisions made along the way

- City anchor: **Addis Ababa** (user's home turf → "built what you know" authenticity) with global plug-and-play via City Packs.
- Intake: **web app first**, Telegram as extension point (post-hackathon / buffer permitting).
- Chicago Open311 proof pack: **committed**.
- Stack: **Python/FastAPI + Strands** backend; **React+Vite** frontend (Next.js rejected — TS SDK lacks interrupts + evals).
