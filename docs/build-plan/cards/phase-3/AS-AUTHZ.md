# AS-AUTHZ: Authorizer v3: span evidence by offset, stem rules retired under v3

ID: AS-AUTHZ
Title: Authorizer v3: span evidence by offset, stem rules retired under v3
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P1-2; AS-FAIL-A; AS-8.5-AUTHZ; AS-FIX-2
Depends on: AS-COMPILE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F2 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §2 RC3, §6.4 step 2
- docs/build-plan/CODE_MAP.md row: authorizer
- handover §8.7 AC4 (L945)
File allow-list:
- apps/api/app/ai_conversation/model_authorizer.py (new function `authorize_v3` + helpers; existing functions unchanged)
- apps/api/tests/test_model_authorizer_v3.py (new)
Goal: Under v3 the authorizer is an invariant checker over ledger spans (rules 0, 1, 6, 7) with no stem binding; legacy rules stay for legacy_v1.
Steps:
1. `authorize_v3(design, voted, force_keep)`: evidence = ledger mention spans (offset-verified); rule 0 promoted → keep; 1 future → suggest; 6 orphan → drop; 7 fold uses the ledger fact kind (link → m2o, dimension ≥ 2 values → selection, else char)
2. No `stems()` call in `authorize_v3` (grep test)
3. Return the same `AuthResult` shape so `apply_calls` is reused
Acceptance criteria:
- AC1: §8.7 AC4 verbatim: "authoriser rules each have unit tests with positive and negative cases from real briefs" (FIX_PLAN 'Verification' list: service history kept, services list kept, salon service folded, NGO pack type + community folded, Stylist Schedule / Generator Log / Resident Share dropped, Loyalty suggested)
- AC2: Pidgin case (bakery_ng 'wetin dem order') keeps Order Line without lexical overlap
- AC3: Legacy `authorize_models` behaviour unchanged (existing tests green)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_model_authorizer_v3.py tests/test_model_authorizer.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §2 RC3. Lexical overlap between owner words and LLM-written labels is the false-fold engine; v3 removes it rather than tuning it.
Oracle tests: The FIX_PLAN verification cases as fixtures (hand-written ledgers), plus the noun-swap metamorphic case (V-07) applied end to end.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
