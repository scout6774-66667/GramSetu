import os
import tempfile

from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.services.events import append_event
from gramsetu.workers import LocalEventDispatcher


def test_event_append_and_sequential_processing():
    coordinator = TransactionCoordinator(store=InMemoryStore())

    # Append 3 events
    e1 = append_event(coordinator, "fpo-alpha", "TEST_EVENT", {"num": 1})
    e2 = append_event(coordinator, "fpo-alpha", "TEST_EVENT", {"num": 2})
    e3 = append_event(coordinator, "fpo-alpha", "TEST_EVENT", {"num": 3})

    assert e1["sequence"] == 1
    assert e2["sequence"] == 2
    assert e3["sequence"] == 3

    processed = []

    def test_handler(event):
        processed.append(event["payload"]["num"])

    dispatcher = LocalEventDispatcher(coordinator)
    dispatcher.register_handler("TEST_EVENT", test_handler)

    count = dispatcher.process_pending_events()
    assert count == 3
    assert processed == [1, 2, 3]
    assert dispatcher.get_cursor() == 3


def test_forced_crash_and_restart_resumption():
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, "event_store.json")
        coordinator = TransactionCoordinator(store=InMemoryStore(), snapshot_path=snap_path)

        # Append 2 events
        append_event(coordinator, "fpo-alpha", "TEST_EVENT", {"val": "first"})
        append_event(coordinator, "fpo-alpha", "TEST_EVENT", {"val": "second"})

        # Dispatcher processes first event, then simulated crash
        processed = []
        dispatcher = LocalEventDispatcher(coordinator)
        dispatcher.register_handler("TEST_EVENT", lambda e: processed.append(e["payload"]["val"]))

        # Process only 1 event
        dispatcher.process_pending_events(max_batch_size=1)
        assert processed == ["first"]
        assert dispatcher.get_cursor() == 1

        # Simulate cold restart from snapshot (close crashed process coordinator)
        coordinator.close()
        new_store = InMemoryStore.load_from_snapshot(snap_path)
        new_coord = TransactionCoordinator(store=new_store, snapshot_path=snap_path)
        new_dispatcher = LocalEventDispatcher(new_coord)
        new_processed = []
        new_dispatcher.register_handler("TEST_EVENT", lambda e: new_processed.append(e["payload"]["val"]))

        assert new_dispatcher.get_cursor() == 1

        # Resume processing
        count = new_dispatcher.process_pending_events()
        assert count == 1
        assert new_processed == ["second"]
        assert new_dispatcher.get_cursor() == 2


def test_poison_event_quarantine():
    coordinator = TransactionCoordinator(store=InMemoryStore())

    # Event 1: bad event (raises exception)
    append_event(coordinator, "fpo-alpha", "BAD_EVENT", {"data": "fail"})
    # Event 2: good event
    append_event(coordinator, "fpo-alpha", "GOOD_EVENT", {"data": "success"})

    good_processed = []

    def bad_handler(e):
        raise ValueError("Simulated handler crash")

    dispatcher = LocalEventDispatcher(coordinator, max_retries=3)
    dispatcher.register_handler("BAD_EVENT", bad_handler)
    dispatcher.register_handler("GOOD_EVENT", lambda e: good_processed.append(e["payload"]["data"]))

    # Process events; bad event fails 3 times and becomes POISON, good event gets processed
    dispatcher.process_pending_events()

    bad_evt = coordinator.store.get_item("events", "evt-000001")
    assert bad_evt["status"] == "POISON"
    assert bad_evt["attempts"] >= 3
    assert "Simulated handler crash" in bad_evt["last_error"]

    assert good_processed == ["success"]
    assert dispatcher.get_cursor() == 2
