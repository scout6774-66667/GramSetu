# GramSetu AI — Official AGMARKNET / DMI Data Acquisition Plan
**Document ID:** `P4-01-ACQUISITION-PLAN`  
**Target Authority:** Directorate of Marketing & Inspection (DMI), Ministry of Agriculture and Farmers Welfare, Government of India  
**Official Portal:** [data.gov.in — Mandi Daily Prices Catalog](https://data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi)  
**Resource ID:** `9ef84268-d588-465a-a308-a864a43d0070`  

---

## 1. Governance, Legal Rights & Terms of Use

1. **National Data Sharing and Accessibility Policy (NDSAP)**:
   - Data published under data.gov.in is subject to the Government of India Open Data License.
   - Reuse requires explicit provenance attribution, preservation of original reporting days, and prohibition against misrepresenting secondary alterations as official government publications.
2. **Authorized Access & Security Constraints**:
   - Zero scraping of un-authenticated APMC portals or arbitrary HTML scraping.
   - Official OGD API keys must be injected strictly through external environment variables (`OGD_API_KEY`), never hardcoded in source repositories.
   - Automated fetching from government endpoints constitutes evidence of provenance, not proof that every field value is error-free. Every batch must undergo row-level quarantine.

---

## 2. Reporting-Day Semantics & Timezone Handling

- **Market Reporting Day**: Wholesale market transactions occur during morning auction hours in local Indian Standard Time (`Asia/Kolkata`, UTC+05:30).
- **Date Semantics**: The `observed_date` is strictly an ISO calendar date (`YYYY-MM-DD`) representing the actual mandi trading session.
- **Retrieval Timestamp**: `retrieved_at_utc` records the exact UTC ISO datetime when bytes were captured. It must strictly satisfy `retrieved_at_utc >= observed_date`.
- **Publication Lag**: AGMARKNET updates typically publish between 18:00 and 22:00 IST on trading days. Models issuing forecasts for day $T+1$ must strictly execute after the evening cutoff of day $T$.

---

## 3. Namespace Isolation Architecture

To prevent synthetic test fixtures or unverified scrapers from poisoning training or production models, data is segregated into three isolated namespaces:

```
data/
├── raw/
│   ├── GOVERNMENT_DMI_PRIMARY/       # Immutable bytes downloaded directly via authorized OGD API
│   ├── SECONDARY_REPUBLISHED_RAW/    # Secondary aggregator snapshots (e.g. CommodityMarketLive)
│   └── SYNTHETIC_SANDBOX_RAW/        # Simulated test batches (flagged simulation_flag=True)
├── normalized/
│   ├── GOVERNMENT_DMI_PRIMARY/
│   ├── SECONDARY_REPUBLISHED/
│   └── SYNTHETIC_SANDBOX/
└── quarantine/
    └── {namespace}/{batch_id}.rejected.json  # Line-numbered rejection logs with exact violation reasons
```

---

## 4. Entity Resolution & Crosswalk Policy

- **Zero Fuzzy Matching**: GramSetu AI strictly rejects automated Levenshtein, phonex, or heuristic string matching for mandis and crop varieties. Fuzzy matching risks merging disparate physical markets with differing logistics costs and qualities.
- **Explicit Crosswalk Registry**:
  Every raw vendor string must have a verified 1:1 mapping in `CANONICAL_MARKET_CROSSWALK` and `CANONICAL_COMMODITY_CROSSWALK`. Any row containing an unmapped market or commodity is automatically diverted to quarantine.
