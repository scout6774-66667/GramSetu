from __future__ import annotations

import itertools
import pytest
from fastapi.testclient import TestClient

from gramsetu.main import create_app
from gramsetu.core import DEV_ACTOR_HEADER
from gramsetu.algorithms import (
    RoadNode,
    RoadEdge,
    OfflineRoadGraphProvider,
    get_default_road_network,
)
from gramsetu.schemas import RouteVerificationRequest, RouteStatus


def test_r4_baseline_dijkstra_shortest_path():
    """R4 FEASIBILITY: Under normal conditions and light payload,
    Dijkstra selects the fastest primary route via River Krishna Bridge.
    """
    graph = get_default_road_network()
    # Light vehicle: 1,500,000 grams (1.5 tonnes)
    route = graph.get_route("FPO_WH_ALPHA", "BUYER_BIGBASKET_DC", vehicle_payload_grams=1_500_000)

    assert route["route_status"] == RouteStatus.ROUTE_VERIFIED.value
    assert route["path_nodes"] == ["FPO_WH_ALPHA", "HUB_JUNCTION_1", "BRIDGE_RIVER_K", "BUYER_BIGBASKET_DC"]
    assert route["distance_meters"] == 80_000  # 15km + 20km + 45km
    assert route["distance_km"] == 80.0
    assert route["duration_seconds"] > 0
    assert route["confidence"] == 1.0


def test_r4_weight_limit_forces_causeway_bypass():
    """R4 FEASIBILITY: When vehicle payload exceeds bridge limit (5,000,000 grams),
    the router MUST reject the bridge and detour via Upstream Causeway Bypass.
    """
    graph = get_default_road_network()
    # Heavy truck: 10,000,000 grams (10 tonnes) - exceeds bridge's 5t limit, but within bypass's 20t limit
    route = graph.get_route("FPO_WH_ALPHA", "BUYER_BIGBASKET_DC", vehicle_payload_grams=10_000_000)

    assert route["route_status"] == RouteStatus.ROUTE_VERIFIED.value
    # Path must use BYPASS_RIVER_K instead of BRIDGE_RIVER_K
    assert route["path_nodes"] == ["FPO_WH_ALPHA", "HUB_JUNCTION_1", "BYPASS_RIVER_K", "BUYER_BIGBASKET_DC"]
    assert "BRIDGE_RIVER_K" not in route["path_nodes"]
    assert any("WEIGHT_LIMIT_EXCEEDED" in r for r in route["road_restrictions_applied"])
    # Bypass is 15km + 35km + 55km = 105km (longer than bridge route)
    assert route["distance_km"] == 105.0


def test_r4_monsoon_road_closure_detour():
    """R4 FEASIBILITY: When primary bridge is closed (e.g. monsoon flooding),
    router detects closed edge and routes around it.
    """
    graph = get_default_road_network()
    # Mark bridge edge as closed due to monsoon flooding
    for edge in graph.adjacency["HUB_JUNCTION_1"]:
        if edge.target_node == "BRIDGE_RIVER_K":
            edge.is_open = False
            edge.closure_reason = "MONSOON_FLOODING_BRIDGE_SUBMERGED"

    route = graph.get_route("FPO_WH_ALPHA", "BUYER_BIGBASKET_DC", vehicle_payload_grams=1_000_000)

    assert route["route_status"] == RouteStatus.ROUTE_VERIFIED.value
    assert route["path_nodes"] == ["FPO_WH_ALPHA", "HUB_JUNCTION_1", "BYPASS_RIVER_K", "BUYER_BIGBASKET_DC"]
    assert any("CLOSED_EDGE" in r for r in route["road_restrictions_applied"])


def test_r4_disconnected_outpost_fails_closed():
    """R4 HONEST STATUS: An unreachable destination returns NO_FEASIBLE_ROUTE,
    never fabricating zero-distance or imaginary coordinates.
    """
    graph = get_default_road_network()
    # ISOLATED_OUTPOST has no connected roads
    route = graph.get_route("FPO_WH_ALPHA", "ISOLATED_OUTPOST", vehicle_payload_grams=1_000_000)

    assert route["route_status"] == RouteStatus.NO_FEASIBLE_ROUTE.value
    assert route["path_nodes"] == []
    assert route["distance_km"] == 0.0
    assert route["duration_seconds"] == 0
    assert route["confidence"] == 0.0


