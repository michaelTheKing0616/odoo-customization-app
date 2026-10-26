# REG-NP-BLb: Re-measure the baseline doc

ID: REG-NP-BLb
Title: Re-measure the baseline doc
Status: done
Phase: 0
Priority: P2
Type: docs
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-BL-01
Depends on: REG-NP-BL
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 3 (C1 U0 F1 K1 V0 I0)
Context pack:
- `sed -n '22,40p' docs/plans/next-phase/cards/BL_BASELINE.md`
- docs/plans/next-phase/03_BASELINE.md
- docs/build-plan/FACTS.md
File allow-list:
- docs/plans/next-phase/03_BASELINE.md
Goal: Re-measure the baseline document from commands run on this date. Write only the counts those commands return.
Steps:
1. Count routers with `ls apps/api/app/routers | wc -l`.
2. Alembic head: `cd apps/api && uv run alembic heads`. Read-only.
3. Count API test files with `ls apps/api/tests/test_*.py | wc -l`.
4. `git status --short -- apps packages docker` for untracked product paths. Do not commit or change git history.
5. Correct a row in `03_BASELINE.md` only when a command shows it is wrong. Add the path that proves it. Do not upgrade a SEEDED row to DONE.
6. STOP-AND-ASK: a needed file is outside the allow-list, or a command would write to a database or a forbidden port.
Acceptance criteria:
- AC1: Every exists / seeded / missing row in `03_BASELINE.md` §B is true on this date or corrected with the command output and the date. (source: ledger NP-BL-01)
Test plan:
- The four commands above are re-run and match the rows written in the doc.
Gate: none (no Tope gate). Narrowest check green → Tester PASS → Reviewer PASS.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code]).
Rollback: Revert `docs/plans/next-phase/03_BASELINE.md` only.
Definition of Done: AC1 cites the command output and the date; no file outside the allow-list changed.
