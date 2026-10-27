# REG-NP-T1b: Option A sandbox install_ready

ID: REG-NP-T1b
Title: Option A sandbox install_ready
Status: todo
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: NP-T1-F3
Depends on: REG-NP-T1
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 8 (C2 U1 F2 K1 V2 I0)
Context pack:
- `sed -n '551,620p' apps/api/app/ai_option_a_quality.py`
- docker/docker-compose.ingenium-sandbox.yml
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_t1b.py (new)
Goal: Pin one real Option A sandbox run. Record the actual `install_ready` result. Do not invent it.
Steps:
1. Read the context pack. The isolated project is `ingenium_sandbox_v19` on port 18119. Do not use ports 8069–8073, 3002, 8001, 8002, 8012, 5433, 5436, or 11434.
2. If that stack is down, start only that compose project. Stop it at the end if this card started it. Drop only a database this card created.
3. Run one Option A module with `run_tests=True`. Write the actual `install_ready` value, `prove_status`, and log path into this card under `captured <date> from current behaviour`.
4. Pin that captured pair in the new test. If `install_ready` is not true, do not force it true. Stop and report the actual status as a suspected bug.
5. STOP-AND-ASK: a needed file is outside the allow-list; the run would touch a non-`ingenium_` database or a forbidden port.
Acceptance criteria:
- AC1: One Option A module is run with `run_tests=True` on `ingenium_sandbox_v19`. The card records the actual `install_ready` value and the log path. (source: ledger NP-T1-F3)
Test plan:
- `cd apps/api && uv run pytest -q -p no:randomly tests/test_reg_np_t1b.py` → pass
Gate: none (no Tope gate). Narrowest named test green → Tester PASS → Reviewer PASS.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]).
Rollback: Revert `apps/api/tests/test_reg_np_t1b.py`. Drop only the `ingenium_*` database this card created.
Definition of Done: AC1 has a captured input and output from a real run; the test matches that capture; no file outside the allow-list changed.
Elite design notes: This is a live sandbox prove, not a product change. The pin is whatever the run returns. A skipped stack is not a pass.
Oracle tests: `test_reg_np_t1b.py` is red until the card contains a `captured <date> from current behaviour` line with `install_ready` and a log path. The test asserts that recorded pair and fails if the sandbox call is skipped.

captured 2026-10-22 from current behaviour
- install_ready: absent (not true). prove_status: proved. log path: `.cache/reg_np_t1b_prove_19.log`

code 2026-10-27: `prove_option_a_in_sandbox` sets `install_ready` true only when `prove_status` is `proved`. The 2026-10-22 capture above is the run from before that key existed (`out_keys` omitted it). The pin test still checks that log. A new live sandbox run was not taken on this pass.
