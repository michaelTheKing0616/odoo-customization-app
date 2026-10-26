# DEV-PYTEST-RANDOMLY: dev dependency pytest-randomly

ID: DEV-PYTEST-RANDOMLY
Title: dev dependency pytest-randomly
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: DEV-PYTEST-RANDOMLY
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- apps/api/pyproject.toml
- apps/api/tests/test_reg_np_dev.py
- apps/api/app/code_studio_service.py (read only; line 591)
- docs/build-plan/09_DECISIONS_FOR_TOPE.md (DEC-047)
File allow-list:
- apps/api/pyproject.toml
- uv.lock
- apps/api/tests/test_reg_np_dev.py
Goal: Install pytest-randomly for both API environments and stop the known order leak in the dev regression test.
Steps:
1. Add pytest-randomly (MIT) to the `apps/api` dev group with `uv add --dev`. Do not add hypothesis. Do not hand-edit the lockfile.
2. Comment in `pyproject.toml`, next to that dependency, that a deterministic rerun passes `-p no:randomly`.
3. In `test_reg_np_dev.py`, stop assigning `safety_dependency._REGISTRY` at import. Set it in a fixture and restore the previous value afterward. Do not edit `safety_dependency.py`.
4. Prove `pytest -p randomly` in the main `.venv` and the nf worktree `.venv`. Do not edit any file in the nf worktree. Install the locked version into that venv only.
Acceptance criteria:
- AC1: `cd apps/api && uv run pytest -p randomly -q tests/test_reg_np_dev.py` exits 0 in the main environment, and the same plugin loads in `/Users/temitopeolaitanmichael/Odoo_Customization_App-nf` `.venv`.
- AC2: The run output contains the randomly seed. The pyproject comment documents `-p no:randomly`.
- AC3: The import-time `_REGISTRY` assignment is gone and restored after the module's tests. `test_ac1_negative_refuses_bind_without_state_code_or_execute_kw` passes. Any other order leak outside the allow-list is listed, not edited.
Worked example:
- Before: importing `test_reg_np_dev.py` sets `safety_dependency._REGISTRY` to one route and never puts the old value back.
- After: a later test sees the registry that was in place before this module's fixture.
- `pytest -p no:randomly -q tests/test_reg_np_dev.py` is the deterministic rerun.
Decision: DEC-047 already accepted this dependency. B0-GREEN must not add or remove it. The MagicMock JSON error is fixed in the test. `code_studio_service.py` stays unchanged.
Test plan:
- `cd apps/api && uv run pytest -p randomly -q tests/test_reg_np_dev.py`
- `cd apps/api && uv run pytest -p no:randomly -q tests/test_reg_np_dev.py`
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · DEV-PYTEST-RANDOMLY · command · result counts · label.
Gate: none (DEC-047 accepted; Tope ordered this card).
Rollback: revert the allow-list diff and uninstall the dev dependency.
Definition of Done: Every AC has evidence; no file outside the allow-list changed; the nf worktree's tracked files are untouched.
