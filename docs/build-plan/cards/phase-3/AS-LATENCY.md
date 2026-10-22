# AS-LATENCY: v3 streamed read-back (provisional sample 1, confirmed on vote)

ID: AS-LATENCY
Title: v3 streamed read-back (provisional sample 1, confirmed on vote)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-LATENCY-ROW
Depends on: AS-V3-WIRE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C2 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §8 item 1, §7 deadline
- docs/build-plan/CODE_MAP.md row: create session
File allow-list:
- apps/api/app/ai_conversation/v3_pipeline.py (an optional `on_event` callback parameter only)
- apps/api/app/routers/ai_studio.py (NDJSON stream endpoint `POST /stream`, v3 only)
- apps/api/tests/test_v3_latency.py (new)
Goal: The owner sees the read-back as soon as the first ledger sample validates (marked provisional), and rows confirm or fade when the vote lands; no new orchestrator.
Steps:
1. `on_event(kind, payload)` hook inside `v3_pipeline.run`: `provisional` (sample 1 after validate), `understood` (after V), `questions?`, `outcome`
2. NDJSON endpoint streams those events; the final line is the same `StudioOutcome` the non-stream route returns
3. Payloads carry quotes for display (restored by `Redactor.restore`) but never log them (INV-17)
Acceptance criteria:
- AC1: With the fake provider (sample 1 at 1 s, others at 3 s), the first `provisional` event arrives before 1.5 s
- AC2: The final streamed outcome equals the non-stream outcome for the same fake run (byte compare)
- AC3: Client disconnect mid-stream does not raise in the server (test with a closed generator)
- AC4: Live time-to-first-row and p95 measured by AS-CONTRACT-EVAL (bar p95 < 45 s)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_v3_latency.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
