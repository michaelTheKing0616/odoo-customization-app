# REG-NP-T1c: Retire the rest of the scrub

ID: REG-NP-T1c
Title: Retire the rest of the scrub
Status: done
Phase: 0
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: NP-T1-RET
Depends on: REG-NP-T1
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 9 (C2 U1 F2 K2 V1 I1)
Context pack:
- `sed -n '195,207p' docs/plans/next-phase/cards/T1_SCHEMA_GROUNDING.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/app/ai_brief_cues.py
- apps/api/app/ai_conversation/understand.py
- apps/api/tests/test_continuous_invent_class.py
- apps/api/tests/test_generate_ir_closed_class.py
- apps/api/tests/test_reg_np_t1c.py (new)
- apps/api/tests/test_reg_np_t1.py
- apps/api/tests/test_brief_understanding_class.py
- apps/api/tests/test_notes_surface_class.py
Goal: Finish T1-RET after the Date family. Do not bring the Date drop back.
Steps:
1. Read the context pack. The Date family is already kept. Leave it kept.
2. Replace the remaining scrub calls with a no-op that asserts nothing was removed.
3. Move Date, Datetime, and money into `approved_craft` only if that edit stays inside the allow-list. If it needs another file, stop and name it.
4. Do not edit `ai_generate_ir.py`. The `seed_snapshot` suspect stays off this card.
5. STOP-AND-ASK: a needed file is outside the allow-list, or the full battery cannot be run here.
Acceptance criteria:
- AC1: Uncued Type, Priority, Rate/Unit, Severity, Channel, and Stage rows are kept, and the removed list is empty. (source: ledger NP-T1-RET)
- AC2: Date, Datetime, and money are in `approved_craft`, or the card records the file that blocks that step. (source: ledger NP-T1-RET)
Test plan:
- `cd apps/api && uv run pytest -q -p no:randomly tests/test_reg_np_t1.py tests/test_reg_np_t1c.py tests/test_continuous_invent_class.py tests/test_generate_ir_closed_class.py tests/test_brief_understanding_class.py tests/test_notes_surface_class.py` → pass
Gate: none (no Tope gate). Narrowest named test green → Tester PASS → Reviewer PASS.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code]).
Rollback: Revert only the allow-list files.
Definition of Done: Both ACs have evidence; the Date family is still kept; no file outside the allow-list changed.
Elite design notes: The Date drop is already retired on REG-NP-T1. This card retires the other invent families without restoring that drop. A full battery run is recorded only if this card actually runs it.
Oracle tests: `test_reg_np_t1c.py` fails if an uncued Severity, Channel, Stage, Type, Priority, or Unit row is removed. It also fails if Due date is removed again.
