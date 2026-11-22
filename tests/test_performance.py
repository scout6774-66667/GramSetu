import time
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER
from gramsetu.algorithms import estimate_route_metrics


def test_request_payload_size_rejection():
    app = create_app()
    client = TestClient(app)

    # 1.5 MB body
    large_payload = {"padding": "x" * (1_500_000)}
    res = client.post(
        "/api/v1/forecasts",
        headers={DEV_ACTOR_HEADER: "farmer-1", "Content-Length": str(len(str(large_payload)))},
        json=large_payload,
    )
    assert res.status_code == 413
    assert res.json()["error"] == "PAYLOAD_TOO_LARGE"


def test_trace_id_propagation():
    app = create_app()
    client = TestClient(app)

    res = client.get("/health", headers={"X-Trace-Id": "custom-trace-12345"})
    assert res.status_code == 200
    assert res.headers["X-Trace-Id"] == "custom-trace-12345"


def test_protected_export_authorization():
    app = create_app()
    client = TestClient(app)

    # Farmer trying to export all platform data -> 403
    res_f = client.get("/api/v1/export/data", headers={DEV_ACTOR_HEADER: "farmer-1"})
    assert res_f.status_code == 403

    # System worker allowed -> 200
    res_sys = client.get("/api/v1/export/data", headers={DEV_ACTOR_HEADER: "system-worker"})
    assert res_sys.status_code == 200
    assert "data" in res_sys.json()


def test_algorithm_and_transaction_p95_performance():
    # Measure p95 of route estimation across 100 iterations
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        estimate_route_metrics(28.61, 77.20, 28.45, 77.02, 400_000, 500_000)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)  # ms

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]
    assert p95 < 5.0, f"Algorithm p95 latency {p95:.2f}ms exceeds 5ms threshold"
