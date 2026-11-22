from __future__ import annotations

import os
import pytest
from gramsetu.core import ProcessLockError, CorruptionError
from gramsetu.store import InMemoryStore, TransactionCoordinator


def test_process_writer_lock_prevents_dual_coordinators(tmp_path):
    """R2 VERIFICATION:
    Verify that an OS-enforced exclusive process lock prevents two independent
    coordinators / worker processes from concurrently writing to the same state file.
    """
    state_file = str(tmp_path / "app_state.json")

    # First coordinator acquires exclusive process lock
    coord1 = TransactionCoordinator(snapshot_path=state_file, enforce_process_lock=True)
    assert coord1.process_lock is not None

    # Second coordinator attempting to start on the same state file MUST fail
    with pytest.raises(ProcessLockError, match="another process holds the exclusive lock"):
        TransactionCoordinator(snapshot_path=state_file, enforce_process_lock=True)

    # When first coordinator closes, lock is released cleanly
    coord1.close()

    # Now second coordinator can acquire the lock successfully
    coord2 = TransactionCoordinator(snapshot_path=state_file, enforce_process_lock=True)
    assert coord2.process_lock is not None
    coord2.close()


def test_atomic_snapshot_cold_restart_reconstruction(tmp_path):
    """R2 CRASH & RESTART RECOVERY:
    Verify that state committed before a cold shutdown is recovered byte-for-byte
    on restart, without corrupting previous state or creating phantom records.
    """
    state_file = str(tmp_path / "durable_state.json")

    # Session 1: Commit initial lots and commitments
    store1 = InMemoryStore()
    coord1 = TransactionCoordinator(store=store1, snapshot_path=state_file)
    with coord1.transaction():
        coord1.store.set_item("lots", "lot-001", {"quantity_grams": 500_000, "status": "AVAILABLE"})
        coord1.store.set_item("metrics", "event_cursor", {"last_sequence": 42})
    coord1.close()

    assert os.path.exists(state_file)

    # Session 2: Cold start from persisted snapshot
    store2 = InMemoryStore.load_from_snapshot(state_file)
    coord2 = TransactionCoordinator(store=store2, snapshot_path=state_file)

    lot = coord2.store.get_item("lots", "lot-001")
    assert lot is not None
    assert lot["quantity_grams"] == 500_000
    assert lot["status"] == "AVAILABLE"

    cursor = coord2.store.get_item("metrics", "event_cursor")
    assert cursor is not None
    assert cursor["last_sequence"] == 42
    coord2.close()


def test_corrupt_snapshot_fails_closed_without_silent_reset(tmp_path):
    """R2 FAIL-CLOSED INTEGRITY:
    Verify that an unreadable or corrupt snapshot raises CorruptionError
    and NEVER silently resets or overwrites the damaged state.
    """
    state_file = str(tmp_path / "corrupt_state.json")
    with open(state_file, "w") as f:
        f.write("{ invalid json corrupted stream...")

    with pytest.raises(CorruptionError, match="JSON decode failure"):
        InMemoryStore.load_from_snapshot(state_file)

    # State file must remain intact (not deleted or truncated)
    assert open(state_file, "r").read() == "{ invalid json corrupted stream..."
