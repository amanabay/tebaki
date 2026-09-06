# Chicago City Pack — Research Checklist

The `chicago.yaml` pack files via the Open311 GeoReport v2 API once the
service codes below are researched. `tebaki validate cities/chicago.yaml
--strict` passes only when `service_code_map` is filled.

## Tasks

### 1. Verify the endpoints (browser — this machine cannot resolve them)
- [ ] Production: open `https://311api.chicago.gov/open311/v2/services.json?jurisdiction_id=chicago.gov` in a browser; confirm a JSON services list loads.
- [ ] Test endpoint: check `http://test311api.cityofchicago.org/open311/v2/services.json?jurisdiction_id=chicago.gov` — historically allowed unauthenticated test POSTs.
- If production 403s without a key, that's expected — key needed for writes.

### 2. Map our categories to service codes
From the services list, find service codes for (paste the JSON for me and I'll pick):
- [ ] `waste` — garbage/sanitation complaints (e.g., garbage cart, alley cleanup, tree debris)
- [ ] `pothole` — pothole complaints
- [ ] `streetlight` — street light out / alley light out
- [ ] `drain` — sewer/drain/street flooding complaints
- [ ] `water` — water main/leak complaints
- [ ] Fill `service_code_map` in `cities/chicago.yaml`; remove the TODO-RESEARCH block.

### 3. API key
- [ ] Chicago requires an API key for production POSTs. Check the Open311 wiki (wiki.open311.org/GeoReport_v2/Servers) or Chicago 311 developer resources for the key request process. Store it as `TEBAKI_CHICAGO_311_KEY` in the environment at runtime.
- If no key is obtainable in time: pivot the proof to the test endpoint (if it accepts writes), or keep Chicago as a "channel wired, awaiting credentials" entry — the adapter is what matters for the demo.

## Findings table

| # | Finding | Source | Verified (date) | Applied to pack |
|---|---------|--------|-----------------|-----------------|
| 1 | _pending_ | | | |
| 2 | _pending_ | | | |
| 3 | _pending_ | | | |

## Rules

- Never guess service codes — a wrong code means the city silently misroutes the complaint.
- One verified endpoint beats three half-remembered ones.
