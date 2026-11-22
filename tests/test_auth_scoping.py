import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import Role, DEV_ACTOR_HEADER


def test_auth_missing_or_unknown_actor():
    app = create_app()
    client = TestClient(app)

    # Missing header
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"] == "UNAUTHORIZED"

    # Unknown actor
    res = client.get("/api/v1/auth/me", headers={DEV_ACTOR_HEADER: "unknown-hacker"})
    assert res.status_code == 401
    assert res.json()["error"] == "UNAUTHORIZED"


def test_auth_valid_actor():
    app = create_app()
    client = TestClient(app)

    res = client.get("/api/v1/auth/me", headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert res.status_code == 200
    data = res.json()
    assert data["actor_id"] == "farmer-1"
    assert data["role"] == "FARMER"
    assert data["organization_id"] == "fpo-alpha"


def test_role_mismatch_forbidden():
    app = create_app()
    client = TestClient(app)

    # Farmer trying to access FPO admin endpoint
    res = client.get("/api/v1/auth/fpo-only", headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert res.status_code == 403
    assert res.json()["error"] == "FORBIDDEN"


def test_cross_organization_forbidden():
    app = create_app()
    client = TestClient(app)

    # FPO admin beta trying to access FPO alpha resource
    res = client.get("/api/v1/auth/fpo/fpo-alpha/check", headers={DEV_ACTOR_HEADER: "fpo-admin-beta"})
    assert res.status_code == 403
    assert res.json()["error"] == "FORBIDDEN"

    # FPO admin alpha accessing FPO alpha resource is allowed
    res_ok = client.get("/api/v1/auth/fpo/fpo-alpha/check", headers={DEV_ACTOR_HEADER: "fpo-admin-alpha"})
    assert res_ok.status_code == 200


def test_driver_assignment_scoping():
    app = create_app()
    client = TestClient(app)

    # Driver 2 trying to update driver 1 assignment
    res = client.post(
        "/api/v1/auth/driver-action",
        headers={DEV_ACTOR_HEADER: "driver-2"},
        json={"assigned_driver_id": "driver-1", "action": "pickup"},
    )
    assert res.status_code == 403
    assert res.json()["error"] == "FORBIDDEN"

    # Driver 1 acting on driver 1 assignment is allowed
    res_ok = client.post(
        "/api/v1/auth/driver-action",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={"assigned_driver_id": "driver-1", "action": "pickup"},
    )
    assert res_ok.status_code == 200
