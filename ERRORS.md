# ERRORS.md — Failure Log

> Check this before suggesting an approach to a task similar to one that's failed before.
> Log any approach that took more than ~2 attempts to work.

## Format
```
### [Date] — [what was being attempted]
**Didn't work:** the approach that failed
**Worked instead:** what actually fixed it
**Note for next time:** one line, generalized if possible
```

### 2026-09-14 — TRUST-6 LLM tests ignored AI_ASSIST
**Didn't work:** Asserting `get_llm_provider().name` follows `AI_ASSIST=auto` while `settings.ai_llm_tier_fast` defaults to `"gemini"`.
**Worked instead:** Autouse fixture sets `ai_llm_tier_fast`/`refine` to `"auto"`; mark the module `no_app_db`.
**Note for next time:** `get_llm_provider()` is `get_llm_provider_for_tier("fast")`. Tests that assert AI_ASSIST routing must not leave the default Gemini tier.

### 2026-09-14 — Designer CMP-3 two preview-theme-scope nodes
**Didn't work:** Wrapping `OdooPreviewScope` in `PreviewThemeScope` (both render `data-testid="preview-theme-scope"`).
**Worked instead:** Pass `previewVars` into `OdooPreviewScope`; one theme scope per canvas.
**Note for next time:** Playwright `getByTestId("preview-theme-scope")` is strict. Nested theme scopes fail CMP-3.

### 2026-09-14 — Sandbox ParseError was amount_tax xpath; Expert blamed xmlrpc.py
**Didn't work:** Live schema treated traceback `xmlrpc.py` as `ir.model` `xmlrpc` and won over the ParseError.
**Worked instead:** ParseError / cannot-be-located xpath wins; skip traceback filenames; rewrite sale.order `amount_tax` inherit to `tax_totals` on zip.
**Note for next time:** Community 17–19 sale form has `tax_totals`, not `amount_tax`. `xmlrpc.py` is not a model. Restart `:8001`.

### 2026-09-14 — Install Sales 404 was our API, not Odoo
**Didn't work:** After Install Sales, App Studio called `POST /api/ai/option-a/reverify`. Local uvicorn on `:8001` has no `--reload`, so that new route 404'd as FastAPI `Not Found`. Expert treated an empty `Error log:` paste as an Odoo RPC fault (`generic_fault_fallback`).
**Worked instead:** Include `METHOD path` on API 404s; if install succeeded and reverify 404s, show restart + **Re-check authoring gate**. Expert: empty Diagnose ≠ RPC; platform 404s use product facts + Gemini/RAG, not view/ACL steps.
**Note for next time:** Kill/restart `:8001` after new API routes. Do not map FastAPI 404 onto Designer/Access Matrix.

### 2026-09-14 — Option A author JSON was a bare array
**Didn't work:** `parse_llm_json_object` required a dict. Gemini returned `[{source_file, content}, …]` → `not an object (expected a ModuleSpec draft)`.
**Worked instead:** `coerce_author_payload` wraps arrays/files into `{blocks}`.
**Note for next time:** Option A author JSON is files, not a ModuleSpec root. Restart `:8001`.

### 2026-09-14 — Option A author JSON unterminated string
**Didn't work:** `json.loads` on Gemini output. Truncation mid-`content` raised `Unterminated string starting at: line 11 column 16 (char 1081)`; UI still said Gemini was busy.
**Worked instead:** Repair truncated JSON (close strings + stack-close braces), compact retry, operator message is incomplete JSON.
**Note for next time:** Option A files live inside JSON strings — truncation looks like JSONDecodeError, not HTTP 503. Restart `:8001`.

### 2026-09-14 — Option A author skipped Gemini 503 retry
**Didn't work:** `_default_generate_blocks` called `provider.generate_json` directly. Gemini HTTP 503 high demand became `author_failed` + `empty_module`; zip stayed locked; App Studio had no Retry.
**Worked instead:** Author through `generate_json_with_timeout_retry` (503 backoff + configured fallbacks). Transient fail omits `empty_module` and shows **Retry authoring**.
**Note for next time:** Option A authoring must use the same 429/503 retry as draft JSON. Restart `:8001`.

### 2026-09-10 — App Studio “existing form” emptied a Sales markup brief
**Didn't work:** Operator picked “Add it to a form you already use.” Clarify appended “Add fields on an existing Odoo form,” which matched `_LIVE_FIELD_SIGNAL_RE` (`field`) and demoted `python_logic` (markup + WHT) off `option_a_authored`. Draft became `models: []`, title = prompt[:80], CTA **Install this app**.
**Worked instead:** Skip pack/stock chips when classify is gold/authored; markup/WHT stays primary Option A even if the merge says “fields”; seed inherit `sale.order` with Markup % 10–25; App Studio zip/sandbox/Promote, not Install.
**Note for next time:** Clarification copy must not inject live-field tokens (`field`, `rate`) onto Python/QWeb jobs. Restart `:8001`. Do not Live Apply markup/WHT.

### 2026-09-09 — Vendor TIN inherit xpath matched five partner_id nodes
**Didn't work:** `//field[@name='partner_id']` after on `account.view_move_form`. Odoo 19 has the header Vendor plus `partner_id` columns inside `invoice_line_ids` / `line_ids` (5 nodes). Inherit create/update raises; Apply swallowed it as a warning; the bill stayed stock (no TIN, no EXTENSION).
**Worked instead:** `//group[@id='header_left_group']//field[@name='partner_id']` (exactly one). Bare `//field[@name=…]` on stock forms must exclude `ancestor::field`.
**Didn't work:** After unique `header_left_group//partner_id`, Apply updated the inherit (x_tin in combined arch) but the bill still looked stock. `partner_id` lives in `div.o_col` with `nolabel="1"` (Vendor search widget). Injecting after the field put TIN *inside* that widget, unlabeled, so it does not show as a form row.
**Worked instead:** xpath `//group[@id='header_left_group']/div[@class='o_col']` position after — TIN is a labeled group sibling under Vendor, above Bill Reference.
**Note for next time:** Stock header widgets (nolabel partner many2one in `o_col`) are not group rows. Inherit after the widget container, not after the field.

### 2026-09-08 — App Studio Download module zip → Internal Server Error
**Didn't work:** `POST .../module-spec/export-zip` called `resolve_sandbox_major(conn.server_version)`. Stored version is `"19.0"`; `int("19.0")` raises ValueError → FastAPI 500. Gold CBN zip itself builds fine.
**Worked instead:** Parse dotted/`+e` version strings; `sandbox_major_for_connection` never raises; zip codec errors return 422 with `message`.
**Note for next time:** Connection `server_version` is a string. Never pass it to `int()` / `resolve_sandbox_major` without coercing the major first.

