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
- [x] Replace `TODO-RESEARCH` in `cities/addis.yaml` → `pitch.number`, `pitch.source`.

### 2. Sub-city boundary GeoJSON (blocks: `boundary`, `admin` ward mapping)
- [ ] Import the full public Addis sub-city layer (10+1 sub-cities: e.g. Addis Ketema, Akaki Kality, Arada, Bole, Gullele, Kirkos, Kolfe Keranio, Lideta, Nifas Silk Lafto, Yeka, Lemi Kura). Tebaki now includes a verified Bole pilot polygon and retains the city-level extent as a safe fallback elsewhere.
  - Option A: overpass-turbo query `admin_level=*` for the city, export GeoJSON.
  - Option B: geoBoundaries (ADM2 for Ethiopia), clip to Addis.
- [ ] Save as `cities/geojson/addis.geojson` (FeatureCollection, one Feature per sub-city, `properties.name` = sub-city name, `properties.admin_level = "sub-city"`).
- [ ] Update `boundary.note` to record provenance (source, extract date, license — ODbL attribution for OSM).
  - The public layer is catalogued as **“Addis Ababa city administrative sub cities”** by the Water and Land Resource Center / Addis Ababa University; its live WFS endpoint was unavailable during the 2026-09-12 retrieval attempt. The Ethiopian National Agri Data Hub WFS did provide a Bole sub-city boundary, which is now vendored as a verified pilot. Tebaki remains `city_fallback` outside Bole until the full layer is validated.

### 3. Real filing contacts (blocks: `channels.email`, `channels.escalation`)
- [ ] Find ≥1 real, reachable email (or verifiable contact route) for: a sub-city sanitation/beautification office; at least one rung of the escalation ladder.
- Candidate sources: city government directory pages, sub-city office pages, Ethiopian Federal Grievance Handling portal (complaint submission route), local news articles citing official contacts.
- [ ] Record each: office name, address/URL, date verified, language of correspondence (am/en).
- [x] Fill `channels.email[0].address`, escalation emails in `cities/addis.yaml`; remove `@placeholder.invalid`.
- Fallback if no public emails verifiable in time: switch the Addis email channel to the Federal Grievance Handling online form via the Browser channel, and note the pivot in the findings table.

### 4. Regulation document (blocks: `regulations[0].doc`)
- [x] Obtain a public source link for the Solid Waste Management Proclamation No. 513/2007 (the PDF remains an optional vendored artifact).
- [ ] Verify: urban administration duties on collection/disposal (cite the specific articles, e.g. duties of urban administrations).
- [ ] Save as `cities/docs/proc513.pdf` (path is relative to `cities/`), update `regulations[0].doc`.
- [ ] Extract the 2–4 most relevant articles as text for the Bedrock Knowledge Base seed.

### 5. Portal form for Browser channel (optional, Day 3+)
- [ ] If a public Addis grievance web form exists, capture URL + field ids → fill `channels.browser` (url, form_map) in `cities/addis.yaml`.
- Else keep `browser: null` and rely on email channel.

## Findings table (fill as you go)

| # | Finding | Source | Verified (date) | Applied to pack |
|---|---------|--------|-----------------|-----------------|
| 1 | 2,647 tonnes/day municipal solid-waste generation estimate for 2022/23 | JICA, *Solid Waste Management Advisor for Addis Ababa City*, Project Completion Report, Fig. 2-11 | 2026-09-11 | `pitch.number`, `pitch.source` |
| 2 | Published city-level extent plus a validated Bole sub-city pilot polygon; full sub-city layer remains incomplete | [Ethiopian National Agri Data Hub](https://data.moa.gov.et/dataset/addis-ababa-city-woreda-boundary1) WFS (`geonode:bole_subcity_boundary`); [WLRC/AAU layer metadata](https://waterhubdata.com/layers/geonode:Sub_city0/metadata_detail) | 2026-09-14 | `cities/geojson/addis.geojson`, `coverage.status=city_fallback` |
| 3 | Official city routing contact verified; sanitation-specific handoff remains unverified | [Addis Ababa Communication Bureau](https://www.addiscommunication.gov.et/) (lists `admin@addiscommunication.gov.et` and +251118127731); [Addis Ababa Mayor's Office](https://www.addismayor.gov.et/aboutus) | 2026-09-12 | `cities/addis.yaml`, coverage metadata |
| 4 | Public legal source linked for Proclamation 513/2007; PDF not vendored | [UNEP/FAOLEX](https://leap.unep.org/en/countries/et/national-legislation/solid-waste-management-proclamation-no-513-2007) | 2026-09-11 | `cities/addis.yaml` regulation citation |
| 4 | _pending_ | | | |
| 5 | _pending_ | | | |

## Rules

- Never invent numbers, emails, or citations — only verified entries, with source + date.
- One verified source beats five half-remembered ones.
- When something can't be verified in time, pivot the channel design (see task 3 fallback) rather than fake the data.
