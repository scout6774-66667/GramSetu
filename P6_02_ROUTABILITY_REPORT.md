# GramSetu AI — Site GPS Ground Truth & Route Safety Report

**Document ID:** P6_02_ROUTABILITY_REPORT.md  
**Audit Phase:** Phase 6 Workstream P6.2  
**Verdict:** `ROUTING_UNSAFE_FOR_UNATTENDED_DISPATCH`

---

## 1. Site GPS Ground Truth vs Administrative Centroid Proxies

All 79 locations in the v2.2 baseline (`locations.csv`) carry:
- `coordinate_provenance: SOURCED_ADMIN_HQ_AREA_PROXY_NOT_SITE`
- `site_coordinate_verified: False`

These coordinates represent Local Government Directory (LGD) district/block headquarters offices (e.g. Suri, Bankura, Bolpur collectorates), not the physical farm gates, collection centers, or warehouse loading docks. Dispatching a heavy cargo truck to a collectorate office building 18 km away from the actual farm gate is an operational failure.

---

## 2. Road Network Invariants & Unknown Constraint Policy

1. **Unknown Bridge & Weight Limits (`P6-07`):**
   - An absent OSM tag (`maxweight: None`) MUST be treated as **UNKNOWN**, never as unlimited.
   - For light commercial vehicles ($\le 3,000,000$ grams = 3 tonnes), rural arterial routes are tentatively permitted under manual driver vigilance.
   - For heavy freight trucks (> 3 tonnes), any segment with unknown bridge capacity requires **mandatory human operator sign-off** before route clearance.
2. **Topological Tests:**
   - Directed routing algorithm (`gramsetu/algorithms.py:OfflineRoadGraphProvider`) tested for:
     - Disconnected components
     - Vehicle weight limit adherence (e.g. 12-tonne truck rejected on 5-tonne culvert)
     - Zero floating-point distance drift (integer meters).
