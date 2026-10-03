# Cards — T8 engine core (P0–P4): ADRs, gateway, Odoo layer, ops, engine, runtime

Self-contained. Normative lists: `../T8_BOT_ENGINE.md` (op catalog lines 125–226, validation/executor 228–245, runtime 247–273, gateway 39–101, Odoo layer 103–123). T5A is the shared core; P3 extends it and never forks it.

> **In flux, 2026-10-02 22:50.** Another session was editing `apps/api/app/changeset/*` (`executor.py`, `policy.py`, `validate.py`, `protected_registry.py`, `protected_core.yaml`, `recovery.py`, `plan_card.py`, `handlers.py`) and `apps/api/app/agent_runtime/runtime.py` while this file was written. Statuses below are a snapshot. Run BL-01 and the card's test command before trusting a status.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests (scripted adapter `llm_gateway/scripted.py` and cassettes only); stay inside "Change". **T8 core-specific (P0 rules, copied):** `[VERIFY]` facts are re-tested into `docs/verified-facts.md`; non-trivial decisions become ADRs; if a change would weaken an invariant, stop and write `docs/open-questions.md`; no provider code outside `llm_gateway/adapters/<provider>/`; no Odoo-version code outside `packages/odoo-client/src/odoo_client/compat/`; no hard-coded model id, price, or context size outside the model registry; fail closed; the engine is deterministic and the agent may repair only inside the caps; `apps/api/app/changeset` imports zero LLM modules (`test_gateway_package_does_not_import_odoo_or_changeset` covers the reverse); there is no apply tool for the model; no `rpc.write`, no `sql` op.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_changeset_engine.py tests/test_handlers_grants_skills.py tests/test_executor_bridge.py \
  tests/test_plan_card_recovery.py tests/test_plan_card_store.py tests/test_dispatch_and_shopify.py \
  tests/test_protected_registry.py tests/test_red_team_engine.py tests/test_agent_runtime.py \
  tests/test_llm_gateway.py tests/test_llm_gateway_adapters.py tests/test_llm_gateway_phase1.py
