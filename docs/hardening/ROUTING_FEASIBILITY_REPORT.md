# GramSetu AI — Logistics Routing Feasibility & Road Graph Report

## 1. Executive Summary
The Phase 1 logistics engine estimated transport distance and duration purely via Haversine great-circle formulas combined with an assumed uniform travel speed of 40 km/h. In rural Indian agricultural geography (Maharashtra/Madhya Pradesh), this assumption fails critically:
1. Haversine ignores physical barriers such as unbridged rivers, railway lines, and mountain ghats.
2. Vehicles crossing rural bridges often face strict gross vehicle weight limits (e.g. 5,000,000 grams / 5 tonnes).
3. Monsoon seasonal washouts and causeway submersion render primary highway segments impassable.

Phase 2 replaced naive chord-distance approximations with a deterministic directed rural road graph provider (`OfflineRoadGraphProvider`) and shortest-duration Dijkstra routing with feasibility constraints.

---

## 2. Road Graph Architecture (`gramsetu/algorithms.py`)

### Data Structures:
- **`RoadNode`**: Identifies hubs, warehouses, mandis, and bridge junctions (`node_id`, `name`, `lat`, `lon`).
- **`RoadEdge`**: Directed road segment between nodes with:
  - `distance_meters`: True road distance.
  - `speed_kmh`: Realistic road segment speed (e.g., 65 km/h on paved highway, 30 km/h on rural unpaved tracks).
  - `weight_limit_grams`: Structural capacity limit for bridges or rural culverts.
  - `is_open`: Operational status (set to `False` during monsoon flooding or maintenance).
  - `closure_reason`: Documented reason for road closure.

### Default Network Fixture (`get_default_road_network()`):
Models a rural aggregation network connecting:
- `FPO_WH_ALPHA` (Central aggregation warehouse)
- `HUB_JUNCTION_1` (Arterial junction)
- `BRIDGE_RIVER_K` (Fast highway bridge, 5t weight limit)
- `BYPASS_RIVER_K` (Longer upstream unpaved causeway bypass, 20t limit)
- `BUYER_BIGBASKET_DC` (Primary buyer terminal)
- `BUYER_RELIANCE_MUMBAI` (Metropolitan terminal)
- `LOCAL_MANDI` (Local agricultural produce market)
- `ISOLATED_OUTPOST` (Completely disconnected node)

---

## 3. Algorithmic Routing Capabilities

### Dijkstra Multi-Constraint Solver
- **Objective**: Minimize total travel duration in seconds ($t = \text{distance} / \text{speed}$).
- **Weight Limit Feasibility**: If `vehicle_payload_grams > edge.weight_limit_grams`, the edge is bypassed and recorded under `road_restrictions_applied`.
- **Road Closure Feasibility**: If `edge.is_open == False`, the edge is pruned.
- **Honest Status Responses**:
  - `ROUTE_VERIFIED`: Path found with verified topology.
  - `ROUTE_UNVERIFIED`: Query coordinates missing from network graph.
  - `NO_FEASIBLE_ROUTE`: Target disconnected or blocked by closures/weight limits. Never invents zero-distance routes.

---

## 4. Empirical Verification & Oracle Proof (`tests/hardening/test_road_graph_routing.py`)

1. **Light Vehicle Baseline (1.5 tonnes)**:
   - Takes primary highway via River Krishna Bridge: `FPO_WH_ALPHA -> HUB_JUNCTION_1 -> BRIDGE_RIVER_K -> BUYER_BIGBASKET_DC`.
   - Distance: 80.0 km; Status: `ROUTE_VERIFIED`.
2. **Heavy Vehicle Detour (10 tonnes)**:
   - Exceeds bridge 5t limit; correctly detours via upstream causeway: `FPO_WH_ALPHA -> HUB_JUNCTION_1 -> BYPASS_RIVER_K -> BUYER_BIGBASKET_DC`.
   - Distance: 105.0 km; Status: `ROUTE_VERIFIED`; `road_restrictions_applied` records `WEIGHT_LIMIT_EXCEEDED`.
3. **Monsoon Road Closure**:
   - Marking River Krishna Bridge `is_open = False` automatically reroutes even light vehicles via the bypass.
4. **Disconnected Hamlet Fail-Closed**:
   - Querying `ISOLATED_OUTPOST` returns `NO_FEASIBLE_ROUTE`, `path_nodes=[]`, `distance_km=0.0`.
5. **Brute-Force All-Paths Oracle Comparison**:
   - Evaluated custom 5-node multi-path graph against exhaustive combinatorial enumeration: Dijkstra shortest path matched the brute-force minimum duration byte-for-byte (2,160.0s).
6. **Execution Speed**: 500 Dijkstra routing queries executed with p50 latency of **0.0044 ms** (4.4 microseconds).

---

## 5. Verification Verdict
- Test suite: `tests/hardening/test_road_graph_routing.py` (7 tests passed).
- Gate status: **GATE R4 — PASS**.
