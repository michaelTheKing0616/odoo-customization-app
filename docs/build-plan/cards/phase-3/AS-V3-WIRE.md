# AS-V3-WIRE: The one v3 orchestrator: N, S, K and L in parallel, then V, Q, C, A, P, O

ID: AS-V3-WIRE
Title: The one v3 orchestrator: N, S, K and L in parallel, then V, Q, C, A, P, O
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-ANYBRIEF; AS-LATENCY-ROW; AS-COMPILE-ROW
Depends on: AS-TOTAL, AS-LEDGER-CALL, AS-COMPILE, AS-CRAFT-APPLY, AS-NO-PACKS, AS-QUESTIONS, AS-CONSERVE, AS-AUTHZ, AS-REPAIR
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 9 (C2 U1 F2 K2 V2 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §3, §6.4 (order), §7 (deadline, provider faults)
- docs/build-plan/app-studio/ORACLES.md §T rows marked AS-V3-WIRE (T-01 v3, T-06 v3, T-07, T-09..T-12)
- docs/build-plan/CODE_MAP.md rows: create session, LLM call, outline fallback
- apps/api/app/ai_conversation/app_design.py L836-848 (`_call_intent_contract` signature) and L2685-2720 (top of `build_app_design`)
File allow-list:
- apps/api/app/ai_conversation/v3_pipeline.py (new)
- apps/api/app/ai_conversation/app_design.py (one branch at the top of `build_app_design`: `if active_profile().pipeline == "v3": return v3_pipeline.run(...)`; legacy code below unchanged)
- apps/api/tests/test_v3_pipeline.py (new)
- apps/api/tests/test_studio_outcome_total.py (remove xfail on this card's rows only)
Goal: One function `run(owner_words, grounding, snapshot, answers, profile) -> StudioOutcome` that is the only place v3 stages are wired, timed and bounded.
Steps:
1. N via `brief_normalise.normalise` on `source_brief(prompt)` (never the expansion); `Redactor` before any provider call
2. In parallel under one executor capped at `profile.max_parallel_calls`: S (retrieval), K = `_call_intent_contract(provider, owner_words, grounding, verifier=None, parallel=None, answers=answers, snapshot=snapshot)` with the checklist off, and L = `ledger_call.sample_ledgers`
3. Every provider call gets `timeout_s = min(stage default, hard − elapsed)`; a 429 halves the in-flight limit for the rest of the request
4. Survivors < 3 with time left before the soft deadline → one top-up sample; at soft, vote what is in hand; at hard → `degraded` with `outline_from_brief(source_brief(...))`
5. Then V → Q (questions outcome if any question is unanswered and the caller has not chosen defaults) → C → D (`odoo_craft.apply` for the connection's major and the session's lane) → A (conservation, authorize_v3, validate_strict, invariants) → P if `profile.polish` and time remains → O. The degraded outline also passes through D
6. K missing → every rule `metadata` + note (T-12); snapshot unreadable → no retrieval + note (T-08 reused)
7. Timing record per stage into `design.llm_outcome.timings`; calls, tokens and 429 count into `llm_outcome.meter`
Acceptance criteria:
- AC1: ORACLES T-01 (v3 positions), T-06 (v3), T-07, T-09, T-10, T-11, T-12 pass with xfail removed
- AC2: With the fake provider at 2 s per call, k = 3 + K complete in ≤ 2.5 s wall time (parallel proof)
- AC3: Under profile legacy_v1 the branch is never taken: the existing studio tests are unchanged and green
- AC4: The expansion string never reaches any provider call (fake records every prompt; assert absent)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_v3_pipeline.py tests/test_studio_outcome_total.py tests/test_studio_step2a_app_design.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §3, §7. Threads cannot be cancelled, so the timeout passed into each call is the only real bound; never rely on abandoning a future. Do not add stages, retries or LLM calls beyond Pack §3's count (4-6 per normal brief).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §T rows marked AS-V3-WIRE.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
