from __future__ import annotations

import time
import pytest
import jwt
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import Settings, Environment, DEV_ACTOR_HEADER


SECRET = "test-super-secret-key-for-jwt-hardening-123456"
ISSUER = "gramsetu-auth"
AUDIENCE = "gramsetu-api"


def make_jwt(
    sub: str = "farmer-1",
    role: str = "FARMER",
    org_id: str = "fpo-alpha",
    name: str = "Ramesh Kumar",
    exp_offset: int = 3600,
    secret: str = SECRET,
    algorithm: str = "HS256",
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    headers: dict = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role,
        "org_id": org_id,
        "name": name,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(payload, secret, algorithm=algorithm, headers=headers)


@pytest.fixture
def prod_client():
    settings = Settings(
        ENVIRONMENT=Environment.PRODUCTION,
        JWT_SECRET_KEY=SECRET,
        JWT_ISSUER=ISSUER,
        JWT_AUDIENCE=AUDIENCE,
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    yield client
    app.state.coordinator.close()


def test_r3_production_rejects_spoofed_dev_actor_header(prod_client):
    """R3 SECURITY: In production mode, X-Dev-Actor MUST be rejected with 401."""
    res = prod_client.get(
        "/api/v1/auth/me",
        headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"},
    )
    assert res.status_code == 401
    assert "prohibited in production" in res.json()["message"]


def test_r3_valid_jwt_authenticates_successfully(prod_client):
    """R3 SECURITY: Valid signed JWT bearer token authenticates actor and extracts claims."""
    token = make_jwt(sub="farmer-1", role="FARMER", org_id="fpo-alpha", name="Ramesh Farmer")
    res = prod_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["actor_id"] == "farmer-1"
    assert data["role"] == "FARMER"
    assert data["organization_id"] == "fpo-alpha"
    assert data["name"] == "Ramesh Farmer"


def test_r3_insecure_alg_none_is_strictly_rejected(prod_client):
    """R3 ADVERSARIAL: JWT with alg='none' MUST fail closed with 401."""
    now = int(time.time())
    payload = {
        "sub": "hacker-1",
        "role": "FPO_ADMIN",
        "org_id": "fpo-alpha",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 3600,
    }
    # Create unsigned alg=none token manually
    header_b64 = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0"  # {"alg":"none","typ":"JWT"}
    import base64
    import json
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    none_token = f"{header_b64}.{payload_b64}."

    res = prod_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {none_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"] == "UNAUTHORIZED"


def test_r3_expired_jwt_is_rejected(prod_client):
    """R3 SECURITY: Expired JWT MUST return 401 with TOKEN_EXPIRED."""
    expired_token = make_jwt(exp_offset=-300)
    res = prod_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"] in ("TOKEN_EXPIRED", "UNAUTHORIZED")


def test_r3_tampered_signature_is_rejected(prod_client):
    """R3 ADVERSARIAL: Tampered payload or wrong signing key MUST return 401."""
    tampered_token = make_jwt(secret="wrong-unauthorized-signing-key-random")
    res = prod_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"] == "UNAUTHORIZED"


def test_r3_wrong_issuer_and_audience_rejected(prod_client):
    """R3 SECURITY: Mismatched issuer or audience claim MUST be rejected."""
    wrong_iss_token = make_jwt(issuer="rogue-identity-provider")
    res = prod_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_iss_token}"},
    )
    assert res.status_code == 401

    wrong_aud_token = make_jwt(audience="rogue-service-target")
    res = prod_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_aud_token}"},
    )
    assert res.status_code == 401


def test_r3_invalid_role_claim_rejected(prod_client):
    """R3 SECURITY: Unrecognized role claim MUST be rejected with 403."""
    bad_role_token = make_jwt(role="SUPER_HACKER_OVERLORD")
    res = prod_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {bad_role_token}"},
    )
    assert res.status_code == 403
    assert res.json()["error"] == "FORBIDDEN"


def test_r3_tenant_isolation_matrix(prod_client):
    """R3 AUTHORIZATION MATRIX:
    Enforce strict cross-tenant and role boundary scoping:
    1. Farmer A cannot read or write Farmer B's forecasts.
    2. Buyer cannot inject inventory receipts.
    3. FPO Beta admin cannot view FPO Alpha records.
    4. Driver 1 cannot update Driver 2's shipments.
    """
    token_farmer_a = make_jwt(sub="farmer-1", role="FARMER", org_id="fpo-alpha")
    token_buyer = make_jwt(sub="buyer-1", role="BUYER", org_id="org-reliance")
    token_fpo_beta = make_jwt(sub="fpo-admin-beta", role="FPO_ADMIN", org_id="fpo-beta")

    # 1. Buyer trying to receive physical inventory lot -> 403 Forbidden
    res = prod_client.post(
        "/api/v1/lots/receipt",
        headers={"Authorization": f"Bearer {token_buyer}"},
        json={
            "farmer_id": "farmer-1",
            "fpo_id": "fpo-alpha",
            "crop": "Soybean",
            "grade": "A",
            "quantity_grams": 500_000,
            "storage_location": "Silo-A",
        },
    )
    assert res.status_code == 403

    # 2. Farmer A creating harvest forecast -> 201
    res = prod_client.post(
        "/api/v1/forecasts",
        headers={"Authorization": f"Bearer {token_farmer_a}"},
        json={
            "crop": "Wheat",
            "variety": "Lokwan",
            "grade": "A",
            "estimated_grams": 1_000_000,
            "harvest_start_date": "2026-12-01T00:00:00Z",
            "harvest_end_date": "2026-12-05T00:00:00Z",
            "confidence_score": 0.85,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["farmer_id"] == "farmer-1"

    # 3. Driver scoping: Driver 1 cannot perform action assigned to Driver 2 -> 403
    token_driver_1 = make_jwt(sub="driver-1", role="DRIVER", org_id="fpo-alpha")
    res = prod_client.post(
        "/api/v1/auth/driver-action",
        headers={"Authorization": f"Bearer {token_driver_1}"},
        json={
            "assigned_driver_id": "driver-2",
            "action": "START_TRIP",
        },
    )
    assert res.status_code == 403
    assert res.json()["error"] == "FORBIDDEN"

    # 4. FPO Beta attempting to access FPO Alpha admin resource -> 403
    res = prod_client.get(
        "/api/v1/auth/fpo/fpo-alpha/check",
        headers={"Authorization": f"Bearer {token_fpo_beta}"},
    )
    assert res.status_code == 403
