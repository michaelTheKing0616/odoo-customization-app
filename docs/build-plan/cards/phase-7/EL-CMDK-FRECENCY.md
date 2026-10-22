# EL-CMDK-FRECENCY: Cmd-K learns what you use

ID: EL-CMDK-FRECENCY
Title: Cmd-K learns what you use
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-CMDK
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L1 separate session · Score: 2 (C1 U0 F0 K1 V0 I0)
Context pack:
- apps/web/src/components/command/
File allow-list:
- apps/web/src/lib/frecency.ts (new)
- apps/web/src/lib/frecency.test.ts (new)
Goal: Rank results by frequency and recency per person and database, stored locally.
Steps:
1. Decay with a named half-life constant
Acceptance criteria:
- AC1: recent frequent item ranks first (test)
Test plan:
- `cd apps/web && pnpm vitest run src/lib/frecency.test.ts`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
