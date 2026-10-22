# AS-GOLD-SPANS: Gold files get verbatim spans

ID: AS-GOLD-SPANS
Title: Gold files get verbatim spans
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-GOLD-SPANS-ROW
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C1 U1 F1 K0 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §9
- apps/api/evals/v2/dev/*.md + *.gold.yaml, dev2/*
File allow-list:
- apps/api/evals/v2/dev/*.gold.yaml
- apps/api/evals/v2/dev2/*.gold.yaml
- apps/api/evals/v2/tests/test_gold_spans.py (new)
Goal: Each gold entity and attribute gets `spans:` (exact substrings of its brief), so alignment does not depend on stems.
Steps:
1. For each of the 28 briefs: add `spans:` lists under each entity and attribute (copy text exactly; no offsets needed, the test finds them)
2. A gold entity or attribute the owner never said (e.g. bakery_ng `Order Line.price`, a RECONSTRUCTED gold under DEC-039) gets `spans: []` and `unstated: true`; never invent a span for it
3. Add `acceptable_alternates:` (stock models) where a stock host is a fair answer (e.g. salon_voice Appointment → `calendar.event`)
4. Never open `holdout_fresh/` (INV-16)
5. Mark the file `spans_status: DRAFT` for Tope's review (DEC-026)
Acceptance criteria:
- AC1: Every non-empty span is a verbatim substring of its brief; every empty `spans` has `unstated: true` (test)
- AC2: No file under `holdout_fresh/` changed (git diff --stat check in the Tester packet)
Test plan:
- `cd apps/api && uv run pytest -q evals/v2/tests/test_gold_spans.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
