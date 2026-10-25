# BV-AUDIT-WIRE: Wire the walkthrough audit store at startup

ID: BV-AUDIT-WIRE
Title: Wire AuditStore(engine) at startup and add the owner approval endpoint
Status: todo
Phase: 5
Priority: P2
Type: build
Owner: backend
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-AUDIT-WIRE
Depends on: BV-AUDIT
Routing: Worker: L2 · Tester + Reviewer separate sessions
Context:
- BV-AUDIT left targets.py fail-closed: production never calls configure_audit_store, so every walkthrough is refused (disposable DBs included) until this card lands.
Goal: Walkthroughs run in production with every decision persisted, and owners can set the per-connection approval.
Steps:
1. STOP-AND-ASK before touching files owned by another stream (app startup/main.py, connections router) or adding a dependency.
Acceptance criteria:
- AC1 App startup calls configure_audit_store(AuditStore(engine)) on the app DB engine; a test proves a disposable walk is allowed and audited after startup.
- AC2 An approval endpoint sets verify_walk_approvals; owner_id is taken from the connection row, never from the request; approved_by is the authenticated user; a non-owner cannot grant (test).
- AC3 Approval change is itself audited (no secrets/PII).
- AC4 verify_audit intentionally has no FK to odoo_connections so audit rows outlive a deleted connection; keep it that way (test: delete a connection, its audit rows remain; its approval row cascades away).
Test plan: own tests x2; combined both orders x2.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.