### 2026-09-08 — CBN prompt Live-Applied Purchase Requests
**Didn't work:** Pasting the CBN live-rates prompt into App Studio (often the remembered Purchase Request session / Refine box) then **Install this app**. Live Apply only writes ir.model/fields/menus — it cannot install Python, `ir.cron`, or a CBN Service. The Currency field on Purchase Request is `x_currency_id`, not `res.currency.rate`.
**Worked instead:** Start **new** app (not Refine). Gold `currency_rate_cbn` zip → sandbox → Accounting Settings → Service = CBN → Update now → Currencies → USD → Rates. Live Install of gold is 409. Refine of a CBN prompt onto a residual form is refused.
**Note for next time:** Apply counts like `0 model(s), 5 field(s), 2 menu(s)` on an existing x_* tile mean re-apply of that app, not Option A. Restart `:8001` after gold code lands.

### 2026-08-31 — Retry AI enrichment died in ~2s (hollow Punch Card)
**Didn't work:** Clicking Retry repeatedly; UI showed “recovered from saved snapshot” and still only `x_name`. Live `:8001` (no `--reload`) had loaded `ai_document_shape` before `draft_needs_residual_recovery` existed; lazy import of newer `ai_enrich_jobs` then raised `ImportError` and the job failed instantly.
**Worked instead:** Restart uvicorn on `:8001`; enrich job reloads stale shape/warm modules on ImportError; wizard surfaces the job error instead of only the hollow snapshot note.
**Note for next time:** After API code changes, kill/restart `:8001`. A ~2s Retry + hollow JSON is almost always a failed enrich job (check `GET /api/jobs/{id}` error), not “AI still down.”

### 2026-08-31 — Applied Visitor Log had model but no home app
**Didn't work:** Re-Apply + group-membership fix alone. Root cause was `web_icon: fa-book,#714B67` — Odoo 19 `_compute_web_icon_data` treats it as a file path and aborts menu create; `_ensure_menus` swallowed the error. Then `res.users.groups_id` does not exist on 19 (`group_ids` does).
**Worked instead:** Sanitize FA icons to `base,static/description/icon.png` on live Apply; write `group_ids`; create menus on Elite Test (root 351). Hard-refresh home grid — not Apps.
**Note for next time:** If model/views exist but no root menu, check Apply warnings for `Menus skipped` and FA web_icon.

### 2026-08-31 — Applied Visitor Log invisible (Apps search + Open in Odoo)
**Didn't work:** Expecting live Apply to appear under Apps → search `visitor_log`, and assuming Open-in-Odoo would work for admin without group membership. Apply restricted the root menu to `Visitor Log User` and never joined the connection login.
**Worked instead:** After menu/ACL apply, add draft app groups to `res.users` of the applying uid. Re-Apply (or Settings → Users → Visitor Log User), then refresh Odoo home — not Apps.
**Note for next time:** Empty Apps search after Apply is expected for metadata residuals. Invisible home tile after Apply is almost always a menu group without user membership.

### 2026-08-31 — Gemini 429 fallback 404’d Ollama with a cloud model id
**Didn't work:** After Retry-After, fallback built `OllamaProvider()` then `generate_json` used `resolve_bulk_model()` (`gemini-2.5-flash`). Ollama `/api/generate` returned HTTP 404. Pipeline labeled the empty seed `step1 timed out`.
**Worked instead:** `_ollama_local_model` never accepts gemini-/gpt-/claude- ids; 429 fallback passes `OLLAMA_MODEL`. Empty step1 says `timed out` only when the error was a timeout.
**Note for next time:** `AI_ASSIST=gemini` + `AI_MODEL_BULK=gemini-2.5-flash` must not be the Ollama tag. “Retry AI enrichment” on an honesty-finished draft repeats the same 429/404 path.

### 2026-08-27 — Same visitor prompt recovered Hotel Management after timeout
**Didn't work:** Wizard catch called `pickCachedDraft` with exact-prompt match then `entries[0]`. The 16:31 hotel pack was saved under the visitor prompt, so timeout recovery showed Hotel Management / Completeness 9.1 / Cert Reject as if it were the new job.
**Worked instead:** Skip cache rows whose `domain_pack` is not named in the prompt; never fall back to newest snapshot; ignore a streamed hotel partial the same way.
**Note for next time:** “Draft recovered from a saved snapshot” + an old timestamp is cache, not a new generation. Do not Apply or enrich that JSON.

### 2026-08-27 — Office visitor log became Hotel Management
**Didn't work:** Hotel pack regex treated bare `front desk` as PMS. `match_domain_pack` seeded hotel; LLM/app-bar grew 12 models + `x_bill` + invoice/sale inherits. Completeness 9.1 was pack hygiene. Critique proposed `x_visitor_log` then skipped it.
**Worked instead:** Collocate `front desk`/`check-in` with hotel/PMS/room/folio; Expert closer rebuilds when the stamped pack would not rematch the prompt.
**Note for next time:** If `_pipeline` is `pack_seed` and `domain_pack` is hotel/restaurant but the brief is a paper log / inherit field, routing leaked — do not Apply.

### 2026-08-27 — SLA invoice field pack became Restaurant Management
**Didn't work:** Create draft called `seed_studio_draft` → `match_domain_pack` while honesty already said `field_pack`. Bare `\bmenu\b` matched “shouldn't see a new menu”. `pack_seed_skips_llm` returned the restaurant pack; closer/app-bar added `x_bill` and Option A computes. Completeness 9.3 was pack hygiene, not the brief.
**Worked instead:** Seed field_pack from the component builder before any vertical pack; skip app-bar on inherit drafts; restaurant menu only as food/dining menu; Expert closer rebuilds from the prompt.
**Note for next time:** If `_generation_engine.grain` is field_pack but `domain_pack` is a vertical, routing leaked — do not Apply or Expert-merge the pack.

### 2026-08-27 — Autopilot warned account missing after invoice smoke
**Didn't work:** Calling `detect_l10n` before installing named stock apps on a SKIP_GATE_MODULES DB. `account.move` was absent, so the warning stuck even after `sale` pulled Accounting and quote→invoice passed.
**Worked instead:** Probe l10n after installs; reconcile named apps that landed as dependencies; unknown country must not assume `l10n_generic_coa`. Coverage 8.0 was the warning cap, not a missing CoA.
**Note for next time:** A bootstrap warning from a pre-install probe is a scoring lie when later probes show CoA/journals/invoices.

### 2026-08-27 — False Expert-fix banners from ready:false
**Didn't work:** Treating `_live_apply.ready === false` as “missing dates/mixins” and `draftFinisherComplete` as false whenever Apply is blocked. Expert closer always ran pack-merge on empty `stock_reuse` and forced `needs_work` because `grain=full_app` + Cert ReviewRequired.
**Worked instead:** Banners quote `_live_apply.findings` only; unfinished = missing `_scorecard`. Closer no-ops / reverts on stock_reuse; restores dropped next_activity rows then stamps mixins.
**Note for next time:** `ready: false` with empty findings is intentional (nothing to Apply). Do not ask Expert to invent x_*. Completeness ≠ Cert ≠ Autopilot.


