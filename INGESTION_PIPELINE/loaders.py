"""GramSetu AI Ingestion Pipeline Loaders.

Provides deterministic, validated ingestion of verified reference and operational datasets into
the in-memory state and snapshot persistence layer.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 checksum of a file for manifest provenance."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class BaseLoader:
    def __init__(self, filepath: str):
        self.filepath = filepath
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Dataset file not found: {filepath}")

    def read_csv(self) -> List[Dict[str, str]]:
        with open(self.filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)


class CommodityLoader(BaseLoader):
    """Loads and validates commodity_master.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "commodity_id": r["commodity_id"].strip(),
                "commodity_name": r["commodity_name"].strip(),
                "scientific_name": r.get("scientific_name", "").strip(),
                "category": r["category"].strip(),
                "hsn_code": r["hsn_code"].strip(),
                "standard_moisture_max_pct": float(r["standard_moisture_max_pct"]),
                "default_shelf_life_days": int(r["default_shelf_life_days"]),
                "is_perishable": r["is_perishable"].strip().lower() in ("true", "1"),
            })
        return validated


class CommodityGradeLoader(BaseLoader):
    """Loads and validates commodity_grades.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "grade_id": r["grade_id"].strip(),
                "commodity_id": r["commodity_id"].strip(),
                "grade_code": r["grade_code"].strip(),
                "min_purity_pct": float(r["min_purity_pct"]),
                "max_foreign_matter_pct": float(r["max_foreign_matter_pct"]),
                "max_moisture_pct": float(r["max_moisture_pct"]),
                "description": r.get("description", "").strip(),
            })
        return validated


class AdministrativeLocationLoader(BaseLoader):
    """Loads and validates administrative_locations.csv with coordinate verification."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            lat = float(r["latitude"])
            lon = float(r["longitude"])

            # India bounding box: lat 8.0 to 37.0, lon 68.0 to 97.0
            if not (8.0 <= lat <= 37.0 and 68.0 <= lon <= 97.0):
                raise ValueError(f"Coordinates outside India bounding box in {r['location_id']}: lat={lat}, lon={lon}")

            validated.append({
                "location_id": r["location_id"].strip(),
                "lgd_code": int(r["lgd_code"]),
                "location_name": r["location_name"].strip(),
                "location_type": r["location_type"].strip(),
                "district_name": r["district_name"].strip(),
                "state_code": r["state_code"].strip(),
                "pincode": r["pincode"].strip(),
                "latitude": lat,
                "longitude": lon,
            })
        return validated


class MandiMasterLoader(BaseLoader):
    """Loads and validates mandi_master.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            if not (8.0 <= lat <= 37.0 and 68.0 <= lon <= 97.0):
                raise ValueError(f"Mandi coords outside India bbox in {r['market_id']}: lat={lat}, lon={lon}")

            validated.append({
                "market_id": r["market_id"].strip(),
                "market_name": r["market_name"].strip(),
                "apmc_code": r["apmc_code"].strip(),
                "state_code": r["state_code"].strip(),
                "district_name": r["district_name"].strip(),
                "latitude": lat,
                "longitude": lon,
                "is_enam_integrated": r["is_enam_integrated"].strip().lower() in ("true", "1"),
            })
        return validated


class MandiPriceLoader(BaseLoader):
    """Loads and validates daily_mandi_prices.csv with unit verification."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            min_p = int(r["min_price_paise_per_gram"])
            max_p = int(r["max_price_paise_per_gram"])
            modal_p = int(r["modal_price_paise_per_gram"])

            # Invariant check: min <= modal <= max
            if not (min_p <= modal_p <= max_p):
                raise ValueError(f"Price invariant violated in {r['observation_id']}: min={min_p}, modal={modal_p}, max={max_p}")

            # Conversion integrity check: raw_modal_price_rs_per_quintal / 1000 == modal_price_paise_per_gram
            raw_rs = float(r["raw_modal_price_rs_per_quintal"])
            calc_paise = round(raw_rs / 100.0)
            if abs(calc_paise - modal_p) > 2:
                raise ValueError(f"Unit conversion mismatch in {r['observation_id']}: {raw_rs} Rs/Q vs {modal_p} paise/g")

            validated.append({
                "observation_id": r["observation_id"].strip(),
                "market_id": r["market_id"].strip(),
                "commodity_id": r["commodity_id"].strip(),
                "variety": r["variety"].strip(),
                "grade": r["grade"].strip(),
                "price_date": r["price_date"].strip(),
                "min_price_paise_per_gram": min_p,
                "max_price_paise_per_gram": max_p,
                "modal_price_paise_per_gram": modal_p,
                "original_reported_unit": r.get("original_reported_unit", "Rs/Quintal").strip(),
                "raw_modal_price_rs_per_quintal": raw_rs,
                "source_url": r["source_url"].strip(),
            })
        return validated


