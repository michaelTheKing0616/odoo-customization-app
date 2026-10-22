# AS-CONTRACT-ROLES: Every contract model row has a role

ID: AS-CONTRACT-ROLES
Title: Every contract model row has a role
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: P1-1-AC2
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C1 U1 F1 K0 V0 I0)
Context pack:
- handover L517 (P1-1 AC2)
- docs/build-plan/CODE_MAP.md row: contract call (`_repair_model_roles` L1238)
File allow-list:
- apps/api/app/ai_conversation/app_design.py (`_repair_model_roles` only)
- apps/api/tests/test_contract_roles.py (new)
Goal: Legacy path: a missing or unknown role is repaired deterministically (no LLM re-ask unless `role_reask`).
Steps:
1. Allowed roles {record, attribute, dimension, context, future, rule, access}
2. Missing → from `decision` (declined→future if the quote is in left_out, else context; metadata→record if kind=model, else attribute)
3. Unknown string → same mapping, log the original
Acceptance criteria:
- AC1: P1-1 AC2 verbatim: "every model row in the contract has a role from `{record, attribute, dimension, context, future, rule, access}`; a missing role is repaired deterministically"
- AC2: Idempotent: repair(repair(x)) == repair(x)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_contract_roles.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
