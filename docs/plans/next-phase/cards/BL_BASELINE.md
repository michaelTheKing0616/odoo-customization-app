# Cards — BL baseline

Self-contained. Load this file and the "Read first" lines on your card. Card format, status legend, and routing are in `../14_WORK_CARDS.md`. The shared rules are repeated here so you do not need to open it.

**Shared do-not (every card):** do not weaken a lock in `../01_LOCKS_DECISIONS_CONFLICTS.md`; do not log secrets; do not run against a customer database; do not vendor `odoo-config-agent` or read Enterprise Studio source; do not assume uvicorn on `:8001` reloads (restart it and say so); do not delete, skip, or loosen a test to go green; no live LLM in a PR-blocking test; no edits outside "Change".

**Shared commands:**

```bash
# API tests (local venv; CI uses `uv run --directory apps/api pytest -q`)
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/<file>.py
# Lint a new module (report-only slot, BL-04)
uv run --directory apps/api --extra dev ruff check app/<module>.py && uv run --directory apps/api --extra dev mypy app/<module>.py
# Migrations
cd apps/api && ../../.venv/bin/alembic heads
```

**Build log:** append the block in `../11_LOGGING_AUDIT_OBSERVABILITY.md` §1 to `docs/plans/INGENIUM_NEXT_PHASE_PROGRESS.md`.

---

### BL-01 — Re-verify the baseline
- **Status:** DONE 2026-10-02 (re-measured in `../03_BASELINE.md` §B). Re-run at the start of any track that has been idle for a week.
- **depends_on:** none
- **Pressure:** C1 U0 F1 K1 V0 I0 +0 = 3 → cheap model or a shell script
- **Read first:** `../03_BASELINE.md` (whole file).
- **Change:** `../03_BASELINE.md` only.
- **Steps:**
  1. Count routers: `ls apps/api/app/routers | wc -l`.
  2. Alembic head: `cd apps/api && ../../.venv/bin/alembic heads`.
  3. Count API test files: `ls apps/api/tests/test_*.py | wc -l`.
  4. List untracked product modules: `git status --short apps packages docker | rg '^\?\?'`.
  5. Run the new-module test set from `03` §B and record pass/fail.
  6. Correct any row that is wrong. Add the path that proves it.
- **Acceptance:** [ ] every exists / seeded / missing row is true or corrected with a path; [ ] the test run result is written with its date.
- **Negative tests:** none (docs). Do not upgrade a SEEDED row to DONE without a progress-log gate entry.
- **Do not:** write feature code.
- **Log / audit:** build log only.
- **Rollback:** `git checkout -- docs/plans/next-phase/03_BASELINE.md`.
- **Evidence of done:** progress-log entry with the four counts and the pytest summary line.

### BL-02 — Request-id middleware
- **Status:** DONE (progress log 2026-10-02 "baseline cards BL-02 through BL-06"). Code `apps/api/app/request_id.py`; tests `tests/test_request_id.py` (3).
- **depends_on:** BL-01
- **Pressure:** C1 U0 F2 K2 V1 I0 +0 = 6 → Grok 4.7 standard
- **Read first:** `apps/api/app/request_id.py`, `apps/api/app/main.py` (middleware block), `../11_LOGGING_AUDIT_OBSERVABILITY.md` §3.
- **Change:** none unless a regression is found.
- **Acceptance:** [x] every response sets `X-Request-Id`; [x] an unsafe incoming id is not echoed; [ ] the audit chain row stores it in `run` when no bot run exists (owned by T6-03).
- **Negative tests:** `test_request_id.py` unsafe-header case.
- **Commands:** `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_request_id.py`
- **Rollback:** remove the middleware registration in `main.py`.
- **Evidence:** 3 passed.

### BL-03 — JSON log formatter
- **Status:** DONE. Code `apps/api/app/logging_config.py`; tests `tests/test_logging_config.py` (5).
- **depends_on:** BL-02
- **Pressure:** C1 U0 F1 K1 V0 I0 +0 = 3 → cheap
- **Acceptance:** [x] one JSON line with `ts`, `level`, `logger`, `msg`, `request_id`; [x] a line containing `password` or `api_key` is dropped; [x] a broken format string does not raise.
- **Known limit:** it is an extra handler, not a replacement for every existing handler. A later card may switch the root handler; this card does not.
- **Commands:** `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_logging_config.py`
- **Rollback:** revert the handler registration.

