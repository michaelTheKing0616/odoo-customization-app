# AS-TOTAL: Total-function boundary: one outcome for every brief and every failure (both profiles)

ID: AS-TOTAL
Title: Total-function boundary: one outcome for every brief and every failure (both profiles)
Status: todo
Phase: 3
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-ANYBRIEF; AS-RC6
Depends on: AS-ROBUST-FUZZ
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 8 (C2 U1 F2 K2 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §1, §7 (N, size classes, injection, provider faults, Odoo faults)
- docs/build-plan/app-studio/ORACLES.md §T (rows whose Card column is AS-TOTAL)
- docs/build-plan/CODE_MAP.md rows: create session, clarify/generate, LLM call, outline fallback
File allow-list:
- apps/api/app/ai_conversation/studio_outcome.py (new)
- apps/api/app/ai_conversation/brief_normalise.py (new)
- apps/api/app/routers/ai_studio.py (create + generate routes: wrap only)
- apps/api/app/ai_conversation/app_design.py (`_call_llm` exception list; the two `AppDesign.from_dict` call sites L2784/L2809 wrapped)
- apps/api/tests/test_studio_outcome_total.py (remove xfail on this card's rows only)
Goal: Both routes return a `StudioOutcome` (proposal | questions | declined | degraded) for every input and fault on the **legacy** pipeline; v3 reuses the same type and normaliser later (AS-V3-WIRE). This card has no dependency on any v3 stage.
Steps:
1. `studio_outcome.py`: Pydantic discriminated union as in Pack §1 table; `degraded.cause` plain text from `_fallback_reason`
2. `brief_normalise.py`: `normalise(text) -> Normalised{text (NFC), clauses: [(id, start, end)], size_class, words}`; control chars, newline collapse, clause numbering (`[c01]` rendering helper), size classes with thresholds read from the profile (`chunk_words`, tiny < 8, too-long > 15,000). AS-LEDGER-CALL and AS-LEDGER-SCHEMA import it; do not duplicate it
3. `_call_llm`: also catch `URLError`, `JSONDecodeError`, `ValidationError`, `KeyError`, `TypeError`, `ValueError` from parsing; map to status `failed` with the class name
4. Wrap `AppDesign.from_dict` call sites so a shape error becomes the existing repair/outline fallback, never an exception
5. Route boundary: one `except Exception` → `degraded` + `logger.exception` + request id; a counter increments (the fuzz asserts 0)
6. Legacy keeps its response shape plus a new `outcome` key (additive), so the UI is not broken
Acceptance criteria:
- AC1: ORACLES T-01 (legacy positions), T-02, T-03, T-04, T-05, T-06 (legacy), T-08 pass with xfail removed
- AC2: No route in ai_studio.py returns 5xx under the legacy fault matrix
- AC3: The boundary catch-all fires 0 times in the suite
- AC4: Existing studio tests unchanged and green
- AC5: `normalise` is pure and its clause intervals tile the content (property test: concatenating clause slices + separators reproduces the NFC text)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_studio_outcome_total.py tests/test_studio_step2a_app_design.py tests/test_studio_step3_design_build.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §7. The catch-all is a safety net and a test target: any real failure class found must get its own mapping. Do not widen the exception list beyond the names in Steps without a Reviewer note. Deadlines, top-up samples and the v3 fault positions belong to AS-V3-WIRE, not here.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §T rows marked AS-TOTAL, written by AS-ROBUST-FUZZ; this card may only remove those xfail markers.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
