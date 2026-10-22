# AS-LEDGER-SCHEMA: Brief Ledger models and validators

ID: AS-LEDGER-SCHEMA
Title: Brief Ledger models and validators
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-LEDGER
Depends on: AS-TOTAL (uses `brief_normalise`)
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F2 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §4
- docs/build-plan/app-studio/ORACLES.md §L
File allow-list:
- apps/api/app/ai_conversation/brief_ledger.py (new)
- apps/api/tests/test_brief_ledger.py (new)
Goal: Pure Pydantic models (`ledger/2`, clause-cited `Quote`) + `validate(ledger, normalised) -> (ledger, report)` implementing L1-L8, with orphans computed by code.
Steps:
1. Models exactly as Pack §4 (no `noise` list; `Quote.start/end` filled only by validate)
2. Use `brief_normalise.normalise` output (NFC text + clause intervals); never a second normaliser
3. L1 resolves each quote inside its cited clause, then the adjacent clauses; compare with `casefold()` applied to both sides after slicing
4. L2-L8 in order; each emits report codes (`quote_not_verbatim`, `thin_record`, `orphan_clause`, …)
5. `model_schema_for_provider()` = `BriefLedger.model_json_schema()` minus `start`/`end`, exported for AS-DECODE
Acceptance criteria:
- AC1: Oracles L-01..L-13 pass unmodified
- AC2: validate is idempotent and pure (no I/O; test with monkeypatched open/socket)
- AC3: The provider schema contains no `start`/`end` properties (unit test)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_brief_ledger.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §4. Offsets index the NFC brief; casefold only after slicing (casefold changes length). Never use stems here. The validator never changes a role except L3 (bad parent → fact) and L7 (future/excluded → left_out).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §L.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
