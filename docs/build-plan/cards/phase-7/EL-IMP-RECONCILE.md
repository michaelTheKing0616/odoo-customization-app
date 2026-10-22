# EL-IMP-RECONCILE: Import control totals

ID: EL-IMP-RECONCILE
Title: Import control totals
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-IMP
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F2 K1 V1 I0)
Context pack:
- handover §3.8
- apps/api/app/suite_import.py
File allow-list:
- apps/api/app/import_reconcile.py (new)
- apps/api/tests/test_import_reconcile.py (new)
Goal: After import: counts and sums by key columns in the file versus what Odoo now holds (by Ingenium external ids), in the import report.
Steps:
1. Read-only after-read by `__ingenium_import__` ids
2. Mismatch → plain list of rows with the difference
Acceptance criteria:
- AC1: matching import → all totals equal
- AC2: one dropped row → named in the report
Test plan:
- `cd apps/api && uv run pytest -q tests/test_import_reconcile.py`
Elite design notes: Money columns compare with Decimal; currency per row.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-IMP-RECONCILE-1 one missing row → reported with its key
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
