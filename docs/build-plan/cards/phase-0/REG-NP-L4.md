# REG-NP-L4: GATE-L4-01

ID: REG-NP-L4
Title: GATE-L4-01
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-L4-01;NP-L4-02;NP-L4-03;NP-L4-04;NP-L4-11;NP-L4-12
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F1 K1 V1 I1)
Context pack:
- `sed -n '75,78p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- `sed -n '97,116p' docs/plans/next-phase/cards/T5C_WORKERBOTS_L4.md`
- `sed -n '242,257p' apps/api/app/worker_bot/l4_policy.py`
- `sed -n '387,457p' apps/api/app/worker_bot/l4_policy.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_l4.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-L4` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: GATE-L4-01 (pressure 16) (source: ledger NP-L4-01, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC2: GATE-L4-02 (pressure 16) (source: ledger NP-L4-02, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC3: GATE-L4-03 (pressure 16) (source: ledger NP-L4-03, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC4: GATE-L4-04 (pressure 16) (source: ledger NP-L4-04, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC5: GATE-L4-11 (pressure 16) (source: ledger NP-L4-11, next-phase cards/T5C_WORKERBOTS_L4.md)
- AC6: GATE-L4-12 (pressure 16) (source: ledger NP-L4-12, next-phase cards/T5C_WORKERBOTS_L4.md)
Worked examples (`l4_may_apply` returns bool; it does not enable L4):
- Pin AC1: tenant allow-list `{mail_template.create}`. `l4_gate_01_refusal(op_type="view.archive", allow_list=listed) == L4_NOT_ON_ALLOW_LIST` (`"not_on_allow_list"`). `field.create` / `model.create` / `model.scaffold` are `ddl=True` and return `L4_R2_DDL` (`"r2_ddl"`) even when listed. `automation.create` whose action is email / `mail_post` returns `L4_OUTBOUND`.
- Pin AC2: `_l4_gate_02_refuses` is True for risk `R3` or `R4`, `module.install` / `module.upgrade` / `module.uninstall`, promote, and `protection_level == "elevate"`, even when the op is on the allow-list.
- Pin AC3: `l4_gate_03_allows(mode="T", plan_hash=same, staging_applies=[StagingApplyRecord(plan_hash=same, verified=True)])` is True. Mode `C`, `verified=False`, a different hash, or flags without that record is False.
- Pin AC4: `StandingRuleBook.open("rule-1").active` is False. One owner approval stays inactive. A second distinct admin (`user_id` different, role `admin` or `owner`) sets `active` True. The same admin twice, a missing `user_id`, or two non-owners stay inactive. An active rule does not turn L4 on.
- Pin AC5: `l4_may_apply(..., op_type="data.unlink", model="res.users", method="unlink", allow_list=every catalog op)` is False. The same for `res.users.apikeys` and a protected parameter write. A benign R1 op on that full list can still pass the other gates.
- Pin AC6: `record_allow_list_change(..., role="admin", ...)` returns `recorded=True`, `auto_applied=False`. `refuse_bot_allow_list_tool_call(..., actor="worker_bot", tool_name in the allow-list edit tools)` does not change the registry; the audit `note` payload has `event == L4_ALLOW_LIST_REFUSED` (`"l4_allow_list_refused"`) and the result reason is `"bot_cannot_widen_allow_list"`. A template that adds an op is not auto-applied.

| Check | `l4_may_apply` |
|---|---|
| op not on the tenant allow-list | False, reason `not_on_allow_list` |
| R2 and `OP_CATALOG[op].ddl` is True | False, reason `r2_ddl` |
| R2, non-DDL, not protected, not outbound, listed, Mode T, same hash verified on staging | True |
| caller risk R3 or R4, or `module.*`, or promote, or `protected:elevate` | False |
| `plan_mode="C"`, or staging record missing / other hash / `verified=False` | False |
| `rows > L4_MAX_BLAST` (`50`) | False (`rows=51`) |
| `rows=50` and every other check passes | True |
| `res.users` unlink, even if every op is allow-listed | False |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_l4.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_l4.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: L4 production autonomy stays off until GATE-L4-08 evidence exists (D10). Thresholds are fixed: 200 applies / 60 days / ≤ 1% rollback / 30-day rules / daily cap 20 / blast radius 50. Every bot write is inside a stated permission grant (`bots/grant.py`) and goes through the write gate. Pitfall: counting dry runs as applies. Oracle cases: cap 21st apply refused; blast 51 refused; grant missing → refused.
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_reg_np_l4.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
