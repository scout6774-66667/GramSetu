# GramSetu AI — Security & Threat Modeling Audit
**Audit Date**: 2026-11-17 | **Auditor**: Independent Principal Validation Engineer

---

## 1. Access Control Matrix (Role $\times$ Action)

| Endpoint Path | Method | Allowed Roles | Enforcement Mechanism | Negative Test Result |
| :--- | :---: | :--- | :--- | :---: |
| `/api/v1/forecasts` | `POST` | `FARMER`, `SYSTEM` | `require_roles(Role.FARMER)` | 403 Forbidden for `BUYER`, `DRIVER` |
| `/api/v1/lots/receipt` | `POST` | `FPO_ADMIN`, `SYSTEM` | `require_roles(Role.FPO_ADMIN)` | 403 Forbidden for `FARMER`, `BUYER` |
| `/api/v1/lots/{id}/split` | `POST` | `FPO_ADMIN`, `SYSTEM` | `require_roles(Role.FPO_ADMIN)` + Org check | 403 Forbidden for cross-FPO admins |
| `/api/v1/commitments` | `POST` | `BUYER`, `SYSTEM` | `require_roles(Role.BUYER)` | 403 Forbidden for `FARMER`, `DRIVER` |
| `/api/v1/shipments` | `POST` | `FPO_ADMIN`, `SYSTEM` | `require_roles(Role.FPO_ADMIN)` + Org check | 403 Forbidden for `DRIVER`, `BUYER` |
| `/api/v1/shipments/{id}/pickup` | `POST` | `DRIVER`, `SYSTEM` | `verify_driver_assignment()` | 403 Forbidden for unassigned drivers |
| `/api/v1/shipments/{id}/delivery`| `POST` | `DRIVER`, `SYSTEM` | `verify_driver_assignment()` | 403 Forbidden for unassigned drivers |
| `/api/v1/risk/scan` | `POST` | `FPO_ADMIN`, `SYSTEM` | `require_roles(Role.FPO_ADMIN)` + Org check | 403 Forbidden for `BUYER`, `FARMER` |
| `/api/v1/recovery/plans/{id}/approve` | `POST` | `FPO_ADMIN`, `SYSTEM` | `require_roles(Role.FPO_ADMIN)` + Org check | 403 Forbidden for `BUYER`, `DRIVER` |
| `/api/v1/settlements/{id}/payments/{pid}/verify` | `POST` | `FPO_ADMIN`, `SYSTEM` | `require_roles(Role.FPO_ADMIN)` + Org check | 403 Forbidden for `BUYER` |

---

## 2. Security Findings & Defect Remediation

### Finding 1: Production Environment Fail-Closed (Resolved - VAL-001)
- **Vulnerability**: In development/testing, authentication is simulated via the `X-Dev-Actor` header. Previously, setting `ENVIRONMENT = Environment.PRODUCTION` did not disable this header, creating an identity spoofing vulnerability.
- **Remediation**: Added an explicit check in `get_current_actor()`: if `settings.ENVIRONMENT == Environment.PRODUCTION`, all requests with `X-Dev-Actor` are rejected with HTTP 401 Unauthorized (`UNAUTHORIZED`). Production deployments must integrate an enterprise OIDC/OAuth2 JWT adapter.

### Finding 2: Insecure Direct Object References (IDOR) & Scoping
- **Audit**: Verified that all entity retrievals (`/lots/{id}`, `/commitments/{id}`, `/settlements/{id}`) execute tenant-scoping checks:
  - Farmers can only inspect lots and settlements bearing their `farmer_id`.
  - Buyers can only inspect commitments and requirements bearing their `buyer_id`.
  - FPO admins are scoped strictly to their `organization_id`.
- **Outcome**: **VERIFIED (No IDOR leakage detected)**.

### Finding 3: Denial of Service / Large Payload Protection
- **Audit**: A middleware in `gramsetu/main.py` inspects `Content-Length`. Requests exceeding `MAX_REQUEST_SIZE_BYTES` (default 1 MB) are rejected immediately with HTTP 413 Payload Too Large.
- **Test Evidence**: Verified by sending a 1.05 MB payload to `/api/v1/forecasts`, returning HTTP 413.

### Finding 4: Path Traversal & Snapshot Isolation
- **Audit**: Snapshot persistence uses an injected, server-controlled `SNAPSHOT_PATH`. Client inputs never influence filesystem paths or directory traversal parameters.
- **Outcome**: **SECURE**.
