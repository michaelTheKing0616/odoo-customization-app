# AS-EXP-X0: Experiment X0: does the expansion leak drive invention?

ID: AS-EXP-X0
Title: Experiment X0: does the expansion leak drive invention?
Status: todo
Phase: 3
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-RC1
Depends on: AS-SRC-BRIEF, AS-HARNESS, AS-EVAL-FAIR
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U2 F1 K0 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §10 X0
- AS-HARNESS usage line in PROGRESS
File allow-list:
- apps/api/evals/v2/experiments/x0.md (new; results only)
Goal: Paired measure of legacy_v1 vs legacy_v1 + `src_brief_only`, on salon_voice-like dev briefs that expand, plus rental_casual and bakery_ng.
Steps:
1. Pick from dev/dev2 the briefs where `not_vague_reason` returns None (they expand); add rental_casual and bakery_ng; at most 6 briefs
2. k=5 per arm with common seeds; disposable v20 DB; `--fresh`
3. Report invented, false folds, coverage ITT and stability with paired CIs
Acceptance criteria:
- AC1: Report written with CIs and the call count (stay within the DEC-040 budget)
- AC2: If invented falls and the CI excludes 0: Orchestrator proposes turning `src_brief_only` on in legacy (Tope yes)
- AC3: Otherwise the report says so; nothing ships
Test plan:
- n/a (measurement card); the Tester re-computes two numbers from the raw JSON
Gate: GATE-A: live LLM spend inside DEC-040; Tester re-computation matches; Reviewer checks no holdout_fresh access.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
