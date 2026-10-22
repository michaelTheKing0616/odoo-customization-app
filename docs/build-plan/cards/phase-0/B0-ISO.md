# B0-ISO: every API test uses throwaway App DB set before settings import; dev DATABASE_URL fails lo

ID: B0-ISO
Title: every API test uses throwaway App DB set before settings import; dev DATABASE_URL fails lo
Status: done
Phase: 0
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-3-AC1;P0-3-AC2;ARCH-1;REL-7.6
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C0 U1 F2 K1 V0 I0)
Context pack:
- `sed -n '473p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '474p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '189p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '843p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- apps/api/tests/test_b0_iso.py (new)
Goal: Make every AC below true for `B0-ISO` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. With `rg -n` inside the allow-list, find the current symbols this card changes; list each as `current symbol → new symbol (signature)` at the top of the Worker packet.
2. Confirm the oracle tests are red: run the Test plan command → expect failures named after the ACs.
3. Implement AC by AC with the smallest change, reusing existing helpers (write gate, `app/ai_client` + `fence_fields`, studio tokens, shared components). No new abstraction unless used twice.
4. Add tests: for each AC one positive and one negative case with concrete input → expected output. If the card writes to Odoo: an idempotency double-run (second run writes 0) and an undo round-trip.
5. Run the Test plan commands → all green; for web changes also `cd apps/web && pnpm typecheck && pnpm lint` → exit 0.
6. Write the Worker packet (`05_PACKETS.md`). Do not touch files outside the allow-list; do not edit oracle tests.
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: every API test uses its own throwaway database (a per-session Postgres database or schema, or SQLite only where the code is DB-agnostic), set by `apps/api/tests/conftest.py` before the app imports settings. A test that tries to open the dev `DATABASE_URL` fails loudly (same pattern as the host guard). (source: INGENIUM_MASTER_HANDOVER.md L473)
- AC2: running the full suite leaves the dev App DB row counts for `odoo_connections`, `plan_cards`, audit and History tables unchanged (a test asserts before and after counts against a snapshot taken by a wrapper script). (source: INGENIUM_MASTER_HANDOVER.md L474)
- AC3: Production test builds overwrite the dev server's `.next`. `next.config.ts` uses `distDir` only when `INGENIUM_DIST_DIR` or `PLAYWRIGHT_E2E_BUILD=1` is set. Otherwise `next build` writes `output: "standalone"` into the default `.next`, the same folder `next dev` on `:3002` uses. G9 used an isolated build (`INGENIUM_DIST_DIR`, port 3017), but nothing enforces it. See P0-4. (source: INGENIUM_MASTER_HANDOVER.md L189)
- AC4: Rules: tests never touch the dev App DB or any non-`ingenium_` Odoo DB (P0-3, 6.7); no test depends on order; no test calls a real cloud AI unless marked and skipped by default. (source: INGENIUM_MASTER_HANDOVER.md L843)
- AC5: Idempotency: running the same plan twice on a disposable DB writes 0 records the second time
Symbols:
- `apps/api/tests/conftest.py` has `_host_blocked` (the loud-fail pattern). It does not set a throwaway `DATABASE_URL` before settings are imported.
- Dev URL already assigned in tests (those files are not on this allow-list): `postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom`.
- AC2 tables: `odoo_connections`, `plan_cards`, plus the audit and History tables.
Worked example:
- Before any `import` of `app.settings`, conftest sets `DATABASE_URL` to a database on `127.0.0.1` whose name starts with `ingenium_`. A test that then sets `DATABASE_URL` to `postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom` raises before a query. Counts of `odoo_connections`, `plan_cards`, and the audit and History tables on that dev database are the same before and after the suite.
Decision:
| URL | result |
| name starts with `ingenium_`, host is loopback, set in conftest before settings import | the test may open it |
| `127.0.0.1:5433/odoo_custom` (dev App DB) | fail loudly, no query |
| any other name that does not start with `ingenium_` | fail loudly |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_iso.py` → all pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
