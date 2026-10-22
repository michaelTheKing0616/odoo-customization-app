# REG-NP-T1: Pre-flight PF-1 to PF-6

ID: REG-NP-T1
Title: Pre-flight PF-1 to PF-6
Status: todo
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-T1-PF;NP-T1-F0;NP-T1-INST;NP-T1-A1;NP-T1-A2;NP-T1-A3;NP-T1-A4;NP-T1-B1;NP-T1-B2;NP-T1-B3;NP-T1-C1;NP-T1-C2;NP-T1-D1;NP-T1-D2;NP-T1-D3;NP-T1-E1;NP-T1-E2;NP-T1-F1;NP-T1-F2;NP-T1-F3;NP-T1-RET;NP-T1-GATE
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 5 (C2 U0 F1 K0 V1 I1)
Context pack:
- `sed -n '27,212p' docs/plans/next-phase/cards/T1_SCHEMA_GROUNDING.md`
- `sed -n '33,36p' apps/api/app/ai_generate_ir.py`
- `sed -n '156,160p' apps/api/app/ai_generate_ir.py`
- `sed -n '33,50p' apps/api/app/ai_schema_client.py`
- `sed -n '98,103p' apps/api/app/ai_schema_client.py`
- `sed -n '150,151p' apps/api/app/ai_schema_client.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_t1.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-T1` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Pre-flight PF-1 to PF-6 (pressure 5) (source: ledger NP-T1-PF, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC2: PR-F.0 entrypoint trace (blocking) (pressure 9) (source: ledger NP-T1-F0, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC3: AI_IR_TRACE on Maintenance (pressure 6) (source: ledger NP-T1-INST, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC4: schema_client positive and negative tests (PR-A; addendum A2) (pressure 4) (source: ledger NP-T1-A1, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC5: TTL deny on stale (addendum A3) (pressure 4) (source: ledger NP-T1-A2, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC6: field_is_writable (pressure 4) (source: ledger NP-T1-A3, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC7: view_has_field stays as built (addendum A6) (pressure 3) (source: ledger NP-T1-A4, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC8: merge_proposals admit rules (PR-B) (pressure 10) (source: ledger NP-T1-B1, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC9: Rate Line and many2one regression (addendum A4) (pressure 6) (source: ledger NP-T1-B2, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC10: Sibling golden hook (pressure 6) (source: ledger NP-T1-B3, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC11: approved_craft defaults off (PR-C) (pressure 7) (source: ledger NP-T1-C1, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC12: Checklist copy (pressure 5) (source: ledger NP-T1-C2, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC13: Repair cap (PR-D) (pressure 9) (source: ledger NP-T1-D1, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC14: proved requires run_tests (D2) (pressure 6) (source: ledger NP-T1-D2, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC15: Verbatim sandbox log (pressure 4) (source: ledger NP-T1-D3, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC16: CI split (PR-E) (pressure 6) (source: ledger NP-T1-E1, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC17: D2 encoded (pressure 3) (source: ledger NP-T1-E2, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC18: Maintenance golden (PR-F) (pressure 8) (source: ledger NP-T1-F1, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC19: Service-cards golden (pressure 8) (source: ledger NP-T1-F2, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC20: One Option A module reaches install_ready on a real sandbox (pressure 8) (source: ledger NP-T1-F3, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC21: Retire scrub (pressure 9) (source: ledger NP-T1-RET, next-phase cards/T1_SCHEMA_GROUNDING.md)
- AC22: Gates that stay even if the code already exists (pressure 4) (source: ledger NP-T1-GATE, next-phase cards/T1_SCHEMA_GROUNDING.md)
Worked examples for the ACs whose behaviour is already in code. The other ACs stay as written.
- Pin AC2: `studio_generate_offline_finish`'s source contains `_finish_seed_draft` and `_apply_locked_craft_and_surface`. Its docstring contains `Goldens must call` and `_finish_seed_draft`. A node invented after `stamp_generate_ir` fails the count invariant.
- Pin AC4: `FakeSchemaClient.model_exists("res.partner")` is True and `model_exists("x_invent_nowhere")` is False. `relation_ok("x_ticket", "x_partner_id", "res.partner")` is True. `relation_ok("x_ticket", "x_partner_id", "res.users")` is False.
- Pin AC5: `schema_client_for_draft` with `loaded_at` older than `SCHEMA_CATALOG_TTL_S` by 10 seconds returns a `DenySchemaClient` whose `reason` is `"stale_or_missing_catalog_ts"` and whose `model_exists("res.partner")` is False. That deny client must not admit a field through `admit_and_apply`.
- Pin AC6: `field_is_writable("x_ticket", "x_partner_id")` is True. `field_is_writable("x_ticket", "x_display")` is False. `field_is_writable("x_ticket", "nope")` is False.
- Pin AC7: `DenySchemaClient.view_has_field` is False. `CatalogSchemaClient.view_has_field` returns False. `FakeSchemaClient.view_has_field` is True only when that model is a key of `view_fields` and the field is in the set. A missing model key is False.
- Pin AC10: `test_service_cards_sibling_closed` stays beside the Maintenance closed-class test. `ai_generate_ir*.py` has no `if "maintenance" in` and no `if "service.card"` branch.
- Pin AC13: `DEFAULT_MAX_REPAIR` is 3. `prove_option_a_in_sandbox(..., run_tests=True, auto_repair=True, max_attempts=3)` after three failing installs returns `prove_status == "failed"`, `promote_eligible is False`, and the install was called 3 times. It is not `install_ready`.
- Pin AC14 and AC17: `prove_option_a_in_sandbox(..., run_tests=False)` on a successful install returns `prove_status == "pending"` and `promote_eligible is False`. The same call with `run_tests=True` and a passing install returns `prove_status == "proved"`. There is no stamp `proved_smoke_only`.
- Pin AC18 and AC19: `test_maintenance_closed_ir_no_uncued_spray` and `test_service_cards_sibling_closed` stay green with no new brief-name branch in `app/ai_generate_ir*.py`.

| `run_tests` | Install result | `prove_status` | `promote_eligible` |
|---|---|---|---|
| False | success | `pending` | False |
| True | success | `proved` | True |
| True | fails 3 times | `failed` | False |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_t1.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_t1.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
