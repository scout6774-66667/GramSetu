from __future__ import annotations

import uuid
from typing import List, Optional, Tuple
from gramsetu.core import DevActor, Role, AuthorizationError, get_current_utc
from gramsetu.schemas import HarvestForecastCreate, HarvestForecastResponse
from gramsetu.store import InMemoryStore, TransactionCoordinator


def create_harvest_forecast(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    actor: DevActor,
    payload: HarvestForecastCreate,
) -> Tuple[HarvestForecastResponse, bool]:
    """Create a new farmer harvest forecast idempotently. Returns (forecast, was_created)."""
    if actor.role not in (Role.FARMER, Role.SYSTEM):
        raise AuthorizationError("Only registered farmers or system engine can record harvest forecasts.")

    farmer_id = actor.actor_id
    fpo_id = actor.organization_id or "fpo-default"

    # Idempotency check
    if payload.idempotency_key:
        existing = store.list_items(
            "forecasts",
            lambda item: item.get("farmer_id") == farmer_id and item.get("idempotency_key") == payload.idempotency_key,
        )
        if existing:
            return HarvestForecastResponse(**existing[0]), False

    forecast_id = f"fc-{uuid.uuid4().hex[:10]}"
    now = get_current_utc()

    record = {
        "forecast_id": forecast_id,
        "farmer_id": farmer_id,
        "fpo_id": fpo_id,
        "crop": payload.crop,
        "variety": payload.variety,
        "grade": payload.grade,
        "estimated_grams": payload.estimated_grams,
        "harvest_start_date": payload.harvest_start_date.isoformat(),
        "harvest_end_date": payload.harvest_end_date.isoformat(),
        "confidence_score": payload.confidence_score,
        "created_at": now.isoformat(),
        "idempotency_key": payload.idempotency_key,
        "status": "ACTIVE",
    }

    with coordinator.transaction():
        coordinator.store.set_item("forecasts", forecast_id, record)

    return HarvestForecastResponse(**record), True


def list_harvest_forecasts(
    store: InMemoryStore,
    actor: DevActor,
    crop: Optional[str] = None,
    grade: Optional[str] = None,
) -> List[HarvestForecastResponse]:
    """List forecasts scoped by actor role and organization."""
    def filter_fn(item: dict) -> bool:
        if actor.role == Role.FARMER and item.get("farmer_id") != actor.actor_id:
            return False
        if actor.role == Role.FPO_ADMIN and item.get("fpo_id") != actor.organization_id:
            return False
        if crop and item.get("crop", "").lower() != crop.lower():
            return False
        if grade and item.get("grade", "").upper() != grade.upper():
            return False
        return True

    items = store.list_items("forecasts", filter_fn)
    return [HarvestForecastResponse(**item) for item in items]
