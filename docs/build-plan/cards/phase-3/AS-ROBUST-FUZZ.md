# AS-ROBUST-FUZZ: Never-errors test suite (written before the code)

ID: AS-ROBUST-FUZZ
Title: Never-errors test suite (written before the code)
Status: todo
Phase: 3
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-ANYBRIEF; AS-RC6
Depends on: AS-PROFILE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C2 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §1 G-TOTAL, §7
- docs/build-plan/app-studio/ORACLES.md §T
File allow-list:
- apps/api/tests/test_studio_outcome_total.py (new)
- apps/api/tests/fakes/fake_llm.py (new)
- apps/api/pyproject.toml (dev dependency `hypothesis` only; MPL-2.0)
Goal: Encode T-01..T-12 as tests that fail today and define done for AS-TOTAL (legacy rows) and AS-V3-WIRE (v3 rows).
Steps:
1. `FakeLLM` with the 12 fault kinds × the legacy and v3 positions in ORACLES §T; it records every prompt, `timeout_s` and the concurrent-call high-water mark (T-10, T-11)
2. Hypothesis strategy for briefs (unicode incl. RTL and emoji, 0-60k chars, CSV/JSON/SQL/code pastes, injections)
3. Drive both routes through FastAPI TestClient with a fake snapshot; no Odoo, no network. The app DB: override `get_db` with a SQLite in-memory session (or the existing test fixture if `tests/conftest.py` provides one; read it first)
4. Mark each row `xfail(strict=True)` with the card that owns it (AS-TOTAL or AS-V3-WIRE, per the Card column), so neither can silently pass
Acceptance criteria:
- AC1: T-01..T-12 exist exactly as written in ORACLES §T
- AC2: Running today: they xfail (proves they test something)
- AC3: Suite runs offline in < 60 s
Test plan:
- `cd apps/api && uv run pytest -q tests/test_studio_outcome_total.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
