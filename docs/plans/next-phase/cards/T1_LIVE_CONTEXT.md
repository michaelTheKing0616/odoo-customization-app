# Cards — live schema context for every LLM surface

The product claim is: Ingenium does not let a model invent fields, call a method the version does not have, or place a field without seeing the live view. GenerateIR already rejects an uncued invent (`proposal_allowed` in `apps/api/app/ai_generate_ir.py`). `SchemaGraph.combined_arch` can read `get_view`. These cards make every other LLM path that names Odoo structure do the same, and they put the live slice in the prompt before the call, not only in a reject gate after it.

**Context packet (one builder, every consumer).** For the connection on the request:

- installed modules (name, state)
- models in scope, each with fields: name, type, relation, required, readonly, store, groups
- for form, list, and search of each target model: the combined arch reduced to an ordered list of field names and their siblings, so "after the customer" is a real anchor (`partner_id` or whatever this database actually shows)
- server version and major, so a method that does not exist on that major is absent from the packet

The packet is built from the live connection. The system decides which slice matters for this request (the models, views, menus, and methods the words point at, plus their relations and the fields already on those views). It fetches that slice. It does not ask the user for technical names, xmlids, or where a field sits. The user states the outcome in their own words.

The packet is not the whole database. If the first slice is too small to place the change, the system widens it with another read (parent view, related model, sibling fields) and calls the model again. A name is dropped only after that lookup shows the live database does not have it and no stock Community module would provide it. The user is not sent to Odoo to check.

**Missing module.** If the request needs a model or menu that is absent because a stock Community app is not installed, Ingenium does not fail the request. It proposes installing that app, in the user's words, with the reason ("Sales is not installed, so there is no quotation to put this field on"). The user confirms once. Ingenium installs it, re-reads the schema, and continues the same request. The user is not asked which app to pick when the map is known. This is `module.install` of a stock app, with approval. It is not promote of a generated zip. Enterprise-only apps on Community are explained, not installed under a false name.

**Rule.** The model sees the slice before it answers. If it then emits a model, field, method, xmlid, or view anchor that the slice does not contain, the engine drops it before any write and repairs from the slice. It does not hand that repair to the user.

**Out of scope.** Calls with no Odoo connection that are not about Odoo capability: marketing copy, billing text, login. A demo question ("Can Odoo do this?") is in scope with no client database. That path is GND-DEMO.

**Shared do-not:** do not weaken GenerateIR admit rules; do not add a per-brief name branch; no live LLM in a PR test (fixture schema clients); no secrets in the packet; stay inside Change.

