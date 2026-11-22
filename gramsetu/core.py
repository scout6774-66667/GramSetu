"""Backward-compatible facade for gramsetu.core."""
from __future__ import annotations

from gramsetu.core.config import Environment, Role, Settings, get_current_utc
from gramsetu.core.exceptions import (
    GramSetuError,
    CorruptionError,
    DomainValidationError,
    NotFoundError,
    ConflictError,
    AuthorizationError,
    InvariantViolationError,
    ProcessLockError,
)
from gramsetu.core.security import (
    DevActor,
    DEV_ACTOR_HEADER,
    INSECURE_WARNING,
    DEV_ACTORS,
    get_current_actor,
    require_roles,
    verify_organization_access,
    verify_driver_assignment,
    verify_farmer_access,
    verify_buyer_access,
)

__all__ = [
    "Environment",
    "Role",
    "Settings",
    "get_current_utc",
    "GramSetuError",
    "CorruptionError",
    "DomainValidationError",
    "NotFoundError",
    "ConflictError",
    "AuthorizationError",
    "InvariantViolationError",
    "ProcessLockError",
    "DevActor",
    "DEV_ACTOR_HEADER",
    "INSECURE_WARNING",
    "DEV_ACTORS",
    "get_current_actor",
    "require_roles",
    "verify_organization_access",
    "verify_driver_assignment",
    "verify_farmer_access",
    "verify_buyer_access",
]
