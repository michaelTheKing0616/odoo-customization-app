# REG-NP-T4: Live progress on four surfaces (6.1; compiler DoD 8–10; master DoD 7)

ID: REG-NP-T4
Title: Live progress on four surfaces (6.1; compiler DoD 8–10; master DoD 7)
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-T4-PROG;NP-T4-OFF;NP-T4-ISPEC;NP-T4-SYNC;NP-T4-BROWSER;NP-T4-WIRE;NP-T4-LLM3;NP-T4-SKT;NP-T4-GROUND
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F1 K1 V2 I0)
Context pack:
- `sed -n '23,30p' docs/plans/next-phase/cards/T4_COMPILER_SURFACES.md`
- `sed -n '57,103p' docs/plans/next-phase/cards/T4_COMPILER_SURFACES.md`
- `sed -n '111,114p' docs/plans/next-phase/cards/T4_COMPILER_SURFACES.md`
- `sed -n '11,24p' apps/api/app/progress/stage_bus.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_t4.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-T4` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Live progress on four surfaces (6.1; compiler DoD 8–10; master DoD 7) (pressure 9) (source: ledger NP-T4-PROG, next-phase cards/T4_COMPILER_SURFACES.md)
- AC2: Offline queue (6.4; master DoD 10) (pressure 13) (source: ledger NP-T4-OFF, next-phase cards/T4_COMPILER_SURFACES.md)
- AC3: ISPEC round-trip (6.5; compiler DoD 1–2) (pressure 14) (source: ledger NP-T4-ISPEC, next-phase cards/T4_COMPILER_SURFACES.md)
- AC4: Recompile and Sync (compiler DoD 3–5; master DoD 11) (pressure 15) (source: ledger NP-T4-SYNC, next-phase cards/T4_COMPILER_SURFACES.md)
- AC5: Browser-testing sub-agent in Stage F (compiler DoD 6–7; master DoD 12) (pressure 11) (source: ledger NP-T4-BROWSER, next-phase cards/T4_COMPILER_SURFACES.md)
- AC6: Wireframe to app (6.6; compiler DoD 12; master DoD 13) (pressure 11) (source: ledger NP-T4-WIRE, next-phase cards/T4_COMPILER_SURFACES.md)
- AC7: Three-tier provider abstraction (6.7; master DoD 14) (pressure 9) (source: ledger NP-T4-LLM3, next-phase cards/T4_COMPILER_SURFACES.md)
- AC8: Skills; Sources; Triggers (6.8; compiler DoD 15–18; master DoD 15) — stop-ship (pressure 16) (source: ledger NP-T4-SKT, next-phase cards/T4_COMPILER_SURFACES.md)
- AC9: Dynamic tools grounded; RAG reuses the index; Odoo widgets (compiler DoD 11; 13; 14) (pressure 8) (source: ledger NP-T4-GROUND, next-phase cards/T4_COMPILER_SURFACES.md)
Worked examples:
- Pin AC2: `POST /api/offline/flush` of `MUTATION_BODY` with the same `Idempotency-Key` twice returns 200 both times, the same JSON, `applied is True`, `effect_seq == 1`, and one recorded effect. Promote without the phrase returns 403, `detail.requires_confirmation is True`, `detail.confirm_phrase == CONFIRM_PHRASE` (`"I understand the risks"`), and zero effects. The same key with `confirm_advanced: true` and that phrase returns 200, `applied is True`, `kind == "promote"`, one effect.

| Body | Confirm | Result |
|---|---|---|
| mutation, same idempotency key twice | none | one effect |
| promote, no phrase | none | 403, zero effects |
| promote, `confirm_advanced` and `CONFIRM_PHRASE` | present | one effect |
- Pin AC6: every module under `app/wireframe` imports neither `llm_gateway`, `llm_provider`, `changeset`, nor `agent_runtime`, and calls none of `apply_module_spec`, `apply_module_spec_ui`, `apply_session_route`, `apply_project_spec`, `apply_project`, `apply_queued_flush`. `wireframe.sketch_to_module_spec` is in `wireframe.__all__`. `regions_to_draft` is not.
- Pin AC7: `load_registry([{"provider": "local", "model_id": "x", "tier": "S"}])` raises `ValueError`. `lookup` of an unknown model id returns `record is None`, `tier is None`, `caps == TIER_C_CAPS`, `caps.read_only is True`, `caps.can_submit_changeset is False`.
- Pin AC8: `fire` on an existing `base.automation` trigger returns `status == "pending"`, `approval_id is None`, and `plan_card(...)["approvals"] == []`. A second `fire` has a different `plan_hash` and stays pending after the first is approved. `fire` on `account.move` or `hr.payslip` raises `ProtectedModelBlocked`.
- Pin AC9 tools and RAG: `accept_tool_target(sale_client, ToolTarget(kind="model", model="x.unknown.nowhere"))` is False. `offer_tool_targets` of `sale.order` plus that unknown model returns only the `sale.order` target. `app/grounding/rag.py` imports `_cache_dir` and `retrieve_with_rag` from `app.ai_rag`. `ai_rag2`, `ai_rag_v2`, and `compiler_rag` do not appear in `app/grounding/*.py`.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_t4.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_t4.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: AI proposes, code authorises (INV-13): no model output reaches `execute_kw`, an install or an export without a deterministic validator. Calls go only through `app/ai_client` with untrusted text in `fence_fields` (source=...). Any call that names Odoo structure first reads the live schema packet (`live_schema_context.build_schema_packet`) and the engine rejects names not in it. Caches never store secrets or PII and never serve write plans.
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_reg_np_t4.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
