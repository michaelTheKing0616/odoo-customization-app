# EL-X-BAR: Feature Excellence scorecard

ID: EL-X-BAR
Title: Feature Excellence scorecard
Status: todo
Phase: 7
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-BAR
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/elevate/00_ELEVATE.md §1
- handover §5.8-5.14 (states, copy, a11y, dark mode, budgets, visual QA)
File allow-list:
- scripts/excellence_scorecard.py (new)
- docs/build-plan/elevate/route_map.json (new)
- apps/api/tests/test_excellence_scorecard.py (new)
Goal: One command prints a red/green row per §1 check for a feature (`--feature connect`) or all, by running the existing tools and the EL-X tests.
Steps:
1. route_map.json: feature → web routes, components dirs, API routers (from handover §3 'Built' lists)
2. Each check shells out to an existing tool (vitest states preview, axe e2e, jargon guard, token lint, EL-X tests)
3. A check with no tool yet prints `not measured` and counts as red, never green
Acceptance criteria:
- AC1: `--feature connect` prints every §1 check with a result
- AC2: unmeasured checks are red (test)
- AC3: exit code non-zero on any red
Test plan:
- `cd apps/api && uv run pytest -q tests/test_excellence_scorecard.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
