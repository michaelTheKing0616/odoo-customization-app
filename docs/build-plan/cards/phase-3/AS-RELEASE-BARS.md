# AS-RELEASE-BARS: Release report against every §8.6 bar

ID: AS-RELEASE-BARS
Title: Release report against every §8.6 bar
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-8.6-COV; AS-8.6-INV; AS-8.6-FOLD; AS-8.6-RECALL; AS-8.6-STAB; AS-8.6-EXCL; AS-8.6-LAT; AS-8.6-COST; AS-8.6-RATING; AS-8.6-INSTALL; AS-CRAFT-EVAL
Depends on: AS-CONTRACT-EVAL, AS-SHADOW, AS-CRAFT-SCORE, AS-CRAFT-PARITY
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- handover §8.6 table (L928-939)
- experiments/x1_x4.md
File allow-list:
- apps/api/evals/v2/experiments/release_bars.md (new)
Goal: One table: each bar, today's value with CI, pass/fail, and the evidence path; Tope's rating of the five headline briefs recorded.
Steps:
1. Collect from experiment reports; install-clean from the live 17-20 harness (P1-3)
2. Tope rates the five headline outputs 1-10 (DEC-035 briefs)
Acceptance criteria:
- AC1: Every §8.6 row present with evidence or 'not measured' (never blank)
- AC2: Ratings recorded with date
- AC3: Craft score row (AS-CRAFT-SCORE): ≥ 95% of applicable idioms pass per brief on the module lane, on 17-20
- AC4: Stock-parity row (AS-CRAFT-PARITY): 0 gaps versus the stock exemplar of the same shape, on the module lane
Test plan:
- Tester checks each number against its source file
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
