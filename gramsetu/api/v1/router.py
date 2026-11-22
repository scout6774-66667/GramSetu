from __future__ import annotations

from fastapi import APIRouter

from gramsetu.api.v1.auth import router as auth_router
from gramsetu.api.v1.demand import router as demand_router
from gramsetu.api.v1.commitments import router as commitments_router
from gramsetu.api.v1.logistics import router as logistics_router
from gramsetu.api.v1.risk import router as risk_router
from gramsetu.api.v1.recovery import router as recovery_router
from gramsetu.api.v1.settlements import router as settlements_router
from gramsetu.api.v1.inventory import router as inventory_router
from gramsetu.api.v1.overview import router as overview_router
from gramsetu.api.v1.sync import router as sync_router
from gramsetu.api.v1.system import router as system_router
from gramsetu.api.v1.admin import router as admin_router
from gramsetu.api.v1.market import router as market_router
from gramsetu.api.v1.farmers import router as farmers_router
from gramsetu.api.v1.listings import router as listings_router
from gramsetu.api.v1.buyers import router as buyers_router
from gramsetu.api.v1.transport import router as transport_router
from gramsetu.api.v1.storage import router as storage_router
from gramsetu.api.v1.traceability import router as traceability_router
from gramsetu.api.v1.voice import router as voice_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(farmers_router)
api_v1_router.include_router(listings_router)
api_v1_router.include_router(buyers_router)
api_v1_router.include_router(demand_router)
api_v1_router.include_router(commitments_router)
api_v1_router.include_router(transport_router)
api_v1_router.include_router(logistics_router)
api_v1_router.include_router(storage_router)
api_v1_router.include_router(traceability_router)
api_v1_router.include_router(risk_router)
api_v1_router.include_router(recovery_router)
api_v1_router.include_router(settlements_router)
api_v1_router.include_router(inventory_router)
api_v1_router.include_router(overview_router)
api_v1_router.include_router(sync_router)
api_v1_router.include_router(system_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(market_router)
api_v1_router.include_router(voice_router)

__all__ = ["api_v1_router"]