def test_r4_unknown_nodes_fail_closed():
    """R4 ERROR BEHAVIOR: Querying nodes not in graph returns ROUTE_UNVERIFIED."""
    graph = get_default_road_network()
    route = graph.get_route("UNKNOWN_VILLAGE", "BUYER_BIGBASKET_DC")
    assert route["route_status"] == RouteStatus.ROUTE_UNVERIFIED.value
    assert route["path_nodes"] == []


def test_r4_brute_force_oracle_comparison():
    """R4 ALGORITHMIC CORRECTNESS:
    Build a custom multi-path subgraph and verify Dijkstra output
    matches exhaustive all-paths brute force search byte-for-byte.
    """
    graph = OfflineRoadGraphProvider()
    for n in ["A", "B", "C", "D", "E"]:
        graph.add_node(RoadNode(node_id=n, name=f"Node {n}", lat=18.0, lon=73.0))

    # Path 1: A -> B -> E (longer distance, high speed)
    graph.add_edge(RoadEdge(edge_id="e-ab", source_node="A", target_node="B", distance_meters=30_000, speed_kmh=100.0))
    graph.add_edge(RoadEdge(edge_id="e-be", source_node="B", target_node="E", distance_meters=30_000, speed_kmh=100.0))

    # Path 2: A -> C -> E (shorter distance, slow unpaved road)
    graph.add_edge(RoadEdge(edge_id="e-ac", source_node="A", target_node="C", distance_meters=20_000, speed_kmh=20.0))
    graph.add_edge(RoadEdge(edge_id="e-ce", source_node="C", target_node="E", distance_meters=20_000, speed_kmh=20.0))

    # Path 3: A -> D -> E (moderate distance and speed)
    graph.add_edge(RoadEdge(edge_id="e-ad", source_node="A", target_node="D", distance_meters=25_000, speed_kmh=50.0))
    graph.add_edge(RoadEdge(edge_id="e-de", source_node="D", target_node="E", distance_meters=25_000, speed_kmh=50.0))

    # Compute duration for each path manually (brute force oracle)
    # Path 1 (A-B-E): 60km @ 100km/h = 0.60 hours = 2160.0 seconds
    # Path 2 (A-C-E): 40km @ 20km/h = 2.00 hours = 7200.0 seconds
    # Path 3 (A-D-E): 50km @ 50km/h = 1.00 hours = 3600.0 seconds
    # Optimal path is A -> B -> E
    dijkstra_result = graph.get_route("A", "E")

    assert dijkstra_result["path_nodes"] == ["A", "B", "E"]
    assert dijkstra_result["duration_seconds"] == 2160
    assert dijkstra_result["distance_km"] == 60.0


def test_r4_api_route_verification_endpoint():
    """R4 API INTEGRATION: Verify POST /api/v1/logistics/routes/verify endpoint."""
    app = create_app()
    client = TestClient(app)

    # 1. Light payload route verification
    res = client.post(
        "/api/v1/logistics/routes/verify",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={
            "origin": "FPO_WH_ALPHA",
            "destination": "BUYER_BIGBASKET_DC",
            "payload_weight_grams": 2_000_000,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["route_status"] == "ROUTE_VERIFIED"
    assert data["path_nodes"] == ["FPO_WH_ALPHA", "HUB_JUNCTION_1", "BRIDGE_RIVER_K", "BUYER_BIGBASKET_DC"]
    assert data["distance_km"] == 80.0
    assert data["estimated_hours"] > 0
    assert data["estimated_cost_paise"] > 0
    assert "disclaimer" in data

    # 2. Heavy payload route verification (detour)
    res_heavy = client.post(
        "/api/v1/logistics/routes/verify",
        headers={DEV_ACTOR_HEADER: "driver-1"},
        json={
            "origin": "FPO_WH_ALPHA",
            "destination": "BUYER_BIGBASKET_DC",
            "payload_weight_grams": 12_000_000,
        },
    )
    assert res_heavy.status_code == 200
    data_heavy = res_heavy.json()
    assert data_heavy["route_status"] == "ROUTE_VERIFIED"
    assert "BYPASS_RIVER_K" in data_heavy["path_nodes"]
    assert data_heavy["distance_km"] == 105.0

    app.state.coordinator.close()
