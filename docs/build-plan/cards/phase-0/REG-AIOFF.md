# REG-AIOFF: regression: ai_assist off returns None provider (mock tier allowed)

ID: REG-AIOFF
Title: regression: ai_assist off returns None provider (mock tier allowed)
Status: done
Phase: 0
Priority: P0
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: H-2.7-AIOFF
Depends on: B0-INV
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F1 K0 V0 I0)
Context pack:
- `sed -n '164p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_aioff.py (new)
Goal: Pin the already-fixed behaviour behind `REG-AIOFF` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: regression: ai_assist off returns None provider (mock tier allowed) (source: ledger H-2.7-AIOFF, §2.7)
Symbols: `resolve_provider_mode()` and `_raw_provider_for_tier(tier="fast")` in `apps/api/app/llm_provider.py`. `settings.ai_assist` default `"off"`. `settings.ai_llm_tier_fast` default `"gemini"`.
Worked example:
- Example AC1: `ai_assist="off"` and `ai_llm_tier_fast="gemini"` → `_raw_provider_for_tier("fast")` is `None`. `ai_assist="off"` and `ai_llm_tier_fast="mock"` → the result is a `MockLLMProvider`.
Decision table (`_raw_provider_for_tier("fast")`):
| `ai_assist` | `ai_llm_tier_fast` | result |
| off | gemini | `None` |
| off | mock | `MockLLMProvider` |
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_aioff.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_aioff.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
