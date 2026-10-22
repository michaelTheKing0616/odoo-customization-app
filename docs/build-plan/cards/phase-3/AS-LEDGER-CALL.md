# AS-LEDGER-CALL: The Ledger call: prompt, numbered clauses, chunks, k samples

ID: AS-LEDGER-CALL
Title: The Ledger call: prompt, numbered clauses, chunks, k samples
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-LEDGER; AS-FAIL-B
Depends on: AS-LEDGER-SCHEMA, AS-STABILITY, AS-DECODE, AS-RETRIEVE, AS-TOTAL
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U2 F2 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §3, §5 (prompt word for word), §7 size classes, injection, deadline
- docs/build-plan/CODE_MAP.md rows: owner words, providers
- apps/api/app/ai_client/guards.py (`fence_untrusted`, `classify_injection`, `Redactor`; read only)
File allow-list:
- apps/api/app/ai_conversation/ledger_call.py (new)
- apps/api/tests/test_ledger_call.py (new)
Goal: `sample_ledgers(normalised, snapshot, profile, *, k, timeout_s) -> SampleResult{ledgers, failures, raw}`: k samples, each validated; long briefs chunked; raw output recorded. Concurrency and deadlines are owned by AS-V3-WIRE, which passes `timeout_s` and an executor.
Steps:
1. Prompt text exactly as Pack §5 (copy, don't paraphrase); owner clauses rendered `[cNN] …` and wrapped with `fence_untrusted(…, "owner_brief")`
2. Size class from `normalise`: normal = 1 call/sample; long = chunks of ≤ `profile.chunk_words` split by headings then paragraphs, clause ids global to the brief, merged per sample with `ledger_vote.cluster` (same identity algorithm as V)
3. Provider call: `generate_json(..., format_schema=brief_ledger.model_schema_for_provider(), timeout_s=timeout_s)`, provider default temperature
4. Parse → Pydantic validate → on a shape error, one repair call with the error list (inside `timeout_s`) → `brief_ledger.validate`; failed samples dropped and counted by fault class
5. Clauses flagged by `classify_injection` are passed to validate so any Rule quoting them is dropped with the assumption note (Pack §7 injection)
6. Write raw samples to `INGENIUM_RECORD_DIR` when set
Acceptance criteria:
- AC1: With the fake provider: 3 samples → 3 validated ledgers; 1 garbage sample → 2 ledgers + a counted failure
- AC2: The prompt string equals the Pack text (golden test)
- AC3: Owner words appear only inside the `fence_untrusted` block; the expansion appears nowhere
- AC4: Customer Health fixture → size class long, 3 chunks per sample at chunk_words = 800, clause ids unique across chunks
- AC5: §8.7 AC3 verbatim: "structured output plus validation; a fuzz test of malformed model output never reaches compile" (200 malformed variants → rejected or repaired; compile never called on an invalid object)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ledger_call.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §5. Votes give stability; never lower temperature to fake stability. This bypasses `app/ai_client` the same way `_call_llm` does today, but reuses its fence, injection classifier and Redactor, so there is one fence convention (INV-13).
Oracle tests: Golden prompt test; fake-provider sample counts; fence test with an injection string; malformed-output fuzz.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