### 2026-08-27 — 09:25 stock_reuse presented as 0-model Gold
**Didn't work:** Empty `stock_reuse` spec scored Completeness 10.0 → Cert Gold; `complete_matched_pack_draft` overwrote `_llm_status` to pack_fallback; architecture merge kept residual budget 8 + “alternatives” ambiguity; wizard counted 0 models as failure chrome.
**Worked instead:** Cap Cert at ReviewRequired; keep `_llm_status.reason=stock_reuse`; force architecture budget 0; UI lists named Community apps + Job Autopilot CTA; hide Apply/Expert/zip.
**Note for next time:** Empty models is success for residual-none. Do not green Cert. Completeness ≠ Cert ≠ Autopilot. Reopen of a Gold snapshot is not a new draft — Create draft after API restart.


### 2026-08-27 — 08:23 Draft Studio still invoice Pay/QR after stock_reuse shipped
**Didn't work:** Telling the operator to restart `:8001` without killing the uvicorn started 2026-08-26 **without `--reload`**. Live JSON was still `component_grain` + `account.move` Pay/QR + POS gold honesty. Autopilot still stamped `option_a` and added `website_sale`.
**Worked instead:** `wants_stock_reuse` before POS gold; defer “receipts stay stock POS”; `draft_module_from_prompt` seeds capability first; named stock section is exclusive (no retail catalog); kill+restart uvicorn as part of the fix.
**Note for next time:** A Create-draft timestamp after a code change is not proof the API loaded it — check `lsof :8001` start time. `component_grain` + `gold_artifact_id=pos_receipt_options` on invoice extras means grain ran first on a stale worker.

### 2026-08-27 — Draft Studio Option A from a stock-first POS brief
**Didn't work:** Matching `receipt designer` / `QWeb` / `pos receipt` on the raw prompt, including Out of scope and “later Option A only if we ask”. Component grain (`add` in the Done bar) ran before capability classification and hosted Pay/QR on `account.move`.
**Worked instead:** `intent_corpus` drops Out of scope / Unknowns / Capability path / Done bar; explicit `stock_first` + residual none → `stock_reuse` seed; `run_draft_job_body` seeds capability before `field_pack`.
**Note for next time:** Listing a designer as out of scope is not an ask. Classify capability before grain. Named stock apps beat vertical catalog `website_sale`.

### 2026-08-26 — Autopilot “wrong FERNET_KEY” on Elite Test
**Didn't work:** Treating InvalidToken as a rotated `.env` key. `FERNET_KEY` was the `dev-only-` placeholder; other connections decrypted.
**Worked instead:** Elite Test was a pytest leftover (`secret_encrypted="dev-only-test"` plaintext). Re-encrypt with the sandbox password; tests now `encrypt_secret` + delete the row.
**Note for next time:** A 13-byte secret that is not `gAAAA…` is an unencrypted test stub, not a key mismatch. API tests that `commit()` to app-db pollute the operator dropdown.

### 2026-08-25 — Embedded lists skipped refresh at 2 identity cols; stock M2Os treated as orphans
**Didn't work:** `collapse_header_o2ms_into_notebook` left lists alone once two non-`x_name` cols existed (`x_code`+`x_employee_id`), so hours/rate/amount never appeared. `repair_orphan_relations` dropped `account.analytic.account` because it was not in `_BUILTIN_MODELS`. `ensure_sequence_specs` numbered every `x_code` including `*_line`, then unique-prefix minted `MATTER2/`. `ensure_relational_smart_buttons` cloned every custom O2M onto the button box.
**Worked instead:** Always apply preferred line columns when the child is known (reserve qty/amount). Never drop/flag non-`x_*` relations. Skip `*_line` sequences and clear leftover sequence help. Prune smart buttons that duplicate header O2Ms to custom children. Related stock documents off the header form (keep the field).
**Note for next time:** sale.order.line lives in the notebook with qty/price; invoices are smart buttons; analytic account is a header dimension. Do not law-firm-special-case any of that.

### 2026-08-25 — Production-shape wrapped each O2M in its own notebook-inside-group
**Didn't work:** `polish_arch_richness` replaced each `<field o2m><list>x_name</list></field>` with a full `<notebook><page>` **inside** the existing group, and `_build_form_arch` emitted one `<group>` per O2M. Result: `<group string="Parties"><notebook>…`. Completeness `has_views` flagged every inherit. `wire_stock_apps` added `x_project_id` because `project` was in depends.
**Worked instead:** `_build_form_arch` + `collapse_header_o2ms_into_notebook` emit one notebook; skip stock Project M2O when tasks already link the residual; `has_views` only for new `x_*`.
**Note for next time:** If the matter form looks like several tiny notebooks, production_shape wrapped O2Ms inside groups — collapse them; do not add stock document O2Ms back.

### 2026-08-25 — Enrichment 7.0 was false validators + add-then-drop O2M
**Didn't work:** Scoring every in-spec M2O as a line parent (`hr.employee` inherit = second header); penalizing `blocked→pending`; adding stock O2Ms then dropping them and leaving empty `<group>` wrappers; critique adding `x_reference` next to `x_code`; Option A-primary OR from the prompt recapping mixed residuals at 7.0.
**Worked instead:** Duplicate-parent = custom `x_*` only; reset-to-draft skip; never emit stock O2Ms; strip empty groups after scrub; skip identity-duplicate fields; residual `x_*` demotes Option A-primary so Completeness can be 10.0 while Cert stays Reject.
**Note for next time:** Completeness 7.0 with Domain/UX/Hygiene 10 is a validator false positive or an Option A cap — not a domain-pack failure. Empty form groups mean a field was dropped after the arch was synced.

### 2026-08-25 — Suggested stock models vanished on Install; inherit bridges wiped
**Didn't work:** Snapshot restore treated every `source=connection` `confirmed` decision as operator chips; capability stamp dropped every inherit field that was not a Pay/QR stub; `ensure_parent_o2ms` treated `sale.order` as a parent (`"order"` in the id) and emitted dotted O2M names; line trim dropped `hr.employee` because that inherit is in the spec.
**Worked instead:** Chips = operator + confirmed installable only; capability drops only mechanism junk; O2M only on `x_*` with `x_calendar_event_ids`; line trim only extra `x_*` parents; packed drafts skip catalog dump; skip grouping when every leaf is one menu category.
**Note for next time:** Auto-confirmed connection reuse is not an operator click. Option A stubs are not the only legal inherit fields. A stock model id containing `order` is not an O2M parent.

### 2026-08-25 — Pack seed reused calendar for Pay/QR; warehouse from “stock Odoo”
**Didn't work:** `host_model_from_draft` = first inherit; inventory noun matched bare “stock”; `normalize_company_fields_for_live` always set `multi_company=True`; `deepen_thin_ops_children` added `x_status` because party has `x_role`, then `ensure_workflow` re-promoted.
**Worked instead:** Rank commercial hosts from brief; strip “stock Odoo documents” before catalog score; honor explicit `multi_company: false`; skip party joins for status/workflow and strip generic `x_status`.
**Note for next time:** First inherit is not the PDF host. “Stock” in “stock Odoo” is not Inventory. `x_company_id` is not multi-company. A role column is not a workflow.

