# AS-SRC-BRIEF: Designer, budget and outline read the owner's words only

ID: AS-SRC-BRIEF
Title: Designer, budget and outline read the owner's words only
Status: todo
Phase: 3
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-RC1
Depends on: AS-PROFILE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F2 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §2 RC1
- docs/build-plan/CODE_MAP.md rows: create session, owner words, design prompt, outline fallback
File allow-list:
- apps/api/app/ai_conversation/app_design.py (`design_user_prompt`; inside `build_app_design` only the argument passed to: `model_budget_for` L2697, `outline_from_brief` L2698, `design_timeout_for` L2734/L2779, `scope_and_limits` L2930, `orphan_repair.repair_step` L2936, `suggest_stock_apps` L2948, `_call_critic` L2962)
- apps/api/tests/test_src_brief.py (new)
Goal: Close RC1 in legacy: every reader in `build_app_design` that still gets the expanded `prompt` gets `source_brief(prompt)` instead; the expansion is labelled context, never the brief. Behind `profile.src_brief_only` (on in v3; on in legacy only after AS-EXP-X0 passes).
Steps:
1. In `design_user_prompt`, when `profile.src_brief_only`: `Operator brief (full)` = `source_brief(prompt)`; append `expansion_context(prompt)` (already labels it context-only)
2. Compute `owner = source_brief(prompt)` once at the top of `build_app_design` under the flag and pass `owner` to each reader listed in the allow-list (the readers already applying `source_brief` stay as they are)
3. Do not touch `routers/ai_studio.py`: the session still stores the expansion for display
Acceptance criteria:
- AC1: With the flag on, an expansion that adds 'Alert Rule' and 'Community' never appears in the `Operator brief` section of the designer prompt (string assert)
- AC2: Budget computed from the 20-word owner brief, not the 200-word expansion (assert value)
- AC3: With the flag off, prompt text is byte-identical to today (golden string)
- AC4: With the flag on, the outline's models equal `outline_from_brief(owner)` (not the expansion), so `_merge_outline`/`_cover_sections` cannot re-add expansion-only models (fixture expansion adds 'Community')
- AC5: With the flag on, the strings passed to `_call_critic`, `repair_step`, `scope_and_limits` and `suggest_stock_apps` contain no expansion-only sentence (spy asserts)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_src_brief.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
