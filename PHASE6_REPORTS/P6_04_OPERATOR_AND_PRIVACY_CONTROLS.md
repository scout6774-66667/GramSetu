# GramSetu AI — Operator Controls, Consent & Privacy Architecture

**Document ID:** P6_04_OPERATOR_AND_PRIVACY_CONTROLS.md  
**Audit Phase:** Phase 6 Workstream P6.4  
**Compliance Target:** Digital Personal Data Protection (DPDP) Act & Least Privilege

---

## 1. Field Operator Override & Human-in-the-Loop Safeguards

1. **No Autonomous Dispatch:** Algorithmic route suggestions or recovery actions cannot automatically command physical vehicles. A human FPO transport coordinator must explicitly approve all dispatch orders.
2. **Pricing Advisory Disclosures:** Market price advisories include clear operational notices:
   `"UNAVAILABLE by system configuration. Model is untrained. Not for financial decision-making."`
3. **Incident Rollback:** Every manual override is recorded as an immutable domain event in `InMemoryStore.items["events"]` with the actor's ID, timestamp, and justification.

---

## 2. Privacy & Data Minimization

1. **Pseudonymous Identifiers:** Farmer names and phone numbers are pseudononymized into synthetic opaque identifiers (`ACT_000001`, `FARMER_0001`) in external exports and research datasets.
2. **Location Consent:** Field GNSS check-ins require explicit, purpose-limited digital consent records referencing the specific pilot harvest season.
3. **Data Retention Policy:** Inactive GPS logs older than 90 days are purged; settlement audit trails are retained for statutory accounting periods.
