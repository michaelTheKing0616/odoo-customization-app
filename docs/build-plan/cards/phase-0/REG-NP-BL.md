# REG-NP-BL: Re-verify the baseline

ID: REG-NP-BL
Title: Re-verify the baseline
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-BL-02;NP-BL-03;NP-BL-04;NP-BL-05;NP-BL-06
Depends on: B0-INV
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F1 K0 V0 I0)
Context pack:
- `sed -n '22,80p' docs/plans/next-phase/cards/BL_BASELINE.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_bl.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-BL` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Split to REG-NP-BLb on 2026-10-22. This card does not pin it. Re-verify writes `docs/plans/next-phase/03_BASELINE.md`, outside this allow-list. Do not freeze router, test-file, or alembic counts here.
- AC2: Request-id middleware (pressure 6) (source: ledger NP-BL-02, next-phase cards/BL_BASELINE.md)
- AC3: JSON log formatter (pressure 3) (source: ledger NP-BL-03, next-phase cards/BL_BASELINE.md)
- AC4: Lint and type slots (pressure 4) (source: ledger NP-BL-04, next-phase cards/BL_BASELINE.md)
- AC5: ADR folder (pressure 2) (source: ledger NP-BL-05, next-phase cards/BL_BASELINE.md)
- AC6: verified-facts and recon (pressure 6) (source: ledger NP-BL-06, next-phase cards/BL_BASELINE.md)
Example for AC1: none. STOP-AND-ASK. Re-verify writes `docs/plans/next-phase/03_BASELINE.md`, which is outside this allow-list. Do not freeze today's router, test-file, or alembic counts.
Symbols: `RequestIdMiddleware`, `REQUEST_ID_HEADER`, `_resolve_request_id` in `apps/api/app/request_id.py`. `JsonLogFormatter`, `SensitiveLogFilter` in `apps/api/app/logging_config.py`. `apps/api/scripts/lint_new_modules.sh`. `docs/adr/ADR-01.md` through `docs/adr/ADR-14.md`. `docs/verified-facts.md`, `docs/recon.md`.
Worked example:
- Example AC2: a response from `RequestIdMiddleware` sets `X-Request-Id`. Incoming `trace_abc123-XYZ_99` is echoed. Incoming `has space inside` and `prefix-Bearer-suffix` are replaced with `uuid.uuid4().hex` (32 lowercase hex chars).
- Example AC3: `JsonLogFormatter.format` returns one JSON object with keys `ts`, `level`, `logger`, `msg`, `request_id`. `SensitiveLogFilter.filter` returns `False` when the message contains `password` or `api_key`. A record whose `getMessage` raises becomes `msg="[unformattable]"` and does not raise.
- Example AC4: `apps/api/scripts/lint_new_modules.sh` names `app/request_id.py` and `app/logging_config.py`. `apps/web/package.json` script `typecheck` is `tsc --noEmit`.
- Example AC5: `docs/adr/ADR-01.md` through `docs/adr/ADR-14.md` exist (14 files).
- Example AC6: `docs/verified-facts.md` and `docs/recon.md` exist. A fact with code evidence is tagged `[verified]` (request-id middleware). A fact with no command or URL stays `[unverified]` (production header rewriting).
Suspects, not pins (2026-10-22): `docs/verified-facts.md` §4 says no `docker-compose.odoo20.yml` exists, and that file is in `docker/`. `docs/adr/ADR-02.md` is accepted while `docs/recon.md` still tags D8 as open.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_bl.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_bl.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