### 2026-08-20 — PDF/QR/pay prompt became junk field_pack
**Didn't work:** Head-noun + 3-field padding turned “dynamic QR / click-to-pay on PDF” into `x_dynamic`/`x_notes`/`x_active` on `account.move` with scorecard noise nouns (`code`/`click`/`directly`).
**Worked instead:** Domain-agnostic `assess_capability_gaps` → primary Option A + honest stubs only; scrub mechanism nouns from scorecard; wizard Option A Callout.
**Note for next time:** If the ask is on the PDF/report/portal/widget/Python, do not invent form chrome — stamp Option A.

### 2026-08-20 — Apply SLA field pack: nothing on invoice form
**Didn't work:** Draft JSON was correct (`field_pack` on `account.move`), but `scrub_spec_for_protected_apply` stripped every field on tier-1 Accounting. Apply 200’d with PCM skips; Odoo had zero `x_sla_*` columns and no inherit view.
**Worked instead:** Allow additive `x_*` on tier-1; inject into `//group[@id='header_right_group']` with an SLA group; skip per-field inject when the extension arch already places the fields.
**Note for next time:** Scorecard 10.0 + Apply 200 does not mean the form changed — check `fields_get` / combined form arch for the `x_*` names.

### 2026-08-20 — Oil-gas prompt inferred law_firm; prune kept x_matter
**Didn't work:** Industry clusters tokenized full model descriptions and inherit stock ids, so stopwords (`and`/`the`) overlapped law_firm and any prompt containing those words. Scorecard also treated supermarket `x_expense` as a packed accounting clone and dropped fixture6 below 9.5.
**Worked instead:** Strip function words and inherit hosts from cluster bags. Score packed clones as bill/invoice/payment/deposit — not store opex `x_expense`.
**Note for next time:** A 3-letter English word in a pack description is not an industry signal. Do not weaken prune to keep calibration.

### 2026-08-19 — 3-model matter file scored as “done”
**Didn't work:** Packed depth collapsed `min_models` to `max(3, current count)`, so `x_matter` + party + line passed comprehensive. Autopilot clipped to residual + `_line` + `_party` even when the pack had more.
**Worked instead:** Pack floor is conflict checks + document register + inherit `x_matter_id` on stock hosts. Packed min_models is pack `x_*` count (at least 5). Autopilot keeps `_pack_model_ids` + inherit.
**Note for next time:** Senior Community depth is stock apps wired to a real residual workspace, not model-count padding and not a 3-row spec.
**Didn't work:** Scorecard skipped generic-loop findings when `domain_pack` was set; `foreign_models_in_draft` only flags cross-industry tokens, so `x_attorney`/`x_bill` looked coherent. Merge upgraded selections only when the pack had *more* keys, so discovery/trial survived. Expert review did not merge the pack before clip; a 10.0→10.0 “ready” banner kept the JSON.
**Worked instead:** Score packed staff/accounting clones and cap at 5.0. Expert merge then clip. Pack `state_field` + selection always win on pack models. Clip again at the end of close so readiness Python blocks for removed models die.
**Note for next time:** Completeness 10.0 with `x_bill` on a law-firm pack is a product lie. Prompt mention of invoices is reuse, not a custom model.

### 2026-08-18 — Retry AI enrichment rebuilt a 13-model law-firm ERP
**Didn't work:** Pack seed was stock-first; Retry AI ran quality/depth/critique with `expand_llm=True`. Critique prompt said “if comprehensive and <10 models, add missing_models”. Generic-loop prune kept `x_bill`/`x_task` because the brief mentioned invoices/tasks. `_pack_model_ids` missing or stale. Farm collocation matched “Harvest” in a client name.
**Worked instead:** Clip clones after every enrich step and in the closer. Skip LLM expand when reuse-rich. Restamp `_pack_model_ids` from the current pack factory. Drop `harvest` as a farm needle. Do not infer a pack from the prompt inside clip.
**Note for next time:** Completeness 10.0 after Retry AI is not Apps Store quality. Autopilot smoke is the done bar. Mentioning invoices is a reuse instruction, not a license for `x_bill`.

### 2026-08-18 — Unpacked drafts became mini-ERPs without a pack
**Didn't work:** Domain density targeted 12–16 custom models and seeded attorney/bill/task/event roles from prompt nouns. Reuse `forbid_parallel` skipped inferred stock until operator confirm, so Create-draft pack_seed was the only path that stayed stock-first.
**Worked instead:** One stock-first contract (`ai_stock_first`) on unpacked seed, closer, density, and Autopilot. Expand forbid aliases by leaf; honor `Custom residual is the X`; skip model-count padding when reuse is rich.
**Note for next time:** A missing pack is not permission to clone Accounting/HR. Residual = what stock apps do not cover.

### 2026-08-18 — Open smoke invoice landed on Invoicing app + restaurant leftovers
**Didn't work:** `#model=account.move&view_type=form&id=56` with id last and no customer-invoice `action`. Odoo 19 routed to the Invoicing app list on a reused DB that still had restaurant POS/invoices.
**Worked instead:** Resolve `account.action_move_out_invoice_type` and open `/odoo/action-<id>/<recordId>`. Probe leftover POS/hotel rows. Seed brief-named partners/products when no client files. Do not wipe the DB.
**Note for next time:** Reused sandbox ≠ clean vertical. Deep-link the smoke record with its window action; warn about leftover docs.

### 2026-08-18 — Draft Studio: “retail template” + farm briefing on a law-firm pack
**Didn't work:** `pack_fallback` banner hard-coded “Built from the retail template”. Collocation `harvest` matched sample client “Northern Harvest Ltd” and stamped farm equipment / banned `project.*`. Critique `notes` as a string became a character list via `list(str)`. Uncovered-noun completeness dumped Adeyemi/Nigeria/sandbox and pushed the LLM to invent parallel `x_bill`.
**Worked instead:** Generic pack banner. Legal `none_of` on farm. Law-firm pack briefing is `legal practice`, not a neighboring collocation. Skip noun-coverage dumps/repairs when `domain_pack` is set. Coerce critique notes to real strings.
**Note for next time:** A sample client name is not the industry. Completeness 10.0 is not Apps Store quality. Pack-fallback copy must not name a specific vertical.

### 2026-08-18 — Wizard 500: next/font/google + Turbopack
**Didn't work:** `Fraunces` / `Inter` / `JetBrains_Mono` from `next/font/google`. Turbopack emitted `@vercel/turbopack-next/internal/font/google/font` and 500'd `/wizard` when `fonts.gstatic.com` was unreachable.
**Worked instead:** System font stacks in `globals.css` (`--font-sans/display/mono`). No Google fetch at compile time.
**Note for next time:** Do not use `next/font/google` on a local-first app. A font CDN outage must not take down Draft Studio.

