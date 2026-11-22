# GramSetu AI Feature Contracts (F0 - F13)

### F0: Bootstrap and State Store
- App factory with `/health`, `/docs`.
- Environment settings via pydantic-settings or os.environ.
- TransactionCoordinator with `threading.RLock`, rollback on exception, and atomic JSON copy-on-write persistence (`.tmp` + flush + `os.replace`).
- Deep-copy read safety. Rejection of corrupted snapshot files.
- Integer quantities (grams) and currency (paise) validation.

### F1: Actors, Role Permissions, and Resource Scoping
- Server-side `DevActor` registry with roles: `FARMER`, `FPO_ADMIN`, `BUYER`, `DRIVER`, `SYSTEM`.
- Header `X-Dev-Actor` validated server-side. Missing/unknown actor -> 401 Unauthorized.
- Scoping rules:
  - Role mismatch -> 403 Forbidden.
  - Cross-organization access (e.g. FPO admin A accessing FPO B resources) -> 403 Forbidden.
  - Driver can only view/update assigned shipments.
  - Farmer can only access their own forecasts and settlements.
  - Buyer can only access their own requirements and commitments.

### F2: DemandSync: Forecasts, Requirements, and Gap Analysis
- Farmer submits `HarvestForecast`: crop, variety, grade, estimated quantity grams, harvest date window.
- Buyer submits `BuyerRequirement`: crop, variety, grade, needed quantity grams, delivery window, max price per kg in paise.
- Demand Gap computation: Pure calculation comparing verified demand vs forecasts within matching crop/grade/time window.
- Explicitly labeled planning-only; never touches physical stock.
- Idempotent repeated submission by idempotency key or natural key.

### F3: BatchTrace: Inventory Receipts, Splits, Merges, and Custody
- Physical receipt creates `InventoryLot` from farmer delivery. Requires FPO admin verification.
- Lot attributes: `lot_id`, `fpo_id`, `farmer_id`, `crop`, `variety`, `grade`, `quantity_grams`, `reserved_grams`, `storage_location`, `status`, `version`.
- Quantity conservation invariant: `reserved_grams <= quantity_grams`, `available_grams = quantity_grams - reserved_grams`.
- Lot split: `parent_lot -> [child_lot_1, child_lot_2, ...]`. Invariant: $\sum child\_grams == parent\_grams$.
- Lot merge: `[lot_1, lot_2] -> merged_lot`. Invariant: identical crop/grade/fpo, $\sum inputs == output$.
- Negative stock is rejected with a domain error.

### F4: CommitGuard: Atomic Buyer Commitments
- Create `Commitment`: matches BuyerRequirement to eligible available inventory in `InventoryLot`s.
- Atomically reserves `quantity_grams` across lots (increments `reserved_grams`).
- Contract validation: grade match, crop match, offer not expired, available inventory sufficient.
- Cancellation pre-pickup releases reserved grams back to available.
- Cancellation post-pickup rejected or handled as logistics return/disruption.
- Idempotent commitment creation.

### F5: Logistics: Collection, Vehicle Assignment, and Delivery
- Vehicle registry: vehicle ID, capacity in grams, operational status, assigned driver ID.
- Shipment creation: references Commitment, vehicle, driver, planned pickup & delivery timestamps.
- Dispatched status: physical inventory transfers custody from warehouse to driver (in-transit).
- Delivery receipt: driver and receiver sign off. Records `accepted_grams`, `rejected_grams`, `loss_grams`.
  - Invariant: `accepted_grams + rejected_grams + loss_grams == dispatched_grams`.
- Straight-line distance / capacity estimator in pure algorithms.

### F6: RiskWatch: Incidents and Time-Based Rules
- Automated scan for risks:
  - Missed pickup deadlines.
  - Expiring inventory lots (perishability shelf-life).
  - Short deliveries or quality rejections.
  - Overdue payments.
- Incident records created with deduplication key (no duplicate incident for same event/lot).
- Severity calculation based on magnitude and remaining shelf-life.
- State resolution requires verified commercial action or explicit loss write-off.

### F7: RecoveryOpt: Disruption Response and Safe Approval
- Triggered by cancelled commitment, transport breakdown, or delivery rejection.
- Bounded algorithm (<= 8 candidates) finding alternative buyers with compatible requirements, computing net return = (buyer offer - transport cost - discount).
- Candidate ranking output labeled purely as a recommendation.
- Safe execution: requires explicit FPO admin approval and buyer confirmation. Atomically creates new commitment and transfers reservation.

### F8: SettleTrack: Payment Accounting
- Payable generation: `payable_paise = (accepted_grams * unit_price_paise_per_gram) - authorized_deductions_paise`.
- Deductions: transport charge, packaging, grading fee (all itemized and authenticated).
- Payment recording: status transitions `PENDING -> PARTIALLY_PAID -> SETTLED`.
- Partial payments tracked with reference/evidence and remaining balance.
- Overpayment rejected. Zero payable handled gracefully (no overdue debt).
- Reversals and adjustments recorded as immutable audit log entries.

### F9: Four App-Facing Query Services
- Role-specific query views with last-updated UTC timestamps:
  - `FarmerOverview`: active forecasts, physical receipts, delivered lots, pending/completed settlements.
  - `BuyerOverview`: open requirements, active commitments, in-transit shipments, completed deliveries, payables.
  - `DriverOverview`: assigned routes, scheduled pickups, delivery confirmations, manifest details.
  - `FpoOverview`: total available vs reserved stock, expiring lots, active shipments, disruption incidents, aggregate financial position.

### F10: Offline Command Reconciliation
- Command envelope: `command_id` (UUID), `actor_id`, `client_timestamp`, `resource_type`, `resource_id`, `expected_version`, `payload`.
- Safe reconciliation:
  - If expected version matches current version, apply mutation and advance version.
  - If version mismatch (conflict), log conflict task with diff, return 409 Conflict with current server state.
  - Replay with same `command_id` returns cached result idempotently.
  - Offline payment confirmations or reservations are rejected if state changed.

### F11: Durable Local Event Processing
- Append-only event journal on disk.
- In-memory event dispatcher with persisted cursor/sequence number.
- Handlers run outside write locks; commit actions through transactional coordinator.
- Bounded retries (e.g. max 3 attempts) and poison event quarantine to prevent infinite loops.

### F12: Performance, Security, and Reliability Gates
- Request payload size limits (e.g., max 1MB).
- Read pagination for lists.
- Structured logging with correlation `trace_id`. Sensitive credentials masked.
- Benchmark script measuring p95 execution time for core transactions and algorithms.
- Explicit operational documentation on single-worker constraint and migration roadmap.

### F13: Final Cross-Feature Acceptance
- End-to-end integration tests:
  - Happy path: Forecast -> Receipt -> Requirement -> Commitment -> Shipment -> Delivery -> Settlement.
  - Disruption path: Mid-transit rejection -> Incident -> RecoveryOpt ranking -> FPO approval -> Alternative buyer settlement.
  - Bad network / offline retry scenario.
  - Snapshot recovery verification: restart app from snapshot and verify complete state consistency.
