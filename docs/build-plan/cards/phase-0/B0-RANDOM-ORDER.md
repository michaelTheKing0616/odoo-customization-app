# B0-RANDOM-ORDER: suite passes twice in random order (or reverse file order once)

ID: B0-RANDOM-ORDER
Title: suite passes twice in random order (or reverse file order once)
Status: todo
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC2;REL-7.6
Depends on: B0-INV, B0-GREEN
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 3 (C0 U1 F1 K1 V0 I0)
Context pack:
- `sed -n '467p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '843p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- apps/api/tests/test_b0_random_order.py (new)
Goal: Make every AC below true for `B0-RANDOM-ORDER` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output.
2. Write the tests in the allow-list files. Each test must fail if the behaviour were removed: name in the Worker packet the product line whose deletion would make it fail.
3. Run the Test plan command twice (second time `-p randomly` for API once DEC-047 lands) → identical green results.
4. If a test exposes a real defect, do not fix product code: mark it `xfail(strict=True, reason=<new ledger row>)` and report it in the Worker packet.
5. Write the Worker packet.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: the suite passes twice in a row with `pytest -p randomly` (or the repo's own random-order option), proving no order dependence. If no random-order plugin is installed, run the suite in reverse file order once. (source: INGENIUM_MASTER_HANDOVER.md L467)
- AC2: Rules: tests never touch the dev App DB or any non-`ingenium_` Odoo DB (P0-3, 6.7); no test depends on order; no test calls a real cloud AI unless marked and skipped by default. (source: INGENIUM_MASTER_HANDOVER.md L843)
Symbols:
- `pytest-randomly` is not in `apps/api/pyproject.toml` `[dependency-groups] dev` (B0-GREEN adds it, DEC-047). `apps/api/pytest.ini` has no random-order `addopts`.
- Existing order-leak fixture: `_isolate_ai_process_state` in `apps/api/tests/conftest.py`.
Worked example:
- When `pytest-randomly` is installed: `cd apps/api && uv run pytest -q -p randomly` twice. Both finish green.
- When it is not installed: `cd apps/api && uv run pytest -q $(find tests -name 'test_*.py' | sort -r)` finishes green.
Decision:
| `pytest-randomly` installed | proof |
| yes | the `-p randomly` command twice, both green |
| no | reverse file order, once, green |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_random_order.py` → all pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