class MandiArrivalLoader(BaseLoader):
    """Loads and validates daily_mandi_arrivals.csv with mass unit verification."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            grams = int(r["arrival_quantity_grams"])
            raw_tonnes = float(r["original_reported_quantity_tonnes"])
            # 1 Tonne = 1,000,000 grams
            if grams != int(raw_tonnes * 1_000_000):
                raise ValueError(f"Tonne to gram conversion mismatch in {r['arrival_id']}")

            validated.append({
                "arrival_id": r["arrival_id"].strip(),
                "market_id": r["market_id"].strip(),
                "commodity_id": r["commodity_id"].strip(),
                "arrival_date": r["arrival_date"].strip(),
                "arrival_quantity_grams": grams,
                "original_reported_quantity_tonnes": raw_tonnes,
            })
        return validated


class RoadNetworkLoader:
    """Loads road_nodes.csv and road_segments.csv into routable graph representation."""
    def __init__(self, nodes_path: str, edges_path: str):
        self.nodes_loader = BaseLoader(nodes_path)
        self.edges_loader = BaseLoader(edges_path)

    def load(self) -> Dict[str, Any]:
        nodes_raw = self.nodes_loader.read_csv()
        edges_raw = self.edges_loader.read_csv()

        nodes = {}
        for n in nodes_raw:
            nid = n["node_id"].strip()
            lat = float(n["lat"])
            lon = float(n["lon"])
            if not (8.0 <= lat <= 37.0 and 68.0 <= lon <= 97.0):
                raise ValueError(f"Node coords outside India bbox in {nid}: lat={lat}, lon={lon}")

            nodes[nid] = {
                "node_id": nid,
                "name": n["name"].strip(),
                "lat": lat,
                "lon": lon,
                "node_type": n["node_type"].strip(),
            }

        edges = []
        for e in edges_raw:
            src = e["source_node"].strip()
            tgt = e["target_node"].strip()

            if src not in nodes:
                raise ValueError(f"Source node '{src}' does not exist in road_nodes.")
            if tgt not in nodes:
                raise ValueError(f"Target node '{tgt}' does not exist in road_nodes.")

            wt_lim = int(e["weight_limit_grams"]) if e.get("weight_limit_grams") and e["weight_limit_grams"].strip() != "" else None

            edges.append({
                "edge_id": e["edge_id"].strip(),
                "source_node": src,
                "target_node": tgt,
                "distance_meters": int(e["distance_meters"]),
                "speed_kmh": float(e["speed_kmh"]),
                "road_class": e["road_class"].strip(),
                "weight_limit_grams": wt_lim,
                "is_open": e["is_open"].strip().lower() in ("true", "1"),
                "closure_reason": e.get("closure_reason") or None,
            })

        return {"nodes": nodes, "edges": edges}


class StorageFacilityLoader(BaseLoader):
    """Loads and validates storage_facilities.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            if not (8.0 <= lat <= 37.0 and 68.0 <= lon <= 97.0):
                raise ValueError(f"Storage facility coords outside India bbox in {r['facility_id']}")

            validated.append({
                "facility_id": r["facility_id"].strip(),
                "facility_name": r["facility_name"].strip(),
                "fpo_id": r["fpo_id"].strip(),
                "facility_type": r["facility_type"].strip(),
                "total_capacity_grams": int(r["total_capacity_grams"]),
                "temperature_controlled": r["temperature_controlled"].strip().lower() in ("true", "1"),
                "latitude": lat,
                "longitude": lon,
            })
        return validated


