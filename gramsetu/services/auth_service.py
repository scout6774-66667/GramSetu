"""GramSetu AI Authentication & Identity Service (Module 14).

Provides:
- Secure user registration and authentication for all system stakeholders:
  - Farmers
  - FPO Administrators
  - Buyers
  - Transporters
  - Storage Operators
  - System Administrators
- Cryptographically salted password hashing via PBKDF2-HMAC-SHA256.
- Production-grade signed JWT Bearer token generation.
"""
from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from typing import Optional, Dict, Any, Tuple
import jwt

from gramsetu.core import (
    Settings,
    Role,
    DevActor,
    DEV_ACTORS,
    GramSetuError,
    AuthorizationError,
    get_current_utc,
)
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
)


def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 with cryptographically random salt."""
    if not salt:
        salt = base64.b64encode(os.urandom(16)).decode("utf-8")
    pwd_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    derived = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, iterations=100_000)
    hashed_str = base64.b64encode(derived).decode("utf-8")
    return hashed_str, salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify password against stored salt and hash."""
    hashed, _ = _hash_password(password, salt)
    return hashed == stored_hash


def register_user(
    store: InMemoryStore,
    coordinator: TransactionCoordinator,
    settings: Settings,
    payload: UserRegisterRequest,
) -> TokenResponse:
    """Register a new user, store credential securely, and issue initial JWT."""
    username = payload.username.strip().lower()

    # Uniqueness check
    existing = store.list_items("users", lambda it: it.get("username") == username)
    if existing:
        raise GramSetuError(
            message=f"Username '{username}' is already registered.",
            status_code=409,
            error_code="CONFLICT",
        )

    actor_id = f"user-{uuid.uuid4().hex[:8]}"
    hashed_pwd, salt = _hash_password(payload.password)
    now = get_current_utc()

    user_record = {
        "user_id": actor_id,
        "username": username,
        "password_hash": hashed_pwd,
        "password_salt": salt,
        "role": payload.role.value,
        "name": payload.name,
        "organization_id": payload.organization_id or "fpo-alpha",
        "contact_phone": payload.contact_phone,
        "is_active": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    with coordinator.transaction():
        coordinator.store.set_item("users", actor_id, user_record)

    # Issue JWT
    token = _create_jwt_token(
        settings=settings,
        actor_id=actor_id,
        role=payload.role.value,
        org_id=user_record["organization_id"],
        name=payload.name,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=86400,
        actor_id=actor_id,
        role=payload.role.value,
        organization_id=user_record["organization_id"],
        name=payload.name,
    )


def login_user(
    store: InMemoryStore,
    settings: Settings,
    payload: UserLoginRequest,
) -> TokenResponse:
    """Authenticate username and password, then issue signed JWT."""
    username = payload.username.strip().lower()

    # 1. Check registered users collection
    users = store.list_items("users", lambda it: it.get("username") == username)
    if users:
        user = users[0]
        if not user.get("is_active", True):
            raise AuthorizationError("Account is inactive or disabled.")

        if not _verify_password(payload.password, user["password_hash"], user["password_salt"]):
            raise GramSetuError(
                message="Invalid username or password.",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

        token = _create_jwt_token(
            settings=settings,
            actor_id=user["user_id"],
            role=user["role"],
            org_id=user.get("organization_id"),
            name=user.get("name", username),
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=86400,
            actor_id=user["user_id"],
            role=user["role"],
            organization_id=user.get("organization_id"),
            name=user.get("name", username),
        )

    # 2. Check DEV_ACTORS fixture (password == username for test accounts, supporting common aliases)
    ALIAS_MAP = {
        "fpo_admin": "fpo-admin-alpha",
        "farmer_subhash": "farmer-1",
        "farmer": "farmer-1",
        "buyer_apex": "buyer-reliance",
        "buyer": "buyer-reliance",
        "driver_mandal": "driver-1",
        "driver": "driver-1",
        "transporter": "transporter-1",
        "storage_operator": "storage-operator-1",
        "admin": "admin-master",
    }
    lookup_user = ALIAS_MAP.get(username, username)
    if lookup_user in DEV_ACTORS and (payload.password == username or payload.password == lookup_user):
        dev_actor = DEV_ACTORS[lookup_user]
        token = _create_jwt_token(
            settings=settings,
            actor_id=dev_actor.actor_id,
            role=dev_actor.role.value,
            org_id=dev_actor.organization_id,
            name=dev_actor.name,
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=86400,
            actor_id=dev_actor.actor_id,
            role=dev_actor.role.value,
            organization_id=dev_actor.organization_id,
            name=dev_actor.name,
        )

    raise GramSetuError(
        message="Invalid username or password.",
        status_code=401,
        error_code="UNAUTHORIZED",
    )


def _create_jwt_token(
    settings: Settings,
    actor_id: str,
    role: str,
    org_id: Optional[str],
    name: str,
    expires_in: int = 86400,
) -> str:
    """Generate signed JWT Bearer token with claims matching JwtIdentityAdapter expectations."""
    now = int(time.time())
    secret = getattr(settings, "JWT_SECRET_KEY", "gramsetu-dev-insecure-secret-key-32b")
    issuer = getattr(settings, "JWT_ISSUER", "gramsetu-auth")
    audience = getattr(settings, "JWT_AUDIENCE", "gramsetu-api")
    algorithm = getattr(settings, "JWT_ALGORITHMS", ["HS256"])[0]

    payload = {
        "sub": actor_id,
        "role": role,
        "org_id": org_id or "fpo-alpha",
        "name": name,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in,
    }

    return jwt.encode(payload, secret, algorithm=algorithm)
