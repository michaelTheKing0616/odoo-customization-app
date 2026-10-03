# Cards — T3 Ingenium Bridge

Self-contained. Rules: `../T3_BRIDGE.md`. The 2026-09-29 addendum wins on contract shape, Connections, and connector tiers. D3 (name Ingenium Bridge), D4 (Shopify first pilot), D5 (Connections first-class) are closed.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T3-specific:** contracts reference `connection_id`, never inline `odoo_target` or `third_party` credential blocks; secrets live on the Connection, encrypted at rest; two-way sync refused unless `conflict_resolution` is set; money entities require `money_policy`; every event carries `idempotency_key`; webhook signature verification is required when the connector supports it; Postgres queue only, no managed queue SaaS; jobs resume from a fresh plan, never a stale one; 3c (LLM-generated) only after 3b cannot express the connector; do not weaken the connector interface to make 3b pass (R-05); Paystack is not the pilot; Autopilot payment connectors are not this contract; Bridge DDL never dry-runs in place on production; kill switch `ingenium.bridge.enabled`; no outbound telemetry (INV-19).

**Interface (copied):** `fetch`, `create`, `update`, `declared_schema`, `verify_webhook_signature`, `parse_webhook_event`.

**Verification tiers (copied):** I static contract validation, incomplete fails. II sandbox dry-run: happy path, duplicate webhook, partial failure, auth failure, rate limit, malformed payload. III reconciliation dry-run with a seeded discrepancy that the run must detect.

**Code today:** `apps/api/app/bridge/contract.py` (Tier I), `connections.py` (`verify_connection`, `connection_may_leave_tier_i`), `connector.py` (`Connector`, `ShopifyConnector`, 76 lines), `queue.py` (`enqueue`, `mark_dead`), `routers/bridge.py` (`POST /api/bridge/contracts/validate`), migration `p6q7r8s9t0u1_bridge_connections_queue`, `r8s9t0u1v2w3_idempotency_keys`. Web: `apps/web/src/app/bridge/contracts/new/page.tsx` (123 lines).

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_bridge_and_config_spec.py tests/test_bridge_queue.py tests/test_bridge_protocol.py \
  tests/test_bridge_shopify_scenarios.py tests/test_dispatch_and_shopify.py tests/test_executor_bridge.py
