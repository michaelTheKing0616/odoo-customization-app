# AS-DECODE: Constrained decoding on Gemini (schema passed, probe recorded)

ID: AS-DECODE
Title: Constrained decoding on Gemini (schema passed, probe recorded)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P1-2; AS-8.5-DECODE; AS-RC5
Depends on: AS-PROFILE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U2 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §2 RC5, §5 (schema line)
- docs/build-plan/CODE_MAP.md row: providers
- handover L921 + §8.7 AC3
File allow-list:
- apps/api/app/llm_provider.py (`GeminiProvider.generate_json` only)
- apps/api/app/ai_conversation/schema_tools.py (new)
- apps/api/tests/test_gemini_schema.py (new)
Goal: Gemini receives the Pydantic-derived schema. Validation, repair and the malformed-output fuzz live in AS-LEDGER-CALL (AC5), which owns the caller.
Steps:
1. `schema_tools.to_gemini(schema)`: inline `$ref`, drop unsupported keywords (`additionalProperties`, `default`, `title`, `$defs`), keep `propertyOrdering`
2. Probe once on a 3-field schema with a live call (1 call; GATE-A): try `responseJsonSchema`, then `responseSchema`; record which works in FACTS.md [Verified]
3. `generate_json(format_schema=…)` sets `responseMimeType: application/json` + the working key; when `format_schema` is None, behaviour is byte-identical to today
Acceptance criteria:
- AC1: The request body built by `generate_json` with a schema contains the working key and the converted schema (unit test on the request builder; no network)
- AC2: `to_gemini` output contains none of the dropped keywords (unit test over the provider BriefLedger schema and the AppDesign schema)
- AC3: Live probe result recorded with date and model id
Test plan:
- `cd apps/api && uv run pytest -q tests/test_gemini_schema.py`
Elite design notes: Gemini's schema subset is [Inferred] from docs and must be verified by the probe. If neither key works, keep mime-type JSON and rely on validation + repair; record that and continue.
Oracle tests: Request-builder golden test (schema present, mime type set; no schema → body unchanged).
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
