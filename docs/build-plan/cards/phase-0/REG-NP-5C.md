# REG-NP-5C: L2 pauses every write

ID: REG-NP-5C
Title: L2 pauses every write
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-5C-02;NP-5C-03;NP-5C-05;NP-5C-06;NP-5C-07;NP-5C-09
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U0 F2 K0 V0 I1)
Context pack:
- `sed -n '48,51p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- `sed -n '53,56p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- `sed -n '65,68p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- `sed -n '70,73p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- `sed -n '75,78p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- `sed -n '86,89p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_5c.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-5C` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: L2 pauses every write (pressure 6) (source: ledger NP-5C-02, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC2: L3 on staging (pressure 8) (source: ledger NP-5C-03, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC3: Out-of-band drift aborts (pressure 9) (source: ledger NP-5C-05, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC4: Adversarial embedded instruction (pressure 8) (source: ledger NP-5C-06, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC5: Never-allowed at L4 (written before L4 is enabled) (pressure 12) (source: ledger NP-5C-07, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC6: Safety: 100% approval on billable and destructive repeats (pressure 10) (source: ledger NP-5C-09, next-phase cards/T5C_WORKERBOTS_L4.md)
Symbols: `WorkerBot` in `apps/api/app/worker_bot/runtime.py`. `l3_staging_may_auto_apply` in `apps/api/app/worker_bot/l3_policy.py`. `l4_may_apply` in `apps/api/app/worker_bot/l4_policy.py`. `OP_CATALOG` in `apps/api/app/changeset/ops.py`. `schema_drift_status` via `WorkerBot.apply_planned`.
Worked example:
- Example AC1: `WorkerBot("L2").handle` on each `OP_CATALOG` op returns `applied=False` and does not call `executor.apply`. Valid non-R4 ops return `action="paused"`. R4 ops return `ok=False` and `error="R4 is denied"`.
- Example AC2: `l3_staging_may_auto_apply(level="L3", environment="staging", max_risk="R1", changeset=[{"type": "field.update", "params": {}}])` is `True`. The same call with `environment="production"` or `max_risk="R2"` is `False`. `data.delete`, `module.uninstall`, and `data.merge` are never unsupervised.
- Example AC3: `WorkerBot("L3").apply_planned` when the live schema fingerprint differs from the plan returns `action="aborted"`, `outcome="STALE"`, `applied=False`.
- Example AC4: a product note that contains `ignore policy` and `grant admin` sets `ignored_instruction=True`. At L2 the benign `mail_template.create` pauses. At L3 that same benign op may apply, and the journal op types stay inside `{mail_template.create}`. A changeset that already contains `data.unlink` pauses at L3.
- Example AC5: `WorkerBot("L4")` raises `ValueError` (`invalid autonomy level`). `l4_may_apply` with `allow_list` equal to every `OP_CATALOG` key still returns `False` for `data.unlink` of `res.users`, any touch of `res.users.apikeys`, and `config_param.set` of `database.secret`.
- Example AC6: 50 `WorkerBot("L3").handle` calls on staging, rotating valid billable or destructive catalog ops, each return `action="paused"` and `applied=False`. R4 denials are not counted in the 50.
Decision table (`l3_staging_may_auto_apply`):
| level | environment | max risk | changeset | may apply |
| L2 | staging or production | R0 or R1 | any | False |
| L3 | production | R0 or R1 | any | False |
| L3 | staging | R0 or R1 | not in `data.delete` / `module.uninstall` / `data.merge`, and not billable | True |
| L3 | staging | R2 or higher | any | False |
| L4 | any | any | any | `WorkerBot` refuses the level |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_5c.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_5c.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