```

**Audit events:** `change` (Odoo side), `rpc_write`, `error`, `note` (dead letter), `apply`.

---

### BR-00 — Phase 0 exit
- **Status:** PARTIAL. Contract schema rejects incomplete fixtures (DONE); queue accepts a test row (`test_enqueue_persists_and_deduplicates_on_postgres`, DONE); PR-J1 live check recorded (OPEN, operator).
- **depends_on:** T2-J1
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] Phase 0 exit: all three recorded in the progress log.

### BR-01 — Contract schema, Tier I fail-closed
- **Status:** DONE (`test_tier_i_accepts_a_complete_contract`, `test_two_way_without_conflict_resolution_fails`, `test_money_entity_without_policy_fails`, `test_inline_secret_is_rejected`, `test_inline_connection_block_is_rejected`).
- **Pressure:** 10 → Grok high effort (re-verify only)
- **Open delta:** a contract with an event missing `idempotency_key` fails Tier I (add if absent).

### BR-02 — Connections verify before Tier I passes
- **Status:** SEEDED (`test_unverified_connection_cannot_leave_tier_i`, `test_verified_connection_may_leave_tier_i`). Live verify per kind is not built.
- **Pressure:** C2 U1 F2 K2 V1 I1 +0 = 9 → Grok standard
- **Steps:** `verify_connection` calls a read-only probe per kind (Odoo: `version` + one `search_count`; Shopify: `shop.json`) and sets `verified_at` and `status`.
- **Acceptance:** [ ] no contract passes Tier I until each referenced connection has `verified_at`.
- **Negative:** a probe that fails leaves `status=failed` and Tier I refuses.

### BR-03 — Secrets encrypted at rest (14+ family: secrets)
- **Status:** OPEN (verify: the connection secrets column type and Fernet use).
- **Pressure:** C2 U1 F3 K2 V1 I2 +0 = 11 → Grok high effort; reviewer recommended
- **Read first:** `apps/api/app/crypto*.py` or `rg -n "Fernet" apps/api/app`; `bridge/connections.py`; the bridge migration.
- **Acceptance:** [ ] no plaintext secret column; [ ] the API never returns a secret (write-only fields); [ ] queue payloads reject secret keys (`test_secret_in_payload_raises` exists).
- **Negative:** `GET` on a connection returns `"api_key": "••••"` or omits it.

### BR-04 — Queue tables
- **Status:** DONE (`test_enqueue_persists_and_deduplicates_on_postgres`, `test_duplicate_idempotency_key_does_not_create_second_event`, `test_mark_dead_increments_attempts`).
- **Pressure:** 4 → cheap

### BR-05 — Connector interface (six methods)
- **Status:** DONE (`test_connector_protocol_has_exactly_six_method_names`).
- **Pressure:** 4 → cheap

### BR-06 — Shopify Tier II (six sandbox scenarios)
- **Status:** SEEDED against fakes (`test_tier_ii_six_scenarios`, `test_shopify_hmac_accepts_only_the_real_signature`, `test_shopify_rejects_unknown_entity_and_malformed_body`). Not run against a real Shopify sandbox.
- **depends_on:** BR-02
- **Pressure:** C2 U2 F2 K2 V2 I1 +0 = 11 → Grok high effort; operator provides a Shopify development store
- **Acceptance:** [ ] DoD 4: the six scenarios pass against a real Shopify development store and an Odoo sandbox; [ ] the run log path is recorded.
- **Do not:** use a merchant's live store.

### BR-07 — Shopify Tier III (seeded discrepancy)
- **Status:** SEEDED against fakes (`test_tier_iii_seeded_discrepancy_is_detected`).
- **depends_on:** BR-06
- **Pressure:** 11 → Grok high effort
- **Acceptance:** [ ] reconciliation dry-run against real sandboxes detects a seeded discrepancy (for example one order total off by 1.00).

### BR-08 — Tier 3b generic REST + webhook (config only)
- **Status:** OPEN
- **depends_on:** BR-07
- **Pressure:** C3 U2 F2 K2 V2 I2 +0 = 13 → Grok high effort
- **Acceptance:** [ ] Phase 2: at least one connector expressed as 3b config only (no Python), passing Tiers I–III.

### BR-09 — Genericity proof (DoD 5)
- **Status:** OPEN
- **depends_on:** BR-08
- **Pressure:** C3 U3 F2 K3 V2 I1 +0 = 14 → frontier
- **Acceptance:** [ ] Shopify expressed via 3b (or 3c) matches the hand-built connector's contract behavior on the same Tier II/III scenarios, with zero changes above the connector interface (diff of `bridge/` above `connector.py` is empty).
- **Negative:** if 3b cannot express Shopify, record why; keep 3a; do not change the interface.

### BR-10 — Tier 3c generated connector
- **Status:** OPEN
- **depends_on:** BR-09 showing 3b insufficient for a named connector
- **Pressure:** 13 → Grok high effort
- **Acceptance:** [ ] a generated connector passes Tiers I–III before listing; generated code is reviewed by a human; it never holds Odoo write credentials (INV-01).

### BR-11 — Dead letter (Phase 3)
- **Status:** SEEDED (`mark_dead`).
- **Pressure:** 7 → Grok standard
- **Acceptance:** [ ] a deliberately failing job lands in the dead-letter state and is visible to an operator in the UI (`/bridge/connections` or the journal).

### BR-12 — Contract Studio
- **Status:** SEEDED (`/bridge/contracts/new`, 123 lines).
- **depends_on:** BR-01 stable, UI-F04
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] form plus connection pickers; choosing two-way reveals `conflict_resolution` and blocks save until set; route block in `../13`.

### BR-13 — Catalog gate (Phase 4)
- **Status:** OPEN
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] a new connector cannot be listed before it passes Tiers I–III (test on the catalog listing).

### BR-14 — Bridge addon methods (shared with T8-OD-BRIDGE)
- **Status:** SEEDED (`test_reader_can_ping_and_cannot_apply_or_impersonate`, `test_kill_switch_protocol_and_escalation_refuse_before_work`, `test_apply_refuses_unknown_prohibited_and_inplace_ddl`).
- **Pressure:** 14 → frontier (owned by T8-OD-BRIDGE; listed here so Bridge workers know it exists)
- **Methods (copied):** `ping`, `introspect`, `combined_view`, `effective_access`, `render_check` (rolled-back savepoint), `apply_changeset` (validate / dry_run / apply, one transaction), `rollback_changeset`.
