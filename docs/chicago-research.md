# Chicago City Pack — Research Checklist

The `chicago.yaml` pack files via the Open311 GeoReport v2 API.

## Completed research

### 1. Endpoints (verified 2026-09-06)
- [x] Production services list: `http://311api.cityofchicago.org/open311/v2/services.json?jurisdiction_id=cityofchicago.org` (124 services, live)
- [x] Write endpoint: `http://311api.cityofchicago.org/open311/v2/requests.json` (in pack)
- [x] Jurisdiction id: `cityofchicago.org`
- Note: an older `311api.chicago.gov` URL floats around stale references — it does not resolve. The canonical Open311 wiki entry uses `cityofchicago.org` hosts.

### 2. Service code map (from live services list)
- [x] `waste` → `4fd3b750e750846c5300001d` (Sanitation Code Violation)
- [x] `pothole` → `4fd3b656e750846c53000004` (Pothole in Street Complaint)
- [x] `streetlight` → `4ffa9f2d6018277d400000c8` (Street Light Out Complaint)
- [x] `drain` → `5c1849d39e6e99eda0add40a` (Sewer Cleaning Inspection Request)
- [x] `water` → `5c1849cc9e6e99eda0ada57e` (Water On Street Complaint)

## Open tasks

### 3. API key (blocks real filings, not the adapter)
- [ ] Request a production key via `http://311api.cityofchicago.org/open311/v2/apps/new` (City of Chicago Open311 app registration). Store it as `TEBAKI_CHICAGO_311_KEY` at runtime.
- [ ] Test endpoint `http://test311api.cityofchicago.org/open311/v2/...` may accept unauthenticated test POSTs — verify before requesting a production key.
- Until a key exists, the adapter is complete and stub-tested; filings against production will return the city's auth error (clean failure).

## Findings table

| # | Finding | Source | Verified (date) | Applied to pack |
|---|---------|--------|-----------------|-----------------|
| 1 | Production/test endpoints + jurisdiction id | Open311 wiki servers list | 2026-09-06 | endpoint, jurisdiction_id |
| 2 | 5 category service codes | Live services.json (124 services) | 2026-09-06 | service_code_map |
| 3 | _API key request pending_ | | | |

## Rules

- Never guess service codes — a wrong code means the city silently misroutes the complaint.
- One verified endpoint beats three half-remembered ones.
