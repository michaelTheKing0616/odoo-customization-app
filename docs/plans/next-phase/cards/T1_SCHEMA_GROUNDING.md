# Cards — T1 schema grounding

Self-contained. Gate text is copied from `../T1_SCHEMA_GROUNDING.md`. Card format and routing: `../14_WORK_CARDS.md`.

**Shared do-not:** do not weaken a lock in `../01`; do not log secrets; no customer database; no Studio source; `:8001` does not reload (restart it and say so); never delete or loosen a test; no live LLM in a PR-blocking test; stay inside "Change". **T1-specific do-not (every card below):** no new `if display_name == "…"` or brief-name branch (repo lock: a new failure adds a property, not a denylist entry); no T5 automatic scrub growth; no T12 blocklist growth; no "class fix" verified on one brief without the sibling golden; at most 3 repair rounds.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/<file>.py
# Trace dump for one brief (writes .cache/ai_ir_trace/)
AI_IR_TRACE=1 bash apps/api/scripts/dump_maintenance_ir_trace.sh
# Sandbox install with tests (Odoo 19 default; pass 16|17|18|19)
./docker/run-sandbox-major-gate.sh 19
```

**Invariants every T1 card protects:** (1) Closure: every field, many2one, one2many, and menu traces to a cue or to `approved_craft`. (2) One source of truth for one2many and menu counts, computed once from `GenerateIR` after `build_ir`. Downstream never adds an uncued node. (3) The harness and the Studio Generate button use the same entrypoint, and the test asserts the final XML.

**Verdicts T1–T12 (do not relitigate):** T1 keep · T2 diagnosis only · T3 not a completion signal · T4 structurally unsound · T5 harmful if automatic, stop · T6 package presence is not a cue · T7 keep, fires on under 5% of thin briefs · T8 miscalibrated goldens · T9 keep the ops loop · T10 over-relied UX · T11 not the bottleneck · T12 harmful, stop blocklist growth.

**Known defects the goldens must still catch:** L1 meta wrong golden stage · L2 many2one spray · L3 Rate Line one2many · L4 install grammar victim · L5 sibling menus · L6 Date versus Datetime.

**Audit events for T1 cards:** none in the product chain unless the card says so. Generate runs already write `audit_logs` through the HTTP middleware.

---

### T1-PF — Pre-flight PF-1 to PF-6
- **Status:** PARTIAL. PF-1 yes (`ai_generate_ir.py`). PF-4 yes (`ai_schema_client.py` has `LiveSchemaClient`). PF-5 has tests (`tests/test_sandbox_test_enable.py`, 6). PF-3 and PF-6 not written up.
- **depends_on:** BL-01
- **Pressure:** C1 U1 F1 K1 V1 I0 +0 = 5 → cheap
- **Read first:** `../T1_SCHEMA_GROUNDING.md` lines 11–21; `apps/api/app/ai_generate_ir.py` (search `build_ir`, `admit_and_apply`).
- **Change:** progress log only.
- **Steps:** answer each row with a path or a command result:
  1. PF-1 `GenerateIR` / `build_ir` landed? `rg -n "def build_ir|class GenerateIR" apps/api/app/ai_generate_ir.py`.
  2. PF-2 any PR-A→F work landed? List it from the cards below whose status is SEEDED. Do not rebuild it.
  3. PF-3 `AI_IR_TRACE` on Maintenance: run the trace script; write whether the scrub-key hypothesis is confirmed or refuted, and quote the pass where nodes appear.
  4. PF-4 live RPC for schema, or only static structures? Name the factory in `ai_schema_client.py` that chooses.
  5. PF-5 can the box mirror run `-i <module> --test-enable` non-interactively with parseable errors? Cite `test_run_module_tests_failing_module_is_parseable`.
  6. PF-6 has PR-J1 landed? Transport yes; live `/doc` is operator (T2-J1).
- **Acceptance:** [ ] six answers in the progress log, each with evidence.
- **Negative:** an answer without a path or command is not an answer.
- **Rollback:** none.

### T1-F0 — PR-F.0 entrypoint trace (blocking)
- **Status:** SEEDED. `tests/test_pr_f0_entrypoint.py` (2): `test_studio_generate_offline_finish_calls_seed_and_locked_craft`, `test_studio_generate_offline_finish_docstring_golden_entrypoint`. Not yet written up as the PR-F.0 record.
- **depends_on:** BL-06
- **Pressure:** C2 U2 F2 K2 V1 I0 +0 = 9 → Grok standard
- **Read first:** `apps/api/app/ai_draft_jobs.py` (`_finish_seed_draft`); the Studio Generate router (`rg -n "generate" apps/api/app/routers/studio*.py apps/api/app/routers/module_spec.py`); `tests/test_pr_f0_entrypoint.py`.
- **Change:** `tests/test_pr_f0_entrypoint.py` if a node-count assertion is missing; progress log.
- **Steps:**
  1. Trace Studio Generate button → API route → function → `_finish_seed_draft`. Write the call chain with file:line.
  2. Confirm `_finish_seed_draft` adds no node after the presumed entrypoint. If it does, retarget the goldens to the true final XML.
  3. Add an assertion that the field, one2many, and menu counts after `_finish_seed_draft` equal the counts from `GenerateIR` (invariant 2), if the test does not already assert that.
  4. Label any battery result recorded before this card as provisional in the progress log.
- **Acceptance:** [ ] PR-F.0 call chain in the progress log; [ ] count-equality assertion exists and passes.
- **Negative:** inject a fake post-entrypoint node in a test double; the assertion fails.
- **Commands:** `pytest tests/test_pr_f0_entrypoint.py tests/test_generate_ir_spine.py`
- **Rollback:** revert the test edit.
- **Evidence:** call chain plus green tests.

### T1-INST — AI_IR_TRACE on Maintenance
- **Status:** OPEN (script exists: `apps/api/scripts/dump_maintenance_ir_trace.sh`; result not recorded).
- **depends_on:** T1-F0
- **Pressure:** C1 U2 F1 K1 V1 I0 +0 = 6 → Grok standard
- **Change:** progress log only.
- **Steps:** run the trace; for each pass list nodes added and removed; state whether scrub removed anything (the scrub-key hypothesis).
- **Acceptance:** [ ] PF-3 answered with the dump path under `.cache/ai_ir_trace/`.
- **Do not:** commit the `.cache` dump.

### T1-A1 — schema_client positive and negative tests (PR-A, addendum A2)
- **Status:** SEEDED. `tests/test_ai_schema_client.py`: `test_model_exists_known_and_unknown`, `test_relation_ok_positive_and_negative`.
- **depends_on:** T1-F0
- **Pressure:** C1 U1 F1 K1 V0 I0 +0 = 4 → cheap
- **Read first:** `apps/api/app/ai_schema_client.py` (whole file); `tests/test_ai_schema_client.py`.
- **Change:** tests only, if `fields_get` lacks a fail case.
- **Steps:** confirm `model_exists`, `fields_get`, and `relation_ok` each have a pass and a fail test. Add the missing `fields_get` unknown-model case if absent.
- **Acceptance:** [ ] three methods × pass and fail = six assertions.
- **Commands:** `pytest tests/test_ai_schema_client.py`

### T1-A2 — TTL deny on stale (addendum A3)
- **Status:** SEEDED. `test_factory_ttl_denies_stale_catalog`, `test_factory_missing_loaded_at_denies`. TTL is `SCHEMA_CATALOG_TTL_S = 15*60`.
- **depends_on:** T1-A1
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] a stale snapshot yields a deny client; [ ] a stale snapshot never admits a field (assert through `admit_and_apply`, not only the factory).
- **Do not:** lengthen the TTL.

### T1-A3 — field_is_writable
- **Status:** SEEDED. `test_field_is_writable_rejects_readonly_related`.
- **depends_on:** T1-A1
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] implemented and tested (it is), and the progress log says so; or [ ] a written deferral.

### T1-A4 — view_has_field stays as built (addendum A6)
- **Status:** DONE (verification only). Live parses `get_views`; Fake uses `view_fields`; Deny and Catalog return false. Tests in `tests/test_view_has_field_wave6.py` (5) and `test_view_has_field_is_stub_false`.
- **Pressure:** 3 → cheap
- **Do not:** delete the Live/Fake parser; do not extend Catalog past the stub.

### T1-B1 — merge_proposals admit rules (PR-B)
- **Status:** SEEDED (`merge_proposals` in `ai_generate_ir.py` and `ai_generate_ir_enforce.py`; `tests/test_generate_ir_closed_class.py`). No single readable structural allowlist constant found (`STRUCTURAL_ALLOWLIST` absent).
- **depends_on:** T1-A1
- **Pressure:** C2 U2 F2 K2 V1 I1 +0 = 10 → Grok high effort
- **Read first:** `apps/api/app/ai_generate_ir.py` (`merge_proposals`, `admit_and_apply`); `apps/api/app/ai_generate_ir_enforce.py`; `../T1_SCHEMA_GROUNDING.md` lines 60–64.
- **Change:** `ai_generate_ir.py` and/or `ai_generate_ir_enforce.py`; a test file.
- **Steps:**
  1. List every admit path today. Each must be one of: (a) cued, (b) on the structural allowlist, (c) schema-verified reuse.
  2. Move the structural allowlist into one named constant, readable in one sitting (target under 40 entries), with a one-line reason per entry.
  3. Delete any admit path that is none of (a)–(c); add a test that would have caught it.
- **Acceptance:** [ ] one allowlist constant; [ ] every admit path is (a), (b), or (c); [ ] existing goldens still pass.
- **Negative:** a node that is uncued, not allowlisted, and not schema-verified is rejected.
- **Commands:** `pytest tests/test_generate_ir_closed_class.py tests/test_generate_ir_spine.py tests/test_invent_leak_closure.py tests/test_invent_outside_admit_wave0.py`
- **Rollback:** revert both modules.

### T1-B2 — Rate Line and many2one regression (addendum A4)
- **Status:** SEEDED (`test_maintenance_closed_ir_no_uncued_spray`, `test_maintenance_o2ms_subseteq_generate_ir`). Confirm a named Rate Line case exists.
- **depends_on:** T1-B1
- **Pressure:** C1 U1 F2 K2 V0 I0 +0 = 6 → Grok standard
- **Acceptance:** [ ] a test named for the Rate Line / maintenance lexical with no one2many cue rejects the one2many; [ ] a test rejects a generic many2one to `res.partner` without a cue.
- **Negative:** both cases above are the negatives.

### T1-B3 — Sibling golden hook
- **Status:** SEEDED (`test_service_cards_sibling_closed`).
- **depends_on:** T1-B1
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] Service-cards lives in the same test module as Maintenance, or the two modules import one shared harness; [ ] a lint or test fails when a brief-specific branch is added (for example `rg -n "maintenance|service.card" apps/api/app/ai_generate_ir*.py` must return no branch condition).

### T1-C1 — approved_craft defaults off (PR-C)
- **Status:** SEEDED (`approved_craft` present across `ai_generate_ir.py`, `ai_enrich.py`, `ai_depth.py`). Default-off not proven by a named test.
- **depends_on:** T1-B1
- **Pressure:** C2 U1 F1 K2 V1 I0 +0 = 7 → Grok standard
- **Read first:** `rg -n "approved_craft" apps/api/app apps/web/src`.
- **Steps:** (1) assert the checklist default is empty/off in the API; (2) assert toggling one row changes the generated XML; (3) the web checklist renders all rows unchecked by default.
- **Acceptance:** [ ] default off; [ ] toggle changes XML.
- **Negative:** generate with no craft rows; no craft field appears.

### T1-C2 — Checklist copy
- **Status:** OPEN
- **depends_on:** T1-C1
- **Pressure:** 5 → cheap
- **Skills to load:** `ux-copy`, `antislop-copywriting`.
- **Acceptance:** [ ] copy critique (9 dimensions, `../T7_UI_MOTION_COPY.md` lines 76–80) with no 1 on Accuracy or Ethics; [ ] each row says in plain words what it adds (for example "Adds a due date field to the form").

### T1-D1 — Repair cap (PR-D)
- **Status:** SEEDED (`MAX_REPAIR` in `ai_repair_loop.py`; `test_three_install_fails_stamps_failed`, `test_fail_repair_then_ok_with_tests_stamps_proved`).
- **depends_on:** T1-C1
- **Pressure:** C2 U1 F2 K2 V1 I1 +0 = 9 → Grok standard
- **Acceptance:** [ ] at most 3 repair iterations; [ ] broken never `install_ready`; [ ] clean is `install_ready` on the first pass; [ ] Odoo errors logged verbatim (see T1-D3).
- **Negative:** a module that fails 4 times stops at 3 and is `failed`.
- **Commands:** `pytest tests/test_option_a_prove_bar.py`

### T1-D2 — proved requires run_tests (D2)
- **Status:** SEEDED (`test_smoke_only_success_leaves_prove_pending`, `test_run_tests_true_stamps_proved`, `test_sandbox_verify_and_repair_defaults_run_tests_true`). Note: the string `proved_smoke_only` does not exist in code; smoke-only leaves `prove_pending`. That satisfies D2's intent; record it.
- **depends_on:** T1-D1
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] a smoke install cannot stamp `proved`; [ ] the progress log names the actual stamp (`prove_pending`) so docs stop saying `proved_smoke_only`.

### T1-D3 — Verbatim sandbox log
- **Status:** OPEN (verify).
- **depends_on:** T1-D1
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] the Odoo error text is stored on the job record byte-for-byte (after secret redaction), not summarized; test feeds a known traceback and asserts the stored text contains it.

### T1-E1 — CI split (PR-E)
- **Status:** OPEN
- **depends_on:** T1-D2
- **Pressure:** C2 U1 F1 K1 V1 I0 +0 = 6 → Grok standard
- **Read first:** `.github/workflows/ci.yml` (api job, lines 45–70).
- **Change:** `ci.yml`, pytest markers in `apps/api/pyproject.toml`.
- **Acceptance:** [ ] tier 1 and tier 2 tests fail on schema-invalid output; [ ] tier 3 (sandbox, slow) is a separate job that does not block the fast suite; [ ] `test_sandbox_prove_slow.py` is marked slow.
- **Do not:** move a currently blocking test to non-blocking.

### T1-E2 — D2 encoded
- **Status:** SEEDED by T1-D2. Close by citing the code path and the MEMORY line.
- **Pressure:** 3 → cheap

### T1-F1 — Maintenance golden (PR-F)
- **Status:** SEEDED (`test_maintenance_closed_ir_no_uncued_spray`). Not proven through the same entrypoint as the button until T1-F0 is written up.
- **depends_on:** T1-E1, T1-F0
- **Pressure:** C2 U1 F2 K2 V1 I0 +0 = 8 → Grok standard
- **Acceptance:** [ ] Maintenance passes with zero new brief-specific code (diff review: no new string literal naming the brief in `app/`).

### T1-F2 — Service-cards golden
- **Status:** SEEDED (`test_service_cards_sibling_closed`).
- **depends_on:** T1-F1
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] same code path as Maintenance; [ ] adding `if "maintenance" in brief` anywhere fails a test.

### T1-F3 — One Option A module reaches install_ready on a real sandbox
- **Status:** PARTIAL. STATE 2026-09-23 records an ephemeral sandbox install OK for `maintenance_tickets` and `service_cards` on Odoo 19 (agent path, not Mac UI).
- **depends_on:** T1-D1
- **Pressure:** C2 U1 F2 K1 V2 I0 +0 = 8 → Grok standard. Needs Docker.
- **Commands:** `./docker/run-sandbox-major-gate.sh 19`
- **Acceptance:** [ ] one Option A module (`option_a_authored` or a gold template) `install_ready` through the sandbox with `run_tests=True`; [ ] the log path is recorded.
- **Do not:** promote it anywhere. Promote stays human.

### T1-RET — Retire scrub
- **Status:** OPEN. `scrub_uncued_` still in `ai_brief_cues.py` and `ai_conversation/understand.py`.
- **depends_on:** T1-F1, T1-F2, and two consecutive full runs with zero scrub removals (recorded)
- **Pressure:** C2 U1 F2 K2 V1 I1 +0 = 9 → Grok standard
- **Steps:**
  1. Instrument a counter of scrub removals per run (trace already exists).
  2. Record two consecutive full-battery runs with zero removals.
  3. Replace scrub calls with a no-op assert (`assert removed == []`) for one release.
  4. Move Date, Datetime, and money into `approved_craft`.
  5. Run the full battery and the live grade.
- **Acceptance:** [ ] two zero-removal runs recorded; [ ] no-op assert in place; [ ] Date/Datetime/money in craft; [ ] battery green.
- **Negative:** reintroduce an uncued Date field; the no-op assert fails.
- **Rollback:** restore scrub calls (keep the counter).

### T1-GATE — Gates that stay even if the code already exists
- **Status:** checklist card, run before claiming master DoD 1.
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] closure holds on a brief that used to spray; [ ] the sibling golden fails if someone special-cases Maintenance; [ ] `schema_client` deny-on-stale is tested, not commented; [ ] no new `if display_name == "…"` denylist in the diff.
