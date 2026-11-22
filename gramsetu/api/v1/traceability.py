"""BatchTrace End-to-End Traceability Timeline API Router (Module 8)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, get_current_actor
from gramsetu.api.deps import get_store
from gramsetu.store import InMemoryStore
from gramsetu.schemas import BatchTraceTimelineResponse
from gramsetu.services.traceability import get_lot_traceability_timeline

router = APIRouter(prefix="/traceability", tags=["traceability"])


@router.get("/{lot_id}", response_model=BatchTraceTimelineResponse)
async def api_get_traceability_timeline(
    lot_id: str,
    actor: DevActor = Depends(get_current_actor),
    store: InMemoryStore = Depends(get_store),
):
    """Reconstruct complete chronological custody and transformation timeline for a lot."""
    return get_lot_traceability_timeline(store, actor, lot_id)