class CropShelfLifeLoader(BaseLoader):
    """Loads and validates crop_shelf_life_rules.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "rule_id": r["rule_id"].strip(),
                "crop_name": r["crop_name"].strip(),
                "ambient_shelf_life_days": int(r["ambient_shelf_life_days"]),
                "cold_storage_shelf_life_days": int(r["cold_storage_shelf_life_days"]),
                "optimal_storage_temp_c": float(r["optimal_storage_temp_c"]),
                "optimal_humidity_pct": float(r["optimal_humidity_pct"]),
            })
        return validated


class FreightRateCardLoader(BaseLoader):
    """Loads and validates freight_rate_cards.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "rate_card_id": r["rate_card_id"].strip(),
                "vehicle_type": r["vehicle_type"].strip(),
                "base_mobilization_paise": int(r["base_mobilization_paise"]),
                "per_km_paise": int(r["per_km_paise"]),
                "max_capacity_grams": int(r["max_capacity_grams"]),
            })
        return validated


class SettlementDeductionsLoader(BaseLoader):
    """Loads and validates settlement_deductions.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "deduction_code": r["deduction_code"].strip(),
                "deduction_name": r["deduction_name"].strip(),
                "deduction_type": r["deduction_type"].strip(),
                "statutory_authority": r["statutory_authority"].strip(),
                "rate_basis": r["rate_basis"].strip(),
                "default_rate_paise_or_pct": float(r["default_rate_paise_or_pct"]),
            })
        return validated


class FPOMasterLoader(BaseLoader):
    """Loads and validates fpo_master.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "fpo_id": r["fpo_id"].strip(),
                "fpo_name": r["fpo_name"].strip(),
                "cin_registration_no": r["cin_registration_no"].strip(),
                "head_office_location_id": r["head_office_location_id"].strip(),
                "operating_district": r["operating_district"].strip(),
                "member_farmer_count": int(r["member_farmer_count"]),
            })
        return validated


class FarmerRegistryLoader(BaseLoader):
    """Loads and validates farmer_registry.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "farmer_id": r["farmer_id"].strip(),
                "farmer_name": r["farmer_name"].strip(),
                "fpo_id": r["fpo_id"].strip(),
                "village_location_id": r["village_location_id"].strip(),
                "landholding_acres": float(r["landholding_acres"]),
                "primary_crop": r["primary_crop"].strip(),
                "kyc_verified": r["kyc_verified"].strip().lower() in ("true", "1"),
            })
        return validated


class BuyerRegistryLoader(BaseLoader):
    """Loads and validates buyer_registry.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "buyer_id": r["buyer_id"].strip(),
                "business_name": r["business_name"].strip(),
                "gstin": r["gstin"].strip(),
                "buyer_category": r["buyer_category"].strip(),
                "terminal_location_id": r["terminal_location_id"].strip(),
                "credit_rating": r["credit_rating"].strip(),
            })
        return validated


class VehicleFleetLoader(BaseLoader):
    """Loads and validates vehicle_fleet.csv."""
    def load(self) -> List[Dict[str, Any]]:
        raw = self.read_csv()
        validated = []
        for r in raw:
            validated.append({
                "vehicle_id": r["vehicle_id"].strip(),
                "fpo_id": r["fpo_id"].strip(),
                "driver_id": r["driver_id"].strip(),
                "capacity_grams": int(r["capacity_grams"]),
                "vehicle_type": r["vehicle_type"].strip(),
                "is_available": r["is_available"].strip().lower() in ("true", "1"),
                "created_at": r["created_at"].strip(),
            })
        return validated
