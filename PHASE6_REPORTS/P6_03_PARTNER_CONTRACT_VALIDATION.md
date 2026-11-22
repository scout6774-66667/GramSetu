# GramSetu AI — Partner Operational Data Contracts Audit

**Document ID:** P6_03_PARTNER_CONTRACT_VALIDATION.md  
**Audit Phase:** Phase 6 Workstream P6.3  
**Verdict:** `PARTNER_DATA_SIMULATED_FIXTURES_ONLY`

---

## 1. Partner Intake Contracts

1. **Farmer Physical Lot Intake (`P6-09`):**
   - Requires physical weighment slip from a calibrated scale with gross, tare, and net weights.
   - Promotion of unharvested harvest forecasts directly into saleable inventory lots is strictly forbidden.
   - All 250 baseline inventory lots are simulated fixtures.
2. **Buyer Procurement Offers (`P6-10`):**
   - Buyer requirements require digital signature verification, legal entity identifier (GSTIN active filing check), quantity, agreed integer paise/kg, and formal expiry.
   - All 100 buyer commitments in baseline are synthetic test fixtures.
3. **Transport Vehicle Availability (`P6-08`):**
   - Driver and vehicle availability require carrier-confirmed operational shifts, load capacity, and signed freight rate cards without time-window overlaps.
   - All 36 vehicles in baseline are simulated.
4. **Cold Storage Slots (`P6-11`):**
   - Usable slot capacity must be confirmed by the warehouse operator; static National Horticulture Board (NHB) directory entries do not establish live vacancy.
