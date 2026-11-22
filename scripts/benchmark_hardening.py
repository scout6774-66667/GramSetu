#!/usr/bin/env python3
"""Phase 2 Comprehensive Hardening & Performance Benchmark for GramSetu AI.

Measures:
1. Workload scaling across Small, Medium, Large prototype tiers.
2. Read and write transaction latencies (p50, p95, p99).
3. Exact Recovery Optimizer runtime across 8, 16, 32, 64 candidates.
4. Offline road graph Dijkstra routing latency.
5. Cold restart reconstruction performance (JSON snapshot size vs parse time).
6. Single-process single-writer throughput bounds.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.algorithms import optimize_recovery_allocation, get_default_road_network
from gramsetu.adapters.evidence import compute_payload_digest


def calc_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    if not latencies_ms:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0, "max": 0.0}
    s = sorted(latencies_ms)
    n = len(s)
    return {
        "p50": round(s[int(n * 0.50)], 4),
        "p95": round(s[min(int(n * 0.95), n - 1)], 4),
        "p99": round(s[min(int(n * 0.99), n - 1)], 4),
        "avg": round(sum(s) / n, 4),
        "max": round(s[-1], 4),
    }


def benchmark_optimizer() -> Dict[str, Any]:
    print("\n--- Benchmarking Recovery Optimizer Scaling (8 to 64 Candidates) ---")
    results = {}
    candidate_counts = [8, 16, 32, 64]

    for count in candidate_counts:
        # Generate synthetic candidates
        candidates = []
        for i in range(count):
            candidates.append({
                "requirement_id": f"req-bench-{i:03d}",
                "buyer_id": f"buyer-{i % 10}",
                "needed_grams": 500_000,
                "offered_price_paise_per_gram": 30 + (i % 20),
                "transport_cost_paise": 50_000 + (i * 2_000),
                "distance_km": 15.0 + i,
            })

        times = []
        # Run 50 iterations
        for _ in range(50):
            t0 = time.perf_counter()
            plan = optimize_recovery_allocation(
                available_grams=2_000_000,
                candidate_requirements=candidates,
            )
            times.append((time.perf_counter() - t0) * 1000.0)

        pct = calc_percentiles(times)
        results[f"candidates_{count}"] = {
            "percentiles_ms": pct,
            "status": plan["optimality_status"],
            "allocated_count": len(plan["ranked_candidates"]),
        }
        print(f"  {count:2d} candidates: p50={pct['p50']}ms, p95={pct['p95']}ms, p99={pct['p99']}ms, max={pct['max']}ms")

    return results


def benchmark_routing() -> Dict[str, Any]:
    print("\n--- Benchmarking Logistics Road Graph Dijkstra Routing ---")
    graph = get_default_road_network()
    times = []
    for _ in range(500):
        t0 = time.perf_counter()
        graph.get_route("FPO_WH_ALPHA", "BUYER_BIGBASKET_DC", vehicle_payload_grams=2_000_000)
        times.append((time.perf_counter() - t0) * 1000.0)

    pct = calc_percentiles(times)
    print(f"  500 Dijkstra Queries: p50={pct['p50']}ms, p95={pct['p95']}ms, p99={pct['p99']}ms")
    return {"dijkstra_routing_ms": pct}


def benchmark_workload_tier(tier_name: str, num_farmers: int, num_buyers: int, num_shipments: int) -> Dict[str, Any]:
    print(f"\n--- Benchmarking Tier: {tier_name.upper()} ({num_farmers} farmers, {num_buyers} buyers, {num_shipments} shipments) ---")

    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = os.path.join(tmpdir, f"state_{tier_name}.json")
        store = InMemoryStore()
        coord = TransactionCoordinator(store=store, snapshot_path=snap_path)

        # 1. Measure writes (Farmer lots creation)
        write_times = []
        for i in range(num_farmers):
            t0 = time.perf_counter()
            with coord.transaction():
                coord.store.set_item("lots", f"lot-{tier_name}-{i}", {
                    "lot_id": f"lot-{tier_name}-{i}",
                    "farmer_id": f"farmer-{i % 50}",
                    "crop": "Soybean",
                    "grade": "A",
                    "quantity_grams": 1_000_000,
                    "storage_location": f"Warehouse-{i % 10}",
                    "status": "AVAILABLE",
                })
            write_times.append((time.perf_counter() - t0) * 1000.0)

        # 2. Add buyers, requirements, commitments, shipments
        with coord.transaction():
            for b in range(num_buyers):
                coord.store.set_item("requirements", f"req-{tier_name}-{b}", {
                    "requirement_id": f"req-{tier_name}-{b}",
                    "buyer_id": f"buyer-{b}",
                    "crop": "Soybean",
                    "grade": "A",
                    "needed_grams": 1_000_000,
                    "max_price_paise_per_gram": 35,
                })

            for s in range(num_shipments):
                coord.store.set_item("shipments", f"ship-{tier_name}-{s}", {
                    "shipment_id": f"ship-{tier_name}-{s}",
                    "commitment_id": f"com-{s}",
                    "driver_id": f"driver-{s % 5}",
                    "dispatched_grams": 1_000_000,
                    "custody": "IN_TRANSIT",
                    "status": "IN_TRANSIT",
                })

        write_pct = calc_percentiles(write_times)
        throughput_writes_per_sec = round(1000.0 / write_pct["p50"], 1) if write_pct["p50"] > 0 else 0

        # 3. Measure reads (Actor dashboard queries)
        read_times = []
        for i in range(min(500, num_farmers)):
            t0 = time.perf_counter()
            coord.store.get_item("lots", f"lot-{tier_name}-{i}")
            read_times.append((time.perf_counter() - t0) * 1000.0)
        read_pct = calc_percentiles(read_times)

        # 4. Measure snapshot file size & cold restart reconstruction
        coord.close()

        file_size_bytes = os.path.getsize(snap_path)
        restart_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            reconstructed_store = InMemoryStore.load_from_snapshot(snap_path)
            restart_times.append((time.perf_counter() - t0) * 1000.0)
        restart_pct = calc_percentiles(restart_times)

        total_objects = sum(len(items) for items in reconstructed_store._data.values())

        print(f"  Write Latency (fsync): p50={write_pct['p50']}ms, p95={write_pct['p95']}ms, p99={write_pct['p99']}ms")
        print(f"  Read Latency (RAM):   p50={read_pct['p50']}ms, p95={read_pct['p95']}ms, p99={read_pct['p99']}ms")
        print(f"  Cold Restart:         p50={restart_pct['p50']}ms (file={file_size_bytes/1024:.1f} KB, objects={total_objects})")
        print(f"  Single-Writer Limit:  ~{throughput_writes_per_sec} writes/sec")

        return {
            "tier": tier_name,
            "counts": {"farmers": num_farmers, "buyers": num_buyers, "shipments": num_shipments, "total_objects": total_objects},
            "snapshot_bytes": file_size_bytes,
            "write_latency_ms": write_pct,
            "read_latency_ms": read_pct,
            "cold_restart_latency_ms": restart_pct,
            "estimated_max_writes_per_sec": throughput_writes_per_sec,
        }


def main():
    print("=" * 70)
    print("GRAMSETU AI - PHASE 2 HARDENING PERFORMANCE BENCHMARK SUITE")
    print("=" * 70)

    t_start = time.perf_counter()

    optimizer_results = benchmark_optimizer()
    routing_results = benchmark_routing()

    tier_small = benchmark_workload_tier("small", num_farmers=10, num_buyers=8, num_shipments=5)
    tier_medium = benchmark_workload_tier("medium", num_farmers=100, num_buyers=20, num_shipments=30)
    tier_large = benchmark_workload_tier("large", num_farmers=1000, num_buyers=100, num_shipments=200)

    total_time = round(time.perf_counter() - t_start, 2)
    print("\n" + "=" * 70)
    print(f"BENCHMARK COMPLETED IN {total_time}s")
    print("=" * 70)

    benchmark_summary = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_runtime_seconds": total_time,
        "optimizer": optimizer_results,
        "routing": routing_results,
        "tiers": {
            "small": tier_small,
            "medium": tier_medium,
            "large": tier_large,
        },
    }

    # Save benchmark metrics to json
    os.makedirs("docs/hardening", exist_ok=True)
    bench_json_path = "docs/hardening/benchmark_metrics.json"
    with open(bench_json_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)

    print(f"Saved benchmark metrics to '{bench_json_path}'.")


if __name__ == "__main__":
    main()
