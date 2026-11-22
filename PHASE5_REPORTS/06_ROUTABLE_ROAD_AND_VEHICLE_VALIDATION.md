# GramSetu AI — Routable Road Network & Vehicle Restriction Audit

**Audit Date:** 2026-11-22  
**Dataset Table:** `road_edges.csv` (v2.2 baseline: 620 edges, 69 nodes)  
**Evaluator:** Principal Geographic Information Systems (GIS) & Logistics SRE Auditor  
**Verdict:** `ROUTING_UNSAFE / PRODUCTION_BLOCKED`

---

## 1. Executive Summary

GramSetu AI’s logistics optimization engine (`gramsetu/algorithms.py` and `gramsetu/services/logistics.py`) plans freight dispatch routes using an in-memory graph representation of `road_edges.csv`.

An exhaustive audit of the 620 road edges in the v2.2 baseline reveals that **100% of edges are synthetic straight-line approximations** (`SIMULATED_CONNECTIVITY_GEODESIC_DETOUR_NOT_OSM`) connecting administrative centroid nodes. 

None of the edges represent real-world navigable road centerlines, and **zero edges have live-verified passability or structural vehicle restrictions**. Deploying physical transport vehicles (specifically 16-tonne multi-axle freight trucks or refrigerated vans) using this network would cause catastrophic operational failures, including routing vehicles over impassable dirt paths, collapsed bridges, or weight-restricted rural culverts.

---

## 2. Statistical Breakdown of Road Edge Attributes

| Parameter | Total Edges | Compliant / Verified | Deficiency % | Operational Implication |
| :--- | :--- | :--- | :--- | :--- |
| **Total Graph Edges** | 620 | 0 Verified | 100.0% | Entire routing topology is synthetic. |
| **Geometry Provenance** | 620 | 0 Real OSM | 100.0% | Edges are Euclidean detours with synthetic distance factors. |
| **Live Passability Status** | 620 | 0 Live Verified | 100.0% | Floods, landslides, and road closures cannot be detected. |
| **Max Vehicle Weight (`maxweight`)**| 620 | 12 Declared (1.9%) | 98.1% Missing | Heavy trucks cannot be checked against bridge weight limits. |
| **Max Overhead Height (`maxheight`)**| 620 | 0 Declared (0.0%) | 100.0% Missing | Risk of vehicle collisions with low rail bridges or rural cables. |
| **Surface Pavement Class** | 620 | 0 Validated | 100.0% Missing | Unpaved mud tracks treated identically to national highways. |

---

## 3. Critical Operational Hazards in Rural Transport

```
+-----------------------------------------------------------------------------+
| RURAL LOGISTICS FAILURE MODES (SYNTHETIC VS REAL OSM)                       |
+-----------------------------------------------------------------------------+
|                                                                             |
|  [ Synthetic Model Assumptions ]          [ Physical Ground Truth ]         |
|                                                                             |
|  Node A (Centroid)                      Village Gate                        |
|       |                                      \                              |
|       | 15 km Euclidean line                  \ Unpaved Cart Track (Mud)    |
|       | Unlimited Ton Capacity                 \ Max 3 Ton Wooden Culvert   |
|       |                                         \                           |
|  Node B (Centroid)                               Bridge (Damaged / Closed)  |
|                                                   \                         |
|                                                    Main APMC Mandi Gate     |
|                                                                             |
|  Outcome: Multi-axle truck dispatched -> Stuck in culvert -> 100% Spoilage  |
+-----------------------------------------------------------------------------+
```

1. **Bridge Load Limit Breaches:**
   - Agricultural bulk transport frequently utilizes 16-tonne to 25-tonne Gross Vehicle Weight (GVW) trucks.
   - Rural culverts and wooden bridge crossings in district networks (e.g., Bankura, Birbhum) routinely enforce a 6-tonne or 10-tonne axle weight restriction.
   - Without `max_vehicle_weight_kg` and bridge clearance attributes, `find_lowest_cost_route` selects structurally hazardous shortcuts.

2. **Monsoon Washout & Surface Impassability:**
   - During the West Bengal monsoon season (June–October), unpaved rural roads (`unpaved / dirt / gravel`) become impassable for non-4WD commercial freight.
   - `road_edges.csv` lacks pavement tags (`surface: asphalt/concrete/unpaved`), leading the Dijkstra algorithm to calculate travel times assuming dry asphalt speeds (45–60 km/h) on unpaved dirt tracks where real speed is 0–10 km/h.

3. **Missing Directed Turn Restrictions:**
   - The synthetic graph models bi-directional connectivity without considering one-way village bazaars, toll plaza lanes, or mandatory truck bypasses.

---

## 4. Remediation Architecture for Phase 6

To unblock the road routing engine for real-world dispatch, the following engineering steps must be implemented:

1. **OSM Overpass Ingestion Pipeline:**
   - Ingest genuine OpenStreetMap `.pbf` road extracts covering project operational districts (Paschim Bardhaman, Purba Bardhaman, Birbhum, Bankura, Darjeeling, Malda).
   - Filter highway tags to: `motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `unclassified`.
   - Extract legal vehicle restriction tags: `maxweight`, `maxheight`, `maxwidth`, `surface`, `bridge`, `access=agricultural`.

2. **Integration with OSRM / Valhalla Freight Profile:**
   - Replace Euclidean straight-line distance calculations with a local Open Source Routing Machine (OSRM) or Valhalla container configured with a custom Heavy Goods Vehicle (HGV) profile.
   - Enforce route verification in `LogisticsService.verify_route`: reject any shipment assignment if `truck_gross_weight > route_min_bridge_weight`.

3. **Status:** **`BLOCKED`** — Synthetic graph retained solely for unit-test algorithm verification. Physical driver dispatch remains strictly disabled.
