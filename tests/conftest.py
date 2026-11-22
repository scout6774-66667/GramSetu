import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.core import Settings


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def coordinator(store):
    return TransactionCoordinator(store=store)


@pytest.fixture
def app(coordinator):
    return create_app(coordinator=coordinator)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def temp_snapshot_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
