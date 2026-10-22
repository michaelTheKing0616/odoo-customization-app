# EL-X-FIDELITY: One harness proving previews match real Odoo

ID: EL-X-FIDELITY
Title: One harness proving previews match real Odoo
Status: todo
Phase: 7
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-FID
Depends on: EL-X-BAR, AS-GROUND-VIEWMAP
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- packages/odoo-client/src/odoo_client/schema_graph.py L103
- apps/web/src/lib/design-preview.ts
- apps/api/app/routers/preview_proxy.py
File allow-list:
- apps/api/app/fidelity.py (new)
- apps/api/tests/test_fidelity.py (new)
Goal: render → apply on a sandbox → re-read combined arch → compare structure (containers, field order, buttons) with what the preview showed; used by App Studio, View Designer, Wireframe and Report proof.
Steps:
1. Structure diff over the view map, not pixels
2. One report shape: matched, moved, missing, extra. Live checks run only on disposable `ingenium_*` sandboxes for 17, 18, 19 (and 20 once its stack exists); drop what you create (INV-03).
Acceptance criteria:
- AC1: identical structures → zero diff
- AC2: a moved field is reported as moved with both paths
- AC3: live run on 17-19 for one design per consumer
Test plan:
- `cd apps/api && uv run pytest -q tests/test_fidelity.py`
Elite design notes: Pure diff over two ViewMaps; the RPC part is the existing combined_arch read.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-X-FIDELITY-1 same arch → empty diff; EL-X-FIDELITY-2 field moved between pages → one 'moved' row
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
