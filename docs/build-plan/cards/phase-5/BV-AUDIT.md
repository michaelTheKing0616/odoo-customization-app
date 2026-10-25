# BV-AUDIT: Persist walkthrough audit and approval (BV-04 F1)

ID: BV-AUDIT
Title: Persist walkthrough audit and approval (BV-04 F1)
Status: in progress
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
- apps/api/app/bot_verify/models.py (ORM rows for the two new tables, drift parity)
- apps/api/app/bot_verify/walkthrough.py, flows.py (reviewer follow-ups AC4-AC6)
- apps/api/tests/test_nf_bot_verify_walkthrough.py, test_nf_bot_verify_flows.py (AC2 rewrite of old caller-arg tests; stand-in audit store)
- apps/web/src/components/bots/VerifyRunPanel.tsx, VerifyRunPanel.test.tsx (AC7)
- apps/api/tests/test_nf_bot_verify_store.py (head pin moves to the BV-AUDIT revision)
- apps/api/tests/test_nf_scans_contract.py (AC8, only if the flake is test-side)
Goal: Walkthrough target approval comes from stored state, and every allow/refuse decision is persisted, never only in memory.
Steps:
1. Read F1 in BV-04_reviewer_indep.md. Build only what the ACs name.
2. Write the tests first; they must fail before the code and pass after.
3. STOP-AND-ASK: a needed file is outside the allow-list (e.g. the connections model/router); the schema needs a column on a table another stream owns; a non-`ingenium_` DB, a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329), a git write, or a new dependency.
Acceptance criteria:
- AC1 verify_audit rows (connection-scoped: db_name, decision, reason, at) are written by resolve_target; AUDIT_LOG in-memory list removed or a read-through view.
- AC2 walkthrough_allowed and approved_by are read from stored state keyed by connection, never from caller arguments; caller-supplied values are ignored (test).
- AC3 migration upgrades and downgrades cleanly on an ingenium_* DB; no secrets/PII in audit rows.
- AC4 (BV-HARDEN review) delete_walk_user falls back to archive only when Odoo refuses access (AccessError / access-denied fault); any other unlink error is re-raised.
- AC5 (BV-HARDEN review) when the walkthrough body raises and walk-user cleanup also fails, the original walkthrough exception propagates; the cleanup error is logged and noted, not lost.
- AC6 (BV-HARDEN review) BV-05 missing-ACL check is broader: model names normalised; group-less access ops and access.update granting no permission do not count as cover; model_id/model keys both read.
- AC7 (BV-UI-WIRE review) VerifyRunPanel COPY_FAILED ends with "Your Odoo data is unchanged." (test).
- AC8 (BV-HARDEN review) investigate the test_nf_scans_contract victim-paused flake; fix if in NF files, else log cause and open a follow-up.
Test plan: own tests ×2; focused set; combined both orders; alembic up/down on test PG 54339.
Gate: own ×2 green; no new failures.
Evidence to log: PROGRESS line. AC8: the test_nf_scans_contract victim-paused flake was NOT reproduced in 5 solo + 4 combined (fwd/rev x2) runs on 2026-10-25; the test is left unchanged and stays logged as not reproduced.
Fail-closed until wired: production never calls configure_audit_store, so every walkthrough is refused (including disposable ingenium_ DBs) with "audit store not configured" until BV-AUDIT-WIRE wires AuditStore(engine) at startup.
Rollback: alembic downgrade; revert files.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.
