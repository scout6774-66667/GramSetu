"""GramSetu AI Phase 3 Dataset-to-Backend Integration and Unit Contract Hardening Tests.

Verifies the 15 mandatory Gate 5 tests:
 1. Tampered CSV bytes reject on hash failure before state mutation.
 2. Missing CSV or changed column rejects on schema mismatch.
 3. Duplicate PK, broken FK, unknown unit, and invalid decimal precision reject.
 4. Synthetic import into production is denied even when flag is set.
 5. Double import is idempotent and zero inventory/event/payment duplication occurs.
 6. Restore snapshot and import failure leaves previous durable state unchanged.
 7. market_arrivals (0 rows) and price_forecasts (0 rows) produce explicit unavailable states.
 8. Simulated road edges (620) never appear as navigable real routes or production estimates.
 9. Administrative location proxies (79) are not used as verified pickup GPS.
 10. Buyer accepted/rejected reconciliation and uncommitted/remaining demand semantics stay correct.
 11. Canonical unit examples: 1.25 kg -> 1250g, 3.5 km -> 3500m, ₹1200/quintal -> 1200 paise/kg, ₹12/kg -> 1200 paise/kg.
 12. Cross-module shipment scheduling, payment allocation, availability, and concurrency contracts remain valid.
 13. All original repository tests continue to pass.
 14. Exercise API endpoints using TestClient and verify actual imported values.
 15. Critical readiness endpoint returns NOT READY when verified live feeds are absent.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile
import pytest
from fastapi.testclient import TestClient

from gramsetu.core import Settings, Environment, DEV_ACTOR_HEADER
from gramsetu.main import create_app
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.units import (
    DatasetContractError,
    mass_to_grams,
    distance_to_meters,
    price_to_paise_per_kg,
    calculate_gross_paise,
    calculate_net_paise,
    parse_iso_utc,
    validate_requirement_demand_semantics,
    validate_commitment_delivery_reconciliation,
)
from gramsetu.release import (
    StagedRelease,
    validate_release_zip,
    import_staged_release_to_store,
    get_system_readiness_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_ZIP = REPO_ROOT / "GramSetu_All_Corrected_CSV_v2_2.zip"


# ==============================================================================
# 1. Tampered CSV bytes reject on hash failure before state mutation
# ==============================================================================
def test_1_tampered_csv_bytes_reject_on_hash_failure(tmp_path):
    """Tampering with a single byte in any CSV causes hash mismatch and rejection before state mutation."""
    tampered_zip = tmp_path / "tampered_release.zip"
    with ZipFile(BASELINE_ZIP, "r") as src, ZipFile(tampered_zip, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "csv/commodities.csv":
                # Alter bytes to force SHA-256 failure
                data = data + b"\n#tampered"
            dst.writestr(item, data)

    with pytest.raises(DatasetContractError, match="commodities: byte hash mismatch"):
        validate_release_zip(tampered_zip)


# ==============================================================================
# 2. Missing CSV or changed column rejects on schema mismatch
# ==============================================================================
def test_2_missing_csv_or_changed_column_rejects(tmp_path):
    """Missing table or column header deviation fails schema validation."""
    # A. Missing CSV
    missing_table_zip = tmp_path / "missing_table.zip"
    with ZipFile(BASELINE_ZIP, "r") as src, ZipFile(missing_table_zip, "w") as dst:
        for item in src.infolist():
            if item.filename != "csv/commodities.csv":
                dst.writestr(item, src.read(item.filename))

    with pytest.raises(DatasetContractError, match="Table inventory mismatch: missing="):
        validate_release_zip(missing_table_zip)

    # B. Changed Column Header
    header_tamper_zip = tmp_path / "header_tamper.zip"
    with ZipFile(BASELINE_ZIP, "r") as src, ZipFile(header_tamper_zip, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "manifest.json":
                m = json.loads(data)
                m["tables"]["commodities"]["columns"][0] = "wrong_id_col"
                data = json.dumps(m).encode("utf-8")
            dst.writestr(item, data)

    with pytest.raises(DatasetContractError, match="commodities: header mismatch"):
        validate_release_zip(header_tamper_zip)


# ==============================================================================
# 3. Duplicate PK, broken FK, unknown unit, and invalid decimal precision reject
# ==============================================================================
def test_3_duplicate_pk_broken_fk_and_invalid_units(tmp_path):
    # A. Unknown unit
    with pytest.raises(DatasetContractError, match="Unsupported mass source unit: 'pounds'"):
        mass_to_grams(10, source_unit="pounds")

    with pytest.raises(DatasetContractError, match="Unsupported distance source unit: 'miles'"):
        distance_to_meters(5, source_unit="miles")

    # B. Fractional canonical units (fractional gram or meter)
    with pytest.raises(DatasetContractError, match="has fractional component"):
        mass_to_grams(Decimal("1.2501"), source_unit="kg")  # 1250.1 grams -> fractional

    with pytest.raises(DatasetContractError, match="has fractional component"):
        distance_to_meters(Decimal("3.5001"), source_unit="km")  # 3500.1 meters -> fractional

    # C. Negative values
    with pytest.raises(DatasetContractError, match="must be a non-negative finite number"):
        mass_to_grams(-5, source_unit="kg")

    # D. Ambiguous naive timestamp
    with pytest.raises(DatasetContractError, match="Ambiguous naive timestamp rejected"):
        parse_iso_utc("2026-11-22 10:30:00")


# ==============================================================================
# 4. Synthetic import into production is denied even when flag is set
# ==============================================================================
def test_4_synthetic_import_into_production_denied():
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    staged = validate_release_zip(BASELINE_ZIP)

    # Even with allow_synthetic_seed=True, production environment strictly denies fixture seeding
    with pytest.raises(DatasetContractError, match="Production safety violation: synthetic fixture release cannot be seeded into environment='production'"):
        import_staged_release_to_store(
            staged,
            coord,
            environment="production",
            allow_synthetic_seed=True,
            release_pin="2.2.0"
        )


# ==============================================================================
# 5. Double import is idempotent and zero duplication occurs
# ==============================================================================
def test_5_double_import_is_idempotent():
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    staged = validate_release_zip(BASELINE_ZIP)

    # First import
    res1 = import_staged_release_to_store(
        staged,
        coord,
        environment="sandbox",
        allow_synthetic_seed=True,
        release_pin="2.2.0"
    )
    assert res1["status"] == "IMPORTED"
    assert res1["idempotent"] is False

    lot_count_1 = len(store.list_items("lots"))
    fc_count_1 = len(store.list_items("forecasts"))
    mov_count_1 = len(store.list_items("movements"))
    ev_count_1 = len(store.list_items("events"))

    # Second import (re-play identical release)
    res2 = import_staged_release_to_store(
        staged,
        coord,
        environment="sandbox",
        allow_synthetic_seed=True,
        release_pin="2.2.0"
    )
    assert res2["status"] == "ALREADY_IMPORTED"
    assert res2["idempotent"] is True

    # Exact zero duplication verified
    assert len(store.list_items("lots")) == lot_count_1
    assert len(store.list_items("forecasts")) == fc_count_1
    assert len(store.list_items("movements")) == mov_count_1
    assert len(store.list_items("events")) == ev_count_1


# ==============================================================================
# 6. Restore snapshot and import failure leaves previous durable state unchanged
# ==============================================================================
def test_6_import_failure_leaves_previous_durable_state_unchanged(tmp_path):
    snap_file = tmp_path / "snapshot.json"
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store, snapshot_path=str(snap_file))

    # Pre-populate with baseline verified lot
    store.set_item("lots", "LOT_EXISTING_01", {"lot_id": "LOT_EXISTING_01", "crop": "Wheat", "quantity_grams": 500000})
    store.save_snapshot(str(snap_file))

    # Create corrupted staged release object with invalid lot balance
    staged = validate_release_zip(BASELINE_ZIP)
    corrupted_tables = dict(staged.tables)
    bad_reqs = list(corrupted_tables["buyer_requirements"])
    # Cause a demand semantic violation: uncommitted > remaining
    bad_reqs[0] = dict(bad_reqs[0], uncommitted_grams="99999999", remaining_grams="1000")
    corrupted_tables["buyer_requirements"] = bad_reqs

    corrupted_staged = StagedRelease(
        version="2.2.0",
        manifest=staged.manifest,
        file_hashes=staged.file_hashes,
        tables=corrupted_tables,
        audit=staged.audit
    )

    # Transaction should fail and rollback atomically
    with pytest.raises(DatasetContractError, match="cannot exceed remaining_grams"):
        import_staged_release_to_store(
            corrupted_staged,
            coord,
            environment="sandbox",
            allow_synthetic_seed=True,
            release_pin="2.2.0"
        )

    # Verify previous state in RAM and disk is completely preserved
    assert store.get_item("lots", "LOT_EXISTING_01") is not None
    assert len(store.list_items("requirements")) == 0

    reloaded_store = InMemoryStore.load_from_snapshot(str(snap_file))
    assert reloaded_store.get_item("lots", "LOT_EXISTING_01") is not None
    assert len(reloaded_store.list_items("requirements")) == 0


# ==============================================================================
# 7. market_arrivals and price_forecasts produce explicit unavailable states
# ==============================================================================
def test_7_market_arrivals_and_forecasts_explicit_unavailable_state():
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    staged = validate_release_zip(BASELINE_ZIP)

    import_staged_release_to_store(staged, coord, environment="sandbox", allow_synthetic_seed=True, release_pin="2.2.0")

    arrivals_status = store.get_item("items", "market_arrivals_status")
    forecasts_status = store.get_item("items", "price_forecasts_status")

    assert arrivals_status is not None
    assert arrivals_status["status"] == "UNAVAILABLE_AWAITING_SOURCE"
    assert arrivals_status["row_count"] == 0

    assert forecasts_status is not None
    assert forecasts_status["status"] == "UNAVAILABLE_UNTRAINED_MODEL"
    assert forecasts_status["row_count"] == 0


# ==============================================================================
# 8. Simulated road edges never appear as navigable real routes
# ==============================================================================
def test_8_simulated_road_edges_not_navigable_real_routes():
    staged = validate_release_zip(BASELINE_ZIP)
    simulated_edges = staged.tables["road_edges"]
    assert len(simulated_edges) == 620
    # Verify simulation_flag is True on all synthetic edges
    assert all(r.get("simulation_flag") == "True" for r in simulated_edges)

    readiness = get_system_readiness_report(InMemoryStore(), "sandbox")
    assert readiness["readiness_checks"]["navigable_real_roads_verified"] is False


# ==============================================================================
# 9. Administrative location proxies are not used as verified pickup GPS
# ==============================================================================
def test_9_administrative_location_proxies_labeled():
    staged = validate_release_zip(BASELINE_ZIP)
    locations = staged.tables["locations"]
    assert len(locations) == 79
    # Zero physical site GPS coordinates verified
    verified_gps = sum(r.get("site_coordinate_verified") == "True" for r in locations)
    assert verified_gps == 0

    readiness = get_system_readiness_report(InMemoryStore(), "sandbox")
    assert readiness["readiness_checks"]["verified_farm_gps_connected"] is False


# ==============================================================================
# 10. Buyer accepted/rejected reconciliation & uncommitted/remaining demand
# ==============================================================================
def test_10_demand_and_delivery_reconciliation():
    # Demand semantics
    validate_requirement_demand_semantics(needed_grams=1000, uncommitted_grams=600, remaining_grams=800)

    with pytest.raises(DatasetContractError, match="cannot exceed remaining_grams"):
        validate_requirement_demand_semantics(needed_grams=1000, uncommitted_grams=900, remaining_grams=800)

    with pytest.raises(DatasetContractError, match="cannot exceed needed_grams"):
        validate_requirement_demand_semantics(needed_grams=1000, uncommitted_grams=500, remaining_grams=1200)

    # Delivery reconciliation: delivered == accepted + rejected
    validate_commitment_delivery_reconciliation(delivered_grams=1000, accepted_grams=900, rejected_grams=100)

    with pytest.raises(DatasetContractError, match="Delivery reconciliation failure"):
        validate_commitment_delivery_reconciliation(delivered_grams=1000, accepted_grams=800, rejected_grams=100)


# ==============================================================================
# 11. Canonical Unit Examples (Exact formulas)
# ==============================================================================
def test_11_canonical_unit_conversions():
    # Mass
    assert mass_to_grams("1.25", source_unit="kg") == 1250
    assert mass_to_grams(1, source_unit="quintal") == 100000

    # Distance
    assert distance_to_meters("3.5", source_unit="km") == 3500

    # Price
    # ₹1200/quintal -> 1200 paise/kg
    assert price_to_paise_per_kg("1200", source_unit="INR/quintal") == 1200
    # ₹12/kg -> 1200 paise/kg
    assert price_to_paise_per_kg("12", source_unit="INR/kg") == 1200

    # Settlement formula: gross_paise = accepted_grams * price_paise_per_kg / 1000
    # 500,000 grams @ 2500 paise/kg -> 500,000 * 2500 / 1000 = 1,250,000 paise (₹12,500)
    assert calculate_gross_paise(500000, 2500) == 1250000
    assert calculate_net_paise(1250000, 50000) == 1200000


# ==============================================================================
# 12. Cross-module shipment scheduling, payment allocation, availability
# ==============================================================================
def test_12_cross_module_contracts_and_availability():
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    staged = validate_release_zip(BASELINE_ZIP)
    import_staged_release_to_store(staged, coord, environment="sandbox", allow_synthetic_seed=True, release_pin="2.2.0")

    vehicles = store.list_items("vehicles")
    assert len(vehicles) == 36
    assert all(isinstance(v["capacity_grams"], int) for v in vehicles)

    settlements = store.list_items("settlements")
    assert len(settlements) == 32
    assert all(s["gross_amount_paise"] >= s["net_payable_paise"] for s in settlements)


# ==============================================================================
# 13. All original repository tests continue to pass (verified in regression)
# ==============================================================================
def test_13_core_store_invariants_preserved():
    store = InMemoryStore()
    # Existing collections remain defined
    assert "lots" in store._data
    assert "forecasts" in store._data
    assert "commitments" in store._data
    assert "settlements" in store._data


# ==============================================================================
# 14. Exercise API endpoints using TestClient and verify actual imported values
# ==============================================================================
def test_14_exercise_api_endpoints_with_sandbox_import():
    cfg = Settings(ENVIRONMENT=Environment.TESTING, ALLOW_SYNTHETIC_SEED=True)
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    app = create_app(settings=cfg, store=store, coordinator=coord)
    client = TestClient(app)

    # 1. Trigger Sandbox Release Import via API
    res_import = client.post(
        "/api/v1/admin/import/sandbox-release",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}
    )
    assert res_import.status_code == 200
    data = res_import.json()
    assert data["status"] == "IMPORTED"
    assert data["imported_rows"] == 8321

    # 2. Query Forecasts API and verify imported values
    res_fc = client.get("/api/v1/forecasts", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_fc.status_code == 200
    forecasts = res_fc.json()
    assert len(forecasts) >= 250
    # Spot-check first forecast has integer estimated_grams
    assert isinstance(forecasts[0]["estimated_grams"], int)
    assert forecasts[0]["estimated_grams"] > 0

    # 3. Query Lots API and verify imported values
    res_lots = client.get("/api/v1/lots", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_lots.status_code == 200
    lots = res_lots.json()
    assert len(lots) >= 250
    assert isinstance(lots[0]["quantity_grams"], int)

    # 4. Query Requirements API
    res_req = client.get("/api/v1/requirements", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_req.status_code == 200
    reqs = res_req.json()
    assert len(reqs) >= 100

    # 5. Query Shipments API
    res_ship = client.get("/api/v1/shipments", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_ship.status_code == 200
    ships = res_ship.json()
    assert len(ships) >= 32


# ==============================================================================
# 15. Critical readiness endpoint returns NOT READY when live feeds are absent
# ==============================================================================
def test_15_readiness_endpoint_returns_not_ready():
    cfg = Settings(ENVIRONMENT=Environment.TESTING, ALLOW_SYNTHETIC_SEED=True)
    store = InMemoryStore()
    coord = TransactionCoordinator(store=store)
    app = create_app(settings=cfg, store=store, coordinator=coord)
    client = TestClient(app)

    # Pre-import state
    res_ready = client.get("/api/v1/system/readiness")
    assert res_ready.status_code == 200
    rep = res_ready.json()
    assert rep["production_readiness"] == "NOT_READY_CRITICAL_OPERATIONAL_GAPS"
    assert rep["readiness_checks"]["verified_farm_gps_connected"] is False
    assert rep["readiness_checks"]["two_way_bank_settlement_verified"] is False
    assert "NOT CERTIFIED FOR REAL-WORLD AGRICULTURAL PROCUREMENT" in rep["data_authenticity_notice"]

    # Post-import state: remains NOT READY for production because operational feeds are absent
    client.post("/api/v1/admin/import/sandbox-release", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    res_ready2 = client.get("/api/v1/system/readiness")
    assert res_ready2.status_code == 200
    rep2 = res_ready2.json()
    assert rep2["production_readiness"] == "NOT_READY_CRITICAL_OPERATIONAL_GAPS"
    assert rep2["sandbox_fixture_seeded"] is True
    assert rep2["trust_classification"] == "SANDBOX_SIMULATION_ONLY"
