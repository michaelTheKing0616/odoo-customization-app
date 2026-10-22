# AS-HOLDOUT-RUN: Final proof on the sealed holdout (once)

ID: AS-HOLDOUT-RUN
Title: Final proof on the sealed holdout (once)
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-HOLDOUT; AS-FIX-6
Depends on: AS-AUTHZ-DEFAULT
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C0 U1 F2 K0 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §10 X6
- handover §3.3 L233
File allow-list:
- apps/api/evals/v2/experiments/holdout_fresh_final.md (new)
Goal: Run holdout_fresh once with `EVAL_UNSEAL=yes`, k=3, fresh, disposable v20; report every bar.
Steps:
1. Tope says go in the current message
2. Verify the MANIFEST hash before the run
3. Right after the unseal and before scoring, run the AS-PROMPT-CONTRACT 6-gram few-shot test against the holdout briefs; a hit voids the run and is reported to Tope
4. Single run; no re-runs to 'improve' numbers
Acceptance criteria:
- AC1: Manifest hash matches handover L233
- AC2: Report has every §8.6 bar
- AC3: Exactly one run logged
Test plan:
- Tester verifies the manifest hash and the single-run log
Gate: GATE-R: Tope's go; Reviewer confirms no earlier read of holdout_fresh in session logs.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
