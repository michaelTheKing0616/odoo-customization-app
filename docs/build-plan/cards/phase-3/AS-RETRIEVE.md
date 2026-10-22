# AS-RETRIEVE: Per-connection retrieval of stock candidates

ID: AS-RETRIEVE
Title: Per-connection retrieval of stock candidates
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P1-2; AS-8.5-RETRIEVE
Depends on: none
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- handover L920 + §8.7 AC2
- docs/build-plan/CODE_MAP.md rows: snapshot, stock routing
File allow-list:
- apps/api/app/ai_conversation/retrieval.py (new)
- apps/api/tests/test_retrieval.py (new)
Goal: Top-k stock model candidates per noun phrase from the live snapshot (keyword + field-name match; embeddings later), refreshed on install.
Steps:
1. Index = installed models' `_description`, technical name tokens and field strings from the snapshot (no new Odoo calls)
2. `candidates(nouns, snapshot, k=5) -> {noun: [model…]}`; BM25-style scoring in pure Python
3. Invalidate on snapshot fingerprint change (install_step re-reads the snapshot)
4. `retrieval_block()` renders candidates for the Ledger prompt
Acceptance criteria:
- AC1: §8.7 AC2 (retrieval part) verbatim: "retrieval indexes are built per connection and refreshed on module install; the mapper cannot choose a model or field outside the retrieved set or 'new'" (the 'cannot choose' half is enforced by L4 in AS-LEDGER-SCHEMA)
- AC2: 'customer' → res.partner in top 3; 'appointment' → calendar.event in top 3 when calendar is installed (fixture snapshots for 17 and 20)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_retrieval.py`
Elite design notes: Keyword first: it is deterministic, free and explainable. pgvector is a later option (PostgreSQL licence) only if X2 shows recall misses.
Oracle tests: Fixture snapshots v17/v20: 10 noun→model expectations listed in the test, written before the code.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
