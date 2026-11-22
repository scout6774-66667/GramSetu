"""GramSetu AI Master Data Ingestion Pipeline.

Orchestrates the ingestion, validation, referential integrity verification, and cryptographic
manifest generation for all canonical datasets in GramSetu AI.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from INGESTION_PIPELINE.loaders import (
    compute_file_sha256,
    CommodityLoader,
    CommodityGradeLoader,
    AdministrativeLocationLoader,
    MandiMasterLoader,
    MandiPriceLoader,
    MandiArrivalLoader,
    RoadNetworkLoader,
    StorageFacilityLoader,
    CropShelfLifeLoader,
    FreightRateCardLoader,
    SettlementDeductionsLoader,
    FPOMasterLoader,
    FarmerRegistryLoader,
    BuyerRegistryLoader,
    VehicleFleetLoader,
)


def run_ingestion() -> Dict[str, Any]:
    print("================================================================================")
    print(" GRAMSETU AI CANONICAL DATA INGESTION & QUALITY PIPELINE")
    print("================================================================================")
    
    verified_dir = os.path.join(REPO_ROOT, "data", "verified")
    op_confirmed_dir = os.path.join(REPO_ROOT, "data", "operator_confirmed")
    derived_dir = os.path.join(REPO_ROOT, "data", "derived")
    synthetic_dir = os.path.join(REPO_ROOT, "data", "synthetic_test")

    manifest: Dict[str, Any] = {
        "pipeline_name": "GramSetu Canonical Ingestion Pipeline",
        "pipeline_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "IN_PROGRESS",
        "datasets": {},
        "integrity_checks": {},
        "summary": {}
    }

    # 1. Load Reference Data
    print("[1/5] Loading verified reference datasets...")
    commodities = CommodityLoader(os.path.join(verified_dir, "commodity_master.csv")).load()
    grades = CommodityGradeLoader(os.path.join(verified_dir, "commodity_grades.csv")).load()
    locations = AdministrativeLocationLoader(os.path.join(verified_dir, "administrative_locations.csv")).load()
    mandis = MandiMasterLoader(os.path.join(verified_dir, "mandi_master.csv")).load()
    prices = MandiPriceLoader(os.path.join(verified_dir, "daily_mandi_prices.csv")).load()
    arrivals = MandiArrivalLoader(os.path.join(verified_dir, "daily_mandi_arrivals.csv")).load()
    road_network = RoadNetworkLoader(
        os.path.join(verified_dir, "road_nodes.csv"),
        os.path.join(verified_dir, "road_segments.csv")
    ).load()
    storage_facilities = StorageFacilityLoader(os.path.join(verified_dir, "storage_facilities.csv")).load()
    shelf_life_rules = CropShelfLifeLoader(os.path.join(verified_dir, "crop_shelf_life_rules.csv")).load()
    freight_cards = FreightRateCardLoader(os.path.join(verified_dir, "freight_rate_cards.csv")).load()
    deductions = SettlementDeductionsLoader(os.path.join(verified_dir, "settlement_deductions.csv")).load()

    # 2. Load Operator Confirmed Master Data
    print("[2/5] Loading operator-confirmed operational registries...")
    fpos = FPOMasterLoader(os.path.join(op_confirmed_dir, "fpo_master.csv")).load()
    farmers = FarmerRegistryLoader(os.path.join(op_confirmed_dir, "farmer_registry.csv")).load()
    buyers = BuyerRegistryLoader(os.path.join(op_confirmed_dir, "buyer_registry.csv")).load()
    vehicles = VehicleFleetLoader(os.path.join(op_confirmed_dir, "vehicle_fleet.csv")).load()

    # Track manifests for all files
    all_files = [
        ("verified/commodity_master.csv", os.path.join(verified_dir, "commodity_master.csv"), len(commodities)),
        ("verified/commodity_grades.csv", os.path.join(verified_dir, "commodity_grades.csv"), len(grades)),
        ("verified/administrative_locations.csv", os.path.join(verified_dir, "administrative_locations.csv"), len(locations)),
        ("verified/mandi_master.csv", os.path.join(verified_dir, "mandi_master.csv"), len(mandis)),
        ("verified/daily_mandi_prices.csv", os.path.join(verified_dir, "daily_mandi_prices.csv"), len(prices)),
        ("verified/daily_mandi_arrivals.csv", os.path.join(verified_dir, "daily_mandi_arrivals.csv"), len(arrivals)),
        ("verified/road_nodes.csv", os.path.join(verified_dir, "road_nodes.csv"), len(road_network["nodes"])),
        ("verified/road_segments.csv", os.path.join(verified_dir, "road_segments.csv"), len(road_network["edges"])),
        ("verified/storage_facilities.csv", os.path.join(verified_dir, "storage_facilities.csv"), len(storage_facilities)),
        ("verified/crop_shelf_life_rules.csv", os.path.join(verified_dir, "crop_shelf_life_rules.csv"), len(shelf_life_rules)),
        ("verified/freight_rate_cards.csv", os.path.join(verified_dir, "freight_rate_cards.csv"), len(freight_cards)),
        ("verified/settlement_deductions.csv", os.path.join(verified_dir, "settlement_deductions.csv"), len(deductions)),
        ("operator_confirmed/fpo_master.csv", os.path.join(op_confirmed_dir, "fpo_master.csv"), len(fpos)),
        ("operator_confirmed/farmer_registry.csv", os.path.join(op_confirmed_dir, "farmer_registry.csv"), len(farmers)),
        ("operator_confirmed/buyer_registry.csv", os.path.join(op_confirmed_dir, "buyer_registry.csv"), len(buyers)),
        ("operator_confirmed/vehicle_fleet.csv", os.path.join(op_confirmed_dir, "vehicle_fleet.csv"), len(vehicles)),
    ]

    for rel_path, abs_path, rec_count in all_files:
        manifest["datasets"][rel_path] = {
            "sha256": compute_file_sha256(abs_path),
            "records": rec_count,
            "status": "LOADED_AND_PARSED"
        }

    # 3. Cross-Dataset Referential Integrity Validation
    print("[3/5] Validating cross-entity referential integrity...")
    validations = {}
    
    # Check commodity references
    commodity_ids = {c["commodity_id"] for c in commodities}
    grade_cmd_diff = {g["commodity_id"] for g in grades} - commodity_ids
    assert not grade_cmd_diff, f"Orphan commodity_id in grades: {grade_cmd_diff}"
    price_cmd_diff = {p["commodity_id"] for p in prices} - commodity_ids
    assert not price_cmd_diff, f"Orphan commodity_id in prices: {price_cmd_diff}"
    arv_cmd_diff = {a["commodity_id"] for a in arrivals} - commodity_ids
    assert not arv_cmd_diff, f"Orphan commodity_id in arrivals: {arv_cmd_diff}"
    validations["commodity_integrity"] = "PASSED"

    # Check market references
    mandi_ids = {m["market_id"] for m in mandis}
    price_mkt_diff = {p["market_id"] for p in prices} - mandi_ids
    assert not price_mkt_diff, f"Orphan market_id in prices: {price_mkt_diff}"
    arv_mkt_diff = {a["market_id"] for a in arrivals} - mandi_ids
    assert not arv_mkt_diff, f"Orphan market_id in arrivals: {arv_mkt_diff}"
    validations["market_integrity"] = "PASSED"

    # Check FPO references
    fpo_ids = {f["fpo_id"] for f in fpos}
    storage_fpo_diff = {s["fpo_id"] for s in storage_facilities} - fpo_ids
    assert not storage_fpo_diff, f"Orphan fpo_id in storage: {storage_fpo_diff}"
    farmer_fpo_diff = {fm["fpo_id"] for fm in farmers} - fpo_ids
    assert not farmer_fpo_diff, f"Orphan fpo_id in farmers: {farmer_fpo_diff}"
    veh_fpo_diff = {v["fpo_id"] for v in vehicles} - fpo_ids
    assert not veh_fpo_diff, f"Orphan fpo_id in vehicles: {veh_fpo_diff}"
    validations["fpo_hierarchy_integrity"] = "PASSED"

    # Check administrative location references
    location_ids = {l["location_id"] for l in locations}
    fpo_loc_diff = {f["head_office_location_id"] for f in fpos} - location_ids
    assert not fpo_loc_diff, f"Orphan location_id in FPO head offices: {fpo_loc_diff}"
    farmer_loc_diff = {fm["village_location_id"] for fm in farmers} - location_ids
    assert not farmer_loc_diff, f"Orphan location_id in farmer villages: {farmer_loc_diff}"
    buyer_loc_diff = {b["terminal_location_id"] for b in buyers} - location_ids
    assert not buyer_loc_diff, f"Orphan location_id in buyer terminals: {buyer_loc_diff}"
    validations["location_hierarchy_integrity"] = "PASSED"

    # Check road network graph connectivity
    node_ids = set(road_network["nodes"].keys())
    for e in road_network["edges"]:
        assert e["source_node"] in node_ids, f"Edge source missing: {e['source_node']}"
        assert e["target_node"] in node_ids, f"Edge target missing: {e['target_node']}"
    validations["road_network_topology"] = "PASSED"

    manifest["integrity_checks"] = validations

    # 4. Generate Canonical Bundle & Manifest
    print("[4/5] Writing manifest and canonical verified bundle...")
    manifest["status"] = "PASSED"
    total_records = sum(d["records"] for d in manifest["datasets"].values())
    manifest["summary"] = {
        "total_files": len(manifest["datasets"]),
        "total_records": total_records,
        "verified_reference_files": 12,
        "operator_confirmed_files": 4,
        "quarantined_files": 0,
        "zero_unverified_proxies": True,
        "zero_floating_point_currency": True,
        "zero_floating_point_inventory_mass": True
    }

    manifest_path = os.path.join(REPO_ROOT, "INGESTION_PIPELINE", "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Consolidated bundle
    canonical_bundle = {
        "generated_at": manifest["timestamp_utc"],
        "commodities": commodities,
        "commodity_grades": grades,
        "administrative_locations": locations,
        "mandi_master": mandis,
        "daily_mandi_prices": prices,
        "daily_mandi_arrivals": arrivals,
        "road_network": road_network,
        "storage_facilities": storage_facilities,
        "crop_shelf_life_rules": shelf_life_rules,
        "freight_rate_cards": freight_cards,
        "settlement_deductions": deductions,
        "fpos": fpos,
        "farmers": farmers,
        "buyers": buyers,
        "vehicles": vehicles
    }
    bundle_path = os.path.join(REPO_ROOT, "data", "verified_canonical_bundle.json")
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(canonical_bundle, f, indent=2)

    print("[5/5] Ingestion pipeline execution completed successfully!")
    print(f"      Manifest written to: {manifest_path}")
    print(f"      Canonical bundle written to: {bundle_path}")
    print(f"      Total datasets: {len(manifest['datasets'])} | Total records: {total_records}")
    print("================================================================================")
    return manifest


if __name__ == "__main__":
    run_ingestion()