### BL-04 — Lint and type slots
- **Status:** DONE for the slot. `apps/api/scripts/lint_new_modules.sh` lints only `request_id.py` and `logging_config.py`. `apps/web/package.json` has `"typecheck": "tsc --noEmit"`; it is not in CI because of 13 pre-existing errors (`BL04_LINT_SLOT.md`).
- **depends_on:** BL-01
- **Pressure:** C1 U0 F1 K1 V0 I1 +0 = 4 → cheap
- **Open delta (do this when you touch the file list):** every new module a later card creates must be appended to `FILES` in `lint_new_modules.sh` and pass `ruff` and `mypy`. Cards in this pack say so in their do-not list.
- **Do not:** mass-reformat existing code; do not add `tsc` to CI until the 13 errors are fixed in their own card (UI-F00 in `T7_UI_FOUNDATION.md`).
- **Rollback:** revert the script.

### BL-05 — ADR folder
- **Status:** DONE. `docs/adr/ADR-01.md`–`ADR-14.md` exist as stubs. ADR-02 stays open (D8). ADR-14 records D11.
- **Pressure:** 2 → cheap
- **Acceptance:** [x] 14 files; [ ] each ADR moves from stub to accepted in its own ADR card in `T8_ENGINE_CORE.md`.

### BL-06 — verified-facts and recon
- **Status:** DONE (files exist: `docs/verified-facts.md`, `docs/recon.md`). GATE-P0-01 has a home. GATE-P0-04 (JSON-2, API key, version, get_view, read_group facts) is PARTIAL until T2-J1 records a live `/doc`.
- **Pressure:** C1 U1 F1 K2 V1 I0 +0 = 6 (scored 8 when opened) → Grok standard
- **Acceptance:** [x] each fact marked verified or unverified; [ ] GATE-P0-04 facts verified on an instance (operator, with T2-J1).
- **Negative:** no invented Odoo signature. A fact with no command or URL stays `unverified`.

### BL-07 — Fix the MCP scan so it ignores tool caches
- **Status:** OPEN. Found 2026-10-02 while writing this pack: `tests/test_no_mcp_write.py::test_no_mcp_execute_kw_or_call_model_method_writes` fails because it scans `apps/api/.pytest_cache/v/cache/nodeids`, which contains the test's own name. 256 of 257 tests in the new-module set pass; this is the one failure.
- **depends_on:** none
- **Pressure:** C1 U0 F1 K1 V0 I0 +0 = 2 → cheap
- **Read first:** `apps/api/tests/test_no_mcp_write.py` (whole file, about 55 lines; see `_skip_path`).
- **Change:** `apps/api/tests/test_no_mcp_write.py` only.
- **Steps:**
  1. Add `.pytest_cache`, `__pycache__`, `.mypy_cache`, `.ruff_cache`, and `node_modules` to the directories `_skip_path` ignores.
  2. Do not add an allowlist entry for a product file. The fix is about caches, not about code.
  3. Run the test with the cache present (run pytest once without `-p no:cacheprovider` first, then again).
- **Acceptance:** [ ] the test passes with a populated `.pytest_cache`; [ ] the test still fails on a planted line `mcp.execute_kw("res.partner", "write", ...)` in a temp file under `apps/api/app/` (write the temp file in the test via `tmp_path` monkeypatching the scan root, or check by hand and delete it).
- **Negative tests:** the planted write still fails the scan.
- **Commands:** `cd apps/api && ../../.venv/bin/python -m pytest -q tests/test_no_mcp_write.py && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_no_mcp_write.py`
- **Do not:** widen `_line_allowed`; do not skip `apps/api/app/`.
- **Log / audit:** build log.
- **Rollback:** revert the test file.
- **Evidence:** both commands green, plus the planted-line check.

### BL-08 — Commit hygiene for the uncommitted slices
- **Status:** OPEN. As of 2026-10-02 the new modules (`changeset/`, `llm_gateway/`, `agent_runtime/`, `bots/`, `worker_bot/`, `bridge/`, `config_as_code/`, `odoo20/`, `offline/`, `skills/`, `progress/`, six migrations, 47 test files) are untracked. Nothing in this pack can be "merged" until they are committed.
- **depends_on:** BL-07
- **Pressure:** C2 U0 F2 K1 V0 I1 +0 = 6 → Grok standard, but **Tope approves the commit** (repo rule: confirm before pushing).
- **Steps:**
  1. Propose small commits by track (one per directory plus its tests and migration). Do not commit `.cache/`, `.pnpm-store/`, or the `0001-*.patch` files.
  2. Show the plan to Tope. Commit only after an explicit yes.
- **Acceptance:** [ ] `git status --short` shows no untracked product module; [ ] each commit's tests pass on their own.
- **Do not:** force-push; do not squash unrelated tracks into one commit; do not push without a yes.
- **Rollback:** `git reset --soft HEAD~N` before push.
