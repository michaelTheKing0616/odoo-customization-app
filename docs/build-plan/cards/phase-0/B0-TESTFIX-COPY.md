# B0-TESTFIX-COPY: API pytest 0 failures or each xfail has reason + P-item + Tope yes

ID: B0-TESTFIX-COPY
Title: API pytest 0 failures or each xfail has reason + P-item + Tope yes
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC1;P0-2-CL3
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
- apps/api/tests/test_ai_conversation_intent_gate.py
- apps/web/src/lib/draft-form-preview.test.tsx
- apps/web/src/lib/expert-copy.test.ts
- apps/api/tests/test_b0_testfix_copy.py (new)
Goal: Make every AC below true for `B0-TESTFIX-COPY` and prove it with the Test plan; change nothing outside the allow-list.
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
Symbols (ledger row on this card: P0-2-CL3. AC1 and AC2 text above is unchanged):
- `build_clarification`, `test_pack_ambiguity_copy_is_plain_language` in `apps/api/tests/test_ai_conversation_intent_gate.py` L198.
- `apps/web/src/lib/draft-form-preview.test.tsx`: `explains field-pack inherit instead of asking for an x_* document` L368; `explains authored Option A instead of asking to start a new app` L384.
- `apps/web/src/lib/expert-copy.test.ts` describe `Expert copy (UI-S-25)`. PROGRESS names draft-form-preview and expert-copy as the tests that still expected `Option A module` or `ModuleSpec`.
Worked example: `IntentAssessment(clear=False, triggers=["pack_ambiguity"], competing_pack_id="project_tracker")` with prompt `track our work this quarter`. The joined question, help, and option labels contain neither `which domain`, nor `vertical pack`, nor `helpdesk`. Option id 0 is `on_existing_form`. A field-pack draft `{grain: "field_pack", models: [{model: "account.move", mode: "inherit"}]}` renders empty-state text matching `/form people already use/i` and not `/x_\*/`. An authored draft `{_generation_engine: {capability: "option_a_authored"}}` matches `/custom-code module/i` and does not match `Start a new app`. Leave `conftest.py`, `pytest.ini`, and `vitest.config.ts` unchanged. Leave product copy unchanged; if the product string is the defect, xfail and STOP-AND-ASK.
Decision:

| string the test expects in owner-facing copy | result |
| `ModuleSpec`, `Option A module`, `vertical pack`, `which domain` | old jargon: point the test at the plain string, or `xfail(strict=True, reason="P0-2-CL3: <nodeid>")` with a P-item and Tope's yes |
| `custom-code module`, `form people already use`, and no `vertical pack` | pass |
2026-10-24 closed. API 2 passed, then `-p randomly` 2 passed. Web 23 passed. Loop 2 adds `expertHonestyLegend()` contains `Completeness is hygiene on drafts, not a shippable score.` Reviewer APPROVE. `P0-2-CL3` is done. Shared `P0-2-AC1` stays Open.

Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_testfix_copy.py tests/test_ai_conversation_intent_gate.py::test_pack_ambiguity_copy_is_plain_language` → all pass
- `cd apps/web && pnpm vitest run src/lib/draft-form-preview.test.tsx src/lib/expert-copy.test.ts` → all pass
- live: L2-HARNESS runner `--card B0-TESTFIX-COPY --matrix 17,18,19,20` on disposable `ingenium_*` DBs → pass per major (Phase 2 on)
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
