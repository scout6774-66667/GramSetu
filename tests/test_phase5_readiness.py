"""Phase 5 Readiness, Field-Validation and Acceptance Gate Tests for GramSetu AI.

Verifies that the backend strictly adheres to Phase 5 operational readiness gates,
reporting truthful blocker statuses for all unverified data domains without crashing.
"""

import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import Settings, Environment, DEV_ACTOR_HEADER
from gramsetu.store import InMemoryStore
from gramsetu.release import validate_release_zip, import_staged_release_to_store, get_system_readiness_report


def test_p5_g01_release_archive_integrity():
    """Verify v2.2 baseline release archive structure, SHA-256 hashes, and table counts."""
    zip_path = "GramSetu_All_Corrected_CSV_v2_2.zip"
    staged = validate_release_zip(zip_path)
    assert staged.audit["table_count"] == 44
    assert staged.audit["normalized_row_count"] == 8321
    assert "market_prices" in staged.tables
    assert "locations" in staged.tables
    assert "road_edges" in staged.tables
    assert len(staged.tables["market_prices"]) == 43
    assert len(staged.tables["locations"]) == 79
    assert len(staged.tables["road_edges"]) == 620


def test_p5_r02_readiness_endpoint_truthful_fail_closed():
    """Verify GET /api/v1/system/readiness returns truthful operational blockers."""
    settings = Settings(
        ENVIRONMENT=Environment.DEVELOPMENT,
        ALLOW_SYNTHETIC_SEED=True,
    )
    app = create_app(settings)
    client = TestClient(app)

    # 1. Cold boot readiness
    res_cold = client.get("/api/v1/system/readiness")
    assert res_cold.status_code == 200
    data_cold = res_cold.json()
    assert data_cold["production_readiness"] == "NOT_READY_CRITICAL_OPERATIONAL_GAPS"
    assert data_cold["trust_classification"] == "EMPTY_COLD_BOOT"
    assert data_cold["phase5_readiness_checks"]["source_authenticity"] == "UNVERIFIED_SECONDARY_ONLY"
    assert data_cold["phase5_readiness_checks"]["site_geolocation"] == "ADMIN_CENTROID_PROXIES_NON_GPS"
    assert data_cold["phase5_readiness_checks"]["road_routability"] == "SYNTHETIC_TOPOLOGY_NON_ROUTABLE"
    assert data_cold["phase5_readiness_checks"]["partner_data"] == "SIMULATED_FIXTURES_ONLY"
    assert data_cold["phase5_readiness_checks"]["payment_credit_confirmation"] == "NO_BANK_GATEWAY_SIMULATED_UTR"
    assert data_cold["phase5_readiness_checks"]["model_training"] == "BLOCKED_INSUFFICIENT_HISTORY"

    # 2. Seeded release readiness
    res_import = client.post(
        "/api/v1/admin/import/sandbox-release",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}
    )
    assert res_import.status_code == 200

    res_seeded = client.get("/api/v1/system/readiness")
    assert res_seeded.status_code == 200
    data_seeded = res_seeded.json()
    assert data_seeded["production_readiness"] == "NOT_READY_CRITICAL_OPERATIONAL_GAPS"
    assert data_seeded["trust_classification"] == "SANDBOX_SIMULATION_ONLY"
    assert data_seeded["operational_trust_verdict"] == "SANDBOX_RESEARCH_HARDENED / PRODUCTION_BLOCKED"
    assert data_seeded["sandbox_fixture_seeded"] is True
    assert "NOT CERTIFIED FOR REAL-WORLD AGRICULTURAL PROCUREMENT" in data_seeded["data_authenticity_notice"]


def test_p5_a01_market_prices_secondary_republished_only():
    """Verify market prices in v2.2 baseline are secondary-republished and span only 2 days."""
    staged = validate_release_zip("GramSetu_All_Corrected_CSV_v2_2.zip")
    prices = staged.tables["market_prices"]
    assert len(prices) == 43
    dates = {r["observed_date"] for r in prices}
    assert dates == {"2026-11-16", "2026-11-17"}
    for r in prices:
        assert r["quality_flag"] == "SECONDARY_REPUBLISHED_NOT_PRIMARY_VERIFIED"


def test_p5_g02_location_gps_proxies_audited():
    """Verify all 79 locations in v2.2 baseline are administrative HQ proxies without field GPS."""
    staged = validate_release_zip("GramSetu_All_Corrected_CSV_v2_2.zip")
    locs = staged.tables["locations"]
    assert len(locs) == 79
    for r in locs:
        assert r["coordinate_provenance"] == "SOURCED_ADMIN_HQ_AREA_PROXY_NOT_SITE"
        assert r["site_coordinate_verified"] == "False"


def test_p5_g03_road_edges_synthetic_connectivity_audited():
    """Verify all 620 road edges in v2.2 baseline are synthetic detours, not live verified OSM."""
    staged = validate_release_zip("GramSetu_All_Corrected_CSV_v2_2.zip")
    edges = staged.tables["road_edges"]
    assert len(edges) == 620
    for r in edges:
        assert r["road_geometry_provenance"] == "SIMULATED_CONNECTIVITY_GEODESIC_DETOUR_NOT_OSM"
        assert r["passable_is_live_verified"] == "False"
        assert r["simulation_flag"] == "True"


def test_p5_f01_settlement_ledger_simulation_flags():
    """Verify settlement ledger balances carry simulation flags and lack live bank credit confirmation."""
    staged = validate_release_zip("GramSetu_All_Corrected_CSV_v2_2.zip")
    ledger = staged.tables["payable_ledger"]
    assert len(ledger) == 32
    for r in ledger:
        assert r["simulation_flag"] == "True"


def test_p5_ml01_ml02_forecasting_fail_closed_under_phase5():
    """Verify forecast endpoint refuses inference in sandbox mode and handles unavailable models gracefully."""
    settings = Settings(
        ENVIRONMENT=Environment.DEVELOPMENT,
        ALLOW_SYNTHETIC_SEED=True,
        PHASE4_FORECASTING_ENABLED=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    res = client.get(
        "/api/v1/market/forecasts?market_id=MKT_000001&commodity_id=COM_POTATO",
        headers={DEV_ACTOR_HEADER: "farmer-1"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNAVAILABLE_FEATURE_DISABLED"
    assert data["predicted_modal_price_inr_quintal"] is None
    assert "DISABLED" in data["operational_notice"]


def test_p5_prod_security_isolation():
    """Verify production environment strictly forbids dev headers and synthetic release seeding."""
    settings = Settings(
        ENVIRONMENT=Environment.PRODUCTION,
        ALLOW_SYNTHETIC_SEED=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    # 1. Dev actor header rejected
    res_actor = client.get(
        "/api/v1/system/readiness",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"}
    )
    # Readiness is public GET, but dev actor header should not grant auth
    assert res_actor.status_code == 200
    assert res_actor.json()["is_production"] is True

    # 2. Synthetic seed blocked in production
    res_seed = client.post(
        "/api/v1/admin/import/sandbox-release",
        headers={"Authorization": "Bearer test"}
    )
    assert res_seed.status_code in (401, 403)
