from __future__ import annotations

import socket
import tempfile
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.store import InMemoryStore, TransactionCoordinator

# ==============================================================================
# 1. Warm-up hook: Pre-warm heavy scientific/ML modules once per session
# ==============================================================================
def pytest_sessionstart(session):
    """Pre-warm expensive lazy imports so no single test bears a 1-2s cold-start penalty."""
    try:
        from sklearn.linear_model import Ridge  # noqa: F401
    except Exception:
        pass


# ==============================================================================
# 2. Loopback guard: Prevent indefinite hang in restricted sandbox on Windows
# ==============================================================================
_orig_fallback_socketpair = getattr(socket, "_fallback_socketpair", None)
if _orig_fallback_socketpair is not None:
    def _guarded_fallback_socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
        temp_srv = socket.socket(family, type, proto)
        try:
            temp_srv.bind(("127.0.0.1", 0))
            temp_srv.listen(1)
            temp_srv.settimeout(2.0)
            addr, port = temp_srv.getsockname()
            client_sock = socket.socket(family, type, proto)
            client_sock.settimeout(2.0)
            try:
                client_sock.connect((addr, port))
                server_sock, _ = temp_srv.accept()
                server_sock.setblocking(True)
                client_sock.setblocking(True)
                return client_sock, server_sock
            except (socket.timeout, OSError) as exc:
                client_sock.close()
                raise RuntimeError(
                    f"Local loopback socket connection blocked or timed out: {exc}. "
                    "Ensure local socket permissions are granted."
                ) from exc
        finally:
            temp_srv.close()

    socket._fallback_socketpair = _guarded_fallback_socketpair


# ==============================================================================
# 3. Network Isolation Guard: Block unmocked outbound WAN connections
# ==============================================================================
_orig_socket_connect = socket.socket.connect


def _offline_guard_connect(self, address):
    host = address[0] if isinstance(address, tuple) and address else address
    # Allow local connections (localhost, 127.0.0.1, ::1)
    if host in ("localhost", "127.0.0.1", "::1"):
        return _orig_socket_connect(self, address)
    raise RuntimeError(
        f"External network connection to {address} attempted in test suite. "
        "All tests must be deterministic, isolated, and offline."
    )


socket.socket.connect = _offline_guard_connect


# ==============================================================================
# 4. Standard Reusable Fixtures with Deterministic Teardown
# ==============================================================================
@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def coordinator(store):
    coord = TransactionCoordinator(store=store)
    yield coord
    try:
        coord.close()
    except Exception:
        pass


@pytest.fixture
def app(coordinator):
    return create_app(coordinator=coordinator)


@pytest.fixture
def client(app):
    test_client = TestClient(app)
    yield test_client
    try:
        test_client.close()
    except Exception:
        pass


@pytest.fixture
def temp_snapshot_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
