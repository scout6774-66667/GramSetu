# GramSetu AI — Codebase Diff & Migration Notes
**Milestone:** Phase 3 Implementation  
**Changeset Scope:** Integration Adapter, Strict Unit Contracts, Release Ingestion, and Route Registration  
**Baseline Test Count:** 143 passing  
**New Test Count:** 158 passing (+15 new tests, 0 regressions)  

---

## 1. Inventory of Modified & Added Files

### Added Files
1. `gramsetu/units.py`:
   - Core unit conversion and contract enforcement module.
   - Non-lossy integer converters (`mass_to_grams`, `distance_to_meters`, `price_to_paise_per_kg`).
   - Settlement calculation functions with half-up rounding (`calculate_gross_paise`, `calculate_net_paise`).
   - ISO 8601 UTC timestamp validator (`parse_iso_utc`).
   - Semantic contract validators:
     - `validate_requirement_demand_semantics(needed_grams, uncommitted_grams, remaining_grams)`
     - `validate_commitment_delivery_reconciliation(delivered_grams, accepted_grams, rejected_grams)`
   - Exception class: `DatasetContractError`.
2. `gramsetu/release.py`:
   - Release archive loader, preflight auditor, and transactional ingestion coordinator.
   - Dataclass `StagedRelease` storing validated tables, hashes, and manifest metadata.
   - `validate_release_zip(archive_path)`: Verifies manifest, table inventory, header alignment, primary keys, and SHA-256 byte hashes.
   - `import_staged_release_to_store(staged, coordinator, environment, allow_synthetic_seed, release_pin)`: Performs atomic multi-table staging into `InMemoryStore`.
   - `get_system_readiness_report(store, environment)`: Computes production readiness audits and operational gap disclosures.
3. `tests/test_phase3_contracts.py`:
   - 15 comprehensive automated acceptance tests validating the negative and integration contracts.

### Modified Files
1. `gramsetu/core.py`:
   - Added configuration settings to `Settings`:
     - `ALLOW_SYNTHETIC_SEED: bool = False` (defaults to False for fail-closed production safety).
     - `RELEASE_PIN: str = "2.2.0"` (pinned release baseline).
     - `RELEASE_ARCHIVE_PATH: str = "GramSetu_All_Corrected_CSV_v2_2.zip"` (path to release archive).
2. `gramsetu/main.py`:
   - Registered endpoints:
     - `GET /api/v1/system/readiness`: Returns `ProductionReadinessReport` auditing operational gaps.
     - `POST /api/v1/admin/import/sandbox-release`: Performs staged atomic ingestion with environment gating (`FPO_ADMIN`, `SYSTEM` roles required).

---

## 2. Backward Compatibility Verification

1. **Zero Database Architecture Unaltered**:
   - `InMemoryStore` and `TransactionCoordinator` contracts remain identical.
   - Existing schema models continue to validate with `extra="forbid"`.
2. **Existing Endpoints & Tests Preserved**:
   - All previous test suites (F0 through F13) continue to pass without modification.
   - Zero breaking changes introduced to existing route signatures.
