# EL-CONN-DOCTOR: Connection doctor in the background

ID: EL-CONN-DOCTOR
Title: Connection doctor in the background
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-CONN, AS-GROUND-WIRE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- apps/api/app/schema_freshness.py
- apps/api/app/routers/health_check.py
File allow-list:
- apps/api/app/connection_doctor.py (new)
- apps/api/tests/test_connection_doctor.py (new)
Goal: Scheduled read-only check per connection: Odoo version change, apps added/removed, key expiry; refreshes the schema catalog and raises a 'Needs you' item.
Steps:
1. Runs on the existing queue (RQ/arq)
2. Version change triggers the existing upgrade check
Acceptance criteria:
- AC1: a changed module list invalidates the schema catalog
- AC2: version change creates one 'Needs you' item
Test plan:
- `cd apps/api && uv run pytest -q tests/test_connection_doctor.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
