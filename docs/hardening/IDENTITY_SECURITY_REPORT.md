# GramSetu AI — Identity & Authorization Security Hardening Report

## 1. Executive Summary
Phase 1 used a development header fixture `X-Dev-Actor` which accepted arbitrary strings from incoming HTTP requests without cryptographic verification. If deployed to production, this represented a critical security vulnerability: any untrusted caller could impersonate system administrators, buyers, or farmers.

Phase 2 architected and implemented a pluggable `IdentityAdapter` framework, delivered production-ready JWT Bearer token authentication with strict cryptographic hygiene, and verified comprehensive multi-tenant isolation.

---

## 2. Architecture & Design (`gramsetu/security/identity.py`)

### The `IdentityAdapter` Interface
An abstract base class `IdentityAdapter` defines the contract:
```python
class IdentityAdapter(ABC):
    @abstractmethod
    def authenticate(self, request: Request) -> DevActor:
        ...
```

### Adapters Implemented:
1. **`DevIdentityAdapter`**:
   - For local development and automated testing only (`ENVIRONMENT != Environment.PRODUCTION`).
   - Reads `X-Dev-Actor` header and validates against `DEV_ACTORS`.
   - **Fail-Closed in Production**: If invoked in `Environment.PRODUCTION`, immediately raises 401 Unauthorized (`DEV_ACTOR_PROHIBITED_IN_PRODUCTION`).
2. **`JwtIdentityAdapter`**:
   - Implements standards-compliant JWT Bearer token authentication using PyJWT.
   - **Cryptographic Algorithm Pinning**: Strictly pinned to `["HS256", "RS256"]`. Explicitly blocks and rejects `alg="none"` in both header inspection and decoding.
   - **Claims Enforcement**: Requires `iss`, `aud`, `exp`, `sub`, and `role`. Verifies not-before (`nbf`) and expiration (`exp`).
   - **Role & Scoping Validation**: Maps `sub` to `actor_id` and maps `role` to validated `Role` enum. Unknown or rogue roles are rejected with 403 Forbidden.
3. **`HybridIdentityAdapter`**:
   - In development/testing, inspects `Authorization` header first; if a Bearer token is present, verifies via `JwtIdentityAdapter`; otherwise falls back to `DevIdentityAdapter`.
   - In production, forces all requests through `JwtIdentityAdapter`.

---

## 3. Adversarial Security Verification (`tests/hardening/test_auth_negative.py`)

Eight adversarial security attack vectors were executed and proven defeated:

| Attack / Adversarial Scenario | Expected Defense | Observed HTTP Status | Verification Result |
|---|---|---|---|
| **Spoofed `X-Dev-Actor` in Production** | Hard fail closed | `401 Unauthorized` | **PASSED** |
| **Insecure `alg="none"` JWT exploit** | Header-level rejection | `401 Unauthorized` | **PASSED** |
| **Expired JWT (`exp < now`)** | Signature rejection | `401 Unauthorized` (`TOKEN_EXPIRED`) | **PASSED** |
| **Tampered JWT signature (invalid HMAC)** | Secret mismatch rejection | `401 Unauthorized` | **PASSED** |
| **Wrong JWT Issuer (`iss != gramsetu-auth`)** | Issuer validation rejection | `401 Unauthorized` | **PASSED** |
| **Wrong JWT Audience (`aud != gramsetu-api`)** | Audience validation rejection | `401 Unauthorized` | **PASSED** |
| **Rogue / Malicious Role Claim in JWT** | Role enum validation | `403 Forbidden` | **PASSED** |
| **Cross-Tenant Intrusion (Buyer writing lots)** | Role and resource scoping | `403 Forbidden` | **PASSED** |

---

## 4. Verification Verdict
- Test suite: `tests/hardening/test_auth_negative.py` (8 tests passed).
- Gate status: **GATE R3 — PASS**.
