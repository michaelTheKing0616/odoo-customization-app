# REG-NP-5A: classify_rpc with the verbatim lists; mapped to Bucket A/B/C

ID: REG-NP-5A
Title: classify_rpc with the verbatim lists; mapped to Bucket A/B/C
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-5A-01;NP-5A-02;NP-5A-03;NP-5A-04;NP-5A-05;NP-5A-06;NP-5A-07;NP-5A-08;NP-5A-09;NP-5A-10;NP-5A-11;NP-5A-12
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F2 K1 V0 I1)
Context pack:
- `sed -n '46,125p' docs/plans/next-phase/cards/T5A_GUARDRAILS.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_5a.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-5A` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: classify_rpc with the verbatim lists; mapped to Bucket A/B/C (pressure 12) (source: ledger NP-5A-01, next-phase cards/T5A_GUARDRAILS.md)
- AC2: Structural dry-run hash on every write tool in T1; T3; T4 (pressure 14) (source: ledger NP-5A-02, next-phase cards/T5A_GUARDRAILS.md)
- AC3: Plan fingerprint (pressure 15) (source: ledger NP-5A-03, next-phase cards/T5A_GUARDRAILS.md)
- AC4: Never-allowed; no override (pressure 15) (source: ledger NP-5A-04, next-phase cards/T5A_GUARDRAILS.md)
- AC5: Hash-chained audit (pressure 13) (source: ledger NP-5A-05, next-phase cards/T5A_GUARDRAILS.md)
- AC6: Snapshot before DESTRUCTIVE or BILLABLE on production (pressure 11) (source: ledger NP-5A-06, next-phase cards/T5A_GUARDRAILS.md)
- AC7: Zero MCP writes (code inspection) (pressure 4) (source: ledger NP-5A-07, next-phase cards/T5A_GUARDRAILS.md)
- AC8: Production policy (pressure –) (source: ledger NP-5A-08, next-phase cards/T5A_GUARDRAILS.md)
- AC9: Staging policy (pressure –) (source: ledger NP-5A-09, next-phase cards/T5A_GUARDRAILS.md)
- AC10: Oracle tests (pressure –) (source: ledger NP-5A-10, next-phase cards/T5A_GUARDRAILS.md)
- AC11: Rollback tiers wired (pressure 13) (source: ledger NP-5A-11, next-phase cards/T5A_GUARDRAILS.md)
- AC12: Production budgets (blueprint §5.6) (pressure 7) (source: ledger NP-5A-12, next-phase cards/T5A_GUARDRAILS.md)
Symbols: `classify_rpc`, `policy_allows`, `READ_METHODS` in `apps/api/app/rpc_classify.py`. `NEVER_ALLOWED` in `packages/odoo-client/src/odoo_client/rpc_policy.py`. `structural_dry_run_hash`, `plan_fingerprint` in `apps/api/app/plan_fingerprint.py`. `verify_chain`, `GENESIS_PREV_HASH` in `apps/api/app/audit_chain.py`. `require_production_snapshot`, `FRESHNESS_WINDOW` in `apps/api/app/snapshot_gate.py`. `mcp_call` in `apps/api/app/mcp_guard.py`. `build_compensating_plan`, `NOT_REVERSIBLE_BY_THIS_TIER` in `apps/api/app/rollback_tiers.py`. `MAX_STEPS`, `MAX_TOOL_CALLS` in `apps/api/app/agent_runtime/runtime.py`. `PRODUCTION_APPLY_RECORD_CAP` in `apps/api/app/blast_radius.py`. `L4_MAX_BLAST` in `apps/api/app/worker_bot/l4_policy.py`. `self_approval_allowed`, `policy_decision` in `apps/api/app/changeset/policy.py`.
Worked example:
- Example AC1: `classify_rpc("res.partner", "search_read", ids=[1])` → `risk="READ"`, `bucket="A"`, `forbidden=False`.
- Example AC3: `plan_fingerprint([{"op": "write", "res_id": 5, "vals": {"name": "a"}}])` == `"8a1e31fc0a9b80d0"` (16 hex). The same call without `res_id` returns the same string.
- Example AC4: `classify_rpc("res.users", "unlink", ids=[1], approved=True)` → `forbidden=True`, `reason="never_allowed"`. `policy_allows` of that result on staging is `False`.
- Example AC5: `verify_chain([])` → `(True, None)`. `verify_chain([{"prev_hash": "1" * 64}])` → `(False, 0)` because `prev_hash` is not `GENESIS_PREV_HASH` (`"0" * 64`).
- Example AC6: `require_production_snapshot(write_mode="production", risk="destructive", snapshot_id=None, snapshot_exists=False)` raises `SnapshotRequired` ("A snapshot recorded for this connection is required..."). `write_mode="staging"` returns without raising. A snapshot older than `FRESHNESS_WINDOW` (10 minutes) raises `SnapshotRequired` ("older than the 10-minute freshness window").
- Example AC8: `policy_allows(classify_rpc("res.partner", "read", ids=[1]), environment="production")` is `True`. The same function on `classify_rpc("res.partner", "create", values={"name": "x"})` is `False`.
- Example AC9: staging allows that read and that create, and refuses `classify_rpc("res.partner", "unlink", ids=[1])`.
- Example AC10: these names exist: `test_read_is_read`, `test_create_is_reversible`, `test_unlink_destructive_and_forbidden`, `test_security_models_destructive`, `test_billable_depends_on_edition`, `test_protected_params_forbidden`, `test_mass_write`, `test_policy_thresholds` in `apps/api/tests/test_rpc_classify.py`; `test_audit_chain_and_tamper`, `test_redaction` in `apps/api/tests/test_audit_chain.py`.
- Example AC11: `build_compensating_plan` on a created `res.partner` change emits `data.unlink`. A module install and a posted `account.move` are listed with `reason="not reversible by this tier"` and are not inverted. A created `res.users` row sets `plan.refused=True`, `plan.reason="never_allowed"`, `plan.changeset=[]`.
- Example AC12: `MAX_STEPS == 40` (step 41 raises `BudgetExceeded`). `MAX_TOOL_CALLS == 120` (call 121 raises `BudgetExceeded`). `PRODUCTION_APPLY_RECORD_CAP == 200` (`assert_production_apply_records(201, environment="production")` raises `BlastRadiusExceeded`; 200 does not). `L4_MAX_BLAST == 50`. `self_approval_allowed("R3")` is `True` and `policy_decision("R3", "production", autonomy="L4")["approvers"] == 1`. Change windows stay a pointer to `docs/plans/next-phase/cards/T6_AUTH_INBOX.md` headings `T6-04` and `T6-06`. The kill switch stays the existing Bridge tests `test_kill_switch_protocol_and_escalation_refuse_before_work` and `test_reader_and_kill_switch_do_not_touch_the_port_or_journal`.
Decision table (`classify_rpc` → `policy_allows`):
| Call | risk | bucket | forbidden | staging | production |
| `res.partner` `search_read` | READ | A | False | True | True |
| `res.partner` `create` | REVERSIBLE | B | False | True | False |
| `res.partner` `unlink` | DESTRUCTIVE | C | False | False | False |
| `res.users` `unlink`, `approved=True` | DESTRUCTIVE | C | True | False | False |
| `ir.module.module` `button_install`, edition `community` | DESTRUCTIVE | C | False | False | False |
| `ir.module.module` `button_install`, edition `enterprise` | BILLABLE | C | False | False | False |
| `res.partner` `write` with 51 ids | DESTRUCTIVE (`mass_write`) | C | False | False | False |
STOP-AND-ASK before pinning an unchecked old-pack box: a separate R0–R4 mapping constant, a request field named `risk`, one `plan_drift` test per track, `GET /api/admin/audit/verify`, or a per-tenant REVERSIBLE glob. `policy_allows` on production is true only for risk `READ`.
STOP-AND-ASK on AC2 and AC7 before writing a test that is red today. AC2: pin `structural_dry_run_hash("install", {"a": 1, "dry_run": True})` == `1358816a89d96233a63b788dcb12f9c9d236a6a59da1065b5edfd328def8cbb2` (canonical JSON drops `dry_run`). Do not require every T1/T3/T4 route to refuse a live write; that acceptance is still unchecked. AC7: `mcp_call("search")` returns `"read"`; `mcp_call("create")` raises `McpWriteForbidden` (`"MCP cannot call create"`). Do not require `tests/test_no_mcp_write.py` to pass; that scan is the BL-07 cache failure.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_5a.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_5a.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: Billing: hosted checkout only (no card data touches Ingenium); provider webhooks verified by signature and handled idempotently (event id unique); amounts as integer minor units with currency; plans are data, not code. Providers and prices need GATE-A (Tope). Paystack has no stock Odoo module; Paystack flows go through Bridge (FACTS).
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/api/tests/test_reg_np_5a.py` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
