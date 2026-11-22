"""Benchmark script measuring p95 and latency for core GramSetu algorithms and transactions."""

import time
import tempfile
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.algorithms import estimate_route_metrics


def run_benchmark():
    print("--- GramSetu AI Backend Performance Benchmark ---")

    # 1. In-memory read performance
    store = InMemoryStore()
    for i in range(1000):
        store.set_item("lots", f"lot-{i}", {"quantity_grams": i * 100, "crop": "Wheat"})

    read_times = []
    for i in range(1000):
        t0 = time.perf_counter()
        store.get_item("lots", f"lot-{i}")
        read_times.append((time.perf_counter() - t0) * 1000.0)

    read_times.sort()
    p95_read = read_times[int(len(read_times) * 0.95)]
    print(f"1,000 In-Memory Reads: p95 = {p95_read:.4f} ms")

    # 2. Algorithm performance: Route metrics
    algo_times = []
    for _ in range(500):
        t0 = time.perf_counter()
        estimate_route_metrics(28.61, 77.20, 28.45, 77.02, 400_000, 500_000)
        algo_times.append((time.perf_counter() - t0) * 1000.0)

    algo_times.sort()
    p95_algo = algo_times[int(len(algo_times) * 0.95)]
    print(f"500 Route Metric Computations: p95 = {p95_algo:.4f} ms")

    # 3. Transaction write with atomic persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, "bench.json")
        coord = TransactionCoordinator(store=InMemoryStore(), snapshot_path=snap_path)

        tx_times = []
        for i in range(100):
            t0 = time.perf_counter()
            with coord.transaction():
                coord.store.set_item("lots", f"lot-{i}", {"quantity_grams": 500_000})
            tx_times.append((time.perf_counter() - t0) * 1000.0)

        tx_times.sort()
        p95_tx = tx_times[int(len(tx_times) * 0.95)]
        print(f"100 Atomic Snapshots (write + fsync + replace): p95 = {p95_tx:.4f} ms")

    print("--- Benchmark Completed Successfully ---")


if __name__ == "__main__":
    run_benchmark()