### 2026-08-18 — Draft Studio: 1800s + restaurant JSON on a law-firm brief
**Didn't work:** Pack-first seed that still auto-ran 900s+ of staged LLM; collocation/connector regex treated "not restaurant" / "No … food marketplace" / "kitchen hardware" as positive hits.
**Worked instead:** Skip LLM on Create draft when a pack has models. Negation window (`no`/`not`/`never`) for briefing, connectors, and pack regex. Legal lexicon is native on `law_firm` packs (not a foreign leak).
**Note for next time:** A negated industry word is not a collocation. Create draft must not start the 7-step LLM when the pack already answers the prompt.

### 2026-08-18 — Draft Studio: 1800s timeout, empty JSON
**Didn't work:** Staged LLM (`draft_module_from_prompt`) as the only Draft Studio path. `qwen3:8b` exceeded the `ai_draft` 1800s cap with no `partial_draft`.
**Worked instead:** Seed a scored domain pack first, cache it, budget LLM enrich at 900s, succeed with the seed on timeout. Wizard polls until terminal.
**Note for next time:** A 30-minute job cap cannot wrap a 7-step local LLM full-app generate. Durable seed first, then optional enrich.

### 2026-08-18 — Autopilot smoke: residual create missing required M2O
**Didn't work:** Custom smoke created with only `x_name`. Live pack left a required many2one (law-firm `x_partner_id`). A follow-up that special-cased field names `x_partner_id` / `partner_id` would miss `x_patient_id` / `x_guest_id`.
**Worked instead:** Smoke fills every required stored field from live `fields_get`. Required many2ones are filled by `relation` from smoke stock ids (`res.partner`, `product.product`, …), not by vertical field names.
**Note for next time:** Residual create must not special-case industry field names. Key M2Os by relation.

### 2026-08-18 — Autopilot poll: stalled after 500 polls, still running custom
**Didn't work:** Treating a quiet `step_label` as a hang. Custom ran `draft_module_from_prompt` (full-app LLM, 25+ min) with no substeps; UI aborted at 500 polls while the worker was still drafting.
**Worked instead:** Autopilot residual seeds from the domain pack / skeleton + deterministic closer — no full-app LLM. Job page polls until the backend is terminal (`untilTerminal`).
**Note for next time:** Never fail a poll while `status=running`. A frozen stage label is a missing heartbeat or an LLM draft that Autopilot should not run.

### 2026-08-18 — Autopilot poll: 600 polls, last status running
**Didn't work:** UI hard-stop at 600×3s while the job was still in smoke. Smoke retries re-ran Expert-fix (Ollama) up to 5 times; ThreadPoolExecutor shutdown waited for that worker, so the 30 min cap only landed after ~56 min.
**Worked instead:** Smoke retry re-applies the existing spec without Expert. Job timeout shutdown is non-blocking. Poll follows stage progress up to 60 min.
**Note for next time:** A poll timeout with status still `running` is a UI budget vs a hung/slow worker — check `step_label` and whether retries re-invoke the LLM.

### 2026-08-18 — Autopilot poll: "Cannot reach API … read ECONNRESET"
**Didn't work:** Treating ECONNRESET as a Next timeout. Autopilot had queued; hundreds of `GET /jobs/{id}` 200s then uvicorn died (reload worker + ~1.5 GB RSS + a second Run on the same connection). Keep-alive GET then reset.
**Worked instead:** Restart uvicorn **without `--reload`**. Poll retries ECONNRESET. One Autopilot per connection. Module zip lives in `.cache/job_autopilot/` not in poll JSON.
**Note for next time:** ECONNRESET during Autopilot poll means the API process died, not that Plan failed. Do not click Run twice; do not `--reload` while a job is running.

### 2026-08-18 — Autopilot Run: client TimeoutError "Request timed out"
**Didn't work:** Holding one HTTP POST for the whole Autopilot job. Browser/Next overlay aborted with `TimeoutError: Request timed out` after ~11 min while uvicorn was still installing apps / applying residual.
**Worked instead:** Queue `job_autopilot` on the in-process runner (30 min cap) and poll `GET /api/jobs/{id}` every 3s. Production refuse stays a sync result.
**Note for next time:** Long sandbox jobs must not be a single fetch. Plan-ok + health-ok + Run timeout = hung request, not a down API.

### 2026-08-17 — Autopilot Run: "Cannot reach API … fetch failed"
**Didn't work:** Treating it as a dead uvicorn. Health and Plan (packet) were fine; Run stayed silent until Node undici `headersTimeout` (~5 min) threw `TypeError: fetch failed`.
**Worked instead:** Next `/api` proxy uses `node:http` with the same 660s budget as Autopilot/Expert. Do not use global `fetch` for jobs that send no headers until they finish.
**Note for next time:** `fetch failed` from the Next proxy is often headersTimeout, not ECONNREFUSED. Check whether Plan works and `/health` is ok.

### 2026-08-17 — Module install during ir.cron lock
**Didn't work:** Immediate `button_immediate_install` of `contacts` after `l10n_ng` — Odoo 19 Fault 2 "processing a scheduled action / Module operations are not possible". Scorecard treated the skip as coverage 7.0 even when sale then pulled contacts.
**Worked instead:** Retry install up to 5 times on that fault; after the stock loop, reconcile skipped names against live `ir.module.module` state.
**Note for next time:** Sequential module installs on a fresh DB race Odoo's post-install cron. Retry and re-read state; do not cap the job scorecard on a skip that later installed.

### 2026-08-17 — Invoice-from-SO over XML-RPC
**Didn't work:** `sale.order._create_invoices` — Odoo 19 RPC refuses private methods. Wizard `create_invoices` often returns `None`, which XML-RPC cannot marshal even when the invoice exists.
**Worked instead:** Public `sale.advance.payment.inv` with `sale_order_ids` + `invoice_policy=order`; treat marshal-None as success only after `sale.order.invoice_ids` is set.
**Note for next time:** Never call `_`-prefixed Odoo methods over RPC; confirm wizard side-effects by reading the document.

### 2026-08-16 — Confirm RPC_ERROR on leftover filter_domain
**Didn't work:** Binding Confirm to object_write. Write then hit `base.automation` leftover `filter_domain` `['x_rate_unit in ('hour','day')']` — invalid Python, SyntaxError in safe_eval.
**Worked instead:** Apply unlinks x_* automations whose domain does not compile; refuse to create that shape.
**Note for next time:** A working header button can still crash if a leftover automation’s filter_domain is not a real domain. Scrub live autos, not only the draft.

### 2026-08-16 — Confirm/Cancel on Walkthrough Engagement did nothing
**Didn't work:** Generated forms used `<button type="object" data-transition-to="open"/>`. Live `x_engagement` has no Python method, so the click is a no-op / error.
**Worked instead:** After writing views, bind each dest to `ir.actions.server` object_write and rewrite the button to `type="action" name="{id}"`.
**Note for next time:** Header workflow chrome on metadata models must be server actions, not `type=object`.

