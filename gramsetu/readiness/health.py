"""System operational readiness and safety gate evaluation for GramSetu AI."""
from __future__ import annotations

from typing import Dict, Any
from gramsetu.infrastructure.persistence import InMemoryStore


def get_system_readiness_report(store: InMemoryStore, environment: str) -> Dict[str, Any]:
    """Expose machine-readable production readiness and trust classification report.

    Declares operational readiness failures without crashing process liveness.
    """
    env = environment.strip().lower()
    is_prod = "production" in env or env == "production"
    has_sandbox_seed = store.get_item("evidence", "release_import_2.2.0") is not None

    arrivals_meta = store.get_item("items", "market_arrivals_status") or {"status": "UNAVAILABLE"}
    forecasts_meta = store.get_item("items", "price_forecasts_status") or {"status": "UNAVAILABLE"}

    return {
        "system_name": "GramSetu AI Backend",
        "environment": environment,
        "is_production": is_prod,
        "production_readiness": "NOT_READY_CRITICAL_OPERATIONAL_GAPS",
        "trust_classification": "SANDBOX_SIMULATION_ONLY" if has_sandbox_seed else "EMPTY_COLD_BOOT",
        "operational_trust_verdict": "SANDBOX_RESEARCH_HARDENED / PRODUCTION_BLOCKED" if has_sandbox_seed else "EMPTY_COLD_BOOT",
        "readiness_checks": {
            "verified_farm_gps_connected": False,
            "navigable_real_roads_verified": False,
            "real_time_buyer_offers_verified": False,
            "two_way_bank_settlement_verified": False,
            "market_arrivals_feed": arrivals_meta.get("status", "UNAVAILABLE"),
            "price_forecasting_model": forecasts_meta.get("status", "UNAVAILABLE"),
        },
        "phase5_readiness_checks": {
            "source_authenticity": "UNVERIFIED_SECONDARY_ONLY",
            "site_geolocation": "ADMIN_CENTROID_PROXIES_NON_GPS",
            "road_routability": "SYNTHETIC_TOPOLOGY_NON_ROUTABLE",
            "partner_data": "SIMULATED_FIXTURES_ONLY",
            "payment_credit_confirmation": "NO_BANK_GATEWAY_SIMULATED_UTR",
            "model_training": "BLOCKED_INSUFFICIENT_HISTORY",
        },
        "sandbox_fixture_seeded": has_sandbox_seed,
        "data_authenticity_notice": (
            "SYSTEM OPERATING IN SYNTHETIC/SECONDARY SIMULATION MODE. "
            "Locations represent administrative district centroid proxies; road edges are synthetic; "
            "market prices are secondary-reported observations; bank payments are unverified self-reported references. "
            "NOT CERTIFIED FOR REAL-WORLD AGRICULTURAL PROCUREMENT, FLEET DISPATCH, OR BANKING SETTLEMENT."
        )
    }
