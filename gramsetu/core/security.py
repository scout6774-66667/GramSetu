"""Security, dev actor fixtures, authentication dependencies, and scoping checks."""
from __future__ import annotations

from typing import Optional, Dict, Callable
from pydantic import BaseModel, ConfigDict
from fastapi import Request, Depends

from gramsetu.core.config import Role, Environment
from gramsetu.core.exceptions import GramSetuError, AuthorizationError


class DevActor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str
    role: Role
    organization_id: Optional[str] = None
    name: str


DEV_ACTOR_HEADER = "X-Dev-Actor"
INSECURE_WARNING = "X-Dev-Actor is an insecure server-side test fixture and MUST NEVER be exposed in production."

DEV_ACTORS: Dict[str, DevActor] = {
    "farmer-1": DevActor(actor_id="farmer-1", role=Role.FARMER, organization_id="fpo-alpha", name="Ramesh Kumar"),
    "farmer-2": DevActor(actor_id="farmer-2", role=Role.FARMER, organization_id="fpo-alpha", name="Suresh Patel"),
    "farmer-other": DevActor(actor_id="farmer-other", role=Role.FARMER, organization_id="fpo-beta", name="Anil Singh"),
    "fpo-admin-alpha": DevActor(actor_id="fpo-admin-alpha", role=Role.FPO_ADMIN, organization_id="fpo-alpha", name="Alpha FPO Admin"),
    "fpo-admin-beta": DevActor(actor_id="fpo-admin-beta", role=Role.FPO_ADMIN, organization_id="fpo-beta", name="Beta FPO Admin"),
    "buyer-reliance": DevActor(actor_id="buyer-reliance", role=Role.BUYER, organization_id="org-reliance", name="Reliance Fresh Procurement"),
    "buyer-bigbasket": DevActor(actor_id="buyer-bigbasket", role=Role.BUYER, organization_id="org-bigbasket", name="BigBasket Sourcing"),
    "buyer-local": DevActor(actor_id="buyer-local", role=Role.BUYER, organization_id="org-local", name="Local Mandi Trader"),
    "driver-1": DevActor(actor_id="driver-1", role=Role.DRIVER, organization_id="fpo-alpha", name="Jagdish Transport"),
    "driver-2": DevActor(actor_id="driver-2", role=Role.DRIVER, organization_id="fpo-alpha", name="Mohan Carrier"),
    "driver-other": DevActor(actor_id="driver-other", role=Role.DRIVER, organization_id="fpo-beta", name="Vikram Freight"),
    "transporter-1": DevActor(actor_id="transporter-1", role=Role.TRANSPORTER, organization_id="fpo-alpha", name="Bengal Rural Transporters"),
    "storage-operator-1": DevActor(actor_id="storage-operator-1", role=Role.STORAGE_OPERATOR, organization_id="fpo-alpha", name="Burdwan Cold Storage Ltd"),
    "admin-master": DevActor(actor_id="admin-master", role=Role.ADMIN, organization_id=None, name="GramSetu System Administrator"),
    "system-worker": DevActor(actor_id="system-worker", role=Role.SYSTEM, organization_id=None, name="GramSetu System Engine"),
}


def get_current_actor(request: Request) -> DevActor:
    """Dependency: Extract authenticated actor via configured identity adapter."""
    app_state = getattr(getattr(request, "app", None), "state", None)
    if app_state and hasattr(app_state, "identity_adapter") and app_state.identity_adapter is not None:
        return app_state.identity_adapter.authenticate(request)

    # Fallback if app state has no explicit adapter
    if app_state and getattr(app_state, "settings", None):
        if app_state.settings.ENVIRONMENT == Environment.PRODUCTION:
            raise GramSetuError(
                message="Production authentication error: X-Dev-Actor test adapter is prohibited in production.",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

    actor_id = request.headers.get(DEV_ACTOR_HEADER)
    if not actor_id or actor_id not in DEV_ACTORS:
        raise GramSetuError(
            message=f"Authentication required: missing or unknown {DEV_ACTOR_HEADER} header.",
            status_code=401,
            error_code="UNAUTHORIZED",
        )
    return DEV_ACTORS[actor_id]


def require_roles(*allowed_roles: Role) -> Callable[[DevActor], DevActor]:
    """Dependency factory enforcing server-side role authorization."""
    def role_checker(actor: DevActor = Depends(get_current_actor)) -> DevActor:
        if actor.role in (Role.SYSTEM, Role.ADMIN):
            return actor
        if actor.role not in allowed_roles:
            raise AuthorizationError(
                f"Role '{actor.role.value}' is not authorized. Allowed roles: {[r.value for r in allowed_roles]}"
            )
        return actor
    return role_checker


def verify_organization_access(actor: DevActor, target_org_id: str) -> None:
    """Ensure actor belongs to target organization or is SYSTEM."""
    if actor.role == Role.SYSTEM:
        return
    if actor.organization_id != target_org_id:
        raise AuthorizationError(
            f"Actor '{actor.actor_id}' from org '{actor.organization_id}' is not authorized to access org '{target_org_id}'"
        )


def verify_driver_assignment(actor: DevActor, assigned_driver_id: str) -> None:
    """Ensure driver is explicitly assigned or actor is SYSTEM/FPO_ADMIN."""
    if actor.role == Role.SYSTEM:
        return
    if actor.role == Role.DRIVER and actor.actor_id != assigned_driver_id:
        raise AuthorizationError(
            f"Driver '{actor.actor_id}' is not assigned to this shipment (assigned driver: '{assigned_driver_id}')"
        )


def verify_farmer_access(actor: DevActor, farmer_id: str, fpo_id: Optional[str] = None) -> None:
    """Ensure farmer owns resource or actor is FPO_ADMIN of farmer's organization."""
    if actor.role == Role.SYSTEM:
        return
    if actor.role == Role.FARMER:
        if actor.actor_id != farmer_id:
            raise AuthorizationError(f"Farmer '{actor.actor_id}' cannot access farmer '{farmer_id}' records")
    elif actor.role == Role.FPO_ADMIN and fpo_id:
        verify_organization_access(actor, fpo_id)


def verify_buyer_access(actor: DevActor, buyer_id: str) -> None:
    """Ensure buyer owns resource or actor is SYSTEM."""
    if actor.role == Role.SYSTEM:
        return
    if actor.role == Role.BUYER and actor.actor_id != buyer_id:
        raise AuthorizationError(f"Buyer '{actor.actor_id}' cannot access buyer '{buyer_id}' records")
