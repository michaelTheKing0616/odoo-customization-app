# AS-EVAL-FAIR: Metrics that can steer: ITT, alignment, CIs, built vs folded

ID: AS-EVAL-FAIR
Title: Metrics that can steer: ITT, alignment, CIs, built vs folded
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-FIX-EVAL
Depends on: AS-HARNESS
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F2 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §9
- docs/build-plan/app-studio/ORACLES.md §E
- docs/specs/APP_STUDIO_FIX_PLAN.md (c) items 3-6
- docs/build-plan/CODE_MAP.md rows: eval harness
File allow-list:
- apps/api/evals/v2/metrics.py
- apps/api/evals/v2/score.py (scoring functions only)
- apps/api/evals/v2/align.py (new)
- apps/api/evals/v2/tests/test_metrics_v3.py (new)
Goal: Scores that a renamed-but-correct entity, an unreached brief or a suggestion cannot distort.
Steps:
1. `align.py`: pure-Python Hungarian (n ≤ 30) over design models ↔ gold entities; cost = 1 − (0.6·span-overlap + 0.3·attribute-overlap + 0.1·name n-gram); pairs with cost > 0.8 are not aligned
2. ITT: unreached → coverage 0; `questions` auto-answered with defaults by the harness
3. Counts: built, folded, suggested, left_out; `false_fold_rate`; `promote_recoverable`
4. Paired hierarchical bootstrap (existing `hboot`, `paired`), B=2000, report point + 95% CI
5. Refuse comparisons across different profile fingerprints
Acceptance criteria:
- AC1: Oracles E-01..E-06 pass unmodified
- AC2: Report prints every §8.6 metric with CI
- AC3: Gold without `spans:` falls back to names + attributes and says so in the report
Test plan:
- `cd apps/api && uv run pytest -q evals/v2/tests/test_metrics_v3.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §9. Alignment weights are fixed constants in `align.py` with a one-line reason each. They are not tuned on holdout_fresh (INV-16).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §E (E-01..E-06).
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
