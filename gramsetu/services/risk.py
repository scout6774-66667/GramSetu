from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from gramsetu.core import (
    DevActor,
    Role,
    AuthorizationError,
    NotFoundError,
    InvariantViolationError,
    get_current_utc,
    verify_organization_access,
)
from gramsetu.schemas import RiskIncidentResponse, IncidentResolveRequest
from gramsetu.store import InMemoryStore, TransactionCoordinator


CROP_SHELF_LIFE_DAYS = {
    "tomato": 3,
    "leafy": 2,
    "banana": 5,
    "apple": 14,
    "potato": 30,
    "onion": 30,
    "wheat": 90,
    "rice": 90,
    "corn": 60,
    "default": 7,
}


def scan_risk_incidents(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    fpo_id: str,
    as_of: Optional[datetime] = None,
) -> List[RiskIncidentResponse]:
    """Scan supply chain objects for risks, create deduplicated incidents, and adjust severities."""
    if actor.role not in (Role.FPO_ADMIN, Role.SYSTEM):
        raise AuthorizationError("Only FPO admins or system engine can trigger risk scanning.")

    verify_organization_access(actor, fpo_id)
    now = as_of or get_current_utc()

    detected_incidents: List[dict] = []

    # 1. Scan Shipments (rejections, shortages, missed pickups)
    shipments = store.list_items("shipments")
    for s in shipments:
        commit = store.get_item("commitments", s.get("commitment_id", ""))
        if not commit or commit.get("fpo_id") != fpo_id:
            continue

        ship_id = s["shipment_id"]

        # Quality rejections
        rej = s.get("rejected_grams") or 0
        if s.get("status") == "DELIVERED" and rej > 0:
            severity = "HIGH" if rej >= 100_000 else "MEDIUM"
            detected_incidents.append({
                "incident_type": "QUALITY_REJECTION",
                "dedup_key": f"QUALITY_REJECTION:{ship_id}",
                "severity": severity,
                "title": f"Quality Rejection on Shipment {ship_id}",
                "description": f"Receiver rejected {rej}g due to quality inspection failure.",
                "resource_type": "shipment",
                "resource_id": ship_id,
                "affected_grams": rej,
                "affected_paise": 0,
            })

        # Short deliveries / transit losses
        loss = s.get("loss_grams") or 0
        if s.get("status") == "DELIVERED" and loss > 0:
            severity = "HIGH" if loss >= 50_000 else "LOW"
            detected_incidents.append({
                "incident_type": "SHORT_DELIVERY",
                "dedup_key": f"SHORT_DELIVERY:{ship_id}",
                "severity": severity,
                "title": f"In-Transit Shortage on Shipment {ship_id}",
                "description": f"Driver delivered with {loss}g unaccounted shortage/loss.",
                "resource_type": "shipment",
                "resource_id": ship_id,
                "affected_grams": loss,
                "affected_paise": 0,
            })

        # Missed pickup deadline (> 24 hours planned without pickup)
        if s.get("status") == "PLANNED":
            created_dt = datetime.fromisoformat(s["created_at"])
            if (now - created_dt) > timedelta(hours=24):
                detected_incidents.append({
                    "incident_type": "MISSED_PICKUP",
                    "dedup_key": f"MISSED_PICKUP:{ship_id}",
                    "severity": "HIGH",
                    "title": f"Missed Pickup on Shipment {ship_id}",
                    "description": "Shipment has remained planned for over 24 hours without driver pickup.",
                    "resource_type": "shipment",
                    "resource_id": ship_id,
                    "affected_grams": s.get("dispatched_grams", 0),
                    "affected_paise": 0,
                })

    # 2. Scan Commitments (disruptions / cancellations)
    commitments = store.list_items("commitments", lambda c: c.get("fpo_id") == fpo_id)
    for c in commitments:
        if c.get("status") == "CANCELLED":
            c_id = c["commitment_id"]
            detected_incidents.append({
                "incident_type": "CANCELLED_ORDER",
                "dedup_key": f"CANCELLED_ORDER:{c_id}",
                "severity": "MEDIUM",
                "title": f"Buyer Cancelled Order {c_id}",
                "description": f"Procurement commitment for {c.get('committed_grams', 0)}g was cancelled.",
                "resource_type": "commitment",
                "resource_id": c_id,
                "affected_grams": c.get("committed_grams", 0),
                "affected_paise": 0,
            })

    # 3. Scan Lots (perishability / aging risk)
    lots = store.list_items("lots", lambda item: item.get("fpo_id") == fpo_id and item.get("status") == "AVAILABLE")
    for lot_item in lots:
        crop_lower = lot_item.get("crop", "").lower()
        shelf_life = CROP_SHELF_LIFE_DAYS.get(crop_lower, CROP_SHELF_LIFE_DAYS["default"])
        created_dt = datetime.fromisoformat(lot_item["created_at"])
        age_days = (now - created_dt).total_seconds() / 86400.0

        if age_days > shelf_life:
            severity = "CRITICAL" if age_days > (shelf_life * 2) else "HIGH"
            lot_id = lot_item["lot_id"]
            detected_incidents.append({
                "incident_type": "AGING_RISK",
                "dedup_key": f"AGING_RISK:{lot_id}",
                "severity": severity,
                "title": f"Perishable Aging Alert on Lot {lot_id}",
                "description": f"{lot_item.get('crop')} lot has been in storage for {round(age_days, 1)} days (shelf-life: {shelf_life} days).",
                "resource_type": "lot",
                "resource_id": lot_id,
                "affected_grams": lot_item.get("quantity_grams", 0),
                "affected_paise": 0,
            })

    # Deduplicate and commit into store
    results: List[RiskIncidentResponse] = []
    with coordinator.transaction():
        for inc_dict in detected_incidents:
            key = inc_dict["dedup_key"]
            existing = coordinator.store.list_items(
                "incidents",
                lambda item: item.get("dedup_key") == key and item.get("fpo_id") == fpo_id,
            )
            if existing:
                inc_record = existing[0]
                # Update severity if escalated
                inc_record["severity"] = inc_dict["severity"]
                inc_record["updated_at"] = now.isoformat()
                coordinator.store.set_item("incidents", inc_record["incident_id"], inc_record)
                results.append(RiskIncidentResponse(**inc_record))
            else:
                inc_id = f"inc-{uuid.uuid4().hex[:10]}"
                inc_record = {
                    "incident_id": inc_id,
                    "fpo_id": fpo_id,
                    "incident_type": inc_dict["incident_type"],
                    "dedup_key": key,
                    "severity": inc_dict["severity"],
                    "title": inc_dict["title"],
                    "description": inc_dict["description"],
                    "resource_type": inc_dict["resource_type"],
                    "resource_id": inc_dict["resource_id"],
                    "affected_grams": inc_dict.get("affected_grams", 0),
                    "affected_paise": inc_dict.get("affected_paise", 0),
                    "status": "OPEN",
                    "resolution_note": None,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                coordinator.store.set_item("incidents", inc_id, inc_record)
                results.append(RiskIncidentResponse(**inc_record))

    return results


def acknowledge_incident(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    incident_id: str,
) -> RiskIncidentResponse:
    """Acknowledge an open risk incident."""
    with coordinator.transaction():
        inc = coordinator.store.get_item("incidents", incident_id)
        if not inc:
            raise NotFoundError(f"Incident '{incident_id}' not found.")
        verify_organization_access(actor, inc["fpo_id"])

        inc["status"] = "ACKNOWLEDGED"
        inc["updated_at"] = get_current_utc().isoformat()
        coordinator.store.set_item("incidents", incident_id, inc)

    return RiskIncidentResponse(**inc)


def resolve_incident(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    incident_id: str,
    payload: IncidentResolveRequest,
) -> RiskIncidentResponse:
    """Resolve an incident with a verifiable note."""
    if not payload.resolution_note or len(payload.resolution_note.strip()) < 3:
        raise InvariantViolationError("Resolution note must provide a verifiable resolution description.")

    with coordinator.transaction():
        inc = coordinator.store.get_item("incidents", incident_id)
        if not inc:
            raise NotFoundError(f"Incident '{incident_id}' not found.")
        verify_organization_access(actor, inc["fpo_id"])

        inc["status"] = "RESOLVED"
        inc["resolution_note"] = payload.resolution_note.strip()
        inc["updated_at"] = get_current_utc().isoformat()
        coordinator.store.set_item("incidents", incident_id, inc)

    return RiskIncidentResponse(**inc)


def list_incidents(
    store: InMemoryStore,
    actor: DevActor,
    fpo_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[RiskIncidentResponse]:
    """List risk incidents scoped by actor."""
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.FPO_ADMIN and item.get("fpo_id") != actor.organization_id:
            return False
        if fpo_id and item.get("fpo_id") != fpo_id:
            return False
        if status and item.get("status", "").upper() != status.upper():
            return False
        return True

    items = store.list_items("incidents", filter_fn)
    return [RiskIncidentResponse(**item) for item in items]
