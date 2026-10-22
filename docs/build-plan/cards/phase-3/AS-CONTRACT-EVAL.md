# AS-CONTRACT-EVAL: Experiments X1-X4: v3 against legacy, paired

ID: AS-CONTRACT-EVAL
Title: Experiments X1-X4: v3 against legacy, paired
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P1-1-AC3; P1-1-AC4; AS-LIVE-BUDGET
Depends on: AS-HARNESS, AS-EVAL-FAIR, AS-GOLD-SPANS, AS-V3-WIRE, AS-LATENCY
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U2 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §10 X1-X4
- handover L518-519 (P1-1 AC3, AC4)
File allow-list:
- apps/api/evals/v2/experiments/x1_x4.md (new; results only)
Goal: Measure v3 vs legacy_v1 on dev + dev2 with the same seeds, ITT, paired CIs; decide go/no-go for shadow.
Steps:
1. X1 ledger reliability (offline validators on 28×3 samples: verbatim rate, orphan-clause rate, chunk thresholds); then replay the 28 recordings through compile and check `python_needed` = 0 except option_a rows (moved here from AS-COMPUTE-MATRIX)
2. X2 paired k=3 per arm on a disposable v20 DB; then a k=5 subset of 10 briefs on 17-19. Report false folds with and without promote-recoverable, and overflow_unsure counts
3. X3 stability k=5 on 10 briefs
4. X4 latency/cost from the harness meter: p95, time to first provisional row, calls, input/output tokens, $ and 429 count per brief (not "round trips")
5. Stop at the DEC-040 call budget; report the spend
Acceptance criteria:
- AC1: P1-1 AC3 verbatim: "the offline check and a subset k=5 re-record on dev plus dev2 run on a disposable v20 DB with the same seeds for both arms. Report with hierarchical bootstrap 95 percent CIs."
- AC2: P1-1 AC4 verbatim: "gates (from APP_STUDIO_FIX_PLAN): invented models per run down with CI upper bound below the baseline; false_fold_rate at most 0.10 (point and CI upper); ITT coverage drop above 0.05 on at most one brief; exclusion recall stays 1.0."
- AC3: The kill rules of Pack §10 are applied and written down
Test plan:
- Tester recomputes 3 headline numbers from the raw JSON
Gate: GATE-A: Tope approves the DEC-040 budget before the first live call; Tester recomputation matches; Reviewer confirms holdout_fresh untouched.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
