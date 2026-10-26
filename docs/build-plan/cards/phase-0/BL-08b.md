# BL-08b: Changeset tests pass on their own

ID: BL-08b
Title: Changeset tests pass on their own
Status: done
Phase: 0
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-BL-08b
Depends on: BL-08
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/cards/phase-0/BL-08.md
- apps/api/app/changeset/setting_ops.py
- apps/api/tests/test_config_apply.py
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/app/changeset/setting_ops.py
Goal: Make the two changeset tests named below pass. Do not edit those tests. Do not edit `docs/handoff/COMMIT_PLAN.md`.
Steps:
1. Read `_FIELD_NAME` in `setting_ops.py`. The key `sale.auto_done` fails it, so `setting_values` raises `DispatchError`.
2. Change only that file so both tests pass. Do not rename the key inside the tests. Decision 2026-10-23: `setting.set` accepts one dotted key `module.field`. Each side uses the existing field character class. `company.update` stays on the undotted `_FIELD_NAME`. Do not allow a space, `..`, or more than one dot.
3. STOP-AND-ASK: the fix would need a file outside this allow-list.
Acceptance criteria:
- AC1: `cd apps/api && uv run pytest -q -p no:randomly tests/test_config_apply.py::test_production_requires_approval_for_everything tests/test_config_apply.py::test_read_back_verification_flags_ignored_writes` passes. (source: BL-08 AC2, held 2026-10-22)
Test plan:
- The command in AC1 → pass.
Gate: none. Narrowest named test green → Tester PASS → Reviewer PASS.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code]).
Rollback: Revert `apps/api/app/changeset/setting_ops.py` only.
Definition of Done: AC1 is green; no file outside the allow-list changed.
