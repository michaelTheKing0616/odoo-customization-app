# AS-FRESH-BYPASS: Answer cache honours x-ingenium-fresh

ID: AS-FRESH-BYPASS
Title: Answer cache honours x-ingenium-fresh
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: P1-1-AC5
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C1 U1 F1 K0 V0 I0)
Context pack:
- handover L520 (P1-1 AC5, quote it verbatim in the test docstring)
- docs/build-plan/CODE_MAP.md rows: design orchestration (`_DESIGN_CACHE`), providers
File allow-list:
- apps/api/app/ai_conversation/app_design.py (`_DESIGN_CACHE` read/write sites only)
- apps/api/app/ai_client/** (cache bypass read only)
- apps/api/tests/test_fresh_bypass.py (new)
Goal: A request carrying `x-ingenium-fresh` makes its own LLM calls at every layer (ai_client cache, `_DESIGN_CACHE`, contract cache).
Steps:
1. Find every cache read on the App Studio path (`rg -n "_CACHE|cache_get|ai_cache" app/ai_conversation app/ai_client`)
2. Thread one `fresh` contextvar from the header (existing) to each read; skip the read, still write
3. Fake provider counts calls in the test
Acceptance criteria:
- AC1: P1-1 AC5 verbatim: "the answer cache honours `x-ingenium-fresh` (rerun extend_sales k=3 with `--fresh`; every rep makes its own LLM calls and latency is not 0.5 s)" (offline: 3 runs → 3× the provider calls; live part is run by AS-CONTRACT-EVAL)
- AC2: Without the header the second identical request is a cache hit (no regression)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_fresh_bypass.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
