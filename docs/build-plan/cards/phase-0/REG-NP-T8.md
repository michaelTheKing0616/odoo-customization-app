# REG-NP-T8: model.create; model.scaffold; field.create; field.update; fie

ID: REG-NP-T8
Title: model.create; model.scaffold; field.create; field.update; fie
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-T8-OP-SCHEMA;NP-T8-OP-UI;NP-T8-OP-LOGIC;NP-T8-OP-SET;NP-T8-SIM;NP-T8-META;NP-T8-CLI
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F1 K1 V1 I1)
Context pack:
- `sed -n '118,129p' docs/plans/next-phase/cards/T8_ENGINE_CORE.md`
- `sed -n '157,161p' docs/plans/next-phase/cards/T8_ENGINE_CORE.md`
- `sed -n '183,197p' docs/plans/next-phase/cards/T8_ENGINE_CORE.md`
- `sed -n '25,80p' apps/api/app/changeset/ops.py`
- `sed -n '104,130p' apps/api/app/changeset/ops.py`
- `sed -n '1,8p' apps/api/app/changeset/cli.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_t8.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-T8` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: model.create; model.scaffold; field.create; field.update; fie (pressure 12) (source: ledger NP-T8-OP-SCHEMA, next-phase cards/T8_ENGINE_CORE.md)
- AC2: view.inherit.create; view.inherit.update; view.archive; view.cr (pressure 10) (source: ledger NP-T8-OP-UI, next-phase cards/T8_ENGINE_CORE.md)
- AC3: server_action.create/update; automation.create/update/disable; cr (pressure 12) (source: ledger NP-T8-OP-LOGIC, next-phase cards/T8_ENGINE_CORE.md)
- AC4: setting.set; config_param.set; company.update; module.install; (pressure 14) (source: ledger NP-T8-OP-SET, next-phase cards/T8_ENGINE_CORE.md)
- AC5: Simulation (pressure 12) (source: ledger NP-T8-SIM, next-phase cards/T8_ENGINE_CORE.md)
- AC6: MetaSnapshot (pressure 10) (source: ledger NP-T8-META, next-phase cards/T8_ENGINE_CORE.md)
- AC7: LLM-free CLI end to end (GATE-P3-09) (pressure 9) (source: ledger NP-T8-CLI, next-phase cards/T8_ENGINE_CORE.md)
Worked examples (`all_handlers()` keys equal `OP_CATALOG`):
- Pin AC1: `OP_CATALOG["field.create"]` is risk `R2`, reversible `E`, `ddl` True. `OP_CATALOG["model.scaffold"]` is the same. `apply_memory` of `field.create` `sale.order` / `x_po_reference` fills the store; `compensate_memory` of that op leaves the store empty. `op_base_risk("field.create", {"compute": "_compute_x"})` is `R3`. `op_base_risk("field.delete", nonempty sensitive params)` is `R4`; otherwise the catalog base `R3`. `field_update_issues` appends `TYPE_CHANGE_UNSUPPORTED` (`"field type change is unsupported"`) when a proposed type differs from the current type. `constraint.sql` on a non-`x_` model returns `CONSTRAINT_X_MODELS_ONLY`. Cascade params return `CASCADE_FORBIDDEN`.
- Pin AC2: `handler_for("view.inherit.create").issues({"model": "sale.order"})` is non-empty. `issues` with `expect_matches: 2` is non-empty. `issues({"model": "sale.order", "xpath": "//field[@name='partner_id']"})` is `[]`. Report ops in the catalog are risk `R2`.
- Pin AC3: `logic_base_raise` returns `R3` for a server action whose channel is code, email, SMS, or webhook, and for an outbound or mass automation. A sensitive sequence returns `R4`. Cron stays on catalog base `R3`. `safe_eval_ast_issues` does not execute the snippet.
- Pin AC4: `setting_base_raise("setting.set", module_* key)` is `R3`. `config_param.set` on a protected key is `R4`. `company.update` with `lock_date` is `R4`. `module.install` catalog risk is `R3`, reversible `S`, and `inverse` is None. `module.uninstall` is `R4`, reversible `N`, `inverse` is None, and `compensate_memory` raises `PermissionError`.

| Op | Params | Result |
|---|---|---|
| `field.create` | no compute | `R2` |
| `field.create` or `field.update` | `compute` is a non-blank string | `R3` |
| `field.update` | proposed type differs from current type | issue `"field type change is unsupported"` |
| `field.delete` | sensitive model and `record_count > 0` | `R4` |
| `field.delete` | otherwise | `R3` |
| `constraint.sql` | model does not start with `x_` | issue, not a lower risk |
| `server_action.*` | code, email, SMS, or webhook | `R3` |
| `automation.*` | outbound or mass | `R3` |
| `setting.set` | key is `module_*` | `R3` |
| `config_param.set` | protected key | `R4` |
| `company.update` | `lock_date` | `R4` |
| `module.uninstall` | any | `R4`, no inverse |
- Pin AC5: `guard_production_apply(menu, environment="production")` with no recorded simulation raises `SimulationRequired` with `code == "simulation_required"`, and `apply(..., mode="T", environment="production")` writes an empty journal. After `simulate` passes for that plan hash, `guard_production_apply` on production returns None. Staging does not require the record. `policy_allows_r1_direct("R1", direct_matrix)` is True. The same helper is False for `R2` and `R3`.

| Environment | Recorded simulation for this hash | Result |
|---|---|---|
| staging | none | `guard_production_apply` returns |
| production | none, and not R1-direct | `SimulationRequired` |
| production | passed, same hash | returns |
| production | passed, different hash | `SimulationRequired` |
- Pin AC6: `equal(payload, reversed_payload)` is True. `MetaSnapshot.build` of those two compare equal. List order does not matter. A renamed field does not compare equal.
- Pin AC7: `python -m app.changeset.cli plan|validate|simulate|apply|rollback tests/fixtures/changeset_cli_two_ops.json` runs the two ops (`field.create` `x_customer_ref`, then `view.inherit.create`) on `FakePort` with no import of `app.llm_gateway`, `google`, `anthropic`, `openai`, or `litellm`. Apply reports `status == "VERIFIED"` and `port_calls == 2`. A bad file exits 1, one stderr line starting `error: `, no `Traceback`.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_t8.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_t8.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: AI proposes, code authorises (INV-13): no model output reaches `execute_kw`, an install or an export without a deterministic validator. Calls go only through `app/ai_client` with untrusted text in `fence_fields` (source=...). Any call that names Odoo structure first reads the live schema packet (`live_schema_context.build_schema_packet`) and the engine rejects names not in it. Caches never store secrets or PII and never serve write plans.
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_reg_np_t8.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
