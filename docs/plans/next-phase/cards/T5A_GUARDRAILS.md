# Cards — T5A guardrail kernel

Self-contained. Gates 5A-1 to 5A-10 and the verbatim lists are in `../T5_GUARDRAILS_CONFIG_WORKERBOTS.md` lines 18–107. One implementation: T8 P3 extends this core and never forks it (master DoD 21).

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T5A-specific:** no override flag for never-allowed, at any autonomy level, including L4 (master DoD 24); classification is code, never a prompt and never a request field; do not create a second audit table or a second taxonomy; do not import `odoo-config-agent` (copy the lists, D7); new modules join `apps/api/scripts/lint_new_modules.sh`.

**Verbatim lists (the code must match these exactly; the code lives in `packages/odoo-client/src/odoo_client/rpc_policy.py` and `apps/api/app/rpc_classify.py`):**

```
READ_METHODS: search, search_read, read, search_count, fields_get, name_search,
  default_get, read_group, formatted_read_group, context_get, exists, get_views
SENSITIVE_MODELS: ir.model.access, ir.rule, ir.access, res.groups, res.groups.privilege,
  ir.config_parameter, ir.mail_server, fetchmail.server, auth.oauth.provider, res.users.apikeys,
  ir.module.module, account.move, account.payment, account.bank.statement,
  account.bank.statement.line, hr.payslip, ir.cron, ir.actions.server, base.automation,
  ir.ui.view, ir.model, ir.model.fields, payment.provider
DESTRUCTIVE_METHODS: unlink, button_immediate_uninstall, button_uninstall, action_post,
  button_cancel, action_cancel, action_reverse, button_draft, action_send_mail, message_post,
  send_mail, action_invoice_sent, action_register_payment, action_create_payments,
  action_validate, button_validate, button_mark_done, action_done, unlink_all, toggle_active,
  action_archive, action_unarchive, reconcile, remove_move_reconcile
BILLABLE_METHODS: button_immediate_install, button_install, button_upgrade,
  button_immediate_upgrade, iap_*, *_iap_*, action_buy_*
NEVER_ALLOWED: (res.users, unlink) (res.company, unlink) (ir.model.data, unlink)
  (ir.config_parameter, unlink) (res.users.apikeys, *)
PROTECTED_PARAMS: database.secret, database.uuid, database.create_date, web.base.url,
  database.enterprise_code, database.expiration_date
```

Extra rules: a write touching > 50 ids escalates to DESTRUCTIVE; module install on Community is DESTRUCTIVE, on Enterprise / Online / Odoo.sh BILLABLE; a new internal user (`share` falsy) on a paid edition is BILLABLE; `res.config.settings` with `module_*=True` follows the edition rule; protected-parameter writes are forbidden even with approval.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_rpc_classify.py tests/test_rpc_guard.py tests/test_plan_fingerprint.py \
  tests/test_audit_chain.py tests/test_dry_run_ledger.py tests/test_snapshot_gate.py \
  tests/test_power_ops_forbidden.py tests/test_mcp_guard.py tests/test_no_mcp_write.py
