# AS-PROMPT-CONTRACT: Contrastive few-shot pairs + manifest guard

ID: AS-PROMPT-CONTRACT
Title: Contrastive few-shot pairs + manifest guard
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-FIX-3
Depends on: AS-LEDGER-CALL
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C1 U1 F1 K0 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §5 (few-shot line)
- apps/api/evals/v2/FEWSHOT_MANIFEST.json
File allow-list:
- apps/api/app/ai_conversation/ledger_fewshot.py (new)
- apps/api/evals/v2/FEWSHOT_MANIFEST.json
- apps/api/tests/test_fewshot_manifest.py (new)
Goal: Two contrastive pairs (dimension vs record) from domains absent from every eval split, with a guard test.
Steps:
1. Write the 2 pairs as tiny briefs + their expected ledgers
2. Add their domains and n-gram fingerprints to the manifest
3. Test: no few-shot sentence shares a 6-gram with any readable eval brief (dev, dev2, unseen). `holdout_fresh/` is never opened, so it cannot be n-gram checked: instead the few-shot domains must be absent from the domain list in the manifest, and AS-HOLDOUT-RUN runs the same 6-gram test right after the unseal, before scoring (a hit voids the run)
Acceptance criteria:
- AC1: Guard test passes
- AC2: Few-shot text is injected into the Ledger system prompt after the rules
Test plan:
- `cd apps/api && uv run pytest -q tests/test_fewshot_manifest.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
