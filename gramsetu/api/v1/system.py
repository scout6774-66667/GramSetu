from __future__ import annotations

from fastapi import APIRouter, Depends

from gramsetu.core import DevActor, Role, Settings, require_roles
from gramsetu.store import InMemoryStore
from gramsetu.release import get_system_readiness_report
from gramsetu.api.deps import get_store, get_app_settings

router = APIRouter(tags=["system"])


@router.get("/export/data")
async def get_export_data(
    actor: DevActor = Depends(require_roles(Role.SYSTEM)),
    store: InMemoryStore = Depends(get_store),
):
    return store.to_dict()


@router.get("/system/readiness")
async def get_system_readiness(
    store: InMemoryStore = Depends(get_store),
    cfg: Settings = Depends(get_app_settings),
):
    return get_system_readiness_report(store, str(cfg.ENVIRONMENT))