### 2026-08-16 — Demo walkthrough Faulted leftover required fields
**Didn't work:** Seeder filled only ModuleSpec `required` flags. Live Odoo still had leftover required columns (`x_rate_hour`, `x_session_type`, `x_revision_number`, …) from earlier applies; booking_line then failed because the parent booking never existed.
**Worked instead:** Merge live `ir.model.fields` required=True into vals; skip children whose required `x_*` parent was not created.
**Note for next time:** After re-apply on an existing sandbox, live required fields can exceed the current spec — seed from Odoo, not the JSON alone.

### 2026-08-16 — Generate UI forced model-by-model picking
**Didn't work:** `_ensure_menus` called `ensure_app_menus` with every `x_*` model as a root child. Spec already had Operations / Inventory / People; those were only used for ACL on the root. Copy said “Open Odoo app switcher or Designer” with no Open-app link.
**Worked instead:** Apply the spec menu tree, hide `*_line` menus, unlink leftover flat root children, return `root_menu_id`, and show **Open app in Odoo**.
**Note for next time:** If the operator still picks models one by one after Apply, the live menu tree was flattened — do not tell them to use Designer as the domain flow.

### 2026-08-16 — Expert-fix button missing at 10.0
**Didn't work:** Gating `expert-review-fix` on `draftScore < 9`. Operator at 10.0 only saw **Ask Expert about draft** (chat) and Saved snapshots (restore, not closer), so they regenerated instead of running Expert-fix.
**Worked instead:** Always render the closer under the scorecard; keep zip/promote at ≥ 9. Helper copy distinguishes chat vs closer.
**Note for next time:** If the operator says they cannot find Expert-fix, check the score ≥ 9 gate — not whether Expert is implemented.


**Didn't work:** Treating Expert-fix 10.0 as Apply-ready. Closer demoted `x_rate_unit` and stripped form chrome, but left search filters `domain=[('x_status', …)]` and remapped Company group_by onto a parent M2O.
**Worked instead:** Drop search filters that name a missing field; restore `group_x_company_id` after company-field sync; live-apply findings for leftover search domains.
**Note for next time:** Scrub search `domain` and `group_by`, not only `<field name=`. A 10.0 scorecard does not inspect search domains unless the live-apply contract does.

### 2026-08-16 — Expert-fix looked like a cache restore
**Didn't work:** Clicking Expert then seeing Note “Restored cached draft” + the same 7.0 JSON. Expert-fix never wrote `ai_draft_cache`; Saved drafts still pointed at the unfixed snapshot. Clicking that row is restore, not Expert. Closer also left two FKs to the same parent (`x_inventory_count_id` + `x_count_id`) so supermarket Expert stayed capped at 7.0.
**Worked instead:** Persist closer JSON after `apply_fixes`; skip narratives on that path; reuse an existing parent M2O instead of adding `x_{leaf}_id`; collapse same-relation parent M2Os. Relabel the list Saved snapshots.
**Note for next time:** “Restored cached draft” is `restoreDraftFromCache`. If Expert-fix returns the same score, check cache write and same-relation duplicate FKs, not the LLM.

### 2026-08-16 — Expert-fix left 7.0 (third usage-line parent)
**Didn't work:** `_is_asset_usage_line` allowed exactly two parents, but close never dropped `x_rate_card_id` and `ensure_line_model_parent_links` still attached `{asset}_line` to rate card. Expert re-ran close and the 7.0 consistency cap stayed.
**Worked instead:** Skip asset usage lines in post-critique parent linking; `trim_line_extra_parents` after that pass; restamp `_meta.smart_button_count` in the live-apply attach.
**Note for next time:** If Expert-fix returns the same scorecard finding, the closer never repairs that element — add the repair to `close_odoo_architecture`, do not widen the validator.

### 2026-08-16 — First ModuleSpec UI apply timed out then group write failed
**Didn't work:** Next `/api` proxy default 12s covered elite-autopilot/validate-live but not `module-spec/apply`. First apply of ~15 models/64 views aborted; retry wrote views then `ir.ui.menu.write({groups_id})` on Odoo 19 and `resolve_xml_id("group_…_user")`.
**Worked instead:** Long timeout for every `module-spec` path; probe `group_ids` vs `groups_id`; create ACL groups by name; default To Do activity type for `next_activity`.
**Note for next time:** A 12s 504 on Generate UI + a second run with 0 models created means the proxy died mid-apply — raise the apply budget, do not assume the spec is empty. After the apply succeeds, remaining skips (`on_time` date, `next_activity` mixin) belong in `ai_live_apply_contract` stamp+findings, not another apply-only patch.

### 2026-08-14 — Hollow cost collapse mangled the lined keeper
**Didn't work:** Naive `str.replace("x_job_cost", "x_job_cost_expense")` turned the keeper into `x_job_cost_expense_expense`.
**Worked instead:** Token-bounded identifier rewrite (`(?<![A-Za-z0-9_])…(?![A-Za-z0-9_])`) in `_rewrite_model_ident` / `_rewrite_field_ident`.
**Note for next time:** Collapsing a shorter model id into a longer one that contains it needs whole-token replace, not substring replace.

### 2026-08-14 — Stale draft warnings named x_site after rename
**Didn't work:** Treating every `x_*` token in a warning as a missing model (dropped `x_code` field notes). Rewriting ids inside `pruned` / `in favor of` closer notes (`x_site in favor of x_studio` became `x_studio in favor of x_studio`). Mapping pruned `x_booking_document` onto live `x_booking`.
**Worked instead:** Rewrite only generic leftover ids that were renamed, not pruned; leave closer prune/rename notes untouched; never treat field names as models.
**Note for next time:** Draft-from-prompt (`_finalize_draft_generation`) must run the same stale-warning filter as enrich jobs, or the wizard keeps pre-close noise.

### 2026-08-14 — 10.0 still had orphan deliverable/cost, dual rate lines, party↔party agreement
**Didn't work:** Job-header collapse + booking→engagement left `x_deliverable` and `x_job_cost_expense` with only a site FK, `x_rate_line` beside `x_rate_card_line`, agreement Party A/B both pointing at the party register, `x_company_id` labeled Studio, `product.product` without `product` in depends, and unavailability as a document workflow.
**Worked instead:** Domain-agnostic closer repairs (job-header children FKs, collapse duplicate `*_line` per parent, agreement → `res.partner` client, Company label, asset-line on booking, relation depends, draft default, calendar-block registers). No vertical pack.
**Note for next time:** A 10.0 scorecard with empty findings means the scorecard never looked for the defect — add the finding and the closer repair together.

### 2026-08-14 — 10.0 validators-green still had two job headers and fake automations
**Didn't work:** Booking→engagement / revision→deliverable closer left `x_project` beside `x_engagement`, `Draft`+`draft` statuses, `('active','inactive')` selections, Python-shaped `safe_actions`, and `is_workflow` on cost registers with no `x_status`.
**Worked instead:** Role-based job-header collapse, selection canonicalize, drop non-metadata automations, demote workflow-without-status — all in `close_odoo_architecture`, no vertical pack.
**Note for next time:** Align FK names to relations *after* typed-asset collapse, or `x_console_id` becomes `x_equipment_id` and the explode-collapse no longer sees two typed FKs.

