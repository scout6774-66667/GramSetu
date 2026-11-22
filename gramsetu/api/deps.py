from __future__ import annotations

from typing import Optional
from fastapi import Request

from gramsetu.core import Settings, DevActor, get_current_actor, require_roles
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.security.identity import get_identity_adapter


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_store(request: Request) -> InMemoryStore:
    return request.app.state.store


def get_coordinator(request: Request) -> TransactionCoordinator:
    return request.app.state.coordinator


def get_identity(request: Request):
    return request.app.state.identity_adapter


__all__ = [
    "get_app_settings",
    "get_store",
    "get_coordinator",
    "get_identity",
    "get_current_actor",
    "require_roles",
]
