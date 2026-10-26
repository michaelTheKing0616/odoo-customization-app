# B0-TESTFIX-MASTERY: API pytest 0 failures or each xfail has reason + P-item + Tope yes

ID: B0-TESTFIX-MASTERY
Title: API pytest 0 failures or each xfail has reason + P-item + Tope yes
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC1;P0-2-CL4
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
- apps/api/tests/test_mastery_regression_battery.py
- apps/api/tests/test_b0_testfix_mastery.py (new)
Goal: Make every AC below true for `B0-TESTFIX-MASTERY` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output.
2. Write the tests in the allow-list files. Each test must fail if the behaviour were removed: name in the Worker packet the product line whose deletion would make it fail.
3. Run the Test plan command twice (second time `-p randomly` for API once DEC-047 lands) → identical green results.
4. If a test exposes a real defect, do not fix product code: mark it `xfail(strict=True, reason=<new ledger row>)` and report it in the Worker packet.
5. Write the Worker packet.
6. Live checks run only on disposable `ingenium_*` sandboxes for 17, 18, 19 (and 20 once its stack exists); drop what you create (INV-03).
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: API pytest has 0 failures, or each remaining failure is marked `xfail` with a reason and a linked P-item, and Tope has agreed to each `xfail`. (source: INGENIUM_MASTER_HANDOVER.md L466)
- AC2: Known clusters (PROGRESS): direct XML-RPC in `code_runner/testing.py`, `bridge/export.py`, `routers/view_engine.py` that bypass the transport contract; version-branch baseline 37 vs 22 (`import_boundary`); pack and Expert copy tests that expect old jargon; the mastery battery; order-dependent tests (`t6_04`, `t6_07`, `test_create_session_blocks_low_ir`, `test_diagnosis_name_strips_management_fluff`); `test_ai_ollama` and `test_ai_module_generation` cases that passed only through live Vertex before AI_ASSIST off worked; 5 `understand` tests; `test_llm_provider::test_ollama_routes_bulk_vs_reasoning_and_strips_cot`. (source: INGENIUM_MASTER_HANDOVER.md L465)
Symbols (ledger row on this card: P0-2-CL4. AC1 and AC2 text above is unchanged): `hosting_operator_message`, `ONLINE_REFUSE_EXACT`, `test_online_operator_message_exact`, `test_online_operator_message_enterprise_appends_studio_warn` in `apps/api/tests/test_mastery_regression_battery.py` L48-71. That file is the mastery battery.
Worked example: `hosting_operator_message("online", edition="community")` equals `ONLINE_REFUSE_EXACT`: `Hosting looks like Odoo Online: metadata customization and data/XML module import are OK; custom Python modules cannot be installed on Online — export install_mode=data or use Odoo.sh / self-host for custom-code Python.` Leave `conftest.py`, `pytest.ini`, and `vitest.config.ts` unchanged. Leave product code unchanged.
Decision:

| call | expected |
| `hosting_operator_message("online", edition="community")` | equal to `ONLINE_REFUSE_EXACT` |
| `hosting_operator_message("online", edition="enterprise")` | starts with `ONLINE_REFUSE_EXACT` and contains `Enterprise edition detected` and `Studio` |
| any battery failure left over | `xfail(strict=True, reason="P0-2-CL4: <nodeid>")` with a P-item and Tope's yes, or AC1 fails |
2026-10-24 closed. `tests/test_b0_testfix_mastery.py` plus the battery: 14 passed in 2.37s, then `-p randomly` 14 passed in 2.05s. `hosting.py` unchanged. Reviewer APPROVE. `P0-2-CL4` is done. Shared `P0-2-AC1` stays Open.

Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_testfix_mastery.py tests/test_mastery_regression_battery.py` → all pass
- live: L2-HARNESS runner `--card B0-TESTFIX-MASTERY --matrix 17,18,19,20` on disposable `ingenium_*` DBs → pass per major (Phase 2 on)
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
