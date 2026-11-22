# GramSetu AI — Primary Source Acquisition & Crosswalk Audit

**Document ID:** P6_01_SOURCE_ACQUISITION_REPORT.md  
**Audit Phase:** Phase 6 Workstream P6.1  
**Status:** `BLOCKED_AWAITING_PRIMARY_FEED`

---

## 1. AGMARKNET & Data.gov.in Interface Evaluation

1. **Access Terms & Permissions:**
   - AGMARKNET (agmarknet.gov.in) and OGD India (data.gov.in) provide public agricultural market price and arrival datasets under the National Data Sharing and Accessibility Policy (NDSAP).
   - Commercial automated harvesting requires registered API keys, IP whitelisting, and strict rate-limiting compliance (maximum 10 requests/second to prevent server degradation).
   - In the active offline sandboxed runtime, outbound network access to external government endpoints is blocked. No pre-seeded API credentials exist in the repository.

2. **Source Ingestion Protocol:**
   - Documented in `gramsetu/acquisition.py`: raw response payloads must be captured immutably to `data/quarantine/` with SHA-256 hash logging, source system attribution (`AGMARKNET_DMI`), publication timestamp, and retrieval timestamp.
   - Direct web scraping behind authentication or CAPTCHAs is prohibited.

3. **Current Ingestion Reality:**
   - Baseline table `market_prices.csv` contains only 43 observations spanning two calendar dates: 2026-11-16 (10 rows) and 2026-11-17 (33 rows).
   - Baseline table `market_arrivals.csv` contains 0 rows (header-only schema).
   - No primary signed government XML/JSON byte stream has been ingested.

---

## 2. Market & Commodity Crosswalk Policy

- Fuzzy matching or automated heuristic joining between internal IDs and AGMARKNET codes is strictly prohibited.
- A manual crosswalk has been compiled for 12 APMC markets and 17 commodities, but remains in status `BLOCKED_AWAITING_DMI_APPROVAL` until officially countersigned by the State Agricultural Marketing Board.
- Any unapproved mapping is quarantined.
