"""High-performance, transactional, database-free persistence layer for GramSetu AI.

Features:
- Pure RAM InMemoryStore with schema validation and deep copy isolation.
- ProcessWriterLock providing cross-platform single-writer OS lock semantics (msvcrt / fcntl).
- TransactionCoordinator supporting copy-on-write isolation, rollback, and atomic fsync snapshotting.
"""
from __future__ import annotations

import atexit
import copy
import json
import os
import sys
import threading
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Callable

from gramsetu.core.exceptions import (
    CorruptionError,
    ProcessLockError,
    NotFoundError,
)

SCHEMA_VERSION = "2.2.0"
KNOWN_COLLECTIONS = {
    "forecasts",
    "requirements",
    "commitments",
    "lots",
    "movements",
    "vehicles",
    "shipments",
    "incidents",
    "recovery_plans",
    "settlements",
    "events",
    "evidence",
    "items",
    "farmers",
    "buyers",
    "transporters",
    "facilities",
    "listings",
    "transport_requests",
    "procurement_offers",
    "users",
}


class InMemoryStore:
    """In-memory, thread-safe, database-free dictionary storage partitioned by entity collections."""

    def __init__(self, data: Optional[Dict[str, Dict[str, Any]]] = None, meta: Optional[Dict[str, Any]] = None):
        self._data: Dict[str, Dict[str, Any]] = {c: {} for c in KNOWN_COLLECTIONS}
        if data:
            for col, items in data.items():
                self._data[col] = copy.deepcopy(items)

        self._meta: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "created_at_utc": "2026-11-22T00:00:00Z",
        }
        if meta:
            self._meta.update(copy.deepcopy(meta))

    def get_item(self, collection: str, key: str) -> Optional[Dict[str, Any]]:
        col = self._data.get(collection)
        if col is None:
            return None
        item = col.get(key)
        return copy.deepcopy(item) if item is not None else None

    def set_item(self, collection: str, key: str, value: Dict[str, Any]) -> None:
        if collection not in self._data:
            self._data[collection] = {}
        self._data[collection][key] = copy.deepcopy(value)

    def delete_item(self, collection: str, key: str) -> bool:
        col = self._data.get(collection)
        if col is not None and key in col:
            del col[key]
            return True
        return False

    def list_items(
        self, collection: str, filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> List[Dict[str, Any]]:
        col = self._data.get(collection, {})
        items = [copy.deepcopy(v) for v in col.values()]
        if filter_fn is not None:
            return [it for it in items if filter_fn(it)]
        return items

    def count(self, collection: str) -> int:
        return len(self._data.get(collection, {}))

    def get_stats(self) -> Dict[str, int]:
        return {col: len(items) for col, items in self._data.items()}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": copy.deepcopy(self._meta),
            "data": copy.deepcopy(self._data),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> InMemoryStore:
        if not isinstance(payload, dict):
            raise CorruptionError("Snapshot payload is not a valid JSON dictionary")
        meta = payload.get("meta")
        if not isinstance(meta, dict) or meta.get("schema_version") != SCHEMA_VERSION:
            raise CorruptionError(f"Snapshot has invalid or unsupported schema metadata: {meta}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise CorruptionError("Snapshot payload missing or invalid 'data' section")
        return cls(data=data, meta=meta)

    @classmethod
    def load_from_snapshot(cls, filepath: str) -> InMemoryStore:
        if not os.path.exists(filepath):
            return cls()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise CorruptionError(f"JSON decode failure in snapshot {filepath}: {exc}") from exc
        except Exception as exc:
            raise CorruptionError(f"Failed to read snapshot {filepath}: {exc}") from exc

        return cls.from_dict(raw)

    def save_snapshot(self, filepath: str) -> None:
        target_dir = os.path.dirname(filepath)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        tmp_path = f"{filepath}.tmp"
        serialized = json.dumps(self.to_dict(), indent=2, default=str)
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, filepath)

            # Directory sync on POSIX platforms where supported
            if hasattr(os, "O_DIRECTORY") and target_dir:
                try:
                    dir_fd = os.open(target_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    pass
        except Exception as exc:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise CorruptionError(f"Failed to atomically persist snapshot to {filepath}: {exc}") from exc


class ProcessWriterLock:
    """Cross-platform, reentrant, process-wide single-writer lock with process exit cleanup."""

    def __init__(self, lockfile_path: Optional[str] = None):
        if lockfile_path is None:
            self.lockfile_path = os.path.join(os.path.abspath(os.getcwd()), ".gramsetu_writer.lock")
        else:
            self.lockfile_path = os.path.abspath(lockfile_path)

        self._thread_lock = threading.RLock()
        self._lock_count = 0
        self._file_handle = None
        atexit.register(self.cleanup)

    def acquire(self) -> None:
        self._thread_lock.acquire()
        if self._lock_count == 0:
            target_dir = os.path.dirname(self.lockfile_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            try:
                self._file_handle = open(self.lockfile_path, "a+b")
                if sys.platform == "win32":
                    import msvcrt
                    self._file_handle.seek(0)
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError) as exc:
                if self._file_handle:
                    try:
                        self._file_handle.close()
                    except Exception:
                        pass
                    self._file_handle = None
                self._thread_lock.release()
                raise ProcessLockError(
                    f"Failed to acquire single-writer OS lock on {self.lockfile_path}: another process holds the exclusive lock.",
                    details={"lockfile": self.lockfile_path, "system_error": str(exc)},
                ) from exc

        self._lock_count += 1

    def release(self) -> None:
        if self._lock_count <= 0:
            return
        self._lock_count -= 1
        if self._lock_count == 0 and self._file_handle:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self._file_handle.seek(0)
                    msvcrt.locking(self._file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                try:
                    self._file_handle.close()
                except Exception:
                    pass
                self._file_handle = None
        self._thread_lock.release()

    def cleanup(self) -> None:
        while self._lock_count > 0:
            self.release()
        if os.path.exists(self.lockfile_path):
            try:
                os.remove(self.lockfile_path)
            except OSError:
                pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class TransactionCoordinator:
    """Manages transactional store mutations and persistence under process write locking."""

    def __init__(
        self,
        store: Optional[InMemoryStore] = None,
        snapshot_path: Optional[str] = None,
        lock_path: Optional[str] = None,
        enforce_process_lock: bool = False,
    ):
        if store is None:
            if snapshot_path and os.path.exists(snapshot_path):
                store = InMemoryStore.load_from_snapshot(snapshot_path)
            else:
                store = InMemoryStore()

        self._store = store
        self._snapshot_path = snapshot_path

        if lock_path is None and snapshot_path:
            lock_path = f"{snapshot_path}.lock"

        self._lock = ProcessWriterLock(lock_path)
        self._enforce_process_lock = enforce_process_lock
        self._active_transaction = False

        if enforce_process_lock:
            self._lock.acquire()
            self.process_lock = self._lock
        else:
            self.process_lock = None

    @property
    def store(self) -> InMemoryStore:
        return self._store

    def close(self) -> None:
        if self._enforce_process_lock:
            self._lock.release()
            self._enforce_process_lock = False
        if self._lock._lock_count > 0:
            self._lock.cleanup()

    @contextmanager
    def transaction(self):
        """Execute a state mutation block with copy-on-write isolation, rollback on exception,
        and atomic snapshot persistence on success.
        """
        with self._lock:
            rollback_data = copy.deepcopy(self._store._data)
            rollback_meta = copy.deepcopy(self._store._meta)
            try:
                self._active_transaction = True
                yield self._store
                if self._snapshot_path:
                    self._store.save_snapshot(self._snapshot_path)
            except Exception:
                self._store._data = rollback_data
                self._store._meta = rollback_meta
                raise
            finally:
                self._active_transaction = False
