"""Road network logistics and graph routing algorithms for GramSetu AI."""
from __future__ import annotations

import math
import heapq
from typing import Dict, Any, Tuple, List, Optional
from pydantic import BaseModel


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def estimate_route_metrics(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    payload_grams: int,
    vehicle_capacity_grams: int,
) -> Dict[str, Any]:
    """Estimate straight-line route metrics, capacity feasibility, travel time, and cost in paise."""
    distance = haversine_distance_km(origin_lat, origin_lon, dest_lat, dest_lon)
    is_feasible = payload_grams <= vehicle_capacity_grams
    utilization = round((payload_grams / vehicle_capacity_grams) * 100.0, 1) if vehicle_capacity_grams > 0 else 0.0

    avg_speed_kmh = 40.0
    est_hours = round(max(0.5, distance / avg_speed_kmh), 2)

    base_paise = 50_000
    per_km_paise = 2_500
    est_cost_paise = int(base_paise + (distance * per_km_paise))

    return {
        "distance_km": distance,
        "is_feasible": is_feasible,
        "utilization_percent": utilization,
        "estimated_hours": est_hours,
        "estimated_cost_paise": est_cost_paise,
        "route_status": "ESTIMATE_ONLY",
        "disclaimer": "PROVISIONAL ESTIMATOR: Straight-line route metrics. Does not account for road obstructions or tolls.",
    }


class RoadNode(BaseModel):
    node_id: str
    name: str
    lat: float
    lon: float


class RoadEdge(BaseModel):
    edge_id: str
    source_node: str
    target_node: str
    distance_meters: int
    speed_kmh: float = 40.0
    weight_limit_grams: Optional[int] = None
    is_open: bool = True
    closure_reason: Optional[str] = None
    road_class: str = "RURAL_ARTERIAL"


