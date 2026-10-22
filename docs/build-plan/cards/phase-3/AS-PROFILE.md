# AS-PROFILE: One App Studio profile instead of 18 env flags

ID: AS-PROFILE
Title: One App Studio profile instead of 18 env flags
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-RC4
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §2 RC4, §3, §9 (first bullet)
- docs/build-plan/CODE_MAP.md rows: design prompt, quality adders, owner words, expansion, orphan repair, grounding
File allow-list:
- apps/api/app/ai_conversation/studio_profile.py (new)
- apps/api/app/ai_conversation/app_design.py (design_knobs only)
- apps/api/app/ai_conversation/brief_checklist.py (enabled only)
- apps/api/app/ai_conversation/brief_expand.py (_enabled only)
- apps/api/app/ai_conversation/clause_grounding.py (enabled only)
- apps/api/app/ai_conversation/orphan_repair.py (mode only)
- apps/api/app/ai_conversation/design_quality.py (authorizer mode read only)
- apps/api/tests/test_studio_profile.py (new)
Goal: A typed `StudioProfile` (frozen dataclass) with presets `legacy_v1` (exactly today's defaults) and `v3`; each old flag reader asks the profile.
Steps:
1. Create `studio_profile.py`: `StudioProfile` fields = every knob in CODE_MAP (rules, gapfill, budget, temperature, checklist, clause_grounding, expand, orphan_repair, authorizer, role_reask) plus `src_brief_only`, `polish`, `contract_verifier`, `deadline_soft_s=30`, `deadline_hard_s=45`, `votes=3`, `chunk_words=800`, `max_parallel_calls=4`, `pipeline='legacy'|'v3'`. Grep all 19 `INGENIUM_*`/`STUDIO_*` readers in `ai_conversation` + the router and list each in the test with its field
2. `active_profile()` reads `INGENIUM_STUDIO_PROFILE` (default `legacy_v1`); individual env flags still override, but ONLY when `INGENIUM_EVAL=1`, and each override is listed in `profile.overrides`
3. `profile.fingerprint()` = sha256 of the sorted fields, 12 hex chars
4. Replace each flag reader's body with a profile lookup (one line each). Keep the function names
5. Log `App Studio profile <name> <fingerprint> overrides=<…>` once per process, and put `profile` + fingerprint into `design.llm_outcome`
Acceptance criteria:
- AC1: `legacy_v1` reproduces today's defaults: a test compares each reader's return against the literal default listed in CODE_MAP
- AC2: Without `INGENIUM_EVAL=1`, setting `INGENIUM_DESIGN_RULES=v2` has no effect and logs a warning naming the ignored flag
- AC3: `llm_outcome['profile']` = {name, fingerprint, overrides} on every design
- AC4: `v3` preset: pipeline v3, expand off, gapfill drop, budget none, checklist off, contract_verifier off, authorizer off (v3 uses `authorize_v3`), src_brief_only on, polish on, votes 3. `legacy_v1`: src_brief_only off, polish off, contract_verifier as today
Test plan:
- `cd apps/api && uv run pytest -q tests/test_studio_profile.py`
- `cd apps/api && uv run pytest -q tests/test_studio_step2a_app_design.py` (regression, unchanged)
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
