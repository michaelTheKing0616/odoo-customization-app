# AS-PACK-RETIRE: Retire domain pack code after Draft Studio and App Studio both run v3

ID: AS-PACK-RETIRE
Title: Retire domain pack code after Draft Studio and App Studio both run v3
Status: todo
Phase: 3
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-DRAFT-V3
Depends on: AS-DRAFT-ADOPT, AS-NO-PACKS
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/PACK_PRESERVATION.md
- handover §3.17
File allow-list:
- apps/api/app/ai_domain_pack*.py (removal only, after Tope's yes)
- the 57 importers of pack modules (remove dead imports only)
- apps/api/tests/ (delete pack-only tests; keep provenance tests until the last importer is gone)
Goal: Remove pack modules and their imports once no supported profile uses them, with every behaviour accounted for.
Steps:
1. Stop and ask Tope for an explicit yes in the current message before deleting any file (INV-05, INV-18)
2. Delete in one importer at a time; full api suite after each batch
Acceptance criteria:
- AC1: `rg ai_domain_pack apps/api/app` returns nothing
- AC2: full api suite green
- AC3: Tope's yes quoted in the Tester packet
Test plan:
- `cd apps/api && uv run pytest -q`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
