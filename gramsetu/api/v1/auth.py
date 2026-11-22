from __future__ import annotations

from fastapi import APIRouter, Depends, status

from gramsetu.core import (
    DevActor,
    Role,
    get_current_actor,
    require_roles,
    verify_organization_access,
    verify_driver_assignment,
)
from gramsetu.api.deps import get_store, get_coordinator, get_app_settings
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.core import Settings
from gramsetu.schemas import DriverActionPayload, UserRegisterRequest, UserLoginRequest, TokenResponse
from gramsetu.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def auth_register(
    payload: UserRegisterRequest,
    store: InMemoryStore = Depends(get_store),
    coordinator: TransactionCoordinator = Depends(get_coordinator),
    settings: Settings = Depends(get_app_settings),
):
    """Register new user credential and issue signed JWT."""
    return register_user(store, coordinator, settings, payload)


@router.post("/login", response_model=TokenResponse)
async def auth_login(
    payload: UserLoginRequest,
    store: InMemoryStore = Depends(get_store),
    settings: Settings = Depends(get_app_settings),
):
    """Authenticate with username and password, returns signed JWT Bearer token."""
    return login_user(store, settings, payload)


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
