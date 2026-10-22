# REG-NP-5B: Schema: 47 sections in apply order

ID: REG-NP-5B
Title: Schema: 47 sections in apply order
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-5B-01;NP-5B-07
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 3 (C0 U0 F1 K0 V1 I1)
Context pack:
- `sed -n '9p' docs/plans/next-phase/cards/T5B_CONFIG.md`
- `sed -n '26,28p' docs/plans/next-phase/cards/T5B_CONFIG.md`
- `sed -n '68,70p' docs/plans/next-phase/cards/T5B_CONFIG.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_5b.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-5B` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Schema: 47 sections in apply order (pressure 6) (source: ledger NP-5B-01, next-phase cards/T5B_CONFIG.md)
- AC2: Custom fields (pressure 3) (source: ledger NP-5B-07, next-phase cards/T5B_CONFIG.md)
Symbols: `SECTIONS`, `load_spec`, `CustomField` in `apps/api/app/config_as_code/loader.py`.
Worked example:
- Example AC1: `len(SECTIONS) == 47`, `SECTIONS[0] == "modules"`, `SECTIONS[-1] == "records"`. Apply order is that tuple, from `modules` through `records`.
- Example AC2: `load_spec("version: 1\nproject: demo\ncustom_fields:\n  - model: res.partner\n    name: note\n")` raises `SpecError` matching `must start with x_`. The same YAML with `name: x_studio_note` raises `SpecError` matching `x_studio_`. `name: x_rc_number` loads.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_5b.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_5b.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
