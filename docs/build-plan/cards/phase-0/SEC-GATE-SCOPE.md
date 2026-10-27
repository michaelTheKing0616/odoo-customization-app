# SEC-GATE-SCOPE: safety gate scopes the connection before the pause check

ID: SEC-GATE-SCOPE
Title: safety gate scopes the connection before the pause check
Status: done
Phase: 0
Priority: P0
Type: security
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: SEC-GATE-SCOPE
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 8 (C1 U1 F3 K2 V1 I0)
Context pack:
- apps/api/app/safety_dependency.py
- apps/api/app/safety_gate.py
- apps/api/app/workspace_auth.py
- apps/api/app/safety_registry.py (read only; locked by L-NF-SCAN-01)
File allow-list:
- apps/api/app/safety_dependency.py
- apps/api/app/safety_gate.py
- apps/api/tests/test_sec_gate_scope.py (new)
Goal: A connection id the caller does not own returns the same 404 as an id that does not exist, before any pause check.
Steps:
1. In `enforce_safety_gate`, resolve a path connection id with `scoped_connection_query` for the caller before `SafetyGate.preflight`.
2. A miss (other workspace or unknown id) raises 404 on that shared path. Do not call `db.get(OdooConnection, conn_id)`.
3. Add the parametrized test. Do not edit `safety_registry.py`.
Acceptance criteria:
- AC1: For every gated route that carries a connection id, workspace B hitting workspace A's connection, paused or not, gets a byte-identical 404 to a random id.
- AC2: A same-workspace paused connection still returns 403 with code `writes_paused`.
- AC3: The test is parametrized from the route registry. `tests/test_safety_gate.py` and `tests/test_sec_gate_scope.py` pass.
Worked example:
- Connection `conn-a` belongs to workspace A and `writes_paused` is true. Caller auth is workspace B. `POST` to a gated route with `conn-a` returns the same status and body as the same route with `conn-missing`.
- Caller auth is workspace A. The same paused connection returns 403 `writes_paused`.
Decision: non-owned and missing ids share one 404 path. Owned paused connections still hit `_check_writes_paused`.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_sec_gate_scope.py tests/test_safety_gate.py`
Elite design notes: The workspace comes from the caller. `enforce_safety_gate` loads a path connection id only with `scoped_connection_query` before `SafetyGate.preflight`. A miss raises 404 `Connection not found`, the same body as an unknown id, including when the other workspace's connection is paused. An owned paused connection still returns 403 `writes_paused`. Do not call `db.get(OdooConnection, conn_id)`. Do not edit `safety_registry.py`; leave `bypass_writes_paused` as it is. The sweep uses account auth so the workspace filter applies.
Oracle tests: Locked in `apps/api/tests/test_sec_gate_scope.py::test_foreign_connection_matches_missing_id`. AC1: workspace B against A's paused and unpaused connection matches the missing-id 404 bytes on every registry route that carries a connection id. AC2: that paused connection as workspace A is 403 `writes_paused`, except `bypass_writes_paused` routes, which still 404 a foreign id. AC3: the parameter list is the route registry. A later loop may not edit this test.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · SEC-GATE-SCOPE · command · result counts · label. Tester packet and Reviewer verdict summary in `docs/build-plan/STATE.md` token ledger.
Gate: none (no Tope gate).
Rollback: revert the allow-list diff.
Definition of Done: Every AC has evidence; the oracle test is unmodified and green; no file outside the allow-list changed.
