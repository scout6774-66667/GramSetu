"""Backward-compatible facade for gramsetu.algorithms."""
from __future__ import annotations

from gramsetu.optimization.routing import (
    haversine_distance_km,
    estimate_route_metrics,
    RoadNode,
    RoadEdge,
    TravelMatrixProvider,
    OfflineRoadGraphProvider,
    get_default_road_network,
)
from gramsetu.optimization.recovery import optimize_recovery_allocation

__all__ = [
    "haversine_distance_km",
    "estimate_route_metrics",
    "RoadNode",
    "RoadEdge",
    "TravelMatrixProvider",
    "OfflineRoadGraphProvider",
    "get_default_road_network",
    "optimize_recovery_allocation",
]
