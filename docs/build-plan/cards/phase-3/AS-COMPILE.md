# AS-COMPILE: Compile the voted Ledger into an AppDesign

ID: AS-COMPILE
Title: Compile the voted Ledger into an AppDesign
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-COMPILE-ROW; AS-FAIL-A
Depends on: AS-STABILITY, AS-RETRIEVE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 8 (C2 U1 F2 K2 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §3 (division of labour), §6.3, §6.4 step 3
- docs/build-plan/app-studio/ORACLES.md §C (C-01..C-11, C-14..C-17)
- docs/build-plan/CODE_MAP.md rows: data shapes, repair/validate, automations
- apps/api/app/ai_conversation/app_design.py L836-1100 (read only: the contract's per-requirement `decision` and capability fields that `contract` carries)
File allow-list:
- apps/api/app/ai_conversation/ledger_compile.py (new)
- apps/api/tests/test_ledger_compile.py (new)
Goal: A pure function `compile(voted, contract, snapshot, profile, host_fit=installed_in_snapshot) -> AppDesign` implementing the Pack §6.3 table, plus `structure_hash` and `validate_strict`. This card does **not** touch `build_app_design`; AS-V3-WIRE calls it.
Steps:
1. Implement the mapping table row by row; technical names via `_model_name`/`_field_name` (import, do not copy)
2. Line inference rule (C-15) and stock-host gating through the `host_fit` callable (C-16)
3. Join ledger rules to contract requirements by evidence-interval overlap; no match → `metadata`; `cannot`/`decline` → `left_out` status `cannot` (C-17); `option_a` → `python_needed` row
4. Hygiene pack (x_name, default views, menu, active; `state` only when a rule/fact implies stages), each recorded as an assumption id
5. Folded items keep a full `DesignModel` in `left_out[].proposal`
6. `structure_hash(design)` over the fields listed in Pack §6.3 (incl. selection values, required, inverse names, relation targets)
7. `validate_strict(design, grounding, packet, snapshot)`: call the existing `validate_and_repair` (it has no `strict_refs` kwarg; do not add one), then move dangling refs to `left_out` with a reason
8. Never call `strengthen_design`, `_merge_outline`, `_cover_sections`, `complete_from_brief`; never apply `MIN_DESIGN_MODELS`
Acceptance criteria:
- AC1: Oracles C-01..C-11 and C-14..C-17 pass unmodified (C-12/C-13 belong to AS-CONSERVE/AS-PROMOTE)
- AC2: Compile never yields a model without a ledger id or assumption id in `requirement_ids` (property test)
- AC3: `compile` is pure: same inputs → byte-identical design JSON; no I/O (monkeypatched socket/open)
- AC4: A dangling many2one target → `left_out` row, design still valid (unit test for `validate_strict`)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ledger_compile.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §6.3. Typed facts: money → monetary + currency_id; file → binary (image when the owner says photo/picture/foto). Selection only from ≥ 2 verbatim values. If the locked diagnosis in `contract` names an inherit host, compile onto it; if the compile would contradict the lock, return the existing compiler failure, never a silent override.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §C.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