uv run --directory packages/odoo-client pytest -q tests/test_schema_graph.py tests/test_read_plane.py tests/test_json2_transport.py
# Import-boundary check (GATE-P0-05 / P1-07), until a lint rule exists:
rg -n "^from app\.(llm_gateway|agent_runtime)|^import app\.(llm_gateway|agent_runtime)" apps/api/app/changeset && echo FAIL || echo ok
```

**Audit and trace events:** trace `phase_changed`, `tool_called`, `evidence_added`, `validation_failed`, `approval_requested`, `apply_started`, `apply_op_done`, `apply_failed`, `verification_result`, `rollback_started`, `rollback_finished`. Chain kinds `tool_call`, `llm_turn` (scrubbed), `approval`, `apply`, `rollback`, `error`.

---

## P0 — ADR cards

Template (all 14): **Status** stub exists in `docs/adr/ADR-NN.md` (BL-05). **Change:** that file only. **Steps:** (1) context in three sentences; (2) options considered (at least two); (3) decision; (4) consequences, including what becomes harder; (5) status `accepted` or `open` with the blocking question. **Acceptance:** [ ] decision, consequences, and status present; [ ] GATE-P0-02 for the phases in flight. **Negative:** an ADR that contradicts `../01` is rejected by the judge. **Rollback:** revert the file. **Evidence:** the file and a progress-log line.

| Card | Decision to record | Pressure | Route | Blocks |
|---|---|---|---|---|
| ADR-01 | Stack and repo layout. Default: this repo (`apps/api`, `apps/web`, `packages/odoo-client`) | 4 | cheap | P1 |
| ADR-02 | LLM gateway: thin in-house vs LiteLLM. **Stays open until Tope accepts (D8).** Record the in-house code that already exists under `llm_gateway/` as evidence, not as the decision | 12 | Grok high | T4-LLM3 |
| ADR-03 | Canonical message and tool schema (`llm_gateway/types.py`) | 6 | Grok std | P1 |
| ADR-04 | Tool-call emulation ladder: native → `emulated_json` → `emulated_text`; emulated capped at Tier B | 6 | Grok std | P1 |
| ADR-05 | Union tools vs family tools, decided by an eval (GATE-P6-04) | 6 | Grok std | P6 |
| ADR-06 | Executor Mode T vs Mode C | 12 | Grok high | P3 |
| ADR-07 | Staging and clone provider (OQ-STAGING) | 6 | Grok std | P3 |
| ADR-08 | Who approves, two-person rule, expiry (`../02` is the proposal) | 12 | Grok high | P5 |
| ADR-09 | Memory model and injection-safe persistence | 6 | Grok std | P4 |
| ADR-10 | Skill package format and router | 6 | Grok std | P4 |
| ADR-11 | Audit hash chain (`../11` §2 is the proposal; `audit_chain.py` is the implementation) | 12 | Grok high | P3 |
| ADR-12 | Secrets, KMS, BYO keys (Fernet until a KMS is chosen) | 6 | Grok std | P1 |
| ADR-13 | Eval harness and tier thresholds | 6 | Grok std | P6 |
| ADR-14 | Supported versions: D11, 17–20 GA, 16 experimental, ≤15 refused | 4 | cheap | — |

### T8-P0-FIX — Fixtures and db reset (GATE-P0-03)
- **Status:** PARTIAL (compose files for 16–20 exist; no seeds named `messy_client`, `accounting_locked`, etc.).
- **Pressure:** C2 U1 F1 K1 V1 I0 +0 = 6 → Grok standard
- **Acceptance:** [ ] fixtures up on 17, 18, 19, 20; [ ] db reset under 60 s; [ ] seeds `demo`, `minimal`, `messy_client` (150+ custom fields), `accounting_locked`, `inventory_live`, `hr_sensitive`, `huge` (nightly only), `portal_public`.
- **Do not:** point a fixture at a customer database.

### T8-P0-LINT — Import-boundary lint (GATE-P0-05, GATE-P1-07)
- **Status:** OPEN (one direction tested).
- **Pressure:** 5 → cheap
- **Acceptance:** [ ] a test fails if `changeset` imports `llm_gateway` or `agent_runtime`; [ ] a test fails if provider SDK code appears outside `llm_gateway/adapters/`; [ ] a test fails if Odoo-version branches appear outside `compat/`.

## P1 — LLM gateway

### T8-GW-TYPES — Canonical types
- **Status:** SEEDED (`llm_gateway/types.py`; `test_canonical_validator_rejects_extra_fields`).
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] tool name `[a-z][a-z0-9_]{2,40}`; [ ] description ≤ 1024 chars; [ ] tests for both limits.

### T8-GW-NORM — Normalization rules 1–10
- **Status:** SEEDED (`normalize.py`; NaN, duplicate keys, depth, synthesized ids tested).
- **Pressure:** 10 → Grok high effort
- **Rules (copied):** (1) synthesize missing ids `call_<ulid>`; (2) args are an object plus the raw string, reject duplicate keys, NaN, depth > 12, size > 256 KB, never eval; (3) parallel reads may run together, write-class tools sequential; (4) repair roles; (5) place the system prompt as the provider requires; (6) map stop reasons; (7) record usage; (8) reasoning is opaque and same-provider only, dropped on a provider switch; (9) Unicode NFC; (10) images only when the model capability says so. OpenAI Responses stateless; no Gemini built-in tools mixed with functions in v1; `idle_timeout_ms` 30 s; AbortSignal honored; `stream_tools:false` fallback.
- **Acceptance:** [ ] one test per rule (rules 3, 4, 6, 7, 8, 9 are the likely gaps).

### T8-GW-C — Conformance C01–C20 with cassettes (GATE-P1-02)
- **Status:** SEEDED (`conformance.py`; `test_conformance_suite_passes_every_gate_case` against scripted adapters).
- **Pressure:** C3 U2 F2 K2 V2 I1 +0 = 12 → Grok high effort
- **Acceptance:** [ ] C01–C20 (table in `../T8_BOT_ENGINE.md` lines 68–91) per provider family on recorded cassettes; blocking cases block; C11, C18, C19 scored; [ ] cassette recording is a manual operator step, replay in CI.
- **Do not:** call a live provider in CI.

### T8-GW-REG — Model registry
- **Status:** SEEDED (`registry.py`; `test_registry_rejects_an_invented_tier_and_a_missing_id`).
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] `rg` test: no model id string outside the registry file; [ ] unknown model id → conservative caps, no tier until probe and eval.

### T8-GW-REST — Remaining P1 gates
- **Status:** SEEDED (lowerers, stream equality on small sets, retries, SSRF, scrub tested).
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] GATE-P1-01 provider map verified (in `docs/verified-facts.md`); [ ] GATE-P1-03 lowerer goldens; [ ] GATE-P1-04 streaming equals non-stream on 200 cassette calls; [ ] GATE-P1-05 error, retry (max 4, arg repair max 2), budget (`max_calls_per_run` 40); [ ] GATE-P1-06 emulated path ≥ 95% on 200 calls; [ ] GATE-P1-08 encryption, SSRF, scrubber.

## P2 — Odoo layer

### T8-OD-TRANSPORT — Transport contracts (GATE-P2-01, P2-05, P2-06)
- **Status:** SEEDED (`packages/odoo-client` transports, `rpc_policy.py`, `read_plane.py`).
- **Pressure:** 10 → Grok high effort
- **Acceptance:** [ ] ≤ 2 concurrent calls per database (test with a slow fake); [ ] read 30 s / write 120 s timeouts; [ ] TLS required, `verify=false` refused, no write-plane redirects; [ ] only idempotent reads retry; a write retries at most twice only when marked `retry_safe` and the error is deadlock or concurrency; [ ] error mapping to AccessError, UserError, ValidationError, MissingError, RedirectWarning, ConcurrencyError, DeadlockDetected, Timeout, AuthFailed, ApiUnavailable, ServerError, Unknown; [ ] method allowlist rejects unknown methods.

### T8-OD-ENV — EnvProfile (GATE-P2-02)
- **Status:** SEEDED (`packages/odoo-client/src/odoo_client/env_profile.py`).
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] fields: version, major, edition, deployment, api, bridge posture P1/P2, installed apps, studio flag, multi-company, languages, capabilities (`yes`/`no`/`unknown`; unknown means no), staging flag, fingerprint; [ ] API unavailable → Guided Mode only; [ ] health ok / degraded / auth_failed / api_unavailable / version_unsupported; unsupported major is read-only Q&A; ≤15 refused.

### T8-OD-GRAPH — SchemaGraph (GATE-P2-03, P2-04, P2-07)
- **Status:** SEEDED (`schema_graph.py`, `schema_fingerprint.py`, `tests/test_schema_graph.py`).
- **Pressure:** 11 → Grok high effort
- **Acceptance:** [ ] builds on `messy_client`; [ ] row cap 200 per tool, sample ≤ 5; [ ] `find_usages` precision ≥ 0.98, recall ≥ 0.95 on a labeled set; [ ] fingerprint stable across two reads of an unchanged database.

### T8-OD-BRIDGE — Bridge addon (GATE-P2-08, P2-09) — 14+ card
- **Status:** SEEDED (`tests/test_bridge_protocol.py`, `tests/test_executor_bridge.py`).
- **Pressure:** C3 U2 F3 K3 V2 I2 +0 = 15 → frontier + reviewer
- **Acceptance:** [ ] seven methods: `ping`, `introspect`, `combined_view`, `effective_access`, `render_check` (rolled-back savepoint), `apply_changeset` (validate / dry_run / apply, one transaction), `rollback_changeset`; [ ] DDL never dry-runs in place on production; [ ] kill switch `ingenium.bridge.enabled`; [ ] unknown ops fail closed; [ ] no outbound telemetry (INV-19); [ ] staging neutralization mandatory; promotion replays a change-set and never copies a database; no staging → non-DDL Bridge dry-run plus a stricter gate, or review-only above R1.
- **Negative:** RT-36 direct Bridge JSON with a stolen key refused.

### T8-OD-DRIFT — Version drift checklist (each row a test on 17, 18, 19, 20)
- **Status:** PARTIAL (O20 table covers some).
- **Pressure:** 9 → Grok standard
- **Rows (copied):** view modifiers; `tree` vs `list`; kanban; chatter; `get_view`; `read_group` vs `formatted_read_group`; `name_get`; translations; company-dependent fields; `groups_id` vs `group_ids`; selection storage; automation split from server actions; server action states; cron `numbercall` removed in 18+; mail template syntax; accounting and stock renames; external API shape; Odoo 20 `ir.access`.
- **Acceptance:** [ ] one fake test per row per major; live in nightly.

## P3 — ops and engine

### Op handler cards (one per family)

Template: **Read first** `changeset/ops.py`, `changeset/handlers.py`, `changeset/dispatch.py`, the family table in `../T8_BOT_ENGINE.md`. **Each op needs:** type, params schema, riskBase, reversible (E/S/N), DDL flag, `simulate_in_place`, preconditions, `riskAdjust`, plan, apply, inverse, postconditions. **Acceptance:** [ ] every op in the family has all twelve parts; [ ] engine suite 1 (op conformance) and suite 2 (apply → verify → inverse → MetaSnapshot equality) pass for the family; [ ] xmlids `ingenium.<stable_key>`, `noupdate=True`, `x_` prefix, never `x_studio_*`, 63-byte limit; never modify a base view when an inherit exists; never overwrite Studio without an explicit adopt. **Status (all):** SEEDED: 62 ops registered (`len(OP_CATALOG)`, matches the six family tables), a handler exists for every op (`test_every_catalog_op_has_a_handler`), memory round-trip tested for `field.create`. Live `OdooPort` dispatch exists for a subset (`test_field_create_writes_ir_model_fields`).

| Card | Family and ops | Risk rules to test | Pressure | Route |
|---|---|---|---|---|
| T8-OP-SCHEMA | `model.create`, `model.scaffold`, `field.create`, `field.update`, `field.deprecate`, `field.delete`, `selection.update`, `constraint.sql` | cascade forbidden by default; compute → R3; type change unsupported; `field.delete` R4 if non-empty financial, HR, or stock; `constraint.sql` on `x_` models only; scaffold into protected = RT-10 | 12 | Grok high |
| T8-OP-UI | `view.inherit.create`, `view.inherit.update`, `view.archive`, `view.create_base`, `action.window.create`, `action.window.update`, `menu.create`, `menu.update`, `menu.archive`, `filter.create`, `filter.update`, `report.inherit`, `report.action.create`, `report.action.update` | R1 except reports R2; exactly one anchor per inherit (`test_view_inherit_requires_exactly_one_anchor`); XPath that replaces root or a large subtree refused (RT-22) | 10 | Grok high |
| T8-OP-LOGIC | `server_action.create/update`, `automation.create/update/disable`, `cron.create/update/disable`, `sequence.create/update`, `mail_template.create/update`, `activity_type.create/update`, `stage.upsert/reorder/archive`, `config_record.upsert` | code, email, SMS, webhook → R3; outbound or mass automation → R3; cron R3; accounting/journal/legal sequence R4; `safe_eval` AST rejects RT-25 patterns | 12 | Grok high |
| T8-OP-SEC | `group.create`, `access.create/update`, `rule.create/update`, `field.groups.set`, `user.groups.assign`, `user.create`, `user.archive` (`user.unlink` is never-allowed and not in the catalog) | group never implies admin; group-less ACL is R4 (`test_groupless_access_is_rejected_before_create`); admin/system/service assignment R4; on Odoo 20 `rule.*` compiles to `ir.access` (O20-04) | 15 | frontier + reviewer |
| T8-OP-SET | `setting.set`, `config_param.set`, `company.update`, `module.install`, `module.upgrade`, `module.uninstall` | `module_*` R3 and may be BILLABLE; protected keys forbidden; lock dates, fiscal year, currency, chart R4; install S-reversible only via uninstall (R4) so warn; uninstall R4, prohibited in v1 | 14 | frontier |
| T8-OP-DATA | `data.create_batch`, `data.update_batch`, `data.archive_batch`, `data.import_upsert`, `data.merge`, `data.delete`, `translation.upsert` | sample ≤ 20, cap 1000, batches of 200; merge R3 N-reversible; delete R4, two-person plus allow-list, default deny; `stock.quant` refused (EV-DATA-07) | 13 | Grok high |

### T8-PROT — Protected registry (14+ card)
- **Status:** SEEDED, actively edited (`protected_registry.py`, `protected_core.yaml`, `tests/test_protected_registry.py`). Covers RT-10 to RT-16 detection paths: scaffold expansion, `$ref`, batch domains, setting side-effects, stored compute, code tricks, sequence aliases; Unicode confusables folded.
- **Pressure:** C3 U2 F3 K3 V2 I3 +0 = 16 → frontier + reviewer
- **Classes (copied):** accounting, inventory, HR and payroll, security and identity, communications, platform. `protected:deny` = R4. `protected:elevate` = risk +1 and a domain-owner approver. Core targets cannot be removed; tenants may only add.
- **Acceptance:** [ ] GATE-P3-05: RT-10–RT-16 at 100%; [ ] a tenant config with `remove_models` has no effect (test exists in intent: `deny_models` ignores it); [ ] reviewer answers "what could be wrong?" in the progress log.
- **Negative:** each RT-10…16 case has a named test that asserts `protected_deny` and a detection record with `alert: policy_denied`.

### T8-RISK — Risk escalation only goes up
- **Status:** SEEDED (`policy.risk_of`; `test_risk_never_decreases`).
- **Pressure:** 10 → Grok high effort
- **Escalations (copied from `../02`):** +1 when the target is protected-elevate, rows > 1000 or users > 10, outbound, no simulation on production, or Mode C.
- **Acceptance:** [ ] one test per escalation; [ ] a property test: for any op and any combination, final risk ≥ base risk; [ ] caller-supplied risk never lowers the catalog risk (`test_caller_risk_does_not_override_the_catalog`).

### T8-POLICY — Policy matrix (17+ card)
- **Status:** SEEDED (`policy.policy_decision`, `self_approval_allowed`).
- **Pressure:** C2 U2 F3 K3 V3 I3 +1 = 17 → frontier + independent reviewer
- **Matrix (copied from `../02`):** staging R1 one approval or none at L3+, R2 and R3 one; production R1 and R2 one plus passed simulation, R3 two approvers plus domain owner if protected plus passed simulation plus backup plus allowed window, requester cannot approve own R3; R4 denied everywhere; expiry production 24 h, staging 7 d; freeze blocks every apply.
- **Acceptance:** [ ] a table-driven test covers all 10 cells plus freeze and expiry; [ ] GATE-P3-06 / suite 8: mutation score ≥ 80% (`mutmut` or `cosmic-ray` on `policy.py`; record the tool and score).
- **Negative:** mutants that flip `>=` to `>` on approver counts are killed.

### T8-VALID — Validation stages 1–9
- **Status:** SEEDED (`validate.py`, "Nine-stage change-set validation"; `test_unknown_op_rejected`, `test_51st_op_rejected`, `test_missing_model_suggests_at_most_three`).
- **Pressure:** 12 → Grok high effort
- **Stages (copied):** shape; static safety; grounding; dependency order; preconditions; impact (rows touched, users affected); risk and policy; lints; report. Max 50 ops per change-set; work packages of about 15; `did_you_mean` ≤ 3; repair max 4 rounds then stop and explain.
- **Acceptance:** [ ] every stage always runs (report lists 9 entries even when an early stage fails); [ ] suite 10 validator fuzz (oversized, deep, polluted payloads: RT-26, RT-27, RT-33).

### T8-SIM — Simulation
- **Status:** OPEN
- **Pressure:** 12 → Grok high effort
- **Modes (copied):** static always; Bridge in-place dry-run for non-DDL; staging for DDL and R ≥ 3; synthetic record tests.
- **Acceptance:** [ ] each mode has a test; [ ] a failed simulation returns the plan to planning; [ ] production apply without a recorded simulation is refused unless policy allows R1 direct (INV-06).

### T8-EXEC — Executor Mode T / Mode C with WAL and recovery (14+ card)
- **Status:** SEEDED, actively edited (`executor.py`; `test_mode_t_failure_rolls_back_fully`, `test_mode_c_compensates_in_reverse`, `test_second_apply_is_idempotent`, `test_crash_matrix_never_reports_a_partial_apply_as_verified`). Journal is an in-process list (`_JOURNAL`, `_RESULTS_BY_FINGERPRINT`) — not durable.
- **depends_on:** T8-POLICY, T8-VALID, 5A-05
- **Pressure:** C3 U3 F3 K3 V3 I3 +0 = 18 → frontier + independent reviewer
- **Apply steps (copied):** lock → reverify approval and hash → fingerprint → decrypt write creds → backup evidence → WAL → heartbeat 5 s → fail and compensate → verify → release. WAL kinds INTENT, BEFORE, RESULT, COMPENSATE, ERROR. Before-image retention 30 days, 90 for R3. Mode T: one transaction, dry-run for non-DDL, native rollback then inverse, default 50 ops. Mode C: per-op, no dry-run, compensate in reverse, only E or S reversible and idempotent ops, default 15 ops, risk +1.
- **Steps:** (1) move the journal to tables `journal_entry` and `before_image` (migration); (2) DB-level lock per Odoo database (`lock` table or advisory lock); (3) recovery job finds an APPLYING run with a stale heartbeat within 2 minutes and resumes or compensates from the journal; (4) never retry a write blindly; unknown outcome → read back, else NEEDS_HUMAN.
- **Acceptance:** [ ] GATE-P3-03 / suite 11: crash at each WAL boundary → zero silent partial applies; [ ] suite 12 unknown-outcome writes; [ ] suite 13 one apply per database; [ ] SLO stale APPLYING detected < 2 min.
- **Negative:** kill the process after INTENT and before RESULT; recovery compensates and the run is not reported as verified.

### T8-VERIFY — Verification (INV-16)
- **Status:** SEEDED (`test_runtime_does_not_treat_an_unverified_apply_as_done`).
- **Pressure:** 12 → Grok high effort
- **Checks (copied):** per-op postconditions; fingerprint diff; view render as requester, low-privilege, and portal; smoke probes; access regression; no new outbound mail; data counts and samples.
- **Acceptance:** [ ] each check has a test; [ ] a failed check rolls back automatically for R2+, otherwise NEEDS_HUMAN with a runbook link; [ ] the model cannot mark a failure as success.

### T8-ROLLBACK — Undo as a change-set
- **Status:** SEEDED (`compensate_memory`).
- **Pressure:** 14 → frontier
- **Acceptance:** [ ] undo goes through the same pipeline (validate, policy, approval); [ ] MetaSnapshot comparison after undo; mismatch → NEEDS_HUMAN; [ ] soft inverse: when data exists in a new field, undo hides the field and reports remaining data; deleting the data is a separate higher-risk approval.

### T8-META — MetaSnapshot
- **Status:** OPEN (distinct from `metadata_snapshots`, which T8-META should reuse if the shape fits).
- **Pressure:** 10 → Grok high effort
- **Exports (copied):** models, fields, views, actions, menus, ACL, rules, groups, automations, crons, templates, sequences, config params on the allowlist, filters, ingenium xmlids.
- **Acceptance:** [ ] equality comparison is order-independent; [ ] suite 2 round-trip uses it.

### T8-CARD — Plan card goldens (GATE-P3-10)
- **Status:** SEEDED (`plan_card.py`; nine sections for every op).
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] snapshot files for at least one op per family; [ ] changing an assumption changes the hash.

### T8-CLI — LLM-free CLI end to end (GATE-P3-09)
- **Status:** OPEN
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] `python -m app.changeset.cli plan|validate|simulate|apply|rollback <file.json>` runs a two-op change-set against a fake port with no LLM import.

### T8-P3-COV — Engine coverage (GATE-P3-08)
- **Status:** OPEN
- **Pressure:** 5 → cheap
- **Acceptance:** [ ] `pytest --cov=app/changeset --cov-branch` ≥ 90% line, ≥ 80% branch; CI floor added; do not lower the existing trust-mutation floors.

## P4 — agent runtime

### T8-RUN — Phase machine and loop guards (GATE-P4-01, P4-02, P4-03, P4-08)
- **Status:** SEEDED, actively edited (`agent_runtime/phases.py`, `runtime.py`, `tools.py`; `test_no_phase_exposes_an_apply_tool`, `test_model_cannot_skip_to_execute`, `test_repeat_detector_aborts_on_the_fourth_identical_call`).
- **Pressure:** 11 → Grok high effort
- **Phases (copied):** INTAKE → DISCOVER → CLARIFY? → PLAN → VALIDATE/REPAIR → CRITIC → SIMULATE → PRESENT → human → EXECUTE (engine, no LLM) → VERIFY → REPORT.
- **Guards (copied):** max 40 LLM calls; max 8 tool calls per step; 10 minutes active wall clock; same tool + same args 3 times = LOOP_DETECTED, a second time aborts; repair max 4; about 20 tools visible; one apply per database, many plans may exist.
- **Open delta:** the source says "3 times is LOOP_DETECTED; a second time aborts". The test name says "aborts on the fourth identical call". Confirm the implemented count matches the source and write the reading in the progress log.
- **Acceptance:** [ ] scripted end-to-end through every phase; [ ] no apply tool exists in any phase; [ ] resumable after a restart (GATE-P4-08).

### T8-TOOLS — Tool surface
- **Status:** SEEDED (`tools.py`).
- **Pressure:** 8 → Grok standard
- **Inspection tools R0 (copied):** `env_info`, `schema_search`, `describe_model`, `describe_field`, `view_get`, `view_test_xpath`, `menu_action_find`, `group_describe`, `access_explain`, `data_count`, `data_sample` (≤ 5), `data_aggregate`, `domain_validate`, `find_usages`, `automation_list`, `action_list`, `cron_list`, `template_list`, `sequence_list`, `report_list`, `settings_describe`, `module_list`, `config_registry_describe`, `search_docs`, `skill_search`, `skill_load`, `skill_read`, `ask_user` (≤ 3 questions), `memory_propose`. Planning: `changeset_create`, `changeset_add_op`, `changeset_update_op`, `changeset_remove_op`, `changeset_reorder`, `describe_op`, `validate`, `simulate`, `render`, `submit_changeset`. After submit (read-only): `changeset_status`, `verification_report_get`, `propose_rollback`.
- **Acceptance:** [ ] the registered tool names equal this list exactly (set equality test); untrusted data appears only inside tool results (`wrap_untrusted`).

### T8-PROMPT — Prompt layers and context budgets (GATE-P4-07)
- **Status:** OPEN
- **Pressure:** 10 → Grok high effort
- **Layers (copied):** core, overlay ≤ 10%, tools, skills, tenant memory, state card, conversation, untrusted data only inside tool results; static prefix about 12k tokens; no runtime-editable prompts in production. **Budgets:** system+tools ≤ 15%, skills ≤ 15%, memory ≤ 5%, history ≤ 40%, tool results ≤ 25%; compact at about 60% of the window; never exceed 90%; explorer sub-runs Tier A only.
- **Acceptance:** [ ] 30-turn compaction test keeps tool-call pairs; [ ] no secret or PII in a cached prefix (scrub test).

### T8-CLARIFY — Clarification rules
- **Status:** OPEN
- **Pressure:** 8 → Grok standard
- **Rules (copied):** ask when two or more targets match, there is no safe default, an R ≥ 3 request is underspecified, sources conflict, or the topic is financial, HR, or legal. R0–R1 may proceed with stated assumptions. Never ask what introspection already answered.
- **Acceptance:** [ ] EV-AMB-01–08 pass on the scripted adapter.

### T8-CRITIC — Critic (cannot waive policy)
- **Status:** OPEN
- **Pressure:** 9 → Grok standard
- **Checklist (copied):** coverage, scope creep, assumptions that should be questions, missed dependents, rollback realism, security, business red flags, wording. Runs for Tier A when risk ≥ R2 or ops ≥ 5.
- **Acceptance:** [ ] a critic "approve" on an R4 plan has no effect on policy.

### T8-MEM — Memory (ADR-09)
- **Status:** OPEN
- **Pressure:** 10 → Grok high effort
- **Model (copied):** working (engine, trusted); tenant or database (human-confirmed); global knowledge (PR plus eval); episodic (never auto-injected).
- **Acceptance:** [ ] `memory_propose` creates a pending item that a human confirms; [ ] RT-47 (memory poisoning through role notes) refused.

### T8-P4-TIERA — Tier A on 60 scenarios (GATE-P4-04) and RT-01–09 (GATE-P4-05)
- **Status:** OPEN (needs a live model; nightly only, never PR).
- **Pressure:** 12 → Grok high effort
- **Acceptance:** [ ] Tier A ≥ 80% on 60 scenarios; [ ] RT-01–09 blocked.
