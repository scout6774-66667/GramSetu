"""GramSetu AI Storage & Spoilage Risk Management Service (Module 7).

Provides:
- Storage facility registration and real-time capacity tracking.
- Spoilage risk scoring based on crop shelf-life decay dynamics and storage duration.
- Honest sensor telemetry state: explicitly disclaims lack of live calibrated IoT
  environmental feeds when storage_sensor_measurements.csv is absent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    DomainValidationError,
    get_current_utc,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    StorageFacilityCreate,
    StorageFacilityResponse,
    SpoilageRiskItem,
)
from gramsetu.services.farmer import PILOT_COMMODITIES

SHELF_LIFE_MAP: Dict[str, int] = {
    c["commodity_name"].lower(): c["default_shelf_life_days"] for c in PILOT_COMMODITIES
}
SHELF_LIFE_MAP.update({
    "potato": 45,
    "rice": 365,
    "paddy": 365,
    "rice (paddy)": 365,
    "tomato": 10,
    "onion": 60,
    "mustard": 270,
    "soybean": 180,
    "wheat": 365,
    "pomegranate": 30,
})


def register_storage_facility(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: StorageFacilityCreate,
) -> StorageFacilityResponse:
    """Register a new storage silo, warehouse, or cold storage bay."""
    facility_id = f"fac-{uuid.uuid4().hex[:8]}"
    now = get_current_utc()

    record = {
        "facility_id": facility_id,
        "facility_name": payload.facility_name,
        "fpo_id": payload.fpo_id or actor.organization_id or "fpo-alpha",
        "location_name": payload.location_name,
        "district": payload.district,
        "total_capacity_grams": payload.total_capacity_grams,
        "temperature_controlled": payload.temperature_controlled,
        "target_temp_celsius": payload.target_temp_celsius,
        "created_at": now.isoformat(),
    }

    with coordinator.transaction():
        coordinator.store.set_item("facilities", facility_id, record)

    return _format_facility_response(store, record)


def list_storage_facilities(
    store: InMemoryStore,
    fpo_id: Optional[str] = None,
    district: Optional[str] = None,
) -> List[StorageFacilityResponse]:
    """List storage facilities with current capacity utilization."""
    facilities = store.list_items("facilities")
    if not facilities:
        # Default cold storage bay in pilot location
        now = get_current_utc().isoformat()
        facilities = [
            {
                "facility_id": "FAC-WH-01",
                "facility_name": "Burdwan Central Ag-Warehouse",
                "fpo_id": "fpo-alpha",
                "location_name": "Galsi Industrial Area",
                "district": "Purba Bardhaman",
                "total_capacity_grams": 50_000_000,
                "temperature_controlled": True,
                "target_temp_celsius": 12.0,
                "created_at": now,
            },
            {
                "facility_id": "FAC-WH-02",
                "facility_name": "Kalna Rural Cold Storage",
                "fpo_id": "fpo-alpha",
                "location_name": "Kalna Mandi Complex",
                "district": "Purba Bardhaman",
                "total_capacity_grams": 30_000_000,
                "temperature_controlled": True,
                "target_temp_celsius": 4.0,
                "created_at": now,
            },
        ]

    filtered = []
    for f in facilities:
        if fpo_id and f.get("fpo_id") != fpo_id:
            continue
        if district and f.get("district", "").lower() != district.lower():
            continue
        filtered.append(_format_facility_response(store, f))

    return filtered


def get_storage_facility(store: InMemoryStore, facility_id: str) -> StorageFacilityResponse:
    """Get single facility with utilization metrics."""
    raw = store.get_item("facilities", facility_id)
    if not raw:
        if facility_id in ("FAC-WH-01", "Bay-P1"):
            now = get_current_utc().isoformat()
            raw = {
                "facility_id": facility_id,
                "facility_name": "Burdwan Central Ag-Warehouse",
                "fpo_id": "fpo-alpha",
                "location_name": "Galsi",
                "district": "Purba Bardhaman",
                "total_capacity_grams": 50_000_000,
                "temperature_controlled": True,
                "target_temp_celsius": 12.0,
                "created_at": now,
            }
        else:
            raise NotFoundError(f"Storage facility '{facility_id}' not found.")

    return _format_facility_response(store, raw)


def compute_facility_spoilage_risks(
    store: InMemoryStore,
    fpo_id: str = "fpo-alpha",
) -> List[SpoilageRiskItem]:
    """Evaluate spoilage risks for all active stored lots."""
    lots = store.list_items("lots", lambda it: it.get("quantity_grams", 0) > 0)
    now = get_current_utc()
    risks: List[SpoilageRiskItem] = []

    for lot in lots:
        crop_lower = lot.get("crop", "").lower()
        shelf_life = SHELF_LIFE_MAP.get(crop_lower, 30)

        created_str = lot.get("created_at")
        if created_str:
            try:
                created_dt = datetime.fromisoformat(created_str)
                days_stored = max(1, (now - created_dt).days)
            except Exception:
                days_stored = 1
        else:
            days_stored = 1

        risk_pct = min(100.0, round((days_stored / float(shelf_life)) * 100.0, 1))
        days_remaining = max(0, shelf_life - days_stored)

        if risk_pct >= 90.0:
            level = "CRITICAL"
            rec = "IMMEDIATE DISPOSAL OR CLEARANCE SALE REQUIRED to avoid total loss."
        elif risk_pct >= 75.0:
            level = "HIGH"
            rec = "Expedite dispatch or activate buyer recovery candidate allocation."
        elif risk_pct >= 50.0:
            level = "MODERATE"
            rec = "Monitor storage conditions closely; schedule upcoming shipment."
        else:
            level = "LOW"
            rec = "Stock is fresh and within safe shelf-life parameters."

        risks.append(
            SpoilageRiskItem(
                lot_id=lot["lot_id"],
                crop=lot["crop"],
                grade=lot["grade"],
                storage_location=lot.get("storage_location", "Main Bay"),
                days_in_storage=days_stored,
                max_shelf_life_days=shelf_life,
                spoilage_risk_pct=risk_pct,
                risk_level=level,
                recommendation=rec,
                sensor_evidence="THEORETICAL_DECAY_CURVE_NO_IOT",
            )
        )

    return sorted(risks, key=lambda x: x.spoilage_risk_pct, reverse=True)


def _format_facility_response(store: InMemoryStore, data: Dict[str, Any]) -> StorageFacilityResponse:
    f_id = data["facility_id"]
    cap = int(data.get("total_capacity_grams", 50_000_000))

    # Compute actual utilization from active lots stored in this facility
    stored_lots = store.list_items(
        "lots",
        lambda it: (it.get("storage_location") == f_id or it.get("storage_location", "").startswith(f_id))
        and it.get("quantity_grams", 0) > 0,
    )
    utilized = sum(it.get("quantity_grams", 0) for it in stored_lots)
    available = max(0, cap - utilized)
    util_pct = min(100.0, round((utilized / float(cap)) * 100.0, 1)) if cap > 0 else 0.0

    return StorageFacilityResponse(
        facility_id=f_id,
        facility_name=data["facility_name"],
        fpo_id=data.get("fpo_id", "fpo-alpha"),
        location_name=data.get("location_name", "Warehouse Central"),
        district=data.get("district", "Purba Bardhaman"),
        total_capacity_grams=cap,
        utilized_grams=utilized,
        available_grams=available,
        utilization_pct=util_pct,
        temperature_controlled=data.get("temperature_controlled", False),
        target_temp_celsius=data.get("target_temp_celsius"),
        sensor_telemetry_status="UNAVAILABLE_NO_CALIBRATED_SENSORS",
        status_notice=(
            "Facility records are operator-reported. Real-time calibrated IoT environmental "
            "feed is unavailable; spoilage risks are computed via agronomic shelf-life decay curves."
        ),
        created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
    )