class TravelMatrixProvider:
    def get_route(
        self,
        origin_node: str,
        dest_node: str,
        vehicle_payload_grams: int = 0,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class OfflineRoadGraphProvider(TravelMatrixProvider):
    """Deterministic offline directed road graph provider with Dijkstra shortest path,
    seasonal road closures, and weight limit feasibility.
    """
    def __init__(self):
        self.nodes: Dict[str, RoadNode] = {}
        self.adjacency: Dict[str, List[RoadEdge]] = {}

    def add_node(self, node: RoadNode) -> None:
        self.nodes[node.node_id] = node
        if node.node_id not in self.adjacency:
            self.adjacency[node.node_id] = []

    def add_edge(self, edge: RoadEdge) -> None:
        if edge.source_node not in self.nodes:
            raise ValueError(f"Source node '{edge.source_node}' does not exist in graph.")
        if edge.target_node not in self.nodes:
            raise ValueError(f"Target node '{edge.target_node}' does not exist in graph.")
        self.adjacency[edge.source_node].append(edge)

    def get_route(
        self,
        origin_node: str,
        dest_node: str,
        vehicle_payload_grams: int = 0,
    ) -> Dict[str, Any]:
        if origin_node not in self.nodes or dest_node not in self.nodes:
            return {
                "origin": origin_node,
                "destination": dest_node,
                "distance_meters": 0,
                "distance_km": 0.0,
                "duration_seconds": 0,
                "estimated_hours": 0.0,
                "estimated_cost_paise": 0,
                "route_status": "ROUTE_UNVERIFIED",
                "path_nodes": [],
                "road_restrictions_applied": ["UNKNOWN_NODE_COORDINATES"],
                "provider_name": "OfflineRoadGraphProvider-v2.0",
                "confidence": 0.0,
                "disclaimer": "ROUTE UNVERIFIED: One or both locations are missing from road network graph.",
            }

        if origin_node == dest_node:
            return {
                "origin": origin_node,
                "destination": dest_node,
                "distance_meters": 0,
                "distance_km": 0.0,
                "duration_seconds": 0,
                "estimated_hours": 0.0,
                "estimated_cost_paise": 0,
                "route_status": "ROUTE_VERIFIED",
                "path_nodes": [origin_node],
                "road_restrictions_applied": [],
                "provider_name": "OfflineRoadGraphProvider-v2.0",
                "confidence": 1.0,
                "disclaimer": "OFFLINE ROAD GRAPH: Origin and destination are identical.",
            }

        # Dijkstra shortest path search (minimizing duration in seconds)
        pq: List[Tuple[float, str, List[str], List[RoadEdge]]] = [(0.0, origin_node, [origin_node], [])]
        visited: Dict[str, float] = {}
        applied_restrictions: List[str] = []

        while pq:
            cost_sec, curr_node, path, edges_taken = heapq.heappop(pq)

            if curr_node in visited and visited[curr_node] <= cost_sec:
                continue
            visited[curr_node] = cost_sec

            if curr_node == dest_node:
                total_meters = sum(e.distance_meters for e in edges_taken)
                total_seconds = int(cost_sec)
                distance_km = round(total_meters / 1000.0, 2)
                estimated_hours = round(total_seconds / 3600.0, 2)
                estimated_cost_paise = int(50_000 + (distance_km * 2500))

                return {
                    "origin": origin_node,
                    "destination": dest_node,
                    "distance_meters": total_meters,
                    "distance_km": distance_km,
                    "duration_seconds": total_seconds,
                    "estimated_hours": estimated_hours,
                    "estimated_cost_paise": estimated_cost_paise,
                    "route_status": "ROUTE_VERIFIED",
                    "path_nodes": path,
                    "road_restrictions_applied": list(set(applied_restrictions)),
                    "provider_name": "OfflineRoadGraphProvider-v2.0",
                    "confidence": 1.0,
                    "disclaimer": "OFFLINE ROAD GRAPH: Verified topology over deterministic rural road segments.",
                }

            for edge in self.adjacency.get(curr_node, []):
                if not edge.is_open:
                    applied_restrictions.append(f"CLOSED_EDGE:{edge.edge_id}:{edge.closure_reason or 'CLOSED'}")
                    continue

                if edge.weight_limit_grams is not None and vehicle_payload_grams > edge.weight_limit_grams:
                    applied_restrictions.append(f"WEIGHT_LIMIT_EXCEEDED:{edge.edge_id}:{edge.weight_limit_grams}g")
                    continue

                speed_mps = (edge.speed_kmh * 1000.0) / 3600.0
                edge_seconds = edge.distance_meters / speed_mps
                next_cost = cost_sec + edge_seconds

                if edge.target_node not in visited or next_cost < visited[edge.target_node]:
                    heapq.heappush(pq, (next_cost, edge.target_node, path + [edge.target_node], edges_taken + [edge]))

        return {
            "origin": origin_node,
            "destination": dest_node,
            "distance_meters": 0,
            "distance_km": 0.0,
            "duration_seconds": 0,
            "estimated_hours": 0.0,
            "estimated_cost_paise": 0,
            "route_status": "NO_FEASIBLE_ROUTE",
            "path_nodes": [],
            "road_restrictions_applied": list(set(applied_restrictions)),
            "provider_name": "OfflineRoadGraphProvider-v2.0",
            "confidence": 0.0,
            "disclaimer": "NO FEASIBLE ROUTE: Target unreachable due to road closures, weight limits, or missing connectivity.",
        }


def get_default_road_network() -> OfflineRoadGraphProvider:
    """Construct a deterministic reference rural road network fixture."""
    graph = OfflineRoadGraphProvider()

    graph.add_node(RoadNode(node_id="FPO_WH_ALPHA", name="FPO Alpha Central Warehouse", lat=18.5204, lon=73.8567))
    graph.add_node(RoadNode(node_id="HUB_JUNCTION_1", name="Rural Arterial Junction 1", lat=18.6200, lon=73.9100))
    graph.add_node(RoadNode(node_id="BRIDGE_RIVER_K", name="River Krishna Bridge", lat=18.7100, lon=73.9500))
    graph.add_node(RoadNode(node_id="BYPASS_RIVER_K", name="Upstream Causeway Bypass", lat=18.7300, lon=73.8900))
    graph.add_node(RoadNode(node_id="BUYER_BIGBASKET_DC", name="BigBasket Distribution Center", lat=18.9220, lon=72.8347))
    graph.add_node(RoadNode(node_id="BUYER_RELIANCE_MUMBAI", name="Reliance Fresh Vashi Terminal", lat=19.0760, lon=72.9980))
    graph.add_node(RoadNode(node_id="LOCAL_MANDI", name="Baramati Agricultural Produce Market", lat=18.1517, lon=74.5772))
    graph.add_node(RoadNode(node_id="ISOLATED_OUTPOST", name="Remote Tribal Hamlet", lat=19.5000, lon=74.2000))

    graph.add_edge(RoadEdge(edge_id="e-wh-hub", source_node="FPO_WH_ALPHA", target_node="HUB_JUNCTION_1", distance_meters=15_000, speed_kmh=50.0))
    graph.add_edge(RoadEdge(edge_id="e-hub-wh", source_node="HUB_JUNCTION_1", target_node="FPO_WH_ALPHA", distance_meters=15_000, speed_kmh=50.0))

    graph.add_edge(RoadEdge(edge_id="e-hub-bridge", source_node="HUB_JUNCTION_1", target_node="BRIDGE_RIVER_K", distance_meters=20_000, speed_kmh=60.0, weight_limit_grams=5_000_000))
    graph.add_edge(RoadEdge(edge_id="e-bridge-hub", source_node="BRIDGE_RIVER_K", target_node="HUB_JUNCTION_1", distance_meters=20_000, speed_kmh=60.0, weight_limit_grams=5_000_000))

    graph.add_edge(RoadEdge(edge_id="e-hub-bypass", source_node="HUB_JUNCTION_1", target_node="BYPASS_RIVER_K", distance_meters=35_000, speed_kmh=30.0, road_class="UNPAVED_TRACK", weight_limit_grams=20_000_000))
    graph.add_edge(RoadEdge(edge_id="e-bypass-hub", source_node="BYPASS_RIVER_K", target_node="HUB_JUNCTION_1", distance_meters=35_000, speed_kmh=30.0, road_class="UNPAVED_TRACK", weight_limit_grams=20_000_000))

    graph.add_edge(RoadEdge(edge_id="e-bridge-bb", source_node="BRIDGE_RIVER_K", target_node="BUYER_BIGBASKET_DC", distance_meters=45_000, speed_kmh=65.0))
    graph.add_edge(RoadEdge(edge_id="e-bypass-bb", source_node="BYPASS_RIVER_K", target_node="BUYER_BIGBASKET_DC", distance_meters=55_000, speed_kmh=50.0))

    graph.add_edge(RoadEdge(edge_id="e-bb-rel", source_node="BUYER_BIGBASKET_DC", target_node="BUYER_RELIANCE_MUMBAI", distance_meters=25_000, speed_kmh=55.0))
    graph.add_edge(RoadEdge(edge_id="e-rel-bb", source_node="BUYER_RELIANCE_MUMBAI", target_node="BUYER_BIGBASKET_DC", distance_meters=25_000, speed_kmh=55.0))

    graph.add_edge(RoadEdge(edge_id="e-wh-mandi", source_node="FPO_WH_ALPHA", target_node="LOCAL_MANDI", distance_meters=12_000, speed_kmh=40.0))
    graph.add_edge(RoadEdge(edge_id="e-mandi-wh", source_node="LOCAL_MANDI", target_node="FPO_WH_ALPHA", distance_meters=12_000, speed_kmh=40.0))

    return graph
