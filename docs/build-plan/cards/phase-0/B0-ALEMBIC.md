# B0-ALEMBIC: test_alembic_drift passes on fresh alembic-only DB; init_db ALTERs removed; one alembic he

ID: B0-ALEMBIC
Title: test_alembic_drift passes on fresh alembic-only DB; init_db ALTERs removed; one alembic he
Status: done
Phase: 0
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC3;ARCH-4
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F1 K1 V0 I2)
Context pack:
- `sed -n '468p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '192p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/api/alembic/
- apps/api/app/db.py
- apps/api/tests/test_alembic_drift.py
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/alembic/
- apps/api/app/db.py
- apps/api/tests/test_alembic_drift.py
- apps/api/tests/test_b0_alembic.py (new)
Goal: Make every AC below true for `B0-ALEMBIC` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. With `rg -n` inside the allow-list, find the current symbols this card changes; list each as `current symbol → new symbol (signature)` at the top of the Worker packet.
2. Confirm the oracle tests are red: run the Test plan command → expect failures named after the ACs.
3. Implement AC by AC with the smallest change, reusing existing helpers (write gate, `app/ai_client` + `fence_fields`, studio tokens, shared components). No new abstraction unless used twice.
4. Add tests: for each AC one positive and one negative case with concrete input → expected output. If the card writes to Odoo: an idempotency double-run (second run writes 0) and an undo round-trip.
5. Run the Test plan commands → all green; for web changes also `cd apps/web && pnpm typecheck && pnpm lint` → exit 0.
6. Write the Worker packet (`05_PACKETS.md`). Do not touch files outside the allow-list; do not edit oracle tests.
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: `test_alembic_drift` passes on a fresh database created only by `alembic upgrade head`, with `init_db` ALTERs disabled. Startup schema ALTERs are removed or made no-ops once a migration covers them; the migration chain from base to head has one head (`alembic heads` prints one line). (source: INGENIUM_MASTER_HANDOVER.md L468)
- AC2: Dangerous sandbox defaults existed. On 19 Oct a test called `run_sandbox_install` against the shared Odoo 20 dev stack and ran `docker compose down -v`, wiping all Odoo 20 databases and the `:5436` app DB. Fixed with isolated `ingenium_sandbox_v<N>` stacks, `assert_isolated()` and a test fixture that blocks real `docker` unless `INGENIUM_LIVE_INFRA=1`. Keep those guards; never weaken them. (source: INGENIUM_MASTER_HANDOVER.md L192)
- AC3: Idempotency: running the same plan twice on a disposable DB writes 0 records the second time
Symbols:
- `init_db(*, bootstrap=True)` and `_ensure_schema_columns()` in `apps/api/app/db.py` (the `ALTER TABLE` statements).
- `tests/test_alembic_drift.py`: `test_baseline_revision_exists` (`ScriptDirectory.get_heads()` length 1), `test_autogenerate_produces_empty_diff_against_head`.
- `cd apps/api && uv run alembic heads` uses `apps/api/alembic.ini`. Revisions live under `apps/api/alembic/`.
- Keep, and do not edit (not on this allow-list): `_no_real_infra_by_default` in `apps/api/tests/conftest.py`; `assert_isolated`, `SandboxGuardError`, `sandbox_stack_for_major`, `SANDBOX_PREFIX` (`ingenium_sandbox_`) in `apps/api/app/sandbox.py`.
Worked example:
- On a new disposable database, run only `cd apps/api && uv run alembic upgrade head` (do not call `init_db`). `uv run alembic heads` prints one line. `uv run pytest -q tests/test_alembic_drift.py` passes.
- `sandbox_stack_for_major(19)` returns. `assert_isolated(SandboxStack(compose=Path("docker-compose.yml"), project="odoo-custom", url="http://127.0.0.1:8069", odoo_service="odoo", odoo_container="odoo20", db_container="odoo20-db", db_host="db", port=8069))` raises `SandboxGuardError`. Inside a pytest test, with `INGENIUM_LIVE_INFRA` unset, `subprocess.run(["docker", "ps"])` raises `RuntimeError` (`real docker is blocked in tests`).
Decision:
| case | action |
| an `_ensure_schema_columns` ALTER is already created by a revision | delete that ALTER or make it a no-op |
| that column is not in any revision | add one new revision (do not edit an applied revision), then delete or no-op the ALTER |
| `INGENIUM_LIVE_INFRA` unset | a docker subprocess raises |
| `INGENIUM_LIVE_INFRA=1` | real docker is allowed; do not point it at a dev stack |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_alembic.py` → all pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: Alembic: one revision per card, additive first (add column/table, backfill, then constrain in a later card); downgrade implemented and tested; never edit an applied revision; `test_alembic_drift` must pass on a fresh alembic-only DB (`init_db` ALTERs removed). Run only against disposable `ingenium_*` App DBs (INV-03).
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_b0_alembic.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
