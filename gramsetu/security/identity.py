from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import jwt
from fastapi import Request

from gramsetu.core import (
    Settings,
    Environment,
    Role,
    DevActor,
    DEV_ACTORS,
    DEV_ACTOR_HEADER,
    GramSetuError,
)

logger = logging.getLogger("gramsetu.security")


class IdentityAdapter(ABC):
    """Abstract authentication adapter interface."""

    @abstractmethod
    def authenticate(self, request: Request) -> DevActor:
        """Extract and verify actor credentials from incoming request."""
        raise NotImplementedError


class DevIdentityAdapter(IdentityAdapter):
    """Development/testing identity adapter reading X-Dev-Actor header."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def authenticate(self, request: Request) -> DevActor:
        # Hard fail-closed in production
        if self.settings.ENVIRONMENT == Environment.PRODUCTION:
            raise GramSetuError(
                message="Production authentication error: X-Dev-Actor test adapter is prohibited in production.",
                status_code=401,
                error_code="UNAUTHORIZED",
                details={"reason": "DEV_ACTOR_PROHIBITED_IN_PRODUCTION"},
            )

        actor_id = request.headers.get(DEV_ACTOR_HEADER)
        if not actor_id:
            raise GramSetuError(
                message=f"Authentication required: missing {DEV_ACTOR_HEADER} header.",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

        if actor_id not in DEV_ACTORS:
            raise GramSetuError(
                message=f"Authentication failed: unknown actor '{actor_id}'.",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

        return DEV_ACTORS[actor_id]


class JwtIdentityAdapter(IdentityAdapter):
    """Production-grade JWT authentication adapter with pinned algorithms and strict claim validation."""

    def __init__(
        self,
        settings: Settings,
        secret_key: Optional[str] = None,
        algorithms: Optional[List[str]] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
    ):
        self.settings = settings
        self.secret_key = secret_key or getattr(settings, "JWT_SECRET_KEY", "gramsetu-dev-insecure-secret-key-32b")
        # Explicitly pinned cryptographic algorithms. "none" is strictly forbidden.
        raw_algorithms = algorithms or getattr(settings, "JWT_ALGORITHMS", ["HS256"])
        self.algorithms = [alg for alg in raw_algorithms if alg.lower() != "none"]
        if not self.algorithms:
            self.algorithms = ["HS256"]
        self.issuer = issuer or getattr(settings, "JWT_ISSUER", "gramsetu-auth")
        self.audience = audience or getattr(settings, "JWT_AUDIENCE", "gramsetu-api")

    def authenticate(self, request: Request) -> DevActor:
        # Explicit rejection of X-Dev-Actor if attempted in production or JWT mode
        if DEV_ACTOR_HEADER in request.headers and self.settings.ENVIRONMENT == Environment.PRODUCTION:
            raise GramSetuError(
                message="X-Dev-Actor header is strictly prohibited in production.",
                status_code=401,
                error_code="UNAUTHORIZED",
                details={"reason": "DEV_ACTOR_PROHIBITED_IN_PRODUCTION"},
            )

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise GramSetuError(
                message="Authentication required: missing Authorization Bearer token.",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise GramSetuError(
                message="Invalid Authorization header format. Expected 'Bearer <token>'.",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

        token = parts[1]

        # Inspect unverified header to ensure 'none' algorithm is rejected before parsing
        try:
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg", "").lower()
            if alg == "none" or alg not in [a.lower() for a in self.algorithms]:
                raise GramSetuError(
                    message=f"Unsupported or insecure JWT algorithm: '{unverified_header.get('alg')}'.",
                    status_code=401,
                    error_code="UNAUTHORIZED",
                    details={"unsupported_algorithm": unverified_header.get("alg")},
                )
        except GramSetuError:
            raise
        except Exception as exc:
            raise GramSetuError(
                message=f"Malformed JWT header: {exc}",
                status_code=401,
                error_code="UNAUTHORIZED",
            ) from exc

        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=self.algorithms,
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require": ["exp", "iss", "aud", "sub"],
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise GramSetuError(
                message="Authentication token has expired.",
                status_code=401,
                error_code="TOKEN_EXPIRED",
            ) from exc
        except jwt.InvalidSignatureError as exc:
            raise GramSetuError(
                message="Invalid JWT signature.",
                status_code=401,
                error_code="UNAUTHORIZED",
            ) from exc
        except jwt.InvalidIssuerError as exc:
            raise GramSetuError(
                message=f"Invalid JWT issuer.",
                status_code=401,
                error_code="UNAUTHORIZED",
            ) from exc
        except jwt.InvalidAudienceError as exc:
            raise GramSetuError(
                message=f"Invalid JWT audience.",
                status_code=401,
                error_code="UNAUTHORIZED",
            ) from exc
        except jwt.PyJWTError as exc:
            raise GramSetuError(
                message=f"Token verification failed: {exc}",
                status_code=401,
                error_code="UNAUTHORIZED",
            ) from exc

        actor_id = payload.get("sub")
        role_str = payload.get("role")
        if not actor_id or not role_str:
            raise GramSetuError(
                message="JWT payload missing required claims 'sub' or 'role'.",
                status_code=401,
                error_code="UNAUTHORIZED",
            )

        try:
            role = Role(role_str)
        except ValueError:
            raise GramSetuError(
                message=f"Invalid actor role '{role_str}' in JWT claims.",
                status_code=403,
                error_code="FORBIDDEN",
            )

        org_id = payload.get("org_id")
        name = payload.get("name", actor_id)

        return DevActor(
            actor_id=actor_id,
            role=role,
            organization_id=org_id,
            name=name,
        )


class HybridIdentityAdapter(IdentityAdapter):
    """Adapter that accepts JWT Bearer tokens, or falls back to X-Dev-Actor in non-production environments."""

    def __init__(self, settings: Settings, jwt_adapter: JwtIdentityAdapter, dev_adapter: DevIdentityAdapter):
        self.settings = settings
        self.jwt_adapter = jwt_adapter
        self.dev_adapter = dev_adapter

    def authenticate(self, request: Request) -> DevActor:
        # If running in production: strictly enforce JWT adapter
        if self.settings.ENVIRONMENT == Environment.PRODUCTION:
            return self.jwt_adapter.authenticate(request)

        # In testing or development: check for Authorization Bearer header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.strip().lower().startswith("bearer "):
            return self.jwt_adapter.authenticate(request)

        # Fall back to Dev adapter
        return self.dev_adapter.authenticate(request)


def get_identity_adapter(settings: Settings) -> IdentityAdapter:
    """Factory creating the appropriate IdentityAdapter based on configuration."""
    jwt_adapter = JwtIdentityAdapter(settings=settings)
    dev_adapter = DevIdentityAdapter(settings=settings)

    auth_mode = getattr(settings, "AUTH_MODE", "auto").lower()
    if auth_mode == "jwt" or settings.ENVIRONMENT == Environment.PRODUCTION:
        return jwt_adapter
    elif auth_mode == "dev":
        return dev_adapter
    else:
        return HybridIdentityAdapter(settings=settings, jwt_adapter=jwt_adapter, dev_adapter=dev_adapter)
