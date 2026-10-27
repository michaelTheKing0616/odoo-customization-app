# B0-RANDOM-ORDER-b: order leaks fixed at the source

ID: B0-RANDOM-ORDER-b
Title: order leaks fixed at the source, sqlite engine first
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-LEAK-SQLITE
Depends on: B0-RANDOM-ORDER
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/cards/phase-0/B0-RANDOM-ORDER.md (List (b), 63 nodes)
- apps/api/tests/conftest.py
- apps/api/tests/test_reg_np_gnd.py
- apps/api/tests/test_reg_np_t6.py
File allow-list:
- apps/api/tests/conftest.py
- apps/api/tests/test_reg_np_gnd.py
- apps/api/tests/test_reg_np_t6.py
- the one extra test file bisection names, teardown only
Goal: Make every AC below true for `B0-RANDOM-ORDER-b` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Do not rerun the red random suite as a loop. Start from `sqlite3.OperationalError: no such table: users` on seed `1766196243`.
2. Find the first test that leaves `app.db.engine` on SQLite. Bisect with `pytest -p randomly -p randomly_seed=1766196243`, or log the engine URL from a session-scoped autouse check. Known import-time swaps: `test_reg_np_gnd.py` and `test_reg_np_t6.py`. `conftest.py` restores the session engine only for tests that are not `no_app_db` and not in `_ENGINE_SWAP_MODULES`.
3. Fix that leak once at the source (fixture teardown, global, cache, or DB state). No xfail and no skip.
4. Re-run all of list (b) before looking for a second cause. Group later fixes by root cause, not by file.
5. Random order becomes the default only after three random seeds all pass. Until then the default stays `-p no:randomly`.
Acceptance criteria:
- AC1: with seed `1766196243`, no list (b) node fails with `no such table: users` after the one teardown.
- AC2: every list (b) node passes in one process under that seed. A node that still fails is a new root cause, not another patch on the same sqlite swap.
- AC3: shuffle stays opt-in until three seeds pass (`-p randomly` or `PYTEST_ADDOPTS='-p randomly'`).
Symbols:
- List (b) is the 63 pass-alone nodes on `B0-RANDOM-ORDER`. Do not edit list (a). Do not edit `test_nf_*`, `app/bot_verify`, scans, assist, or `migration_studio`.
- Full-suite logs go to `/tmp/B0-RANDOM-ORDER-b_seed<seed>.txt`. Read the summary line only.
Worked example:
- `cd apps/api && uv run pytest -q -p randomly -p randomly_seed=1766196243 <list (b) node ids> > /tmp/B0-RANDOM-ORDER-b_seed1766196243.txt 2>&1`
Decision:
2026-10-23 opened from the split. The red `-p randomly` run is expected and is not re-looped on the parent. Hypothesis, not yet bisected: one import swaps `app.db.engine` / `SessionLocal` onto SQLite and a later test uses that engine. Confirm with the seed before editing.
2026-10-24 parent merged `9e8e360b`. Worker starts from that conftest. Seed invocation is `-p randomly --randomly-seed=1766196243` (`-p` loads a plugin, so `-p randomly_seed=` is not the seed flag). Postgres is the existing container `ingenium-b0-pg54329` on 127.0.0.1:54329.
2026-10-24 closed. List (b) under that seed: 63 passed, 15 warnings in 26.70s. No `no such table: users`. Allow-list diff empty. `pytest.ini` still `-p no:randomly`. Reviewer APPROVE. Shuffle stays off.
Test plan:
- One fixed-seed run of all list (b) nodes, log file as above, summary line green.
- Do not turn `-p randomly` on in `pytest.ini` in this card until two further seeds also pass.
Common mistakes: xfail or skip for a leak; editing an NF file; restarting `:8001`; a second full random suite before list (b) is green.
Gate: none (no Tope gate).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label.
Rollback: Revert this card's diff (allow-list files only).
Definition of Done: AC1–AC3 have evidence; no file outside the allow-list changed; Status set to done.
