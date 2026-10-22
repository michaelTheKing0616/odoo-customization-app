# AS-CH-BRIEF: Headline briefs: Customer Health file + reconstructed briefs flagged

ID: AS-CH-BRIEF
Title: Headline briefs: Customer Health file + reconstructed briefs flagged
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CH-BRIEF; AS-RECON-BRIEFS
Depends on: none
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: L1 separate session · Reviewer: L2 separate session · Score: 1 (C0 U0 F1 K0 V0 I0)
Context pack:
- apps/api/tests/fixtures/customer_health_brief.md
- apps/api/evals/v2/dev/bakery_ng.gold.yaml (header only)
File allow-list:
- apps/api/evals/v2/dev/customer_health.md (new)
- apps/api/evals/v2/dev/customer_health.gold.yaml (new, DRAFT)
- apps/api/evals/v2/HEADLINE.md (new)
Goal: The five headline briefs are files, and the reconstructed ones are flagged for Tope's exact words (DEC-039).
Steps:
1. Copy the fixture verbatim to `dev/customer_health.md`
2. Draft the gold from the brief's own headings (status DRAFT, reviewer Tope)
3. `HEADLINE.md` lists the five paths + their status (ACCEPTED / DRAFT / RECONSTRUCTED)
Acceptance criteria:
- AC1: `customer_health.md` is byte-identical to the fixture
- AC2: HEADLINE.md names all five and flags bakery_ng + event_hire as RECONSTRUCTED
Test plan:
- `cmp` of the two files; YAML loads
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
