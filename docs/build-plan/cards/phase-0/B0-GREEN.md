# B0-GREEN: tsc --noEmit exits 0 (EmailDesigner.tsx:226 errors gone)

ID: B0-GREEN
Title: tsc --noEmit exits 0 (EmailDesigner.tsx:226 errors gone)
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-1-AC1;P0-1-AC2;P0-1-AC3;P0-1-AC4
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 3 (C0 U1 F1 K1 V0 I0)
Context pack:
- `sed -n '460p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '461p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '462p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '459p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/web/src/
- apps/api/tests/
- apps/api/pyproject.toml (do not edit; DEV-PYTEST-RANDOMLY owns pytest-randomly)
- docs/build-plan/FACTS.md
File allow-list:
- apps/web/src/
- apps/api/tests/
- apps/api/pyproject.toml (do not edit; DEV-PYTEST-RANDOMLY owns pytest-randomly)
- apps/api/tests/test_b0_green.py (new)
Goal: Make every AC below true for `B0-GREEN` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output. Reading is the only reading.
2. Write only `apps/api/tests/test_b0_green.py`. Do not edit any other file under `apps/api/tests/`. It fails if `pnpm --filter @odoo-custom/web exec tsc --noEmit` does not exit 0. Name that command in the Worker packet. This file does not replace AC1–AC4.
3. Do not add, remove, or edit pytest-randomly. DEV-PYTEST-RANDOMLY owns it. Do not edit `apps/api/pyproject.toml`. Run `cd apps/api && uv run pytest -q -p no:randomly tests/test_b0_green.py` twice → identical results. Do not edit or delete `apps/web/.next-trial-grok/`, `apps/web/src/app/e2e/trial-xray-grok/`, or `docs/vision-verify/trial-xray/`. They stay untracked.
4. The xfail does not apply to AC1. If `EmailDesigner.tsx` or another file under `apps/web/src/` still fails tsc, fix that file. Do not xfail AC1. Do not xfail a Vitest failure. "Passes in full" means 0 failed.
5. Write the Worker packet. Include the four command counts: tsc, full Vitest, API pytest (not integration), and the CI red-team step. A green oracle file alone is not those ACs.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong. After tsc exits 0, run full Vitest. If it is not 0 failed, STOP-AND-ASK and do not close. Do not xfail it. The logged StockMapPanel error is history, not a waiver. If that panel is the only failure, do not edit it; it belongs to B0-VITEST-STOCKMAP. Any other Vitest failure is the same stop. Do not open that fix on this card.
Acceptance criteria:
- AC1: `pnpm --filter @odoo-custom/web exec tsc --noEmit` exits 0 (the 20 Oct `EmailDesigner.tsx:226` errors are gone). (source: INGENIUM_MASTER_HANDOVER.md L460)
- AC2: web Vitest passes in full (last logged: 1,571 pass with 1 unrelated `StockMapPanel` error). (source: INGENIUM_MASTER_HANDOVER.md L461)
- AC3: API pytest failure count is written down with each failing test's file and a one-line cause. Last logged: 82 failed, 4,898 passed (Oct 20 y). (source: INGENIUM_MASTER_HANDOVER.md L462)
- AC4: Run `tsc`, the full web Vitest suite, the API pytest suite (not integration) and the CI red-team step. Record counts. (source: INGENIUM_MASTER_HANDOVER.md L459)
Symbols:
- `apps/web/src/components/report-designer/EmailDesigner.tsx` (the AC1 `:226` site).
- `apps/web/package.json`: `typecheck` is `tsc --noEmit`; `test` is `vitest run`.
- CI step `AI red-team pack + guards (release gate)` in `.github/workflows/ci.yml` runs `uv run --directory apps/api pytest -q tests/test_ai_shared_client.py tests/test_power_ops_money_lock.py`.
- `pytest-randomly` is owned by DEV-PYTEST-RANDOMLY. This card does not add, remove, or edit it. Deterministic reruns pass `-p no:randomly`.
Worked example:
- `pnpm --filter @odoo-custom/web exec tsc --noEmit` → exit 0. That exit code is the only proof of AC1. Do not xfail AC1.
- `pnpm --filter @odoo-custom/web test` → 0 failed. The parenthetical count stays on the AC2 line. It is history, not a waiver.
- `cd apps/api && uv run pytest -q` (no `-m integration`) → summary counts. Each failure names its file and a one-line cause in the Worker packet. This run is the API-pytest count, not a second `-p randomly` run.
- The red-team command above → its counts in the Worker packet.
- `cd apps/api && uv run pytest -q -p no:randomly tests/test_b0_green.py` twice. A green result here is not AC1–AC4.
Decision:

| Situation | Action |
| AC1 | proved only by `pnpm --filter @odoo-custom/web exec tsc --noEmit` exiting 0 |
| tsc still fails under `apps/web/src/`, including `EmailDesigner.tsx` | fix that file; do not xfail AC1 |
| AC2 "passes in full" | 0 failed |
| only Vitest failure is the logged StockMapPanel error | history, not a waiver; do not edit that panel; belongs to B0-VITEST-STOCKMAP; STOP-AND-ASK; this card does not close |
| any other Vitest failure | not a waiver; do not xfail; do not edit it on this card; STOP-AND-ASK; this card does not close |
| an edit to `apps/api/pyproject.toml`, or adding or removing pytest-randomly | STOP-AND-ASK; DEV-PYTEST-RANDOMLY owns that dependency |
| green `test_b0_green.py` without the four packet counts | AC1–AC4 not met |

Reading:
1. AC1 is proved only by `pnpm --filter @odoo-custom/web exec tsc --noEmit` exiting 0. Step 4's xfail does not apply to AC1. If `EmailDesigner.tsx` or another file under `apps/web/src/` still fails tsc, fix that file. Do not xfail AC1.
2. AC2's parenthetical count stays in the AC line. "Passes in full" means 0 failed. The logged StockMapPanel error is history, not a waiver. If that one error is still the only failure, it belongs to B0-VITEST-STOCKMAP. This card does not close on a failing Vitest suite.
3. Do not add, remove, or edit pytest-randomly, and do not edit `pyproject.toml`. DEV-PYTEST-RANDOMLY owns that dependency. Run the narrow test twice with `-p no:randomly`.
4. `apps/api/tests/test_b0_green.py` does not replace AC1–AC4. The Worker packet must include the four command counts (tsc, full Vitest, API pytest not integration, red-team). A green oracle file alone is not those ACs.
Test plan:
- `cd apps/api && uv run pytest -q -p no:randomly tests/test_b0_green.py` twice → identical results. This green file is not AC1–AC4.
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
