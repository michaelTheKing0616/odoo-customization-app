# AS-GROUND-WIRE: One live schema packet per v3 run, used by every stage

ID: AS-GROUND-WIRE
Title: One live schema packet per v3 run, used by every stage
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-GROUND
Depends on: AS-V3-WIRE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.7 item 1
- apps/api/app/live_schema_context.py L130-300 (build/studio packet)
- apps/api/app/ai_conversation/understand.py L1428-1462 (how the intent call prepends the packet today)
File allow-list:
- apps/api/app/ai_conversation/v3_pipeline.py
- apps/api/app/ai_conversation/ground_v3.py (new)
- apps/api/tests/test_ground_v3.py (new)
Goal: Build the packet once at t=0 (parallel with N) for contract/retrieval hosts plus direct relations; give K and L the fenced render, C/D/A/preview the structured packet.
Steps:
1. `ground_v3.packet_for_run(connection, hosts, profile) -> SchemaPacket` wraps `studio_schema_packet`; records its fingerprint on the run
2. K and L prompts get `fence_untrusted(render_schema_packet(p))`; C, D, A and the preview receive the same object
3. Connection present + empty or stale packet → `StudioOutcome.degraded` with a plain reason; no design emitted
4. After `install_step` (GND-MOD) rebuild the packet before the next stage; log both fingerprints
5. Prompt text carries names and counts only, never record contents (INV-17)
Acceptance criteria:
- AC1: ORACLES G-01, G-02, G-03 and G-12 pass unmodified
- AC2: No v3 stage reads Odoo structure from anywhere but the run's packet (import-graph test)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ground_v3.py`
Elite design notes: Pack §6.7. The packet is the only door to Odoo structure for the LLM stages; a second read path is a defect.
Oracle tests: docs/build-plan/app-studio/ORACLES.md: app-studio/ORACLES.md G-01, G-02, G-03, G-12
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
