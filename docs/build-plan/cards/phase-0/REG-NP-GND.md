# REG-NP-GND: Live schema context packet

ID: REG-NP-GND
Title: Live schema context packet
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-GND-PKT;NP-GND-GEN;NP-GND-EXPERT;NP-GND-DEMO;NP-GND-AUTO;NP-GND-MOD;NP-GND-G-PIPE;NP-GND-G-MAP;NP-GND-G-TEXT
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U0 F1 K0 V2 I2)
Context pack:
- `sed -n '32,65p' docs/plans/next-phase/cards/T1_LIVE_CONTEXT.md`
- `sed -n '73,78p' docs/plans/next-phase/cards/T1_LIVE_CONTEXT.md`
- `sed -n '83,87p' docs/plans/next-phase/cards/T1_LIVE_CONTEXT.md`
- `sed -n '95,105p' docs/plans/next-phase/cards/T1_LIVE_CONTEXT.md`
- `sed -n '149,205p' apps/api/app/live_schema_context.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_gnd.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-GND`. The Oracle session writes the test before the Worker. The Worker does not edit it. No product change.
Steps:
1. Read the context pack. State each pin that already names an input and an output. Reading is the only reading.
2. "Write the regression test" means the Oracle session. Score is 7, so that session writes `apps/api/tests/test_reg_np_gnd.py` before the Worker. The Worker does not edit that file. If the file is absent, STOP-AND-ASK. Do not create it in the Worker session.
3. In the Worker packet, name the product line whose deletion would make a pinned assertion fail. If a pin is already green, the regression test stays green. Do not break product code to force a red test.
4. Run the Test plan command. Second run is reverse file order. Do not add pytest-randomly. A new dependency is STOP-AND-ASK.
5. If a pin is red, stop: report the failing assertion. The Orchestrator opens a fix card. If a pin is already green, leave it green.
6. The approve row is a live check on a disposable `ingenium_*` database for 17, 18, 19 (and 20 once its stack exists). Not a fake registry. Not a new status code. If no stack is up, STOP-AND-ASK. Drop what you create (INV-03). The L2-HARNESS line is Phase 2. It is not the approve-row proof.
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong. Also stop on each row in the STOP-AND-ASK table. Do not invent the missing input or the missing output.
Acceptance criteria:
- AC1: Live schema context packet (pressure 10) (source: ledger NP-GND-PKT, next-phase cards/T1_LIVE_CONTEXT.md)
- AC2: Draft Studio prompts get the packet (pressure 12) (source: ledger NP-GND-GEN, next-phase cards/T1_LIVE_CONTEXT.md)
- AC3: Expert cites the packet when a connection exists (pressure 9) (source: ledger NP-GND-EXPERT, next-phase cards/T1_LIVE_CONTEXT.md)
- AC4: Can Odoo do this; with no client database (pressure 10) (source: ledger NP-GND-DEMO, next-phase cards/T1_LIVE_CONTEXT.md)
- AC5: Autopilot; ingest; workflow drop unknown names (pressure 10) (source: ledger NP-GND-AUTO, next-phase cards/T1_LIVE_CONTEXT.md)
- AC6: Install the missing stock app; then continue (pressure 10) (source: ledger NP-GND-MOD, next-phase cards/T1_LIVE_CONTEXT.md)
- AC7: Draft pipeline calls read the packet (pressure 8) (source: ledger NP-GND-G-PIPE, next-phase cards/T1_LIVE_CONTEXT.md)
- AC8: Import column mapping keeps only live fields (pressure 4) (source: ledger NP-GND-G-MAP, next-phase cards/T1_LIVE_CONTEXT.md)
- AC9: Display text names only live structure (pressure 5) (source: ledger NP-GND-G-TEXT, next-phase cards/T1_LIVE_CONTEXT.md)
Worked examples (pin these; do not add a stricter reject). Pin only an input and an output that this section already names. One negative per AC only where that pin already states the reject. Do not invent a stricter reject.
- Pin AC1: `build_schema_packet(connection, models=["sale.order"], ...)` → `packet.models["sale.order"].views["form"] == ("partner_id", "partner_invoice_id", "date_order")`, `fields["partner_id"].relation == "res.partner"`. A field not on the model (`x_not_on_sale`) is absent. Major 17 omits `formatted_read_group` and keeps `action_confirm`. `loaded_at` older than `SCHEMA_CATALOG_TTL_S` → `packet.is_empty()` is True. No connection raises; it does not guess Community defaults.
- Pin AC2: `ground_studio_generate("Add a field after the customer on quotations", schema_packet=packet)` puts `LIVE SCHEMA PACKET` and `partner_id` in `user_message`, sets `placement_anchor == "partner_id"`, and the result JSON does not contain `x_po_ref`. An intent host model absent from the packet is discarded, not turned into a new app.
- Pin AC3: `ask_expert(..., question="What type is partner_id on sale.order on this instance?", connection_id="fixture-sale")` → `result.grounded is True`, `result.declined is False`, and `result.answer_markdown` contains `partner_id` and `LIVE SCHEMA PACKET`.
- Pin AC4: `generate_live_answer` for "Can Odoo do quotations?", edition Community, major 20, model verdict `stock_community` / app Sales → `answer.verdict == STOCK_COMMUNITY`, `answer.app_name == "Sales"`, the surface does not ask for a database, `json_calls == 1`, `text_calls == 0`. Helpdesk on Community is Enterprise only. A bank API is never stock. Major 16 is not a demo target.
- Pin AC5: `build_job_packet(..., schema_packet=sale_packet, planned_models=["sale.order", "project.task"])` → `operator_brief["schema_models"] == ["sale.order"]` and `project.task` is not in `custom_residuals`. A version-mismatched method does not leave the planner.
- Pin AC6: on a base-only database, prompt "add a PO reference on quotations" → `status == "clarifying"`, `clarification.kind == "stock_app_install"`, `stock_app.module == "sale"`, help contains "Sales is not installed", options are "Install Sales and continue" and "Not now", and `button_immediate_install` is not called. `POST /api/ai/sessions/{id}/stock-app` with `{"decision": "decline"}` → `stopped is True`, `status == "stopped"`, message "Stopped. Sales was not installed, so this request was not built.", and the body has no `Traceback`.

