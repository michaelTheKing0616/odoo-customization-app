# BV-AUDIT: Persist walkthrough audit and approval (BV-04 F1)

ID: BV-AUDIT
Title: Persist walkthrough audit and approval (BV-04 F1)
Status: todo
Phase: 5
Priority: P2
Type: build
Owner: backend
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-AUDIT
Depends on: BV-04 (23d84b58), BV-STORE (d650f151), BV-HARDEN
Routing: Worker: L2 · schema change · Tester + Reviewer separate sessions
Context pack:
- ~/.ingenium_nf/nfwt/BV-04_reviewer_indep.md (F1)
- apps/api/app/bot_verify/targets.py, store.py
- apps/api/alembic/ (latest revision)
File allow-list:
- apps/api/app/bot_verify/targets.py
- apps/api/app/bot_verify/store.py
- apps/api/alembic/versions/<new>_bv_audit.py (new)
- apps/api/tests/test_nf_bot_verify_audit.py (new)
Goal: Walkthrough target approval comes from stored state, and every allow/refuse decision is persisted, never only in memory.
Steps:
1. Read F1 in BV-04_reviewer_indep.md. Build only what the ACs name.
2. Write the tests first; they must fail before the code and pass after.
3. STOP-AND-ASK: a needed file is outside the allow-list (e.g. the connections model/router); the schema needs a column on a table another stream owns; a non-`ingenium_` DB, a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329), a git write, or a new dependency.
Acceptance criteria:
- AC1 verify_audit rows (connection-scoped: db_name, decision, reason, at) are written by resolve_target; AUDIT_LOG in-memory list removed or a read-through view.
- AC2 walkthrough_allowed and approved_by are read from stored state keyed by connection, never from caller arguments; caller-supplied values are ignored (test).
- AC3 migration upgrades and downgrades cleanly on an ingenium_* DB; no secrets/PII in audit rows.
Test plan: own tests ×2; focused set; combined both orders; alembic up/down on test PG 54339.
Gate: own ×2 green; no new failures.
Evidence to log: PROGRESS line.
Rollback: alembic downgrade; revert files.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.
