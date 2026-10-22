# REL-STATIC-WRITE: static test: write functions only called from plan runner; no model output to execute_kw/e

ID: REL-STATIC-WRITE
Title: static test: write functions only called from plan runner; no model output to execute_kw/e
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: REL-7.2
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F1 K1 V1 I1)
Context pack:
- `sed -n '814p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '163,199p' apps/api/app/write_gate.py`
- `sed -n '320,336p' apps/api/app/config_as_code/apply.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_static_write_paths.py (new)
- apps/api/tests/static_write_baseline.json (new)
- apps/api/tests/test_rel_static_write.py (new)
Goal: Make every AC below true for `REL-STATIC-WRITE` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output.
2. Write the tests in the allow-list files. Each test must fail if the behaviour were removed: name in the Worker packet the product line whose deletion would make it fail.
3. Run the Test plan command twice (second time `-p randomly` for API once DEC-047 lands) → identical green results.
4. If a test exposes a real defect, do not fix product code: mark it `xfail(strict=True, reason=<new ledger row>)` and report it in the Worker packet.
5. Write the Worker packet.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: AC: there is no code path where model output reaches `execute_kw`, a file write in an exported module, or an install without passing a validator. A static test checks that write functions are only called from the plan runner. (source: INGENIUM_MASTER_HANDOVER.md L814)
- AC2: Elevate: every Odoo write path returns a receipt with an Undo link; the static test fails on a planted write that bypasses the gate
Worked example:
- Pin AC1: the static scan walks `apps/api/app`. `client.execute_kw(model, "write"|"create"|"unlink", ...)` and a module-export file write or an install are allowed only from the baseline caller set, which includes `write_gate.guard_record_write` (its `execute_kw` method is `"read"`, then `save_snapshot`) and `config_as_code.apply.apply_plan` / `changeset.executor.apply` after validation. A planted module `apps/api/app/_planted_bypass.py` whose body is `client.execute_kw("res.partner", "write", [[1], {"name": "x"}])` is a hit. Delete the baseline check and that planted file must fail the test. Model output does not reach those calls without the validator.
- Pin AC2 planted half: the same scan fails when the planted call sits outside the baseline. `guard_record_write` returns the History row from `save_snapshot` (`payload.op == "write"`, `reversible == "yes"` when before-values exist). L814 does not name an Undo URL. If that row has no undo-link field, STOP-AND-ASK. Do not add one.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_rel_static_write.py` → all pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: Every Odoo create/write/unlink goes through `write_gate.py` (layers per handover §2.3: receipt valid 1 h; 428 without a receipt, 403 when refused; `mutation_lock` serialises per connection; anomaly cap 500/h; blast-radius check). Never add a bypass flag or call `execute_kw` directly. Tests drive the public route, not internals. Idempotency: a second identical run writes 0 records (compare record counts + write_date). Pitfall: tests that mock the gate prove nothing; use the dry-run ledger. Rejected: per-page guard copies (the shared Run sheet is the single path, FA A5).
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_rel_static_write.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
