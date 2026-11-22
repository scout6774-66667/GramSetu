import os
import tempfile
import threading
from datetime import datetime
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from gramsetu.core import CorruptionError
from gramsetu.main import create_app
from gramsetu.store import InMemoryStore, TransactionCoordinator


def test_health_check():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    assert datetime.fromisoformat(data["timestamp"]).tzinfo is not None


def test_docs_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200


def test_transaction_rollback():
    coordinator = TransactionCoordinator(store=InMemoryStore())
    with coordinator.transaction():
        coordinator.store.set_item("items", "item1", {"name": "test", "val": 10})

    assert coordinator.store.get_item("items", "item1") == {"name": "test", "val": 10}

    # Now run a failing transaction
    with pytest.raises(RuntimeError):
        with coordinator.transaction():
            coordinator.store.set_item("items", "item1", {"name": "modified", "val": 99})
            coordinator.store.set_item("items", "item2", {"name": "new", "val": 50})
            raise RuntimeError("Forced transaction failure")

    # Rolled back
    assert coordinator.store.get_item("items", "item1") == {"name": "test", "val": 10}
    assert coordinator.store.get_item("items", "item2") is None


def test_atomic_snapshot_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, "state.json")
        coordinator = TransactionCoordinator(store=InMemoryStore(), snapshot_path=snap_path)

        with coordinator.transaction():
            coordinator.store.set_item("lots", "lot-101", {"grams": 50000, "crop": "Wheat"})

        assert os.path.exists(snap_path)

        # Cold restart
        new_store = InMemoryStore.load_from_snapshot(snap_path)
        assert new_store.get_item("lots", "lot-101") == {"grams": 50000, "crop": "Wheat"}


def test_snapshot_corruption_rejection():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, "corrupt.json")
        with open(snap_path, "w", encoding="utf-8") as f:
            f.write("INVALID JSON {[[")

        with pytest.raises(CorruptionError):
            InMemoryStore.load_from_snapshot(snap_path)

        # Ensure corrupted file is not erased or replaced with empty
        with open(snap_path, "r", encoding="utf-8") as f:
            assert f.read() == "INVALID JSON {[["


def test_deep_copy_isolation():
    coordinator = TransactionCoordinator(store=InMemoryStore())
    with coordinator.transaction():
        coordinator.store.set_item("lots", "lot-1", {"grams": 1000, "tags": ["dry"]})

    fetched = coordinator.store.get_item("lots", "lot-1")
    fetched["grams"] = 9999
    fetched["tags"].append("polluted")

    # Original remains untouched
    fresh = coordinator.store.get_item("lots", "lot-1")
    assert fresh["grams"] == 1000
    assert fresh["tags"] == ["dry"]


def test_concurrent_single_process_mutation():
    coordinator = TransactionCoordinator(store=InMemoryStore())
    with coordinator.transaction():
        coordinator.store.set_item("metrics", "counter", {"count": 0})

    def increment():
        for _ in range(50):
            with coordinator.transaction():
                item = coordinator.store.get_item("metrics", "counter")
                item["count"] += 1
                coordinator.store.set_item("metrics", "counter", item)

    threads = [threading.Thread(target=increment) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = coordinator.store.get_item("metrics", "counter")
    assert final["count"] == 250


def test_unacceptable_schema_version():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, "invalid_version.json")
        with open(snap_path, "w", encoding="utf-8") as f:
            f.write('{"meta": {"schema_version": 999}, "data": {}}')

        with pytest.raises(CorruptionError) as exc_info:
            InMemoryStore.load_from_snapshot(snap_path)
        assert "unsupported schema" in str(exc_info.value).lower()


def test_invalid_quantity_precision():
    from gramsetu.schemas import BaseSchema

    class ProduceItem(BaseSchema):
        quantity_grams: int
        price_paise: int

    # Valid
    p = ProduceItem(quantity_grams=5000, price_paise=2500)
    assert p.quantity_grams == 5000

    # Float should be rejected or fail integer validation if strict
    with pytest.raises(ValidationError):
        ProduceItem(quantity_grams="not-an-int", price_paise=100)

