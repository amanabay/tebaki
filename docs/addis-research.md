# Addis Ababa City Pack — Research Checklist

Every `TODO-RESEARCH` marker in `cities/addis.yaml` maps to a task below.
`tebaki validate cities/addis.yaml --strict` (engine: `app.city_pack.validate_pack_file(strict=True)`) passes only when all are resolved. Fill findings directly into the pack YAML + this doc's findings table.

## Tasks

### 1. Citable pitch stat (blocks: `pitch`)
- [ ] Find one citable number quantifying the problem in Addis (waste generation vs collection, or service-request non-response).
- Candidate sources (verify, don't trust from memory):
  - World Bank — *What a Waste 2.0* (country/city waste profiles)
  - Addis Ababa Cleansing Management Agency reports / city government statistics
  - UN-Habitat Addis Ababa solid waste studies
- [ ] Record exact number + full citation (title, year, page/URL) in findings table.
- [ ] Replace `TODO-RESEARCH` in `cities/addis.yaml` → `pitch.number`, `pitch.source`.

### 2. Sub-city boundary GeoJSON (blocks: `boundary`, `admin` ward mapping)
- [ ] Extract Addis Ababa admin boundaries from OpenStreetMap (10+1 sub-cities: e.g. Addis Ketema, Akaki Kality, Arada, Bole, Gullele, Kirkos, Kolfe Keranio, Lideta, Nifas Silk Lafto, Yeka, Lemi Kura).
  - Option A: overpass-turbo query `admin_level=*` for the city, export GeoJSON.
  - Option B: geoBoundaries (ADM2 for Ethiopia), clip to Addis.
- [ ] Save as `cities/geojson/addis.geojson` (FeatureCollection, one Feature per sub-city, `properties.name` = sub-city name, `properties.admin_level = "sub-city"`).
- [ ] Update `boundary.note` to record provenance (source, extract date, license — ODbL attribution for OSM).

### 3. Real filing contacts (blocks: `channels.email`, `channels.escalation`)
- [ ] Find ≥1 real, reachable email (or verifiable contact route) for: a sub-city sanitation/beautification office; at least one rung of the escalation ladder.
- Candidate sources: city government directory pages, sub-city office pages, Ethiopian Federal Grievance Handling portal (complaint submission route), local news articles citing official contacts.
- [ ] Record each: office name, address/URL, date verified, language of correspondence (am/en).
- [ ] Fill `channels.email[0].address`, escalation emails in `cities/addis.yaml`; remove `@placeholder.invalid`.
- Fallback if no public emails verifiable in time: switch the Addis email channel to the Federal Grievance Handling online form via the Browser channel, and note the pivot in the findings table.

### 4. Regulation document (blocks: `regulations[0].doc`)
- [ ] Obtain the Solid Waste Management Proclamation No. 513/2007 PDF ( Ethiopian Federal Negarit Gazeta, or an official/academic mirror).
- [ ] Verify: urban administration duties on collection/disposal (cite the specific articles, e.g. duties of urban administrations).
- [ ] Save as `cities/docs/proc513.pdf` (path is relative to `cities/`), update `regulations[0].doc`.
- [ ] Extract the 2–4 most relevant articles as text for the Bedrock Knowledge Base seed.

### 5. Portal form for Browser channel (optional, Day 3+)
- [ ] If a public Addis grievance web form exists, capture URL + field ids → fill `channels.browser` (url, form_map) in `cities/addis.yaml`.
- Else keep `browser: null` and rely on email channel.

## Findings table (fill as you go)

| # | Finding | Source | Verified (date) | Applied to pack |
|---|---------|--------|-----------------|-----------------|
| 1 | _pending_ | | | |
| 2 | _pending_ | | | |
| 3 | _pending_ | | | |
| 4 | _pending_ | | | |
| 5 | _pending_ | | | |

## Rules

- Never invent numbers, emails, or citations — only verified entries, with source + date.
- One verified source beats five half-remembered ones.
- When something can't be verified in time, pivot the channel design (see task 3 fallback) rather than fake the data.
