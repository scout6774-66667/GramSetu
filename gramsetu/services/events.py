from __future__ import annotations

from typing import Dict, Any, List, Optional
from gramsetu.core import get_current_utc
from gramsetu.store import InMemoryStore, TransactionCoordinator


def append_event(
    coordinator: TransactionCoordinator,
    fpo_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Append an immutable domain event record into the durable event journal."""
    with coordinator.transaction():
        events = coordinator.store.list_items("events")
        max_seq = max((e.get("sequence", 0) for e in events), default=0)
        next_seq = max_seq + 1
        event_id = f"evt-{next_seq:06d}"
        now = get_current_utc().isoformat()

        record = {
            "event_id": event_id,
            "sequence": next_seq,
            "fpo_id": fpo_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": now,
            "status": "PENDING",
            "attempts": 0,
            "last_error": None,
        }
        coordinator.store.set_item("events", event_id, record)

    return record


def get_unprocessed_events(
    store: InMemoryStore,
    cursor: int,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve ordered unprocessed events after the specified cursor."""
    def filter_fn(item: dict) -> bool:
        seq = item.get("sequence", 0)
        status = item.get("status")
        return seq > cursor and status in ("PENDING", "FAILED")

    events = store.list_items("events", filter_fn)
    events.sort(key=lambda x: x["sequence"])
    return events[:limit]