**Shared command:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_live_schema_context.py
```

---

### GND-PKT — Context packet
- **Status:** DONE. pytest `tests/test_live_schema_context.py` — 5 passed. **depends_on:** T1-A1
- **Pressure:** C2 U1 F2 K2 V2 I1 +0 = 10 → Grok high
- **Change:** `apps/api/app/live_schema_context.py`. Uses `ai_schema_client` and `odoo_client.schema_graph.SchemaGraph`.
- **Acceptance:** [ ] packet for a fixture `sale.order` lists `partner_id` and its form siblings in arch order; [ ] a field not on the model is absent; [ ] a method absent from the version table for that major is absent; [ ] stale catalog (TTL) yields an empty packet, not a stale yes.
- **Negative:** a packet built with no connection raises; it does not guess Community defaults.

### GND-GEN — Draft Studio generation
- **Status:** DONE. pytest `tests/test_gnd_gen_live_schema.py` and `tests/test_live_schema_context.py` — 9 passed. **depends_on:** GND-PKT
- **Pressure:** 12 → Grok high
- **Change:** `ai_conversation/intent_llm.py`, `ai_conversation/understand.py`, `ai_conversation/refine.py`, and the studio generate path in `routers/ai_studio.py`. Prepend the packet to the user message. After the model returns, run the existing admit gate.
- **Acceptance:** [ ] a test with a fake client whose `sale.order` has no `x_po_ref` shows the prompt contains the packet and the result does not contain `x_po_ref`; [ ] "add a field after the customer" resolves the anchor from the packet's form order.
- **Negative:** intent JSON that names a model the packet does not contain is discarded, not repaired into a new app.

### GND-EXPERT — Expert when a connection exists
- **Status:** DONE. pytest `tests/test_gnd_expert_live_schema.py` and `tests/test_expert_ask.py` — 25 passed. **depends_on:** GND-PKT
- **Pressure:** 9 → Grok standard
- **Change:** `expert/ask.py`. Live Demo with no database is GND-DEMO, not this card.
- **Acceptance:** [ ] an answer that names a field cites the packet; [ ] if the first slice lacks the field, the system reads again (search by the user's words) before answering; [ ] it declines only when that second read shows the database has no such field and no stock place to add one.
- **Negative:** retrieval notes alone cannot introduce a field the live packet does not contain. The user is not asked to open the form and report field names.

### GND-DEMO — "Can Odoo do this?" with no client database
- **Status:** DONE. pytest `tests/test_gnd_demo.py` — 14 passed. One scripted model call proposes the verdict. The version table checks it. A failed check becomes not sure. **depends_on:** none.
- **Pressure:** C2 U1 F3 K2 V2 I0 +0 = 10 → Grok high
- **Change:** `live_demo_copilot/stage2_answer.py`. No connection is required. The consultant picks the demo target: major **20 by default**, or **19, 18, or 17**. Major 16 and below are not demo targets. They also pick the edition the client is asking about: Community, Enterprise, or both. Hosting (Online, Odoo.sh, on-prem) is named only when the capability depends on it.
- **Verdict, then bullets.** Each answer names the edition. It is one of: stock Community (name the app), stock Enterprise only (name the app, and say it is not in Community), stock once that app is installed, customization, or not sure. The two or three overlay bullets are cut from that verdict. A second model call must not rewrite them.
- **Acceptance:** [ ] "Can Odoo do quotations?" with no connection, edition Community, major 20, answers stock Community, app Sales, and does not ask for a database; [ ] "Can Odoo do a helpdesk?" on Community answers Enterprise only (Helpdesk), not stock Community and not customization; [ ] "Can Odoo post to our bank's API?" answers customization or not sure, never stock; [ ] a feature that exists only on 20 is not described as stock when the demo target is 19; [ ] low confidence stays on screen when the verdict is not sure.
- **Negative:** the overlay never says "connect a database" as the answer to a capability question. It never describes an Enterprise app as Community stock. It never claims a field or menu that the version table does not list for the selected major and edition.

### GND-AUTO — Autopilot, ingest, workflow
- **Status:** DONE. pytest `tests/test_gnd_auto_live_schema.py` — 8 passed. The job entry builds the packet itself. **depends_on:** GND-PKT
- **Pressure:** 10 → Grok high
- **Change:** `job_autopilot/planner.py`, `ingest/classify.py`, `ai_workflow.py`.
- **Acceptance:** [ ] planner output that references a model or method outside the packet is dropped before sandbox apply; [ ] version-mismatched method names do not leave the planner.

### GND-AGENT — Bot tools use the same packet
- **Status:** OPEN. **depends_on:** GND-PKT, T8-TOOLS
- **Pressure:** 11 → Grok high
- **Change:** `agent_runtime` inspection tools (`describe_model`, view tools). They read the packet. They do not keep a second schema cache.
- **Acceptance:** [ ] `describe_model` output is a subset of the packet; [ ] `view_test_xpath` uses `combined_arch` from the same graph the packet used.

### GND-MOD — Install the stock app, then continue
- **Status:** OPEN. **depends_on:** GND-PKT, T8-OP-SET (`module.install`)
- **Pressure:** C2 U1 F2 K2 V2 I1 +0 = 10 → Grok high
- **Change:** a stock-app map (user words and missing model → Community module technical name) and one confirm step used by every GND consumer. Fresh database with only base is the fixture.
- **Acceptance:** [ ] "add a PO reference on quotations" against a database without `sale` proposes installing Sales, states why, and does not error; [ ] after approval, `sale` is installed, the schema is re-read, and the original field request continues; [ ] declining the install stops that request without a stack trace; [ ] the user is not asked to name the app.
- **Negative:** a Community connection is not offered an Enterprise-only app as if it could be installed. Uninstall is not offered. A generated zip is not installed by this path.

### Grounding the 13 sites GND-GATE lists as `ungrounded` (founder decision 2026-10-05: ground all 13)
Shared rule for the four cards below: before the call, put the connection's `schema_packet` slice in the prompt. After the call, check every model, field, method, or view placement the output names against that slice, and reject or strip anything not in it. Each site gets a fake-LLM test where the output invents a name and the test proves it is dropped or refused (no live LLM). The site's GND-GATE allowlist entry moves from `ungrounded` to `live_packet` in the same change. With no connection, the site refuses to name structure rather than guess.

### GND-G-PIPE — Draft pipeline calls read the packet
- **Status:** OPEN. **depends_on:** GND-PKT, GND-GEN, GND-GATE
- **Pressure:** C2 U1 F2 K2 V1 I0 +0 = 8 → strong generalist
- **Change:** `ai_pipeline._llm_json`, `ai_depth.llm_expand_depth`, `ai_critique.llm_critique`, `ai_model_quality.llm_deepen_model_fields`, `ai_model_quality.llm_emit_missing_scaffold_models`, `ai_domain_briefing._enrich_briefing_with_llm`, `ai_ollama.draft_module_from_prompt`, `ai_ollama.call_ollama_generate` (no callers today: ground it or delete it, and say which). Use one shared helper for prompt and filter; each site keeps its own output format.
- **Acceptance:** [ ] all 8 sites are `live_packet` in the GND-GATE test; [ ] for each, an invented stock-model field in the fake output is dropped before it reaches the draft (new `x_*` fields the draft proposes to create stay allowed); [ ] the existing generation-engine tests that pass today still pass, and the 10 known failures are not made worse.

### GND-G-OPTA — Option A authoring reads the packet
- **Status:** OPEN. **depends_on:** GND-PKT, GND-GATE
- **Pressure:** C3 U2 F2 K2 V2 I1 +0 = 12 → Grok high
- **Change:** `ai_option_a_author._default_generate_blocks` and `ai_option_a_feedback._default_repair_blocks`. Pass the packet slice for the host model(s). Statically check the authored code before the sandbox: `_inherit`/`_name` hosts, `self.env['…']` models, field names on known hosts, and view `inherit_id` plus xpath targets against `combined_arch`.
- **Acceptance:** [ ] both sites are `live_packet` in the GND-GATE test; [ ] authored code referencing a field missing on the host is refused before zip/sandbox with a message naming the field; [ ] an xpath target missing from the host view's `combined_arch` is refused the same way; [ ] the gold shortcuts and the authoring gate keep passing their existing tests.

### GND-G-MAP — Import column mapping keeps only live fields
- **Status:** OPEN. **depends_on:** GND-PKT, GND-GATE
- **Pressure:** 4 → cheap
- **Change:** `ingest/map_columns._llm_map_columns`.
- **Acceptance:** [ ] the site is `live_packet` in the GND-GATE test; [ ] a mapping to a field not in the live list is dropped and the column is left unmapped with a reason; [ ] with no client or an empty field list, the LLM is not called and the columns stay unmapped.

### GND-G-TEXT — Display text names only live structure
- **Status:** OPEN. **depends_on:** GND-PKT, GND-GATE
- **Pressure:** 5 → cheap
- **Change:** `expert/narrative.generate_finding_narratives` and `routers/ai_studio.refine_session_route`.
- **Acceptance:** [ ] both sites are `live_packet` in the GND-GATE test; [ ] a model or field technical name in the generated text that is not in the packet (or, for refine, not in the admitted patch) is removed or the sentence is replaced with a fixed fallback; [ ] existing tests for both surfaces pass unchanged.

### GND-GATE — No ungrounded LLM surface left
- **Status:** SEEDED (gate test built 2026-10-05). **depends_on:** GND-GEN, GND-EXPERT, GND-AUTO, GND-AGENT, GND-MOD, GND-DEMO, GND-G-PIPE, GND-G-OPTA, GND-G-MAP, GND-G-TEXT
- **Pressure:** 6 → cheap
- **Acceptance:** [ ] a test walks every `generate_json` / `generate_text` call site under `apps/api/app` and fails if a new site appears that is not on the allowlist (the four cards above, plus `wireframe_live.py`, which must keep refusing to invent regions). Adding a call site means updating this test in the same change.
