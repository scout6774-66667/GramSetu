from __future__ import annotations

import logging
from typing import Dict, Any, Callable
from gramsetu.core import get_current_utc
from gramsetu.store import TransactionCoordinator
from gramsetu.services.events import get_unprocessed_events

logger = logging.getLogger("gramsetu.workers")


class LocalEventDispatcher:
    """Processes committed durable events with retries, poison event quarantine, and state cursor persistence."""
    def __init__(self, coordinator: TransactionCoordinator, max_retries: int = 3):
        self.coordinator = coordinator
        self.max_retries = max_retries
        self._handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

    def register_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._handlers[event_type] = handler

    def get_cursor(self) -> int:
        cursor_data = self.coordinator.store.get_item("metrics", "event_cursor")
        if cursor_data:
            return cursor_data.get("last_sequence", 0)
        return 0

    def _set_cursor(self, sequence: int) -> None:
        self.coordinator.store.set_item(
            "metrics",
            "event_cursor",
            {"last_sequence": sequence, "updated_at": get_current_utc().isoformat()},
        )

    def process_pending_events(self, max_batch_size: int = 50) -> int:
        """Process pending events in monotonic sequence order. Heavy operations execute outside transaction locks."""
        cursor = self.get_cursor()
        pending = get_unprocessed_events(self.coordinator.store, cursor=cursor, limit=max_batch_size)

        processed_count = 0

        for event in pending:
            evt_type = event["event_type"]
            handler = self._handlers.get(evt_type)

            if handler is None:
                # No handler registered; mark processed and advance cursor
                with self.coordinator.transaction():
                    event["status"] = "PROCESSED"
                    self.coordinator.store.set_item("events", event["event_id"], event)
                    self._set_cursor(event["sequence"])
                processed_count += 1
                continue

            # Attempt processing with bounded retries
            success = False
            while event.get("attempts", 0) < self.max_retries:
                try:
                    handler(event)
                    success = True
                    break
                except Exception as exc:
                    event["attempts"] = event.get("attempts", 0) + 1
                    event["last_error"] = str(exc)
                    logger.warning(
                        f"Attempt {event['attempts']} failed for event {event['event_id']} ({evt_type}): {exc}"
                    )

            if success:
                with self.coordinator.transaction():
                    event["status"] = "PROCESSED"
                    self.coordinator.store.set_item("events", event["event_id"], event)
                    self._set_cursor(event["sequence"])
                processed_count += 1
            else:
                # Quarantined as POISON after max_retries exceeded
                with self.coordinator.transaction():
                    event["status"] = "POISON"
                    self.coordinator.store.set_item("events", event["event_id"], event)
                    self._set_cursor(event["sequence"])
                logger.error(
                    f"Event {event['event_id']} quarantined as POISON after {event['attempts']} attempts."
                )

        return processed_count