| Decision | Result |
|---|---|
| decline | Unit pin. Include the POST body and the assertions already written: `POST /api/ai/sessions/{id}/stock-app` with `{"decision": "decline"}` → `stopped is True`, `status == "stopped"`, message "Stopped. Sales was not installed, so this request was not built.", and the body has no `Traceback`. The clarify assertions in the AC6 pin stay in this same unit pin: `status == "clarifying"`, `clarification.kind == "stock_app_install"`, `stock_app.module == "sale"`, help contains "Sales is not installed", options are "Install Sales and continue" and "Not now", and `button_immediate_install` is not called. |
| approve | Stays. Live check on a disposable `ingenium_*` database (step 6): `sale` installed, schema re-read includes `sale.order`, original request continues. Not a fake registry. Not a new status code. If no stack is up, STOP-AND-ASK. |
| Enterprise-only app on Community | Sentence kept. STOP-AND-ASK. Missing input: which app and which prompt. Missing output: which response fields. Do not invent either. |

STOP-AND-ASK (keep each sentence; do not assert it; do not invent the input or the output):

| Sentence | Missing input | Missing output |
|---|---|---|
| Helpdesk on Community | which prompt, edition, and major | which verdict or answer fields |
| a bank API | which prompt and which API | which verdict or answer fields |
| major 16 | which prompt and which call | which verdict or answer fields |
| a version-mismatched method does not leave the planner | which method and which version pair | which planner field must omit it |
| Enterprise-only app on Community | which app and which prompt | which response fields |
- Pin AC7: `ai_pipeline._llm_json` with a packet for `res.partner` drops invented stock field `commercial_partner_phone` and keeps `x_studio_tier` (that keep is the current green result; do not flip it). The prompt contains the packet. The same drop applies at `llm_expand_depth`, `llm_critique`, `llm_deepen_model_fields`, `llm_emit_missing_scaffold_models`, `_enrich_briefing_with_llm`, `draft_module_from_prompt`, and `call_ollama_generate`.
- Pin AC8: `enhance_mapping_with_llm` maps "Kunde Name" → `name` and "Mail Adresse" → `email`, leaves "Telefon Nr" unmapped, and the warning names `x_phone_invented` and "left unmapped". No client, or an empty live field list, does not call the LLM.
- Pin AC9: `generate_finding_narratives` given a paragraph that names `x_po_ref` replaces that paragraph with `narrative._fallback_paragraph(finding)`. A name that is in the packet (`partner_id`) stays.
Reading:
1. Score is 7 and this card has an Oracle tests line. A separate L3 Oracle session writes `apps/api/tests/test_reg_np_gnd.py` before the Worker. The Worker does not edit that file. Step 2's "write the regression test" means the Oracle session.
2. Pin only the worked-example inputs and outputs that already name an input and an output. Do not invent a stricter reject. One negative per AC only where that pin already states the reject. When that pin states more than one reject, keep each stated reject in that one negative. An AC whose pin states no reject gets no negative. For the absent-host sentence, do not invent a host-model string: the input is "absent from the packet", and the output is discarded, not a new app.
3. These sentences have no input and no expected value: Helpdesk on Community, a bank API, major 16, "a version-mismatched method does not leave the planner", and "Enterprise-only app on Community". Keep the sentences. Each STOP-AND-ASK row names the missing input and the missing output. Do not invent either.
4. The AC6 decline row is the unit pin, including the POST body and the assertions already written. The approve row stays. It is a live check on a disposable `ingenium_*` database (step 6), not a fake registry and not a new status code. If no stack is up, STOP-AND-ASK.
5. If a pin is already green, the regression test stays green. Do not break product code to force a red test. If a pin is red, stop; the Orchestrator opens a fix card.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_gnd.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_gnd.py` in reverse file order → pass. Do not add pytest-randomly.
- live: L2-HARNESS runner `--card REG-NP-GND --matrix 17,18,19,20` on disposable `ingenium_*` DBs → pass per major (Phase 2 on). That line is Phase 2. It is not the approve-row proof.
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Elite design notes: AI proposes, code authorises (INV-13): no model output reaches `execute_kw`, an install or an export without a deterministic validator. Calls go only through `app/ai_client` with untrusted text in `fence_fields` (source=...). Any call that names Odoo structure first reads the live schema packet (`live_schema_context.build_schema_packet`) and the engine rejects names not in it. Caches never store secrets or PII and never serve write plans.
Oracle tests: Score is 7. A separate L3 Oracle session writes `apps/api/tests/test_reg_np_gnd.py` (named `test_ac<n>_...`) before the Worker. The Worker does not edit that file. Step 2's "write the regression test" means the Oracle session. Pin only worked-example inputs and outputs that already name an input and an output. One negative per AC only where that pin already states the reject. Do not invent a stricter reject. If a pin is already green, the regression test stays green. Do not break product code to force a red test. If a pin is red, stop; the Orchestrator opens a fix card. E1 reviews oracles when score ≥ 10 (DEC-046); this score is 7, so no E1 review.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
