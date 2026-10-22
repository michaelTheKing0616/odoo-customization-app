# REG-NP-DEV: Code Studio a customer can use alone

ID: REG-NP-DEV
Title: Code Studio a customer can use alone
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-DEV-CS
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F1 K1 V1 I1)
Context pack:
- `sed -n '28,40p' docs/plans/next-phase/cards/DEV_MODES_PRODUCTION.md`
- `sed -n '437,458p' apps/api/app/code_studio_service.py`
- `sed -n '14p' apps/api/app/snapshots.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_dev.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-DEV` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Code Studio a customer can use alone (pressure 15) (source: ledger NP-DEV-CS, next-phase cards/DEV_MODES_PRODUCTION.md)
Worked example:
- `POST /api/connections/{id}/code-studio/bind` with `code="import os\nx = 1"`, `confirm_advanced=True`, and `confirm_phrase="I understand the risks"` (`snapshots.CONFIRM_PHRASE`) returns 400 `detail.error == "imports_forbidden"` and does not call `execute_kw`. `bind_code_action` raises before a `state=code` row when `validate_code` / `first_blocked_rule` fails.
- Option A: the zip is produced and not installed (`test_option_a_zip_is_not_installed`).

| Input | Result |
|---|---|
| `import os` | 400 `imports_forbidden`; no `execute_kw` |
| `rec.sudo()` | refused `sudo_pattern`; no `state=code` row |
| `rec.unlink()` | refused `unlink_pattern`; no `state=code` row |
| missing confirm phrase | bind refused before Odoo |
| observer connection | bind refused |
| failed instance probe | bind refused |
| probe + developer role + `dev_tools` + confirm phrase + snapshot | bind allowed |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_dev.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_dev.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: High-risk card without a family note: the Oracle session writes one positive and one negative case per AC before the Worker starts. Invariants that bite here: INV-03 (disposable DBs), INV-13 (validator before any Odoo call), INV-14 (guard paths), INV-15 (honest data). STOP-AND-ASK on any AC that cannot be tested as written.
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_reg_np_dev.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
