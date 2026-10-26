# B0-TESTFIX-AIOFF: API pytest 0 failures or each xfail has reason + P-item + Tope yes

ID: B0-TESTFIX-AIOFF
Title: API pytest 0 failures or each xfail has reason + P-item + Tope yes
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC1;P0-2-CL6
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
- apps/api/tests/test_b0_testfix_aioff.py (new)
Goal: Make every AC below true for `B0-TESTFIX-AIOFF` and prove it with the Test plan; change nothing outside the allow-list.
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
Symbols:
- AC2 names these; they are not on this allow-list (STOP-AND-ASK before editing them): `app/code_runner/testing.py`, `app/bridge/export.py`, `app/routers/view_engine.py`, `import_boundary`, `t6_04`, `t6_07`, `test_create_session_blocks_low_ir`, `test_diagnosis_name_strips_management_fluff`, `test_ai_ollama`, `test_ai_module_generation`, `test_llm_provider.py::test_ollama_routes_bulk_vs_reasoning_and_strips_cot`.
- xfail shape: `pytest.mark.xfail(strict=True, reason=...)`.
- `apps/api/pytest.ini` has marker `odoo_live` (skipped unless `ODOO_LIVE=1`). There is no `live_ai` marker in `apps/api`.
Worked example:
- `cd apps/api && uv run pytest -q` prints `0 failed`, or every remaining failure is an `xfail` whose reason names a P-item (for example `P0-2-CL6`) and Tope has agreed to that `xfail`.
Decision:
| suite result | AC1 |
| `0 failed` | met |
| every failure is `xfail` with a reason, a linked P-item, and Tope's yes | met |
| any other failure | not met |
2026-10-24 closed on the named pin. `tests/test_b0_testfix_aioff.py` 3 passed, then `-p randomly` 3 passed. Reviewer APPROVE. `P0-2-CL6` is done. Shared `P0-2-AC1` stays Open. No xfail added.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_testfix_aioff.py` → all pass
- live: L2-HARNESS runner `--card B0-TESTFIX-AIOFF --matrix 17,18,19,20` on disposable `ingenium_*` DBs → pass per major (Phase 2 on)
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
