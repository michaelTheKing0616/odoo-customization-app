# B0-TESTFIX-ORDER: API pytest 0 failures or each xfail has reason + P-item + Tope yes

ID: B0-TESTFIX-ORDER
Title: API pytest 0 failures or each xfail has reason + P-item + Tope yes
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC1;P0-2-CL5
Depends on: B0-INV, B0-GREEN
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 5 (C0 U1 F1 K1 V2 I0)
Context pack:
- `sed -n '466p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '465p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- apps/api/tests/test_t6_04_inbox_binding.py
- apps/api/tests/test_t6_07_client_inbox_scope.py
- apps/api/tests/test_ai_conversation_session.py
- apps/api/tests/test_brief_understanding_class.py
- apps/api/tests/test_b0_testfix_order.py (new)
Goal: Make the order cluster pass in both Test plan pytest commands. AC1's suite-wide bar stays. If the rest of the API suite is red, record the count and STOP-AND-ASK. Do not add an xfail.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output. Reading is the only reading. The AC1 and AC2 lines stay.
2. Edit only the order-cluster files: `tests/test_t6_04_inbox_binding.py`, `tests/test_t6_07_client_inbox_scope.py`, `tests/test_ai_conversation_session.py`, `tests/test_brief_understanding_class.py`, and new `tests/test_b0_testfix_order.py`. The other clusters named in AC2 are other cards. Do not edit them and do not xfail them here. Name in the Worker packet the line whose deletion would make an order assertion fail.
3. Run the two Test plan pytest commands. They prove the order cluster. They must both pass and they must agree. Do not add `-p randomly`. If a named test still fails, step 4. After those two pass, run `cd apps/api && uv run pytest -q` once and record the failed count. If any failure sits outside the five order-cluster files, that rest-of-suite count is not 0: STOP-AND-ASK. Do not edit that file. Do not xfail it.
4. There is no Tope yes for an xfail on this card. Do not add an xfail. A still-failing named test is STOP-AND-ASK. Do not fix product code.
5. Write the Worker packet. List only the order-cluster files edited.
6. Keep the L2-HARNESS line in the Test plan. It is Phase 2. It is not this card's close proof. Do not run it to close this card.
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong. Also stop when a named test still fails, when the API suite failed count is not 0, or when an AC2 cluster outside the order-cluster files would have to change.
Acceptance criteria:
- AC1: API pytest has 0 failures, or each remaining failure is marked `xfail` with a reason and a linked P-item, and Tope has agreed to each `xfail`. (source: INGENIUM_MASTER_HANDOVER.md L466)
- AC2: Known clusters (PROGRESS): direct XML-RPC in `code_runner/testing.py`, `bridge/export.py`, `routers/view_engine.py` that bypass the transport contract; version-branch baseline 37 vs 22 (`import_boundary`); pack and Expert copy tests that expect old jargon; the mastery battery; order-dependent tests (`t6_04`, `t6_07`, `test_create_session_blocks_low_ir`, `test_diagnosis_name_strips_management_fluff`); `test_ai_ollama` and `test_ai_module_generation` cases that passed only through live Vertex before AI_ASSIST off worked; 5 `understand` tests; `test_llm_provider::test_ollama_routes_bulk_vs_reasoning_and_strips_cot`. (source: INGENIUM_MASTER_HANDOVER.md L465)
Symbols (ledger row on this card: P0-2-CL5. AC1 and AC2 text above is unchanged):
- `tests/test_t6_04_inbox_binding.py` `test_decide_fingerprint_mismatch_returns_409_plan_stale`: a decide body with the wrong schema fingerprint or the wrong plan hash returns HTTP 409 and `detail.error == "plan_stale"`. The matching `plan_hash` and `schema_fp` returns 200 and `card.status == "approved"`.
- `tests/test_t6_07_client_inbox_scope.py` `test_client_approver_inbox_lists_only_granted_connection_and_hides_other_plans`: another client's list is HTTP 404 (not 403). A viewer decide is HTTP 403.
- `tests/test_ai_conversation_session.py` `test_create_session_blocks_low_ir` L341.
- `tests/test_brief_understanding_class.py` `test_diagnosis_name_strips_management_fluff` L349: `build_understanding(VEHICLE).title == "Vehicle Request"` and `scrub_residual_display_name("Fleet Vehicle Request Management") == "Vehicle Request"`.
Worked example: `POST /api/ai/sessions` with `{"prompt": "Use stock Odoo apps only for our small business.", "connection_id": null}` and no earlier test in the process. Expected: HTTP 200, `status == "clarifying"`, `clarification` is not None. The same three assertions hold for `pytest -q tests/test_ai_conversation_session.py::test_create_session_blocks_low_ir` when that process already imported `test_t6_04_inbox_binding.py`. Leave `conftest.py`, `pytest.ini`, and `vitest.config.ts` unchanged unless one of the named tests fails because of cross-test leakage that the test module cannot isolate. Only then may those files change, and only to remove that leak. Leave product code unchanged. Do not edit or xfail the other AC2 clusters.
Decision:

| how the named test is run | required |
| that file alone | pass |
| after another test in the same process | the same result as alone |
| passes only because a previous test left DB, env, or import state | fail; isolate inside the test module first |
| test module cannot isolate that leak | then edit `conftest.py`, `pytest.ini`, or `vitest.config.ts` only for that leak |
| still failing | STOP-AND-ASK. Do not add an xfail. There is no Tope yes |
| file other than the five order-cluster files | do not edit and do not xfail, except the leak row above for `conftest.py`, `pytest.ini`, or `vitest.config.ts` |
| rest of the API suite is red | record the failed count; STOP-AND-ASK; AC1's suite-wide bar stays |
2026-10-24 the last full default suite was 68 failed. Do not rerun it on this card. Shared `P0-2-AC1` stays Open. Prove the two order-cluster commands only.
2026-10-24 `test_compound_vehicle_type_dropped_without_cue` stays at HEAD (`x_vehicle_type` not in names). It fails on the uncommitted REG-NP-T1c keep in `ai_brief_cues.py`. It is not a named node on this card. Do not invert it.
2026-10-24 closed. Named orders A 12 passed in 4.84s and B 12 passed in 4.52s. No xfail. `P0-2-CL5` is `[Done, code]`. `P0-2-AC1` stays Open. Reviewer APPROVE.
| L2-HARNESS line | Phase 2. Not this card's close proof |

Reading:
1. The AC1 and AC2 lines stay. This card edits only the order-cluster files on its allow-list (the four named tests plus `test_b0_testfix_order.py`). The other clusters named in AC2 are other cards. Do not edit them and do not xfail them here.
2. AC1's suite-wide bar stays. This card's two pytest commands prove the order cluster. If the rest of the API suite is red, record the count and STOP-AND-ASK. Do not xfail a file outside the allow-list.
3. Leave `conftest.py`, `pytest.ini`, and `vitest.config.ts` unchanged unless one of the named tests fails because of cross-test leakage that the test module cannot isolate.
4. There is no Tope yes for an xfail on this card. Do not add an xfail. A still-failing named test is STOP-AND-ASK.
5. Keep the L2-HARNESS line. Label it Phase 2. It is not this card's close proof.

Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_testfix_order.py tests/test_t6_04_inbox_binding.py tests/test_t6_07_client_inbox_scope.py tests/test_ai_conversation_session.py::test_create_session_blocks_low_ir tests/test_brief_understanding_class.py::test_diagnosis_name_strips_management_fluff` → all pass
- `cd apps/api && uv run pytest -q tests/test_brief_understanding_class.py::test_diagnosis_name_strips_management_fluff tests/test_ai_conversation_session.py::test_create_session_blocks_low_ir tests/test_t6_07_client_inbox_scope.py tests/test_t6_04_inbox_binding.py tests/test_b0_testfix_order.py` → the same pass/fail result
- live: L2-HARNESS runner `--card B0-TESTFIX-ORDER --matrix 17,18,19,20` on disposable `ingenium_*` DBs → pass per major (Phase 2 on)
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
