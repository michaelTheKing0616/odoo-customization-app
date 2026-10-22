# EL-X-AUTHZ: Every API route declares who may call it

ID: EL-X-AUTHZ
Title: Every API route declares who may call it
Status: todo
Phase: 7
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-SEC
Depends on: EL-X-BAR
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C1 U1 F2 K1 V1 I1)
Context pack:
- apps/api/app/main.py (router registration)
- apps/api/app/auth.py, apps/api/app/workspace_auth.py (existing dependencies)
- AGENTS.md App API auth (Phase 7)
File allow-list:
- apps/api/tests/test_route_authz.py (new)
- apps/api/tests/authz_public_routes.json (new; each public route with a reason)
- apps/api/tests/authz_baseline.json (new; ratchet)
Goal: A test walks `app.routes` and fails on any route without an access dependency, unless it is listed as public with a reason.
Steps:
1. Collect dependencies recursively per route (router-level and endpoint-level)
2. Ratchet: today's failures are written once to the baseline file named in the allow-list; the test fails on any new failure and on any baseline entry that now passes (so the list only shrinks). Each feature's EL-BAR card removes its entries.
Acceptance criteria:
- AC1: a planted route with no dependency fails the test
- AC2: public list entries each carry a non-empty reason
- AC3: baseline entries listed in the Tester packet with owning feature
Test plan:
- `cd apps/api && uv run pytest -q tests/test_route_authz.py`
Elite design notes: Detection only; fixes land in each feature's EL-BAR card. Never weaken an existing dependency to make the test pass.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-X-AUTHZ-1 planted unguarded route → fail; EL-X-AUTHZ-2 public route without reason → fail
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