### 2026-08-14 — 9.5 validators-green still leaked matter / typed FKs / staffing
**Didn't work:** Rename/ACL/line-menu closer left `x_deliverable.x_matter_id`, six `x_console_id`… FKs on engagement, `x_staffing` (generic loop only matched exact `staff`), equipment kanban `default_group_by="x_status"` with no such field, booking O2M `x_booking_id` missing on `x_equipment_line`, and `x_job_cost` header totals without line subtotals.
**Worked instead:** Wire those repairs into `close_odoo_architecture` (foreign FK rewrite, typed-asset collapse, `staffing` prune, O2M inverse fill, kanban group-by, header computes). Briefing rewrites Option A/B on any type field.
**Note for next time:** Scorecard findings that survive a regenerate are closer gaps — add the repair to close, do not add a vertical pack.

### 2026-08-14 — Close pass left missing ACL / ghost menus / ENGA/ prefixes
**Didn't work:** `_hide_line_model_menus` ran *before* `ensure_default_ui`, which re-added line menus. Access stubs ran in rules before density/app-bar added `x_booking_line`/`x_maintenance`. `ensure_workflow_transitions_on_draft` re-promoted registers (and `*_line`) after demote. `senior_sequence_prefix` truncated to 4 letters (`ENGA/`). Menu purge kept ghost items when the action was already deleted (`__keep__` default).
**Worked instead:** Close after UI: access stubs, prompt-noun rename, line parent/orphan drop, ghost-menu drop, hide lines, skip register/line in workflow transitions, whole-word prefixes. Scorecard flags only truncated *segments* (ENGA/), not EVENT/ or PROMO/.
**Note for next time:** If scorecard still reports a defect Expert is supposed to fix, the closer never ran that repair — wire it into `close_odoo_architecture`, do not add commentary.

### 2026-08-14 — Staged timeout raised “Ollama request timed out”
**Didn't work:** Default `AI_PIPELINE_MODE=staged`. Step1/step2 LLMError with no domain pack re-raised as `AiAssistUnavailable`; the wizard job failed and offered Diagnose with Expert.
**Worked instead:** Seed an unpacked draft from the prompt, density-bootstrap site/party/engagement, finish app-bar. Per-entity field timeouts continue with minimal fields.
**Note for next time:** Timeout is a degraded LLM step, not a missing Odoo connection — never fail the draft job when a deterministic finisher can still produce an app.

### 2026-08-14 — “Production” leaked MRP; studios got film gear
**Didn't work:** Catalog `score_model_for_prompt` +3 on `mrp.production` when the prompt contained `production`; MRP app boost also treated `production` as manufacturing. LLM `x_type` used camera/lens because “studio” collocates with film. Expert/scorecard could not rewrite selections.
**Worked instead:** Weak-token skip + MRP intent = factory/BOM/work order only; per-prompt domain briefing rewrites equipment/rate selections and drops banned catalog rows. Expert setup-stack uses the same MRP intent and drops briefing-banned apps.
**Note for next time:** Shared industry words (`production`, `studio`, `service`) are not vertical intent — require a collocation or a strong manufacturing phrase. Close the same leak on every path that maps keywords → stock apps.

### 2026-08-14 — Expert review-and-fix left architecture defects
**Didn't work:** Expert `apply_deterministic_scorecard_fixes` re-ran post-critique + production_shape only. Post-critique `apply_pattern_rules` re-promotes any `x_status` model to a document workflow; domain-fit FKs were tagged suggestions, not fixes. Critique-added `x_recording_session` kept `x_studio_id` → `x_equipment`.
**Worked instead:** Last-word `close_odoo_architecture` after elite; Expert runs `run_odoo_app_bar_pass` + that closer; skip register promotion in rules/post-critique.
**Note for next time:** If Expert cannot repair a scorecard finding, the finisher never ran that repair — wire the same pass, do not add a second commentary path.

### 2026-08-14 — 4–6 models after generic-loop prune
**Didn't work:** Pruning deposit/task/bill/party_link left a 4–6 model Studio stub that is not Apps Store scale.
**Worked instead:** Default comprehensive ambition for real business prompts + `ensure_domain_density` (domain-named roles, keep job-cost expense, `hr.employee` crew, `account.move` invoices).
**Note for next time:** Thin model count after prune is a density gap, not a success. Do not refill with generic ops-loop filler.

### 2026-08-14 — Scorecard 10.0 UX on a generic ops loop
**Didn't work:** Treating `_scorecard` Structure/UX/Hygiene 10.0 as Apps Store quality when the draft still had `x_deposit`/`x_party_link`/`x_bill` and `x_session.x_studio_id` → `res.partner`.
**Worked instead:** Pack-free generic-loop prune + FK repair + session-as-header + honest scorecard penalties.
**Note for next time:** Completeness validators do not measure whether the module is the right app.

### 2026-08-13 — Jaccard floor on regex pack hits
**Didn't work:** Rejecting regex-matched packs when Jaccard < 0.04 or a competing pack scored higher (clinic 0.08 vs car_rental 0.04 on "auto hire booking system"; hospital prompt Jaccard 0.03).
**Worked instead:** Trust curated regex as the precision signal; keep Jaccard/ambiguity gates for unpatterned retrieval only. Load `domain_pack` by id when already chosen.
**Note for next time:** Short prompts never overlap a large pack vocab — regex exists because Jaccard cannot.

### 2026-07-28 — ModuleSpec apply skipped draft smart buttons / automations
**Didn't work:** Strict `on_model`/`related_model` + exact `AutomationTrigger` enum; assumed `relation_field` already on target; no M2O create before O2M/bundle.
**Worked instead:** Normalize key/trigger aliases; `_ensure_m2o_on_target_for_smart_button` before bundle; apply `access_rules` when resolvable.
**Note for next time:** AI drafts use Studio-ish labels (`create`/`write`, `source_model`); apply must coerce — related-window M2O always on target.

### 2026-07-28 — ModuleSpec builder showed Models (0) after Open from Wizard
**Didn't work:** Persist-on-mount wrote default `{ models: [] }` into `sessionStorage` before the AI draft was read, wiping the Wizard handoff.
**Worked instead:** Gate session writes on `hydrated` after load completes.
**Note for next time:** Never mirror React state to sessionStorage until initial hydrate finishes.

### 2026-07-28 — Open in Odoo: Name 'active_id' is not defined
**Didn't work:** Designer picked first act_window matching view_mode by name order (e.g. "API Loans") — related smart-button actions whose context/domain reference `active_id`.
**Worked instead:** Prefer standalone actions (`standalone_only` + `pickStandaloneWindowAction`); never deep-link related windows without a parent record.
**Note for next time:** Related window actions are correct for smart buttons; Open-in-Odoo must exclude any domain/context containing `active_id`/`active_ids`.

