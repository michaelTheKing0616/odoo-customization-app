# EL-X-EDGE-RECORDS: Edge-case records for any preview

ID: EL-X-EDGE-RECORDS
Title: Edge-case records for any preview
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-FID
Depends on: EL-X-BAR
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- packages/odoo-client/src/odoo_client/schema_graph.py (`search_read` with ROW_CAP)
File allow-list:
- apps/api/app/edge_records.py (new)
- apps/api/app/routers/views.py (one read-only endpoint)
- apps/api/tests/test_edge_records.py (new)
Goal: For a model: ids of the record with the longest name, the most empty fields, the most lines, an archived one, another currency, a right-to-left partner language, each when it exists.
Steps:
1. Read-only, capped queries; return ids and reasons only
2. Missing case → reason 'none in this database', never a fake record (INV-15)
Acceptance criteria:
- AC1: returns only ids + reasons (property)
- AC2: no write RPC on any path (test)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_edge_records.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
