# REG-NP-BR: Contract schema; Tier I fail-closed

ID: REG-NP-BR
Title: Contract schema; Tier I fail-closed
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-BR-01;NP-BR-04;NP-BR-05
Depends on: B0-INV
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F1 K0 V0 I0)
Context pack:
- `sed -n '31,33p' docs/plans/next-phase/cards/T3_BRIDGE.md`
- `sed -n '50,52p' docs/plans/next-phase/cards/T3_BRIDGE.md`
- `sed -n '54,56p' docs/plans/next-phase/cards/T3_BRIDGE.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_br.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-BR` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Contract schema; Tier I fail-closed (pressure 10) (source: ledger NP-BR-01, next-phase cards/T3_BRIDGE.md)
- AC2: Queue tables (pressure 4) (source: ledger NP-BR-04, next-phase cards/T3_BRIDGE.md)
- AC3: Connector interface (six methods) (pressure 4) (source: ledger NP-BR-05, next-phase cards/T3_BRIDGE.md)
Symbols: `validate_contract`, `ContractError`, `IntegrationContract` in `apps/api/app/bridge/contract.py`. `enqueue_pure`, `mark_dead` in `apps/api/app/bridge/queue.py`. `Connector` in `apps/api/app/bridge/connector.py`.
Worked example:
- Example AC1: `validate_contract({"odoo_connection_id": "odoo-1", "third_party_connection_id": "shop-1", "direction": "inbound", "webhook_signature_required": True, "entities": [{"name": "orders", "money": True, "money_policy": "odoo_wins"}]})` returns an `IntegrationContract` with `idempotency_key_field="idempotency_key"`. The same payload with `direction="two_way"` and no `conflict_resolution` raises `ContractError`. `entities=[{"name": "orders", "money": True}]` raises `ContractError`. A top-level `api_key` raises `ContractError` matching `secrets`. `odoo_target={"url": "https://odoo.example", "username": "admin"}` raises `ContractError` matching `connection_id`.
- Example AC2: `enqueue_pure([], connection_id="c", idempotency_key="k", payload={"n": 1})` twice returns the same event and leaves one row. `mark_dead` on `status="queued"`, `attempts=0` sets `status="dead"` and `attempts=1`. Do not open a database that is not `ingenium_*`; `enqueue_pure` is the in-memory pin.
- Example AC3: `set(Connector.__protocol_attrs__)` == `{"fetch", "create", "update", "declared_schema", "verify_webhook_signature", "parse_webhook_event"}`.
STOP-AND-ASK before requiring an event with no `idempotency_key` to fail Tier I. `validate_contract` does not check per-event keys; that open delta is not the current behaviour.
Decision table (`validate_contract`):
| Payload | Result |
| complete inbound contract above | `IntegrationContract` |
| `direction="two_way"` and `conflict_resolution` missing | `ContractError` |
| money entity and `money_policy` missing | `ContractError` |
| a secret key (`api_key`, `password`, `token`, ...) anywhere in the payload | `ContractError` matching `secrets` |
| inline `odoo_target` or `third_party` credential block | `ContractError` matching `connection_id` |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_br.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_br.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