### 2026-07-28 — Activity Open in Odoo: Missing template "undefined"
**Didn't work:** Designer emitted `<activity><field/>…</activity>` without `<templates><div t-name="activity-box">`.
**Worked instead:** Match stock mail activity arches — always emit `activity-box` OWL template; put display fields inside it.
**Note for next time:** Activity view type is template-driven (OWL); ORM arch validation ≠ web client requirements.

### 2026-07-28 — Activity Save to Odoo: root should be `<activity>`, not `<data>`
**Didn't work:** Inherit strategy second-save wrote `render_inherit_replace_arch` (`<data><xpath>…`) onto the designer *primary* view (same name `model.designer.activity` as the first create).
**Worked instead:** When the designer-named view *is* the primary, update full typed arch in place; only use `<data><xpath>` for true extension children.
**Note for next time:** Never write inherit wrappers onto a primary `ir.ui.view` — Odoo validates root tag by `type` (activity/form/…).

### 2026-07-27 — Generate UI broke Contacts (`phone` xpath)
**Didn't work:** `_inject_button_box` rewrote `res.partner` primary form via `render_form_arch` → stock inherits looking for `//field[@name='phone']` failed.
**Worked instead:** Always upsert `{model}.studio.smart_buttons` inherit into `button_box` (or create box before sheet children); refuse stock primary rewrites for explicit views / polish.
**Note for next time:** Never mutate stock module primary arches — inherit xpath only (same rule as field inject / header actions).

### Soft warning — Odoo RPC claims without instance proof
**Didn't work:** (anticipated) Shipping `ir.model` / view XML / `base.automation` calls from model memory alone.
**Worked instead:** Smoke-test every new RPC helper against local Docker Odoo 19 before the next card.
**Note for next time:** Odoo API "certainty" is a gate failure waiting to happen — verify on `odoo:19`.

### 2026-07-27 — next_activity default user_id on custom models
**Didn't work:** `activity_user_field_name=user_id` on `x_lib_book` (no such field) → KeyError on `ir.actions.server.run`.
**Worked instead:** Resolve assignee field to `user_id` → `create_uid` → `write_uid`; Designer/API omit hard-coded `user_id`.
**Note for next time:** Custom `x_` models rarely have `user_id`; never assume CRM-like fields for mail activities.

### 2026-07-27 — Library status is loaned not borrowed
**Didn't work:** UAT wrote `x_status='borrowed'` (invalid selection).
**Worked instead:** Use `available|loaned|lost`; Designer update-field picker reads real selection options.
**Note for next time:** Never hard-code selection literals — load from `ir.model.fields.selection`.

### 2026-07-27 — Duplicate Mark Available from stacked inherits
**Didn't work:** Smoke created `x_lib_book.uat.phase2.buttons` then `x_lib_book.uat2.phase2.buttons` — both inject `<header>` before sheet → two buttons + two statusbars.
**Worked instead:** Single upsert inherit `x_lib_book.studio.header_actions`; unlink stale `*.uat*` views; smoke asserts `Mark Available` count == 1.
**Note for next time:** Form button/header xpath inherits must use one stable name and overwrite, never a new name per run.

### 2026-07-27 — Odoo 19 DB init CLI changed
**Didn't work:** Legacy `odoo -d DB -i base --stop-after-init --admin-passwd=...` (`--admin-passwd` gone; CLI is subcommand-based). Also failed when connection flags were placed after `init`.
**Worked instead:** `odoo db --db_host=db -r odoo -w odoo init --username admin --password admin [--force] DBNAME`
**Note for next time:** On `odoo:19`, run `odoo db --help` / `odoo db init --help` before assuming pre-19 recipes.

### 2026-07-27 — Sandbox compose tore down primary Odoo
**Didn't work:** `docker compose -f docker/docker-compose.sandbox.yml down -v` without `-p` (project defaults to folder name `docker`, same as primary stack).
**Worked instead:** Always `docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml …` (wired in `app/sandbox.py`). Host port is **18069** (not 8070 — that belongs to permanent Odoo 18).
**Note for next time:** Sibling compose files in the same directory need distinct `-p` project names **and** non-overlapping host ports.

### 2026-07-27 — base_import_module cannot load Python models
**Didn't work:** Promote Python addon zip via `base.import.module` / `import_module` (access CSV fails: `model_x_*` missing because Python never loads).
**Worked instead:** Filesystem install into `/mnt/extra-addons` (+ restart) for local Docker; `install_mode=data` (ir.model / ir.model.fields XML) for remote import.
**Note for next time:** Treat `base_import_module` as data-only; never assume it equals `button_immediate_install` of a Python addon.

### 2026-07-27 — Odoo 19 res.groups / ACL field shapes
**Didn't work:** Assuming `res.groups.category_id` still exists (KeyError on Odoo 19).
**Worked instead:** Read `full_name`, `name`, `share`. `ir.model.access` / `ir.rule` `perm_*` are booleans; `ir.rule.groups` is many2many.
**Note for next time:** Probe field lists via `fields_get` on Odoo 19 before hard-coding Enterprise-era assumptions.

### 2026-07-27 — Confirm gates after Odoo connect hid 403
**Didn't work:** Calling `_client()` / Odoo RPC before `require_advanced_confirmation` on delete routes — bad connection → 502 instead of confirmation 403.
**Worked instead:** Connection existence check → confirm phrase → then Odoo client / mutation.
**Note for next time:** Authz/confirm gates must run before any dependency that can 502.

### 2026-07-27 — Required many2one + on_delete set null (Odoo 19)
**Didn't work:** Creating required `many2one` via `ir.model.fields` without `on_delete` (defaults to set null).
**Worked instead:** Set `on_delete=restrict` (or cascade) when `required=True`.
**Note for next time:** Odoo 19 validates m2o ondelete against required; Studio-like builders must set it.
**Note for next time:** `fields_get` before coding ACL helpers — group UX changed in 19.

### 2026-07-27 — Odoo 16/17 init while worker running → KeyError ir.http
**Didn't work:** `docker exec … odoo -i base --stop-after-init` against a DB the long-running container was already serving (partial registry; XML-RPC 500).
**Worked instead:** Stop worker → DROP DATABASE → `compose run --rm --no-deps odooN -i base,web --stop-after-init` → start worker.
**Note for next time:** Never install modules into a DB that a live odoo worker already has open.

### 2026-07-27 — create_model type=list fails on Odoo ≤17
**Didn't work:** Hard-coded `ir.ui.view.type='list'` / `<list>` arch (ValueError wrong value).
**Worked instead:** `views_vN.list_type_fallbacks("list")[0]` for type + matching arch root (`tree` on 16/17).
**Note for next time:** Prefer adapter list-type order for creates, not only for find_view fallbacks.

### 2026-07-27 — ir.model.fields.currency_field missing on Odoo 16
**Didn't work:** Always `read`/`search_read` including `currency_field` (Invalid field on 16).
**Worked instead:** `_ir_model_fields_columns()` filters via `fields_get` once per client.
**Note for next time:** Optional columns on `ir.model.fields` must be version-probed, not assumed from 19.
