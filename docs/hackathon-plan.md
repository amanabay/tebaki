# Tebaki — Hackathon plan (Good Neighbor Agents)

**Track:** Good Neighbor Agents — *an agent that helps groups of people, not just one* (neighborhoods, nonprofits, schools, local orgs).
**Official rules:** [agentsforhumans.devpost.com](https://agentsforhumans.devpost.com/)
**Official deadline:** Monday Sep 14, 2026 @ 5:00pm PDT
**Our deadline:** Sunday Sep 13, 8:00pm (buffer before the official cut)

Judging criteria are **equally weighted**. Tie-break order: Technical Implementation → Design → Impact → Creativity → Presentation. A live demo and/or AgentCore **explicitly** raise Technical Implementation. builder.aws.com posts add up to **0.6 bonus points** (0.2 each, max 3). Title must include **Agents for Humans**.

---

## Calendar

| When | Mode | Done when |
|---|---|---|
| **Mon 7 – Thu 10** | **Code freeze Thursday night.** All product, engine, tests, and a working live URL. | Judges can click report → Run tonight → approve → ticket → chase without curling. |
| **Fri 11 – Sat 12** | **Polish.** No new features. README, architecture diagram, UI copy, seeded demo, builder.aws posts, video dry-run. | **Fri 11, 12:00pm PT:** AWS credits form (hard close). |
| **Sun 13** | **Video + submit, 8:00pm.** | Devpost form locked with public repo, MIT in About, Builder ID, live URL, diagram, video. |

Do not start new engine features on Friday. If something is unfinished Thursday night, cut it and document it as out of scope — do not slip video into Monday.

---

## What we already have (do not rewrite)

The engine is a real Strands product, not a chatbot wrapper:

- **Graph** `triage → cluster → drafter` with conditional edges (`engine/app/agents/nightly_graph.py`)
- **HITL interrupts** on `file_complaint` — approve / edit / drop from the web queue
- **Chaser agent** with SLA clocks and a 3-rung escalation ladder
- **City Packs** as data, engine as code (`cities/*.yaml`)
- **Channels:** sandbox portal, Open311, SES, and Gmail SMTP (human-approved production path)
- **Web:** night-watch dashboard, bilingual masthead, decision cards, map, ledger, scoreboard, evidence, impact, and replay
- **97 tests** + CI; **DynamoDB store** already implemented

The pitch is distinctive: *every civic app makes the citizen do the follow-up; Tebaki makes the government do the follow-up.* Clustering several neighbor reports into one complaint **is** the Good Neighbor mechanic. The case timeline, evidence drawer, impact view, and run replay now make that story visible in the product.

---

## Honest gap vs. `tebaki.md`

| Promised | Actual |
|---|---|
| Photo + GPS + one line; vision triage | GPS + note only. `photo_key` exists on `Report` but intake never uploads. Category is user-picked. |
| Bilingual Amharic/English drafts + KB-cited regs | Scripted drafter is English-only. Cite is a YAML string. Amharic is detected, never written. |
| Addis flagship (real emails, OSM sub-cities, Proc. 513/2007, citable stat) | City-level boundary, source-linked regulation/statistics, Gmail SMTP for human-approved filing, and a verified Bole pilot polygon are present; routing outside Bole remains city-level fallback. |
| AgentCore Browser channel (recorded) | Form map exists in sandbox YAML; **no `BrowserChannel` class**. Escalation letters are logged, not sent. |
| Nightly cycle files **and** chases | `run_nightly_cycle` does not call `run_chase`. Two separate admin endpoints. |
| Hooks: PII, geo-fence, Cedar; OTel | Only `filing_approval_hook`. |
| Evals in CI, AgentCore Runtime, EventBridge, Terraform | AgentCore runtime/deployment helper, durable run evidence, and browser-safe proxy template are present; EventBridge schedule and live URL remain deployment work. |
| PWA, `tebaki init` | Manifest exists; no service worker. CLI has validate/run/demo/chase, not `init`. |
| Live Bedrock demo | Factory exists. Live smoke was blocked by **account daily token quota**. |

Judges score what they can **see working**.

---

## Track fit: already close, not yet obvious

Good Neighbor is **groups, not one person**. Stay on civic-neighborhood. Do **not** pivot to mutual-aid / food-bank / tool-lending — the chase inversion is the originality score.

Three things currently hide the track:

1. **Clustering must remain visible.** The case dossier now exposes linked reports, corroboration counts, evidence, and the full agent timeline.
2. **The group must hear back.** Public case views expose ticket, SLA, and escalation state after filing.
3. **Addis claims must stay honest.** The pack links boundary/contact claims to sources; Bole is a verified pilot polygon and every other area remains city-level fallback.

---

## Code week (Mon 7 – Thu 10)

Ship in this order. Later items die if Thursday slips.

### Mon 7 / Tue 8 — neighborhood story + demoable loop

The product must be operable without curl, and the Good Neighbor story must be visible.

1. **Addis pack, for real** (`cities/addis.yaml`, `cities/geojson/addis.geojson`, `docs/addis-research.md`)
   - One **citable** waste/collection or non-response number + source URL (World Bank *What a Waste*, UN-Habitat, or city CMA). Never invent.
   - OSM / geoBoundaries **sub-city** GeoJSON with real names (Bole, Kirkos, Yeka, …).
   - Proclamation 513/2007: cite + 2–4 article excerpts in-repo as text (PDF optional).
   - Contacts: do **not** leave `@placeholder.invalid`. If no public sub-city email verifies, pivot Addis to SES → a verified demo inbox *labelled as such*, or the Federal grievance form. The research doc already allows this pivot.
2. **`geo.py` MultiPolygon.** OSM extracts will otherwise be silently dropped (`load_boundary_features` filters `type == "Polygon"` only).
3. **Dashboard "Run tonight" + "Chase now."** `api.runNightly` / `api.runChase` already exist in `web/src/lib/api.ts` and are unused. Default Run tonight to **paused** so decision cards appear.
4. **Chase inside the nightly cycle.** One button should triage → cluster → draft → interrupt → (after approve) file → chase. Escalation must **send** through the channel (sandbox POST or SES), not only append `escalation_log`.
5. **Cluster story on cards + ledger.** Report notes, count, "3 neighbors → 1 complaint," map pins for the merged cluster.
6. **Reporter loop + SLA.** After filing, original reports / a public ticket view show ticket id + ack/resolve deadlines. Scoreboard tracks filed, acknowledged, resolved, and escalated states.
7. **Geo-fence + PII hooks** on `BeforeToolCallEvent` for `file_complaint` (drop out-of-city points; redact phones/names). Surface hits in the night log. This is the extra Strands surface judges look for.

**Mon/Tue done when:** sandbox E2E from the web — two nearby waste reports + one pothole → Run tonight → two cards, one of them "2 neighbors merged" → approve → ticket → Chase (or auto-chase after file) → night log shows it. Addis scoreboard shows real sub-city names on seeded points.

### Wed 9 — product complete + Strands depth

8. **Photo on intake** (camera on mobile). Store bytes or S3 key; show it on the decision card. Vision classification can wait — the photo makes it civic.
9. **Bilingual drafts + UI toggle.** Drafter emits `text_am` + `text_en` when the pack has `am`. Scripted model must do this too, not only Bedrock. Toggle on Report, Decisions, and key dashboard labels.
10. **Complaint detail page.** Click a ledger row: draft, ticket, SLA countdown, escalation log, linked reports.
11. **Seed dataset** (Bole / Kirkos hotspots) so the live URL is never empty.
12. **Persist paused filings** (or a sticky single instance). `_registry.paused` is process-local (`engine/app/agents/registry.py`) — a restart makes HITL 409. Required for judges clicking hours later.
13. **2–3 evals in CI.** Trajectory (triage then cluster), faithfulness (draft cite matches pack regulation), one prompt-injection / geo-fence block. Wire into `.github/workflows/ci.yml`.
14. **`BrowserChannel`** against the sandbox portal if time (Playwright is enough if AgentCore Browser is heavy). Footage for Sunday.

**Wed done when:** photo + Amharic draft are in the decision card; evals green in CI; approve still works after an engine restart (or the deploy plan is "one sticky process" and documented).

### Thu 10 — live URL, then code freeze

15. **Live demo URL.** AgentCore Runtime preferred (explicit Technical Implementation boost). App Runner / Fargate is an acceptable fallback — a working URL beats empty `infra/`. DynamoDB persistence. Bedrock on in prod if quota allows; if not, ScriptedModel on the live URL is honest, and the video says so once.
16. **Bedrock quota + credits.** Confirm Nova access. Credits form closes **Fri 11, 12:00pm PT** — request Thursday if not already done, confirm Friday morning.
17. Freeze. Anything not on this list is cut.

**Thu done when:** public URL runs the Mon/Tue E2E. README has the URL even if the rest of the README is still thin.

Chicago Open311 is a portability proof, not the flagship. Demo **Addis**. Request the Chicago key only if it takes <30 minutes.

---

## Polish (Fri 11 – Sat 12)

No new features. If a bug blocks the video path, fix only that.

### Friday 11

- **Before noon PT:** AWS credits form — [https://forms.gle/6sjzKiX6bKUMA5NEA](https://forms.gle/6sjzKiX6bKUMA5NEA)
- Architecture diagram (Graph + interrupt + chase as the nervous system; City Pack as the plug). Export PNG into `docs/`.
- README rewrite for judges (they may never run the CLI):
  - One-paragraph pitch + track name
  - Live demo + seeded scenario
  - Diagram
  - Strands features used (graph, interrupts, hooks, evals, AgentCore) as a table
  - "Add a city" in 10 lines
  - Honest demo vs production
- Confirm GitHub repo is **public**, MIT license detected in **About**, AWS Builder ID ready.
- First builder.aws.com post. Title includes **Agents for Humans**. Suggested topics: (1) City Packs as data, (2) Strands interrupts as civic HITL, (3) Addis research + bilingual drafting.
- Dry-run the video path on the **live URL**. Write a shot list. Fix whatever broke.

### Saturday 12

- UI copy pass: night log in guardian voice (expand `web/src/lib/strings.ts`); decision card framed as *"Complaint #C-… goes to the Bole sanitation office tomorrow — approve, edit, or drop?"*
- Pitch stat on the dashboard hero (the citable Addis number).
- Two remaining builder.aws posts (hit the 0.6 cap).
- Seed data looks good on first load. Empty states are intentional, not broken.
- Confirm the live URL still files a ticket. Do not redeploy unless it is down.

---

## Sunday 13 — video and submit (8:00pm)

### Video (keep under 4 minutes; 5 min hard cap)

Record from the **live URL**, not localhost.

| Time | Beat |
|---|---|
| 0:00–0:40 | Problem: civic reports vanish; one citable Addis number; *who* = neighbors / iddirs / resident groups, not "users." |
| 0:40–1:10 | Three reports on the same block (photo if it works). Map lights up. |
| 1:10–2:20 | Run tonight. Night log: triage, cluster (3→1), bilingual draft citing 513/2007, **interrupt**. Approve. Ticket id. |
| 2:20–3:10 | Fast-forward SLA: chase, escalation to the next rung, scoreboard ticks. "The neighbors did not chase anyone." |
| 3:10–3:50 | City Pack YAML: Addis vs Chicago vs sandbox. "Any city is a pull request." Diagram, 10 seconds. |
| 3:50–4:00 | Close on the inversion line. |

Upload to YouTube or Vimeo, **public**. Pitch must cover (1) problem (2) who (3) why — required.

### Submit by 8:00pm

Devpost fields:

- Track: **Good Neighbor Agents**
- Text description
- **Public** repo URL
- README, architecture diagram, MIT in About
- Video URL
- AWS Builder ID
- Live demo URL
- builder.aws.com post URLs (bonus)

After 8:00pm Sunday, do not touch the Devpost form. The official window stays open until Monday 5:00pm PDT — that is emergency-only (dead live URL, private video). Repo commits after submit are allowed by Devpost but do not change what judges were handed; treat Sunday 8:00pm as the real freeze.

---

## What we are not building this week

Telegram, Cedar, OTel, Bedrock Knowledge Base, `tebaki init`, vision-model classification, full Terraform of every box in `tebaki.md`, extra city packs, red-team beyond 3 evals, auth, full PWA offline queue, city switcher in the nav.

Listing these as "not yet" in the README is honest. Shipping a half-wired Cedar file is worse.

---

## Risks

1. **Live demo is ScriptedModel + empty Addis scoreboard.** Looks mocked. AWS judges will notice. Unblock Bedrock quota Monday; if it stays dead, say so once in the video and show the factory seam.
2. **Credits form missed Friday noon PT.** $50 is gone. Request Thursday.
3. **Paused HITL dies on deploy restart.** Judges approve and get 409. Persist or keep one sticky instance.
4. **Video is architecture talk without a ticket id.** Presentation is *demonstrate the project working.*
5. **Thursday slip eats Sunday.** Cut BrowserChannel, photo, then bilingual UI — never cut the live URL, cluster story, or video.
6. **Track drift.** A chatbot or generic "AI 311" weakens Stage One (theme fit) and originality.

---

## Files the code week will touch

- `cities/addis.yaml`, `cities/geojson/addis.geojson`, `docs/addis-research.md`
- `engine/app/orchestrator.py` — chase in nightly; escalation send
- `engine/app/agents/roles.py` + new hooks module — PII, geo-fence
- `engine/app/agents/scripted_model.py` + drafter prompt — bilingual
- `engine/app/geo.py` — MultiPolygon
- `engine/app/api/main.py` — scoreboard resolved; photo; public ticket view
- `engine/app/agents/registry.py` — persist paused filings
- `engine/app/channels.py` — BrowserChannel; escalation send
- `web/src/pages/{Dashboard,Decisions,Report}.tsx`, `web/src/lib/strings.ts`
- `README.md`, `docs/architecture.png`
- `.github/workflows/ci.yml` + eval tests
- `infra/` — only what is required for a public URL

---

## Criteria → this plan

| Criterion | How we score it |
|---|---|
| **Technical Implementation** | Graph + interrupts already real. Add hooks, evals, chase-in-cycle, live URL, AgentCore if quota allows. |
| **Design** | Run tonight on the dashboard; cluster story; photo; bilingual toggle; complaint detail; seeded live URL. |
| **Potential Impact** | Real Addis pack (stat, sub-cities, excerpts); reporter loop; pitch stat on the hero and in the first 40s of video. |
| **Creativity & Originality** | Protect the inversion. The interrupt **is** the product. Do not add a chatbot. |
| **Presentation** | 4-min live-URL video, diagram, judge README, submit Sunday 8pm. |
| **Bonus (0.6)** | Three builder.aws.com posts, Fri–Sat, title contains Agents for Humans. |
