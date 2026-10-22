# EL-LDC-REPLAY: Meeting replay bench

ID: EL-LDC-REPLAY
Title: Meeting replay bench
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-LDC
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- handover §3.12
- apps/api/app/live_demo_copilot/pipeline.py
- stage1_filter.py, stage2_answer.py
File allow-list:
- apps/api/evals/ldc_replay/ (new; synthetic transcripts with timing, no real people)
- apps/api/tests/test_ldc_replay.py (new)
Goal: Feed timed transcripts through the full pipeline offline; score question detection, label accuracy and answer latency without a live meeting.
Steps:
1. Client-side vs presenter speakers marked in fixtures
2. Fake provider in CI; live provider only under the call budget
Acceptance criteria:
- AC1: report prints precision, recall, label accuracy, p95 latency
- AC2: presenter questions never answered (property)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ldc_replay.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
