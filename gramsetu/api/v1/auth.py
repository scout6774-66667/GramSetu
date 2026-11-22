from __future__ import annotations

from fastapi import APIRouter, Depends

from gramsetu.core import (
    DevActor,
    Role,
    get_current_actor,
    require_roles,
    verify_organization_access,
    verify_driver_assignment,
)
from gramsetu.schemas import DriverActionPayload

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def auth_me(actor: DevActor = Depends(get_current_actor)):
    return {
        "actor_id": actor.actor_id,
        "role": actor.role.value,
        "organization_id": actor.organization_id,
        "name": actor.name,
    }


@router.get("/fpo-only")
async def auth_fpo_only(actor: DevActor = Depends(require_roles(Role.FPO_ADMIN))):
    return {"status": "authorized", "actor_id": actor.actor_id}


@router.get("/fpo/{fpo_id}/check")
async def auth_fpo_org_check(fpo_id: str, actor: DevActor = Depends(require_roles(Role.FPO_ADMIN))):
    verify_organization_access(actor, fpo_id)
    return {"status": "authorized", "fpo_id": fpo_id}


@router.post("/driver-action")
async def auth_driver_action(
    payload: DriverActionPayload,
    actor: DevActor = Depends(require_roles(Role.DRIVER, Role.FPO_ADMIN)),
):
    verify_driver_assignment(actor, payload.assigned_driver_id)
    return {
        "status": "authorized",
        "action": payload.action,
        "driver_id": payload.assigned_driver_id,
    }