uv run --directory packages/odoo-client pytest -q tests/test_rpc_policy.py
```

**Audit events:** `rpc_write`, `change`, `error` (refusals), `apply`, `rollback`.

---

### 5A-01 — classify_rpc with the verbatim lists, mapped to Bucket A/B/C
- **Status:** DONE for classification (progress log "Track 5A kernel"). Bucket A/B/C mapping table not written.
- **Pressure:** C2 U1 F3 K3 V1 I2 +0 = 12 (security) → Grok high effort for the mapping; already reviewed by Claude Sonnet
- **Read first:** `apps/api/app/rpc_classify.py` (whole, about 240 lines); `apps/api/app/safety_registry.py` (Buckets); `packages/odoo-client/src/odoo_client/rpc_policy.py`.
- **Open delta:** write the two-way mapping table READ/REVERSIBLE/DESTRUCTIVE/BILLABLE ↔ Bucket A/B/C ↔ R0–R4 as a constant with a test that every Bucket entry maps to a class and back (master DoD 21).
- **Acceptance:** [x] 5A-1 sample classifies as the lists say (`test_read_is_read` … `test_mass_write`); [ ] mapping constant plus test.
- **Negative:** [x] `test_approved_does_not_override_never_allowed`; [ ] a request field named `risk` cannot change the class (add).

### 5A-02 — Structural dry-run hash on every write tool in T1, T3, T4
- **Status:** PARTIAL. `dry_run_middleware.py` refuses a JSON request with `dry_run: false` until the same body was seen with `dry_run: true`; `power_ops_recipes.run_recipe` enforces it. Requests that do not carry a `dry_run` key are not covered. Ledger storage needs checking (`dry_run_ledger.py`: per-process memory or the database?).
- **depends_on:** 5A-01
- **Pressure:** C3 U2 F3 K3 V2 I1 +0 = 14 → frontier, reviewer optional
- **Read first:** `apps/api/app/dry_run_middleware.py`, `apps/api/app/dry_run_ledger.py`, `apps/api/app/plan_fingerprint.py` (`dry_run_hash`).
- **Steps:**
  1. Inventory write-capable routes in T1 (generate apply, module install), T3 (`routers/bridge.py`, queue enqueue), T4 (dashboard save, offline flush, skills/triggers) with `rg -n "@router\.(post|put|patch|delete)" apps/api/app/routers`.
  2. For each, decide: it carries `dry_run`, or it goes through the change-set executor (whose plan hash is the dry-run), or it is not an Odoo write. Write the table in the progress log.
  3. Any Odoo-writing route in none of those three groups gets a `dry_run` field or moves behind the executor.
  4. If the ledger is per-process memory, move it to a table (TTL 1 h) so two workers agree.
- **Acceptance:** [ ] 5A-2 and DoD 22: every write-capable tool in T1, T3, T4 refuses a live write until `(tool, args minus dry_run)` was seen; [ ] the route table is in the progress log.
- **Negative:** a live write without a prior dry run returns `dry_run_receipt_required`; a dry run on worker A followed by a live write on worker B succeeds only if the ledger is shared.
- **Rollback:** revert the route edits; keep the middleware.

### 5A-03 — Plan fingerprint
- **Status:** DONE for the helper (`plan_fingerprint.py`; `test_plan_fingerprint_excludes_res_id`, `test_plan_fingerprint_drift`). "Apply re-plans; mismatch aborts" is enforced in the change-set executor (`changeset/executor.py`, `test_prohibited_op_and_hash_mismatch_write_nothing`). Not proven for one operation per track.
- **depends_on:** 5A-01
- **Pressure:** C2 U2 F3 K3 V2 I3 +0 = 15 → frontier + reviewer (plan-hash binding is a 14+ card)
- **Open delta:** a test per track that edits the database between plan and apply and sees `plan_drift`: T1 (generate apply), T3 (Bridge apply), T4 (dashboard or offline flush), T5B (config apply). DoD 23.
- **Acceptance:** [x] SHA-256 of actionable JSON, `sort_keys`, `res_id` excluded, 16 hex; [ ] one drift test per track.
- **Negative:** a stale plan applies → must fail.

### 5A-04 — Never-allowed, no override
- **Status:** DONE (in the client itself, `rpc_policy.builtin_forbidden`; `test_unlink_destructive_and_forbidden`, `test_apikeys_any_method_forbidden`, `test_config_parameter_key_shape_forbidden`, `test_set_param_args_forbidden`, `test_rt_protected_param_still_forbidden`).
- **Pressure:** 15 → frontier + reviewer (done; re-review only if the file changes)
- **Acceptance:** [x] 5A-4; [ ] the L4 path calls the same check (owned by L4-11).
- **Known open risk (progress log):** READ methods other than on `res.users.apikeys` are auto-allowed, including `read` of `ir.config_parameter`; protected keys are filtered out of `search_read` results. A `read` by id of a protected parameter row needs a test.

### 5A-05 — Hash-chained audit
- **Status:** DONE for the chain (`audit_chain.py`, `AuditChainEntry`, migrations `n4o5…`, `o5p6…`; `test_audit_chain_and_tamper`, `test_genesis_prev_is_zeros`, `test_append_two_rows_verify_db`; the HTTP audit middleware writes `http_mutation` rows in the same transaction). Missing: a verify entry point and the `tenant`, `connection`, `plan_hash`, `schema_fp`, `risk` columns from `../11` §2 if absent.
- **Pressure:** C2 U1 F3 K3 V1 I3 +0 = 13 → Grok high effort; reviewer recommended (audit chain is on the 14+ list)
- **Read first:** `apps/api/app/audit_chain.py` lines 78 and 218 (`verify_chain`, `verify_db`); `apps/api/app/db_models.py` (`AuditChainEntry`).
- **Steps:** (1) add `GET /api/admin/audit/verify` (admin only) returning `{ok, first_broken_index}`; (2) add `python -m app.audit_chain verify` CLI; (3) add the missing columns by migration if they are not in the row model; (4) fail closed: if the append fails, the apply does not proceed (INV-18).
- **Acceptance:** [x] 5A-5 tamper detected; [ ] verify endpoint and CLI; [ ] columns match `../11` §2; [ ] append failure blocks the apply (test with a failing session).
- **Negative:** a non-admin calling verify gets 403 (or 404 under the client-approver policy).

### 5A-06 — Snapshot before DESTRUCTIVE or BILLABLE on production
- **Status:** PARTIAL. `snapshot_gate.py` refuses production `destructive` and `code` routes without `X-Snapshot-Id` naming a `metadata_snapshots` row for the connection. It does not check that the snapshot was taken immediately before, and BILLABLE is not named.
- **depends_on:** 5A-01
- **Pressure:** C2 U1 F3 K2 V1 I2 +0 = 11 → Grok high effort
- **Steps:** (1) add a freshness window: the snapshot's `created_at` is within 10 minutes and newer than the last write audited for that connection; (2) cover BILLABLE classes; (3) on Odoo 20 accept a metadata snapshot (O20-08).
- **Acceptance:** [ ] 5A-6 and DoD 28: a DESTRUCTIVE or BILLABLE production apply refuses without a successful snapshot recorded immediately before.
- **Negative:** a 2-hour-old snapshot id is refused; a snapshot from another connection is refused.

### 5A-07 — Zero MCP writes (code inspection)
- **Status:** DONE, but the test is red today because of the cache bug (BL-07). `mcp_guard.py` refuses writes (`test_mcp_write_is_refused`, `test_trigger_existence_is_not_approval`).
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] DoD 27: `test_no_mcp_write.py` green after BL-07.

### 5A-08 — Production policy
- **Status:** DONE (`policy_allows`, `test_policy_thresholds`).
- **Acceptance:** [x] 5A-8: production apply of anything except READ and an allow-listed REVERSIBLE glob requires approval; [ ] the allow-list glob is configurable per tenant and defaults to empty (verify).

### 5A-09 — Staging policy
- **Status:** DONE (`policy_allows`).
- **Acceptance:** [x] 5A-9: staging auto-approves only READ and REVERSIBLE; DESTRUCTIVE asks.

### 5A-10 — Oracle tests
- **Status:** DONE. Every name exists in `tests/test_rpc_classify.py` or `tests/test_audit_chain.py`: `test_read_is_read`, `test_create_is_reversible`, `test_unlink_destructive_and_forbidden`, `test_security_models_destructive`, `test_billable_depends_on_edition`, `test_protected_params_forbidden`, `test_mass_write`, `test_policy_thresholds`, `test_audit_chain_and_tamper`, `test_redaction`.

### 5A-11 — Rollback tiers wired
- **Status:** OPEN
- **depends_on:** 5A-05, 5A-06
- **Pressure:** C2 U2 F3 K2 V2 I2 +0 = 13 → Grok high effort
- **Rule (copied):** (1) database snapshot restore where `/web/database/*` exists (not Online, not Odoo.sh, not relied on for 20); (2) compensating plan from the audit: created → unlink, updated → write old values; module installs and posted entries are not undone this way; (3) manual, with the changelog.
- **Acceptance:** [ ] a compensating plan is generated from `change` rows and goes through the change-set pipeline (not a raw RPC loop); [ ] module install and posted entries are listed as "not reversible by this tier".
- **Negative:** a compensating plan that would unlink `res.users` is refused by never-allowed.

### 5A-12 — Production budgets (blueprint §5.6)
- **Status:** PARTIAL (agent runtime caps exist: `BudgetExceeded`, `LoopDetected`).
- **Pressure:** 7 → Grok standard
- **Acceptance:** [ ] max 40 LLM steps, max 120 tool calls, blast radius 200 records per apply (L4: 50), change windows, two-person R3, kill switch, each with a test or a pointer to the card that owns it.
