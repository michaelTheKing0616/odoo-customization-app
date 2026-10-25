# BV-AUDIT-WIRE: Wire the walkthrough audit store lazily (no main.py hook)

ID: BV-AUDIT-WIRE
Title: Wire AuditStore(app.db.engine) lazily in bot_verify, audit approval-read failures, add the owner approval endpoint
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: NF (backend)
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-AUDIT-WIRE
Depends on: BV-AUDIT (merged). Blocks: BOT-KILL-AUDIT (reuses the same startup hook and store).
Routing: Worker: L2 · Tester + Reviewer separate sessions
Context: targets.py is fail-closed: nothing in apps/api/app calls configure_audit_store (grep 2026-10-25), so every walkthrough is refused. In resolve_target, `_STORE.approval(connection_id)` can raise and the refusal is then never audited.
File allow-list:
- apps/api/app/bot_verify/targets.py
- apps/api/tests/test_nf_bot_verify_wire.py (new)
- apps/api/app/routers/bot_verify.py (PUT /connections/{id}/verify-runs/walk-approval)
- apps/api/app/security/idor_registry.py (register the new route)
- apps/api/tests/test_nf_bot_verify_contract.py (route count 3 -> 4)
- this card
Owner = the workspace's `owner` membership of the connection's workspace (connections have no owner column); approval + its audit row are written in one transaction.
Decision (Grok Bot, 2026-10-25): apps/api/app/main.py belongs to another stream and is NOT edited. targets.ensure_audit_store() wires AuditStore(app.db.engine) on first use (resolve_target/_audit/audit_log), double-checked under a lock, idempotent; an explicit configure_audit_store() (even None) is never overridden. No DB probe: if the DB is down the audit write fails and the walk is refused (fail-closed).
Goal: Walkthroughs run in production with every decision persisted, and owners can set the per-connection approval.
Steps:
1. Tests first (fail before, pass after). 2. STOP-AND-ASK: a needed file is outside the allow-list; a non-`ingenium_` DB; a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329); a git write; a new dependency.
Acceptance criteria:
- AC1 First walk-path use wires AuditStore(app.db.engine) once (thread-safe). Evidence: resolve_target on an ingenium_ DB with an unset store → allowed + one verify_audit row; 16 concurrent ensure calls → one store; DB down → refused "audit write failed".
- AC2 Approval read failure: if store.approval() raises, resolve_target writes a refused row with reason "approval read failed" (exception type only) and raises TargetNotAllowed. Evidence: test with a raising stand-in store; row present; no traceback/secrets in reason.
- AC3 If the audit write itself fails, the walk is still refused (unchanged fail-closed). Evidence: test.
- AC4 Approval endpoint sets verify_walk_approvals; owner_id from the connection row, never from the request; approved_by = authenticated user; non-owner → 403. Evidence: 3 tests.
- AC5 Approval grant/revoke is itself audited (no secrets/PII). Evidence: row assertions.
- AC6 verify_audit keeps no FK to odoo_connections: delete a connection → audit rows remain, approval row cascades. Evidence: test.
Non-goals: kill switch, risk classes, UI for approvals (BOT-APPROVAL-TIERS).
Test plan: own tests x2; combined focused set both orders (fwd/rev) x2 each; test PG 54339. Chaos: concurrent first use → one store; DB down → walks refused "audit write failed" (not audited: nowhere to write; logged by exception type).
What can still go wrong: none from worker processes (lazy per process); audit table growth (no retention yet).
Evidence to log: PROGRESS line with test counts both orders.
Rollback: revert files (no migration).
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.
