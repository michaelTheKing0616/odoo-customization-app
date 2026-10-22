# B0-JUNK: scripts/cleanup_test_connections.py dry-run default; --apply after Tope yes; pg_dump -Fc f

ID: B0-JUNK
Title: scripts/cleanup_test_connections.py dry-run default; --apply after Tope yes; pg_dump -Fc f
Status: todo
Phase: 0
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-3-AC3;P0-3-AC4;ARCH-1
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 5 (C0 U1 F1 K1 V0 I2)
Context pack:
- `sed -n '475p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '476p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '189p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- docs/build-plan/FACTS.md
File allow-list:
- scripts/cleanup_test_connections.py (new)
- apps/api/tests/test_b0_junk.py (new)
Goal: Make every AC below true for `B0-JUNK` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. With `rg -n` inside the allow-list, find the current symbols this card changes; list each as `current symbol → new symbol (signature)` at the top of the Worker packet.
2. Confirm the oracle tests are red: run the Test plan command → expect failures named after the ACs.
3. Implement AC by AC with the smallest change, reusing existing helpers (write gate, `app/ai_client` + `fence_fields`, studio tokens, shared components). No new abstraction unless used twice.
4. Add tests: for each AC one positive and one negative case with concrete input → expected output. If the card writes to Odoo: an idempotency double-run (second run writes 0) and an undo round-trip.
5. Run the Test plan commands → all green; for web changes also `cd apps/web && pnpm typecheck && pnpm lint` → exit 0.
6. Write the Worker packet (`05_PACKETS.md`). Do not touch files outside the allow-list; do not edit oracle tests.
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: a cleanup script (`scripts/cleanup_test_connections.py`, dry run by default) lists rows that match test-fixture patterns and have never been used by a real session, prints counts, and deletes only with `--apply` after Tope's yes. Back up the App DB with `pg_dump -Fc` first. (needs Tope) (source: INGENIUM_MASTER_HANDOVER.md L475)
- AC2: after cleanup, `GET /api/connections` returns only real connections, and the count is reported to Tope. (source: INGENIUM_MASTER_HANDOVER.md L476)
- AC3: Production test builds overwrite the dev server's `.next`. `next.config.ts` uses `distDir` only when `INGENIUM_DIST_DIR` or `PLAYWRIGHT_E2E_BUILD=1` is set. Otherwise `next build` writes `output: "standalone"` into the default `.next`, the same folder `next dev` on `:3002` uses. G9 used an isolated build (`INGENIUM_DIST_DIR`, port 3017), but nothing enforces it. See P0-4. (source: INGENIUM_MASTER_HANDOVER.md L189)
- AC4: Idempotency: running the same plan twice on a disposable DB writes 0 records the second time
Symbols:
- New `scripts/cleanup_test_connections.py`. No flag means dry-run. `--apply` deletes.
- P0-3 evidence names (examples of fixture rows): `Matrix conn`, `Other client`, `Granted client`, `code-studio`, `fake-m3`, `Alice victim conn`, `fake-ops`, `role-matrix`.
Worked example:
- `python3 scripts/cleanup_test_connections.py` prints a count and deletes 0 rows.
- `python3 scripts/cleanup_test_connections.py --apply` with no yes in Tope's current message deletes 0 and exits non-zero.
- After that yes: `pg_dump -Fc` of the App DB finishes, then `--apply` deletes only rows that match test-fixture patterns and have never been used by a real session. `GET /api/connections` returns the remaining connections, and that count is in the Worker packet.
Decision:
| invocation | effect |
| no `--apply` | print counts, delete 0 |
| `--apply` without Tope's yes in the current message | delete 0 |
| `--apply` after that yes | `pg_dump -Fc` first, then delete only the matching unused rows |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_junk.py` → all pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: D (destructive or non-disposable step needs Tope's explicit yes; `pg_dump -Fc` first). GATE-D recorded at prep: do not run this script, `--apply`, `pg_dump`, or any delete until Tope's explicit yes in the current message. Writing the dry-run script is in scope. Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
