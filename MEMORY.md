### 2026-09-14 — View Designer Track B: semantic XPath, ElementTree `//` is eval-only
**Decided:** Score/rewrite locators toward `@name`/`@id` (unique `@string` only if needed). Classify preview issues as error (missing/ambiguous/invalid XML) vs warning (positional / `@string` fragility). Block inherit/overlay writes on errors; warnings do not block. ElementTree evaluates Odoo `//field` as `.//field` and inherit XML still emits `//`. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Studio’s #1 upgrade pain is positional `group[2]`. Python `xml.etree` rejects absolute `//` on an element, which made every locator look unevaluable until the eval mapping.
**Rejected:** Track C/D; rewriting the whole Designer page; silently rewriting operator expr on save; treating `@string` as as-safe-as `@name`.

### 2026-09-14 — View Designer Track A: field properties are view-layer chrome
**Decided:** FieldNode round-trips `help`, `placeholder`, `class`, `groups`. Related path is ORM metadata + `listRelatedPaths` picker (not an arch attr — dotted names are not valid view field names). Remove-from-view stays view-only. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Studio-class inspector for day-to-day field editing; `groups=` needs xml ids, not `res.groups` numeric ids.
**Rejected:** Tracks B/C/D this run; writing `related=` from Designer; treating group display names as xml ids.

### 2026-09-14 — Sale inherit xpath is tax_totals, not amount_tax
**Decided:** Option A sale.order form inherit xpaths `amount_tax` / `amount_untaxed` rewrite to `tax_totals` at author + zip. Expert ParseError/xpath-miss beats live schema on traceback filenames (`xmlrpc.py`). Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Sandbox Install ParseError: xpath `//field[@name='amount_tax']` not in parent view. Expert said `xmlrpc` missing.
**Rejected:** Installing an xmlrpc app; Live Install of the zip.

### 2026-09-14 — Production in-app fault log is later (diagnosis first)
**Decided:** Table a production **in-app** fault log + founder-accessible dashboard/export until Expert/platform diagnosis is trustworthy. Scope is this app’s API/UI faults (stale `:8001`, FastAPI 404, empty Diagnose), not a dump of customer Odoo RPC. Each event must carry a real diagnosis (this-app vs Odoo; LLM-fixable vs codebase). No Sentry/paid SaaS while bootstrapping. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Install Sales 404 was mis-diagnosed as an Odoo view/ACL fault; a log without that split would page the founder on noise.
**Rejected:** Building the dashboard now; treating Expert “generic Fault” as the production signal.

### 2026-09-14 — Install Sales 404 is a stale API process, not Odoo
**Decided:** Host-install reverify 404 → honest restart copy + **Re-check authoring gate**. Expert does not treat empty Diagnose / FastAPI Not Found as an Odoo Fault. Gemini gets product facts (`PLATFORM_GROUNDING`) plus project RAG; App Studio generate-intent chips stay out of Expert Q&A. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Operator saw Something went wrong / Not found after Install Sales; Expert diagnosed a blank Error log as RPC (Designer/ACL).
**Rejected:** Inventing x_sale; Live Install of the zip; Designer/ACL steps for our own 404.

### 2026-09-14 — Missing inherit hosts offer stock app install
**Decided:** `model_missing` on Option A inherit (`sale.order` / `sale.order.line`) opens a host-install dialog for the stock CE app (`sale` / Sales). Phrase-confirm, then RPC install-community + re-verify the authoring gate (no LLM). That is not Live Install of the zip. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** NGN sandbox had no Sales app; the gate listed dead findings instead of offering the install that unlocks inherit.
**Rejected:** Inventing `x_sale`; clicking Install this app; re-authoring the module just to clear `model_missing`.

### 2026-09-14 — Option A author accepts a bare JSON array of files
**Decided:** LLM `{blocks:[…]}`, `{files:[…]}`, a single block object, or a bare array all coerce to `{blocks}`. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Retry authoring returned `JSON but not an object (expected a ModuleSpec draft)` — Gemini listed files as an array.
**Rejected:** Failing the gate because the wrapper object was missing.

### 2026-09-14 — App Studio loaders are InfinityLoop + Spokes in brand/accent
**Decided:** Generating canvas uses InfinityLoop in `--brand` orange. Compact busy actions use Spokes via `currentColor` (white on brand buttons, inherited on primary). Hardcoded red/black CSS loaders are out. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** The old ring spinner was generic; operator asked for loading-ui infinity and spokes aligned with app colour.
**Rejected:** Pasting #f03355 / black CSS loaders; a third diamond/dots animation in the same flow.

### 2026-09-14 — Incomplete Option A JSON is repaired automatically
**Decided:** Truncated author JSON is closed and parsed in-job; empty/unparseable output compact-retries the LLM once. App Studio auto-reauthors a JSON-fail session once. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Operator should not debug `Unterminated string` or click Retry for a cut-off JSON blob.
**Rejected:** Leaving truncated JSON as a user-facing author_failed.

### 2026-09-14 — Option A truncated JSON is retryable
**Decided:** Author JSON uses `parse_llm_json` (close unterminated strings, stack-close braces). One compact retry on parse fail. Operator copy is “incomplete JSON”, not Gemini busy. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Retry authoring after 503 returned `Unterminated string … char 1081` — the model cut off mid-file, and raw `json.loads` failed.
**Rejected:** Treating truncated JSON as a finished module; Start over.

### 2026-09-14 — Option A authoring retries Gemini 503
**Decided:** LLM-authored Option A uses `generate_json_with_timeout_retry` (503 backoff + configured fallbacks). A busy Gemini is `author_failed` (retryable), not a second `empty_module` finding. App Studio **Retry authoring** re-runs generate; diagnosis stays locked. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Operator confirmed diagnosis, Gemini returned high-demand 503, zip stayed locked with no retry.
**Rejected:** Treating 503 as a failed module; asking the operator to Start over.

### 2026-09-10 — Diagnosis is editable before generate
**Decided:** The diagnosis card is the first refine surface. Operator can change name, host form, inherit vs new tile, Option A vs live fields, and constraints, plus a free-text correction note, then **Yes — build this** locks that IR. Gold templates and refuse-clone stay locked. Later Draft Studio refine is still after generate. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Confirming a wrong host is worse than editing before the compiler runs.
**Rejected:** Free-form generation before confirm; letting gold/refuse be flipped from the card.

### 2026-09-10 — Diagnosis lock before App Studio generate
**Decided:** After intent chips, App Studio shows a locked diagnosis IR (host, inherit vs new app, needs module, constraints). Generate waits for **Yes — build this**. Deterministic classify wins; a fast LLM may fill summary/constraints/missing host on long/client SOW briefs. The compiler stamps `_understanding` and surface-fails a draft that invents an x_* app when inherit `sale.order` was locked. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Parse/author split is not enough if generate starts before the operator sees what we think they asked for.
**Rejected:** Letting the LLM freely pick a pack or residual; skipping the card on high-confidence briefs.

### 2026-09-10 — App Studio parse: Option A does not ask pack-choice
**Decided:** Gold / `option_a_authored` briefs skip pack/stock clarification. “Add to an existing form” stamps `Host: sale.order` (via `preferred_inherit_host`) and must not say “Add fields.” Markup + WHT stays primary Option A even with a live-field token. Intent LLM may return `host_model` + `needs_module`. Seed inherit preview (Markup % 10–25); App Studio CTAs are zip → sandbox → Promote. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** The Sales markup client brief became a blank Install tile after the existing-form chip.
**Rejected:** Treating markup/WHT as a new x_* app; inventing `account.tax`.

### 2026-09-10 — LLM-authored Option A is the general path; gold is a shortcut
**Decided:** Live metadata still wins when it is enough. Matching CBN/POS/invoice Pay+QR still select gold. Every other Python/QWeb/HTTP/OWL ask is `option_a_authored`: the LLM fills `custom_code_blocks`; zip and sandbox return 422 until `_option_a_authoring.status=pass` (lint, no `account.tax` create, no SSRF/private HTTP, no secrets, dry structural zip, optional RPC xmlid check). Completeness ≠ Cert ≠ Autopilot. Promote stays human. No live `state=code`.
**Why:** A closed gold catalog caps the product. Unvalidated LLM zips are worse. The gate is the product.
**Rejected:** Requiring a new gold ID for every client SOW; downloading LLM Python before the gate.

### 2026-09-09 — Inherit partner xpath must be unique
**Decided:** `account.move` next-to-vendor is `//group[@id='header_left_group']//field[@name='partner_id']`, not bare `//field[@name='partner_id']`. Odoo 19 move form has five `partner_id` nodes; a multi-match inherit fails and the bill stays stock. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Operator Re-Apply after slots showed a clean Vendor bill — no TIN, no EXTENSION. Bill Date red is stock required-empty.
**Rejected:** Leaving Apply as a silent warning when the inherit view Faults.

### 2026-09-09 — Field-pack slots, not an EXTENSION group
**Decided:** Inherit extras use named xpaths (after vendor, dates column fields-only, Other Info, named tab). Never `<group string="EXTENSION">` in `header_right_group`. Default from field meaning; operator override via placement row / `put TIN next to vendor`. Drop `x_active` unless the brief asks. View Designer stays the power editor. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Vendor TIN on bills landed in a nested EXTENSION island under Journal with Notes/Active padding and whitespace.
**Rejected:** Figma/Studio drag on live Odoo; keep-alive sandbox as inspect UI.

### 2026-09-09 — Field-pack Open in Odoo is the stock host list
**Decided:** After **Apply these fields**, Open in Odoo is enabled when the draft inherits a stock host — even with `root_menu_id` null. Deep-link the vendor-bill `act_window` (`account.action_move_in_invoice_type`), not a new home-grid tile. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Field packs create no app menu; gating Open in Odoo on a root menu left the button disabled after a successful Apply.
**Rejected:** Requiring a new Apps tile; leaving Open in Odoo disabled until Install this app.

### 2026-09-09 — Field-pack preview + first-run copy
**Decided:** Inherit drafts preview the stock host form (Vendor bill), not an x_* empty state. App Studio CTAs say **Apply these fields** — no new home-grid tile. Clarify asks *where it lives* (existing form vs new record); “Internal helpdesk / tickets” only if the prompt names tickets. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** S01 UAT showed a blank canvas and repeated pack-choice chips a first-time operator cannot decode.
**Rejected:** Keeping domain/vertical-pack jargon; treating field packs as a new Apps tile.

### 2026-09-09 — NGN sandbox is a new DB, not a currency rewrite
**Decided:** USD CoA `odoo_dev` stays. Fresh NGN proof uses `SKIP_GATE_MODULES=1` then country/currency **before** `account`+`l10n_ng` (`./docker/init-db-ngn.sh`, db `odoo_ngn`). CBN gold writes `res.currency.rate`; company NGN Odoo `rate` = `1 / CBN centralrate`. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Odoo blocks company currency once journals exist. Operator's connected DB was USD.
**Rejected:** Wiping `odoo_dev`; writing NGN after sale/account.

### 2026-09-09 — CBN inspect is Invoicing Settings after Promote, not Settings search
**Decided:** App Studio must not deep-link `res.config.settings` without `account.action_account_config`. That hash is General Settings; Currency search hits Community `module_currency_rate_live` (Enterprise tease). No Accounting app until `account` is installed on *this* connection (sandbox prove does not). Install Invoicing → Promote → Invoicing → Configuration → Settings → CBN. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Operator opened “Accounting Settings” after sandbox; connection had no Invoicing; Automatic Currency Rates offered an Enterprise upgrade.
**Rejected:** Treating General Settings search as CBN; keep_alive sandbox as the inspect UI.

### 2026-09-09 — App Studio gold: Promote + Accounting Settings
**Decided:** After Option A sandbox prove, App Studio records `validation_id` + zip (2h TTL) and shows **Promote to this connection** (confirm phrase) plus **Open Accounting Settings** on the *connected* Odoo (`res.config.settings`). Ephemeral `:18069` is torn down; App Studio Open in Odoo stays a menu deep-link and is the wrong control for CBN. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Operator sandbox-installed CBN gold and had no path to inspect changes.
**Rejected:** keep_alive sandbox as the inspect UI; Live Apply of gold.

### 2026-09-08 — export-zip must parse stored server_version
**Decided:** `resolve_sandbox_major` accepts `"19.0"` / `"19.0+e"`. HTTP zip/sandbox/prove use `sandbox_major_for_connection` (unsupported major → 19, never 500). Zip codec failures are 422, not Internal Server Error.
**Why:** Operator Download module zip on gold CBN returned 500; `int("19.0")` on `odoo_connections.server_version`.
**Rejected:** Requiring the UI to send `odoo_major`; treating the gold zip as the 500.

### 2026-09-08 — App Studio Install is not CBN conversion
**Decided:** CBN live rates stay gold Option A (`currency_rate_cbn`). App Studio **Install this app** is live metadata only — 409 on gold. Refine of a CBN/POS-print ask onto a residual (Purchase Request) is refused; operator must **Start new app**. Prove: sandbox zip → NGN company currency → activate USD/GBP/EUR → Accounting Settings → Service = Central Bank of Nigeria → Update now → `res.currency.rate` on USD. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Operator's CBN prompt Live-Applied Purchase Requests; Currency on that form is not the CBN cron.
**Rejected:** Live `state=code` Code Studio for urllib; inventing `x_fx`.

### 2026-09-07 — CBN live rates are gold Option A, not an x_* FX app
**Decided:** `currency_rate_cbn` is a hand-written gold zip (same path as POS receipt). Community 16–19 Docker has no `currency_rate_live` — Automatic Currency Rates is `upgrade_boolean`. Gold depends on `account` only, adds Service = Central Bank of Nigeria on Accounting Settings, fetches `https://www.cbn.gov.ng/api/GetAllExchangeRatesGRAPH`, writes stock `res.currency.rate` for USD/GBP/EUR (Odoo `rate` = company units inverted from CBN naira-per-unit when company is NGN). Classify requires CBN/Central Bank of Nigeria **and** a rate/service phrase — Nigeria Autopilot / “activate NGN” stays stock_reuse. Module → sandbox → Promote. Do not clone Apps Store bank packs.
**Why:** Operator asked for CBN in the ECB Service dropdown. That dropdown is Enterprise; inventing `x_fx` would lie.
**Rejected:** Depending on `currency_rate_live`; LLM-authored OWL/Python; Job Autopilot storing CBN keys.

### 2026-09-07 — Quality gates are invariants + mutants, not screenshot denylists
**Decided:** Surface/Install gates live in `ai_surface_invariants.py` as *properties* (title grounded in the brief, isomorphic siblings, preview↔O2M contract, brief slots: money/roles/approval/to-do). Compiler and gate share `extract_brief_slots`. New operator failures add a property + a mutant on an unseen prompt (leave/expense/visitor), never `if display_name == "…"`. Completeness 10.0 / Cert Gold still ≠ premium in Odoo. We cannot enumerate every failure; we keep a closed set of classes. Promote stays human. Restart `:8001`.
**Why:** Screenshot-specific checks only catch issues already reported; the next hallucinated menus would pass.
**Rejected:** Scaling quality by more vertical packs; pixel-matching Odoo; treating named denylists as coverage.

### 2026-09-07 — Document Grammar compiler is the product; LLM proposes
**Decided:** Every draft is compiled to a declared Community shape before Install. Packs stamp `document_shape` (thin purchase_request = `transactional_header`, verticals = `workspace`). Pack match no longer forces workspace. `named in brief` is residual lock, not a title. Duplicate notebooks / isomorphic extras / placeholder names are live-apply surface findings and disable App Studio Install. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Same purchase-request prompt installed as Named In Brief with identical Agreements/Expenses tabs; Completeness did not fail amateur Odoo.
**Rejected:** Scaling quality by writing more vertical packs; treating Completeness 10.0 as premium UX.

### 2026-09-03 — App Studio “one simple document” locks residual_app
**Decided:** `pack_choice` / `pack_conflict` transactional stamps named residual + `residual_app` and records `ir_confidence` so the stock-vs-custom chip does not fire. A later “Stock Community apps only” click cannot wipe that residual. Empty `stock_reuse` canvas tells the truth (no x_* form; Job Autopilot) instead of “open the wizard.” Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Purchase-request + manager approval answered “one simple document” then the follow-up stock chip produced `models: []` and “No form preview.” Community Purchase is RFQ/PO, not staff requests.
**Rejected:** Treating stock-only as a valid second hop after the operator already picked a custom document.

### 2026-09-03 — Stock letterhead is packet replay; custom QWeb stays Option A
**Decided:** Config Packet captures/applies `res.company.report_header` and `report_footer` (stock `web.external_layout` text, max 4000). Logo stays a human upload. Custom invoice/POS QWeb/OWL stays gold zip (`invoice_qweb` / `pos_receipt_options`) — not live XML from the prompt. `option_a_qweb_needed` is true only when a custom zip or residual is present. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Operators asked for header/footer on PDFs; those fields already exist on Community company. Inventing QWeb from Autopilot is the MEMORY reject.
**Rejected:** Live QWeb inherit from the packet; storing the company logo binary in the packet.

### 2026-09-03 — 12 Config Packet features closed (no invented taxes)
**Decided:** Remaining A–C gaps ship as: create missing fiscal positions + rec models; write cash basis on *existing* l10n taxes only; never create `account.tax`. Smoke: RFQ→receipt, POS session open then close (leave-open is fail), CRM won stage/probability. Opening TB ingest gaps when company lock date ≥ TB date (still draft, never auto-post). Users.csv template on Import + Ingest. Capture Settings allowlist POST. Overview fingerprint card. Instance Config mail health (warn only). Checklist Open-in-Odoo uses action_id / model. QWeb header/footer stays Option A gold zip. Autopilot still refuses production. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Operator asked to fully implement the 12 features that were partial (xmlid-only fiscal, POS config probe, CRM create, SMTP text hints, no lock guard, no users template UI).
**Rejected:** Inventing tax codes; storing SMTP/Paystack secrets; leaving a POS session open; live OWL/QWeb from the prompt.

### 2026-09-03 — Refine history click-to-undo is textual restore/oops
**Decided:** History **Undo** (and Undo on the latest chat bubble) submits the same Refine instruction the operator would type: latest → `oops` (`_refine_undo` stack); older remove/add/restore → inverted `restore`/`remove` text. Phrase click still reuses in the composer. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Typing restore works; operators also want one click. Inverse ops on a stale draft would lie; the text path uses the removed-field ledger.
**Rejected:** A separate undo-op API; applying old `_refine_undo` stacks onto a later draft.

### 2026-09-03 — App Studio View Designer + compact refine history
**Decided:** App Studio header/footer and Draft Studio toolbar link to `/designer?model=` on the primary custom `x_*` (not `_line`). Chat stays the refine trail; a history icon lists user phrases for reuse — not a second undo timeline. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Operators who want to edit the live form should not hunt Build → View Designer; long refine chats bury earlier phrases.
**Rejected:** Duplicating the chat as a full history page; opening Designer only after Apply (link stays live with an Install-first tooltip).

### 2026-09-03 — Config Packet is the client hop; Autopilot stays sandbox
**Decided:** Expedited configuration is Job Autopilot (sandbox) then Config Packet dry-run/apply on the client with confirm + snapshot. Not a new Settings menu; Instance Config stays the manual knob. Autopilot still refuses `write_mode=production`. Taxes are l10n xmlids only. Users.csv never stores passwords. Generated PNG icons for Apps Store zips; live Apply still sanitizes FA `web_icon` and best-effort `web_icon_data`. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Stock Settings time is the 10×; Autopilot-on-prod and clone-prod stay forbidden.
**Rejected:** Autopilot writing production; inventing tax codes; FA menu icons on Odoo 19; storing SMTP/Paystack secrets in the packet.

### 2026-09-03 — Compound Refine applies every clause
**Decided:** Split on command onsets (`and`/`then`/`,` before a new verb); apply ops sequentially so later clauses see the updated draft. Same-verb lists (`remove priority and category`) stay one clause. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** “Remove the Extra and restore the Asset Tag ticket” only ran the first verb.
**Rejected:** LLM-only multi-op; splitting on every `and`.

### 2026-09-03 — App Studio 2-col is the live Odoo sheet structure
**Decided:** ModuleSpec form arch wraps Identity|Details in `<group col="2">` so Community Odoo sits them side-by-side even with chatter-right. Statusbar `clickable: False` when header transition buttons exist. Studio preview unwraps untitled wrap groups so CSS 2-col stays. Do not port Odoo CSS/OWL; do not move chatter under the sheet in live Odoo. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** Sibling titled groups as sheet children stack full-width (Helpdesk screenshot vs App Studio 2-col). Pixel-matching Odoo purple/OWL is rejected (2026-09-01).
**Rejected:** Skinning Studio to look like stacked Odoo; fighting 17+ `<chatter/>` sibling.

### 2026-09-03 — Production Refine NL lexicon
**Decided:** `intent_lexicon` matches verbs anywhere (remove/yeet/without/oops/undo/put back/…), typos via allowlist + SequenceMatcher, `it`/undo from last op ledger, comma/and field lists. Never invent Extra. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Start-anchored regexes missed messy chat; restore without a verb map hit LLM add_field Extra.
**Rejected:** LLM-only refine; expanding `_STOP` so remainder tokens disappear.

### 2026-09-03 — Restore + Community approval execution
**Decided:** Refine restore uses `_refine_removed_fields` (never Extra). Approval briefs stamp draft→submitted→approved/refused with Submit/Approve/Refuse object_write buttons; Approve/Refuse restricted to app Manager; on_write activity when entering submitted. Not Enterprise Approvals. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** “restore the Asset Tag ticket” hit LLM add_field with no label → Extra. Operators need gated execution in Community Odoo, not a preview-only statusbar.
**Rejected:** Inventing `x_extra`; treating `/web` Discuss as the drafted app; cloning Enterprise Approvals.

### 2026-09-03 — Open in Odoo is live only after Install
**Decided:** App Studio **Open in Odoo** requires Apply `root_menu_id`. Do not fall back to `/web`. Live-metadata residuals appear on the Odoo **home grid** (Helpdesk tile; Tickets is a submenu), never Apps search. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Operators clicked Open in Odoo on a preview session and looked for a Tickets app that was never applied (`x_ticket` / Helpdesk menu absent on Elite Test).
**Rejected:** Treating `/web` (Discuss/home) as “open the drafted app.”

### 2026-09-02 — Helpdesk “don’t clone project.task” forbids Project; Refine is a real patcher
**Decided:** `span_is_negated` does not split on dotted model ids. Operator brief treats don’t-clone `project.task` / fake Project as `forbidden_bridges: project`. Helpdesk closer strips Project/PO inherit, `x_project_id` / `x_purchase_order_id`, duplicate `x_employee_id`, and line `x_status` (keep hours+note). Refine maps remove/hide/add/required and restamps `form_preview`. Unmapped refine stays in chat (200), not a deposit example. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** “Don’t clone project.task … fake Project” leaked `stock_reuse: project` because `.` broke the negation window; app-bar then inherited Tasks/PO. Refine only knew “make the deposit field required.”
**Rejected:** Treating Completeness 10.0 / Expert “no JSON gaps” as prompt-fit; leaving Refine as a one-regex toy.

### 2026-09-01 — Odoo preview = structural fidelity, not pixel parity
**Decided:** Shared `OdooPreviewKit` mimics Odoo *interaction grammar* (sheet, statusbar, smart buttons, 2-col groups, notebook tabs, field widgets, kanban color/state) with teal `--odoo-*` tokens. Open-in-Odoo / iframe stays authoritative. Explicitly **no** pixel-perfect Odoo 19 CSS / OWL / Enterprise Studio port — see `docs/reference/ODOO_PREVIEW_SPEC.md`. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Clean-room + copyright; external builder ≠ Odoo web client; purple clone branding rejected; CSS would drift every major.
**Rejected:** Porting Community/Enterprise web client styles for “indistinguishable from Odoo” previews.

### 2026-08-31 — Operator surface map in Draft Studio
**Decided:** Stamp `_operator_surface` (app menu, host smart buttons, residual buttons, stock form links + summary). Wizard callout «Where this app shows up». Residual keeps Contact/PoS as many2ones — not duplicate stat buttons. Custom↔custom O2M buttons unchanged. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`, Retry/Expert to attach surface.
**Why:** Operators found Punch Cards on Contacts but had no in-product map of where smart buttons land.
**Rejected:** Adding Contact/PoS oe_stat_buttons on Punch Card beside existing M2Os.

### 2026-08-31 — Stock-host smart buttons survive PCM Apply scrub
**Decided:** `scrub_spec_for_protected_apply` keeps smart buttons when `on_model` is stock (tier-1/2) and `related_model` is custom `x_*` with `x_*` relation_field (Contacts/PoS → Punch Cards). Still strips buttons whose related target is tier-1. Apply skips inventing O2M on tier-1 (count badge optional; existing O2M reused). Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`, Re-Apply Punch Card.
**Why:** Draft stamped Punch Cards on Contacts; Apply scrub dropped all tier-1 host buttons so none appeared in Odoo. “No record” on empty Last Transaction is correct when `pos.order` count is 0.
**Rejected:** Leaving Contacts smart buttons draft-only; inventing O2M on every stock host for a count badge.
**Decided:** `ai_stock_host_smart_buttons.py` stamps inherit smart buttons when residual M2O → Contacts (punch/tied only), Employees, sale/invoice/CRM/project/PoS/… Related stock docs get buttons whenever the FK exists; visitor/key/call logs drop Contacts buttons. Closer + depth synthesize + hygiene/Retry. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`.
**Why:** LLM “prefer useful smart buttons” was soft; punch Cards on Contacts worked only as a one-off restore — quality lift needs a registry like create-gates.
**Rejected:** Prompt-only hope; Contacts buttons on every register with a partner M2O (visitor false second Contacts app).

### 2026-08-31 — Create-gates: keep pos.order with no_create (not strip)
**Decided:** Registry `ai_odoo_create_gates.CREATE_GATE_BY_MODEL` — `pos.order` / `pos.session` / `pos.payment.method` = **no_create** (keep M2O; stamp `options` + help; form arch synced). `pos.order.line` / `pos.payment` = **strip**. Unguarded gates trip hygiene/Retry. Real PoS DBs already have orders — create block is correct; operators pick existing. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`, Retry/Expert, re-Apply.
**Why:** Stripping Last Transaction discarded useful FK; Invalid Operation on Create was Odoo protecting PoS — not a reason to delete the field.
**Rejected:** Always stripping pos.order M2Os; leaving create-able Many2one Create buttons on gated models.

### 2026-08-31 — Retry disable + no pos.order M2O + field help tooltips
**Decided:** Retry button stays visible but **disabled** only when `_llm_status.enrichment_clean` (successful llm_full, no hygiene). *(Superseded for pos.order: use create-gates no_create, not strip — see entry above.)* Stamp short `help` tooltips + Contacts smart buttons; LLM prompts prioritize OPERATOR UX. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Operators hit Invalid Operation creating Last Transaction→pos.order; Retry was always on after llm_full; cashiers need field help on custom apps.
**Rejected:** Hiding Retry entirely after llm_full.

### 2026-08-31 — Retry hidden after llm_full; Expert skipped punch hygiene at 10.0
**Decided:** Always surface **Retry AI enrichment** for residual drafts (not only pack_fallback/llm_partial). Expert closer runs when `draft_needs_hygiene_repair` (duplicate Customer M2O, punch noise, junk depends) even if Completeness is 10.0. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001` + hard-refresh; Expert or Retry on 15:06 JSON, then Apply.
**Why:** Button gated on `_llm_status` banner; Expert skipped mutate when scorecard was green after contact stopword while Flash left `x_punch_card` + `x_partner_id`.
**Rejected:** Leaving Retry unavailable after llm_full; Expert “no_repair_needed” on duplicate Customer.

### 2026-08-31 — Punch-card llm_full still had duplicate Customer
**Decided:** Closer collapses partner M2Os named like the model (`x_punch_card` → Customer) into `x_partner_id`; drops `x_total_punches` / `x_next_free_punch_date`; clips register depends to used relations; Contacts noun is covered by `res.partner` / stopword. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001`, Retry or Expert on 14:58 JSON, then Apply.
**Why:** Flash + residual merge left two Customers and junk stock/purchase depends; scorecard falsely flagged `noun:contact`.
**Rejected:** Applying the 14:58 JSON as-is; greening Cert on Completeness 9.6 alone.

### 2026-08-31 — Retry AI enrichment wakes AI and re-runs missed work
**Decided:** Async Retry: (1) `revive_llm_providers` (warm Ollama + probe Flash/cloud/fallbacks), (2) deterministic `recover_residual_draft`, (3) re-run `draft_module_from_prompt` when Create draft was honesty/timeout/partial (`needs_draft_llm_retry`, 420s budget), (4) quality/critique (skip depth on thin seeds), (5) residual recover again. Sync path wakes + residual only. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001` + refresh web.
**Why:** Operators need one button that both brings AI back and finishes the ModuleSpec Create draft missed — not only brief-seed fields.
**Rejected:** Retry that only polish-steps without revive/draft_llm; “Create draft again / restart API” as the primary story.

### 2026-08-31 — Retry AI enrichment is production self-serve recovery
**Decided:** Retry always runs `recover_residual_draft` (brief → register fields/Contacts) before optional LLM polish. Hollow/honesty thin seeds skip depth. Empty `failed_steps` means recovery, not force quality+depth+critique. Banners tell operators to Retry when AI is down. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001` + refresh web.
**Why:** Production end-users cannot restart the API or re-paste prompts; Flash/local/cloud outages must still yield a usable residual via one button.
**Rejected:** “Do not Retry / Create draft again” as the primary recovery story; forcing depth on register honesty seeds.

### 2026-08-31 — Punch-card honesty seed stamps Contacts + remaining punches
**Decided:** When residual is a loyalty/punch card, register seed fills `x_partner_id` (required), punches / remaining / next free / punches-for-reward from “buy N get …”, and keeps a Contacts smart button. Visitor logs still drop Contacts back-refs. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** 13:42 Lagos brief routing was correct (residual_app / register / Punch Card) but honesty left only `x_name` after Flash unavailable / 900s enrich fail.
**Rejected:** Applying the hollow JSON without recovery.

### 2026-08-31 — Hop IR is a hint; log final LLM prompts
**Decided:** Stamp `residual_kind` / `capability_source` / `ir_confidence` on the operator brief. `brief_llm_contract` + Flash payload label Original as authoritative and Upstream IR as may-be-wrong. `AI_LOG_LLM_PROMPTS=1` writes exact system+user payloads to `.cache/ai_llm_prompts/`. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Restart `:8001` without `--reload`.
**Why:** Lagos UAT failed at the brief hop (silent stock_first), not inside Flash — Claude’s intent→LLM advice matches; we harden hops without collapsing deterministic stock-first/Option A gates.
**Rejected:** Replacing Generation Engine with one unstructured frontier call; logging full prompts in production by default.

### 2026-08-31 — Residual is X; Receipts stay stock ≠ stock_first
**Decided:** Match `Residual is the …` and `what we don't have is a simple …` as named residual → `residual_app` + register for punch/loyalty cards. Remove `receipts stay stock` from `_STOCK_FIRST_PATH_RE` (keep in `_DEFER_POS_PRINT_RE`). Scrub “receipts stay stock” before density `stay` token hits; do not use bare `stay` for `fa-bed`. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply 13:16; Create draft after `:8001` restart.
**Why:** Lagos UAT misrouted to stock_first + hotel `x_stay` / `fa-bed` because “Receipts stay stock” looked like stock_first and “Residual is the punch card” was ignored.
**Rejected:** Retry enrichment on the 13:16 JSON; treating icon sanitize as the only Live Apply fix for this prompt.

### 2026-08-31 — Odoo 19 rejects FA web_icon; users use group_ids
**Decided:** Live Apply coerces Font Awesome `web_icon` (`fa-book,#714B67`) to `base,static/description/icon.png`. Join the applying login via `res.users.group_ids` (Odoo 19), not `groups_id`. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Accra Apply created model/views/ACL but skipped all menus — FA icon raised `Unsupported file: fa-book/#714B67`. Group join then failed on renamed user field, so a later restricted menu would stay invisible.
**Rejected:** Leaving FA icons on live Apply; treating empty Apps search as the bug.

### 2026-08-31 — Live Apply must join the operator to app menu groups
**Decided:** After Apply creates draft `res.groups` and restricts the root menu, also `(4, gid)` those groups onto the connection `res.users` login. Apps Store search will never find a live-metadata residual. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Re-Apply 12:32 after `:8001` restart (or manually add Visitor Log User).
**Why:** Accra Apply succeeded but Open-in-Odoo / home grid showed nothing — root menu was limited to `group_visitor_log_user` and the applying admin was not a member.
**Rejected:** Treating “not in Apps” as a failed Apply; greening Cert on Apply alone.

### 2026-08-31 — Register ACL names follow the residual, not the few-shot
**Decided:** After Flash, register closer sets header `description` and `ir.model.access` names from `display_name`, and stamps `required` from the brief column list (employee / purpose / time in; ID stays optional). Do not add `x_partner_id` when Flash omitted it — contacts is a forbidden bridge, not a second Contacts app. Completeness ≠ Cert ≠ Autopilot. Promote stays human. 12:18 is ReviewRequired, not go-live. Create draft after `:8001` restart.
**Why:** 12:18 was the first Accra `llm_full` (429→Ollama model fix worked) but ACL rows said “One Row In The Named Paper Book” and Employee/Purpose/Time In were optional because Flash copied the step1/few-shot placeholder.
**Rejected:** Greening Cert on 12:18; forcing an optional Contact M2O; Retry enrichment on 12:04.

### 2026-08-31 — Ollama fallback never POSTs a Gemini model id
**Decided:** `OllamaProvider` resolves `_ollama_local_model` (`OLLAMA_MODEL` / `qwen3:8b`). Cloud `AI_MODEL_BULK` (gemini-/gpt-/claude-) is not sent to `/api/generate`. HTTP 404 keeps status_code 404 (not default 503). Empty step1 after LLM fail is `step1 empty`, not `timed out`, unless the error was a timeout. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Retry 12:04; Create draft after `:8001` restart.
**Why:** 12:04 Accra was the right register (10.0 / ReviewRequired) but Gemini 429 fell back to Ollama with `gemini-2.5-flash` → HTTP 404 → honesty seed and a false timeout banner.
**Rejected:** Retry enrichment on the honesty JSON; greening Cert; leaving bulk-id as the Ollama tag.

### 2026-08-31 — Gemini 429 waits Retry-After then falls back
**Decided:** Treat HTTP 429 / RESOURCE_EXHAUSTED as quota, not a timeout. Sleep Retry-After (cap 25s, three extra attempts), then try another configured cloud key or reachable Ollama. Honesty seed only if every backend fails. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Retry AI enrichment on 11:50/11:54 honesty JSON; Create draft after `:8001` restart.
**Why:** 0.4s/0.8s 503-style retries never cleared Gemini free-tier RPM; step1 429 became honesty seed and a Retry banner.
**Rejected:** Asking the operator to Retry enrichment; greening Cert on the honesty seed.

### 2026-08-31 — Flash interprets the brief; closer is backup
**Decided:** Every ModuleSpec LLM call receives `brief_llm_contract` derived from the operator brief + document shape (not a visitor pack). Register step1 asks for one entity, not a FULL vertical; step2 does not pad with company/currency/status. Thin reuse omits `res.company` / `res.currency` / `res.users` unless the brief named a legal-entity split, a currency field, or a login assignee. Workspace CRM still gets the CE-19 partner stack. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply the 11:30 JSON; re-paste after the `:8001` restart.
**Why:** 11:30 Accra was the right register after the closer, but Flash still invented required Company and Check-in labels because staged prompts and `_ALWAYS` reuse fought the brief.
**Rejected:** Accra-only prompt tweaks; ripping the subtractive closer; swapping Create to Opus; greening Cert.

### 2026-08-31 — Register does not invent multi-company or hotel check-in labels
**Decided:** On a register, `x_company_id` + multi-company ir.rule only if the prompt names a legal-entity split (`prompt_asks_multi_company`). Unknown “multi-company vs one company” stays empty. Clock labels that say Check-in/Check-out become Time In/Out unless the brief used check-in. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply the 11:30 JSON; re-paste. Do not Retry AI enrichment on a Gemini 429 honesty finish.
**Why:** 11:30 Accra had the right one-header register and one duration alert (10.0 / ReviewRequired) but required Company plus hotel clock labels. Planner already says two offices of one company are not multi-company ir.rule.
**Rejected:** Applying 11:30; treating an existing Flash `x_company_id` as “wants multi-company”; greening Cert.

### 2026-08-31 — One duration clock; drop Flash create_date twins and unprompted notes
**Decided:** When the brief asks for a stay-duration alert, keep one `on_time` on the header datetime (`x_time_in`), not `create_date`. Drop competing critique rows (null domain, `user_id: x_host_id`). Drop `x_notes` on a register unless the prompt named notes/comments. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply the 11:24 JSON; re-paste.
**Why:** 11:24 Accra scored 10.0 / ReviewRequired with honest fields and search, but still had two clocks — Flash `create_date` plus honesty `x_time_in` — and an unprompted Notes field. Scorecard signatures differed so Expert said no gaps.
**Rejected:** Applying 11:24; greening Cert; treating Completeness 10.0 as Apply-safe while `create_date` + field `user_id` remain.

### 2026-08-31 — Duration alert is signature-idempotent; uid is res.users
**Decided:** `ensure_duration_activity` treats an existing `on_time` on the same model/date field as present even after `rewrite_critique_automations` title-cases the name. Honor and close also `dedupe_automations_by_signature`. Register field strings that are all-lowercase are title-cased. Search “My records” (`uid`) is emitted only when the field relation is `res.users` — not `hr.employee`. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply the 11:15 JSON; re-paste. Do not Retry AI enrichment on an honesty seed.
**Why:** 11:15 Accra was the correct one-header register (Gemini step1 timeout → honesty seed) but hygiene 9.5 from a duplicate 2h alert, lowercase “visitor name”, and `x_employee_id = uid`.
**Rejected:** A visitor pack; greening Cert; Retry enrichment on a finished honesty seed.

### 2026-08-31 — Register closer subtracts Flash chrome the prompt did not enumerate
**Decided:** After Flash, a register keeps identity `x_name` (residual “N name”, not Log Entry Reference), purpose/notes as char unless the prompt listed values, and list/form arch without `x_status` decorations. Unused CE19 hosts (`res.users`/`company`/`currency`) and catalog spam are clipped on thin shapes. Completeness is rebuilt from the operator brief so out-of-scope invoicing/python are not checklist failures. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply the 10:24 JSON; re-paste.
**Why:** 10:24 Accra was the right one-model register (10.0 / ReviewRequired) but still wore sequence chrome, an invented purpose taxonomy, stale list decorations, and a leftover completeness row for “invoicing”.
**Rejected:** A visitor pack; greening Cert; treating Completeness 10.0 as Apply-ready.

### 2026-08-31 — Register closer is document-shape, not a visitor pack
**Decided:** Paper-book polish (no workflow/kanban/`x_code`/Contacts back-ref; residual root menu; clip forbidden account/crm; restamp no-code duration `on_time`) runs for any register (`x_*_log`, key log, call log). Shape regex is `NOUN log|book|ledger`, not an industry allowlist. Elite `tests/`/`i18n/` are zip hygiene, not Option A. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply 09:53 visitor JSON.
**Why:** 09:53 Accra draft was honest architecture (`_document_shape=register`) dressed as hotel check-in because leaf `log` was missing, duration died after Flash, and reuse still listed Accounting/CRM.
**Rejected:** Adding a visitor domain pack; special-casing “Visitor name”/Host labels; greening Cert on completeness.

### 2026-08-27 — Accra gazetteer writes Ghana; honesty seed is pack_fallback
**Decided:** City gazetteer stamps `OperatorBrief.country` (Accra → Ghana). Named residual is lifted from an empty `## Custom residual` via goal (`add SLA due date on invoices`). Domain-fit ignores out-of-scope / gazetteer / function words; `x_attorney` on a forbid list is not a lexicon leak. Unpacked AI-off seed is `pack_fallback` / `honesty_seed`. Scorecard copies cert onto `_live_apply`. Register closer adds search views (UI only). Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Independent checker scored 86: Ghana never appeared in the IR, Completeness 8.63 from English nouns + attorney substring, AI-off banner said operational seeds, live_apply cert was unset.
**Rejected:** Inventing industry/company from Accra; greening Cert Production on a register.

### 2026-08-27 — Draft Studio: honesty IR, then Flash, then subtract
**Decided:** Stamp `_document_shape` (`register` / `field_pack` / `stock_reuse` / `catalog` / `transactional_header` / `workspace` / `option_a`) before Flash. Ambition and model budget follow shape, not word count. Closer and enrichment may fill fields or subtract forbidden extras — not density/satellites/CRM-account bridges on register/field_pack. Flash emits only `architecture_plan` models; 503 → honesty seed (`llm_status.reason=honesty_seed`), not a padded workspace. Cert prompt-fit hard-fails out-of-scope hosts, plan drift, register satellites; unknown sandbox is not Production for `full_app`. No visitor vertical pack. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Do not Apply 17:03 visitor JSON or Hotel · 16:31.
**Why:** Gemini 503 only skipped the LLM; the additive closer still ran comprehensive floors (density 16, party+line, CRM/invoice bridges) and Cert Production scored the bloat. Same class as restaurant-`menu` / hotel-`front desk`: a generic workspace prior.
**Rejected:** Swapping Create-draft to Opus; greening Cert on a bloated spec; adding a visitor domain pack; asking Flash to “be more senior” while satellites still run.

### 2026-08-27 — After infra/actions, paste the commands
**Decided:** After doing something (Docker, uvicorn, curl, git), show the operator the exact commands so they can repeat them. Do not only describe the outcome.
**Why:** Operator asked to always see the commands after they are run.
**Rejected:** Outcome-only recaps for infra.

### 2026-08-27 — Timeout must not restore a foreign domain pack
**Decided:** After a draft-job timeout, restore a cache row only when the prompt matches **and** `domain_pack` still fits the prompt (pack-id token as a word). Do not fall back to the newest snapshot. Completeness 9.1 of a recovered hotel JSON is not a visitor-log success. Completeness ≠ Cert. Promote stays human. Do not Apply Hotel Management · 16:31.
**Why:** Create draft after the hotel-regex fix still timed out; wizard `pickCachedDraft` reloaded the 16:31 hotel row because the prompt string matched and newest-entry was the fallback.
**Rejected:** Retry AI enrichment on the hotel JSON; treating the recovered snapshot as a new generation.

### 2026-08-27 — Office visitor log never seeds the hotel pack
**Decided:** Hotel pack regex requires lodging collocates (`hotel`/`pms`/`room`/`folio`/`housekeeping`) next to `front desk` / `check-in`. Bare office “front desk” is not PMS. Expert closer rebuilds when `domain_pack` does not match the prompt. Completeness ≠ Cert. Promote stays human. Do not Apply the 16:31 Hotel snapshot.
**Why:** Visitor-log prompt matched hotel `\bfront desk\b`; pack-seed + LLM grew rooms/bookings/`x_bill`. Critique already named `x_visitor_log` and skipped the repair.
**Rejected:** Expert-merging the hotel JSON; greening Completeness 9.1; treating `front desk` as hotel.

### 2026-08-27 — Field-pack inherit never seeds a vertical pack
**Decided:** `classify_generation` grain `field_pack` seeds via `draft_component_from_prompt` before `match_domain_pack`. Restaurant regex does not treat UI “new menu” as dining. `_finish_seed_draft` skips `close_odoo_architecture` on inherit seeds. Expert closer rebuilds a leaked restaurant pack from the user prompt. Completeness ≠ Cert. Promote stays human. Do not Apply the restaurant snapshot.
**Why:** SLA-on-invoices prompt (“Cashiers shouldn’t see a new menu”) matched restaurant `\bmenu\b`, pack-seed skipped the component path, then app-bar/LLM grew 11 models + `x_bill`. Honesty IR already said field_pack.
**Rejected:** Treating Gemini as the bug; Expert-fixing the restaurant JSON in place; greening Cert.

### 2026-08-27 — Autopilot l10n probe after stock install
**Decided:** Stamp `detect_l10n` only after named stock apps (and named country l10n) are installed. If `sale`/`point_of_sale` pulled `account`, list it in `already_installed`. Unknown country does **not** install `l10n_generic_coa`. Missing `account.move` *before* install is not a coverage warning. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Fresh SKIP_GATE_MODULES POS job: smoke passed (SO 1 → invoice 1) but log said “Accounting is not installed” twice and coverage capped at 8.0. CoA and invoice existed; `sale` had pulled `account`. Probe ran first on an empty DB.
**Rejected:** Treating the warning as a failed Accounting install; assuming a country CoA; greening Cert.

### 2026-08-27 — Reused sandbox invoice form is not stock Community
**Decided:** Autopilot smoke creates a stock `sale.order` → `account.move`. It does not wipe leftover `x_*` / view inherits from prior Draft Studio Apply (PAY/QR, TEST GROUP, `x_demo_note`). Probe `sandbox_form` lists leftover `x_*` on `account.move`/`sale.order`. Due date “or Pay…” is stock payment terms (`nolabel`). Fresh DB for clean UAT. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** Operator opened invoice 85 (S00108) and saw PAY/QR, unlabeled Pay…, TEST GROUP, `x_demo_note`, company “one company”, NGN — not a stock invoice chrome.
**Rejected:** Treating leftover Apply as this job; wiping the sandbox; greening the form as stock.


**Decided:** Job Autopilot writes `res.company.name` only from `Client/Company/Business name:` (or an explicit override). It does not scrape `for one company` / `for B2B`. Unknowns stay empty. Completeness ≠ Cert ≠ Autopilot smoke. Promote stays human.
**Why:** Residual-none POS Autopilot smoke passed (quote→invoice id=84, score 7.0 data-N/A) but bootstrap wrote company name `"one company"` because `(?i) for ([A-Z]…)` matched the goal sentence.
**Rejected:** Inventing a legal name when the brief lists company name as unknown.


**Decided:** Warning banners derive from `_live_apply.findings` and missing `_scorecard`, never from `ready: false` alone. Expert closer **no-ops** on `stock_reuse` / `refuse_clone` (`verdict=no_repair_needed`, `models: []` stays empty). If the closer would drop completeness, invent x_* on stock_reuse, or add stock clones, it **reverts**. Live-apply `next_activity` automations that the pipeline dropped are restored, then mixins stamped. Cert ReviewRequired on `full_app` is not an Expert repair. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
**Why:** 12:22 JSON was honest (`findings: []`, score 10.0) but banners asked Expert to fix missing dates/mixins. The closer would have packed an empty stock-reuse spec into x_* and made JSON worse. Expert “needs_work” was forced by `grain=full_app` + Cert < Production.
**Rejected:** Hiding Expert entirely; greening Cert; using `ready: false` as “unfinished” on a scored residual.

### 2026-08-27 — Empty stock_reuse ModuleSpec is not Cert Gold
**Decided:** Residual-none `stock_reuse` keeps `models: []`. Completeness 10.0 is empty-spec hygiene. Certification caps at **ReviewRequired** (never Gold/Production). Live-apply `ready` is false. UI lists named Community apps and sends the operator to Job Autopilot. Expert closer is visible but must not invent x_*. Autopilot quote→invoice smoke remains a separate job scorecard.
**Why:** 09:25 Draft Studio routed correctly (stock_reuse) but presented 0 models as a failed draft with Cert Gold and a “domain pack / Retry AI” banner. Autopilot smoke had already passed.
**Rejected:** Greening Cert on an empty spec; inventing x_* so the count is non-zero; treating Autopilot smoke as Draft Studio Gold.



### 2026-08-27 — Stale uvicorn served the 08:23 invoice-QR draft
**Decided:** After routing changes, kill and restart `:8001` (no `--reload`) in the same session. `stock_reuse` classifies **before** POS gold. Deferred “receipts stay stock POS until Option A” is not a print ask. Named `## Stock reuse` is the exclusive Autopilot install list (no `website_sale` from Retail/eCommerce). `draft_module_from_prompt` must seed capability before component grain.
**Why:** Operator re-paste at 08:23 still got Document extras because the API process started 2026-08-26 never loaded the fix. Autopilot smoke ≠ Draft Studio success.
**Rejected:** Treating a new snapshot timestamp as proof the new router is live.

### 2026-08-27 — Stock-reuse is residual-none only; extension and named x_* stay first-class
**Decided:** `stock_reuse` (empty Draft Studio spec) fires only when custom residual is **explicitly none** and the brief is not an inherit/field-pack ask. `stock_first` + named residual (loyalty punch card) → residual_app / Autopilot `x_*`. `stock_first` + “Add SLA due date on invoices” → field_pack on `account.move`. “Do not invent x_receipt” is a constraint, not residual none.
**Why:** Operators still need high-quality inherit-and-wire and from-scratch residuals; yesterday’s POS fix must not starve those paths.
**Rejected:** Treating every `capability path: stock_first` as an empty seed.

### 2026-08-27 — Stock-first POS brief is stock_reuse, not Option A
**Decided:** A structured operator brief with `capability path: stock_first`, custom residual None, and “receipts stay stock POS until a separate Option A” is **`stock_reuse`**: empty models, no `x_receipt`, no invoice Pay/QR QWeb, no gold `pos_receipt_options`. Out-of-scope “receipt designer” and “later Option A only if we explicitly ask for OWL/QWeb” are stripped from capability detection (`intent_corpus`). Autopilot installs **named** stock apps only — do not add `website_sale` from POS / “shop manager” via the retail catalog. Completeness ≠ Cert ≠ Autopilot smoke. Promote stays human.
**Why:** Draft Studio classified this brief as Option A invoice extras (Pay now + QR on `account.move`) because `receipt designer` in Out of scope, `QWeb` in the deferred path, and `add` in the Done bar flipped grain to `field_pack`. Autopilot’s quote→invoice smoke was the correct done-bar; Draft Studio was not.
**Rejected:** Treating Autopilot smoke as Draft Studio success; inventing `x_receipt`; greening Cert; installing eCommerce because the actor is “shop manager”.

### 2026-08-26 — Generation Engine: gold patterns, not Apps Store clones
**Decided:** `classify_generation` runs before pack/LLM. Residual → stock-first pack/unpacked + closer. Option A (POS receipt, invoice QWeb) → **select** a hand-written gold template (`pos_receipt_options` / `invoice_qweb`); LLM does not author OWL. `[custom]` / standalone = module zip CTA. Explicit clone/copy/reverse-engineer of Apps Store/GM is **refuse** — a GM *product-name paste* is still the honest POS options template, not a clone. Car rental drops `x_rent_customer` / `x_rent_payment` (Contacts + `account.move`). Completeness ≠ Cert ≠ Autopilot. Promote stays human. Structural zip gate (ACL + syntax) fails closed before Docker.
**Why:** Operators want Odoo-quality for any custom app. Apps Store specialists (GM / Receipt Studio) are hand-built OWL; a prompt factory will not match them. Fake `x_receipt` / parallel customers are the failure mode.
**Rejected:** Cloning GM; LLM-authored POS frontend; greening Cert; auto-promote; in-app thermal WYSIWYG (deferred).

### 2026-08-26 — Pytest must not leave plaintext secrets on app-db
**Decided:** Connection fixtures encrypt with `encrypt_secret` and delete the row in `finally`. Autopilot/RPC maps a non-Fernet secret to “re-enter the Odoo password”, not “wrong FERNET_KEY”.
**Why:** Wave 18 committed `Elite Test` with `secret_encrypted="dev-only-test"` into live `odoo_custom`; Job Autopilot failed with a Fernet InvalidToken traceback.
**Rejected:** Rotating FERNET_KEY; wiping the sandbox Odoo DB; treating every InvalidToken as a lost key.

### 2026-08-26 — Operator brief IR; POS receipt is Option A not a residual
**Decided:** Every Draft Studio / Autopilot prompt is normalized into `_operator_brief` / `structured_brief` from stated facts only (goal, actors, stock reuse, residual, constraints, unknowns). Empty slots stay unknowns — do not invent country/currency/company/industry. POS receipt designer / thermal / live preview is Option A OWL/QWeb on `point_of_sale`; skip vertical packs (restaurant/retail examples in marketing copy); no `x_receipt` residual. Completeness ≠ Cert; Promote stays human.
**Why:** Operators paste marketing dumps or one-liners; GM-style receipt copy would otherwise match the restaurant pack and invent a fake back-office receipt app.
**Rejected:** Cloning third-party POS receipt modules; treating receipt “show/hide fields” as live `ir.model.fields`; assuming bar/restaurant/retail from benefit examples.

### 2026-08-26 — Line forms are sale.order.line (no statusbar/chatter)
**Decided:** `*_line` is a nested row, not a document. `_build_form_arch` omits `<header>`/`statusbar` and keeps `x_status` as a sheet column. Rules do not promote lines to `is_workflow` or `mail.thread`. Closer strips leftover statusbar/chatter; inject chatter skips lines. Domain-agnostic — no vertical branches.
**Why:** AOP 11:33 `x_matter_line.form` still had statusbar + chatter after mixins were demoted, because form rebuild emits a header whenever `x_status` exists and rules stamp `mail.thread` on any status field.
**Rejected:** Dropping line `x_status`; treating `_time` suffix as a line (false friend: `x_downtime`); greening Cert.

### 2026-08-26 — Line date/status, commercial labels, Contacts residual only
**Decided:** `ensure_line_model_parent_links` only strips transfer geometry (`x_from_branch_id`, …) and `x_date` when the parent already has `x_date`. Optional `x_company_id` stays on lines. `strip_non_workflow_state` keeps `*_line` billing `x_status` (no Confirm/kanban). Embedded lists: people/date → qty/hours/rate/amount → `x_code`/`x_notes`. `short_model_label` uses Community commercial names for stock hosts (Quotations, Invoices, Meetings, Tasks, Leads). Contacts button_box is the residual header, not every notebook child; `*_party` join menus hide like `*_line`.
**Why:** AOP 10:08 draft: no Date on Billable Time, Reference before Hours, “Sale Orders”/“Account Moves”, Contacts cluttered with Parties/Conflicts/Documents, Matter Parties as an Operations menu.
**Rejected:** Restoring header M2Os or line sequences; greening Cert; counting Contacts children toward the Apps Store smart-button floor.

### 2026-08-25 — Header form: notebook children, not Identity docs / line sequences
**Decided:** Embedded custom O2M lists always refresh to preferred columns (qty/hours/rate/amount reserved, cap 8) even when two identity cols already exist. Related stock *documents* (`crm.lead`, `sale.order`, `account.move`, …) stay on the model and as smart buttons; they are omitted from header Identity. `account.analytic.account` is an analytic dimension, not a related document — keep it on the form. Non-`x_*` relations are never quality orphans. `*_line` models get no `ir.sequence` (sale.order.line). Custom `x_*` children already on the header as O2M are notebook pages, not `oe_stat_button`s. Domain-agnostic — no vertical branches.
**Why:** AOP 21:18 draft: thin Billable Time list, `x_lead_id` on Identity, `MATTER2/` line help, dropped analytic account, Parties/Time smart buttons duplicating the notebook.
**Rejected:** Law-firm-only form rules; dropping `x_lead_id` from the model; hiding analytic account; greening Cert; treating notebook children as the Apps Store smart-button floor.

### 2026-08-25 — Official header form is one notebook; three bars stay separate
**Decided:** Custom children on an `x_*` header sit in **one** `<notebook>` (sale.order shape). Do not wrap each O2M in `<group><notebook><page>`. Nested lists use child columns (`x_partner_id`, `x_role`, `x_hours`, …), not `x_name` only. `x_project_id` → `project.project` is skipped when `project.task` is link-only / already FKs the residual. Completeness `has_views` is only for new `x_*` models — inherit hosts do not fail it. Critique does not add `x_status` on party joins. Draft Studio copy lists Completeness / Certification / Autopilot as three bars; Expert closer repairs JSON hygiene and does **not** raise Cert to Production.
**Why:** AOP post-enrich form was group-wrapped notebooks; Completeness listed `calendar.event` as missing views; closer put Project on the matter; operators read “Ask the Expert to review and fix” as a Cert unlock.
**Rejected:** Restoring stock O2Ms on the matter form; greening Cert without Option A prove; treating Expert closer as Autopilot/Option A smoke.

### 2026-08-25 — Completeness 10.0 is hygiene; stock docs are smart buttons
**Decided:** Line “duplicate parent” only counts custom `x_*` headers — `hr.employee` / `account.analytic.line` on a `*_line` are stock FKs (sale.order.line pattern). `blocked → pending` is Reset to Draft, not an illegal terminal exit (`cleared`/`closed` still cannot reopen). Stock related documents (sale/invoice/calendar/lead) are **smart buttons**, never form O2Ms (nested lists emit `x_name`). Critique must not add `x_reference` beside `x_code`. Custom `x_*` residual + Pay/QR is **mixed**, not Option A-primary — completeness may be 10.0; Certification stays Reject until sandbox prove. Promote stays human.
**Why:** AOP enrich stayed 7.0 on two false validators, then added-and-dropped stock O2Ms leaving empty Calendar/Sale groups and a second matter number.
**Rejected:** Restoring stock O2Ms on the matter form; greening Cert without Option A prove; treating `blocked→pending` as the same as `closed→pending`.

### 2026-08-25 — Domain-agnostic quality: commercial host, live catalog, offices ≠ companies
**Decided:** Pay/QR/PDF Option A always hosts on a commercial document (`account.move` > sale/PO/picking), never `calendar.event` because it is first inherit. QWeb inherit is `account.report_invoice_document` (etc.). Documented `sudo()` (`SUDO-JUSTIFIED` on ICP `web.base.url`) is not a hygiene finding. Pack Create-draft loads the connection catalog so `reuse.plan.source=connection` and `_planner_grounding.catalog_size>0`. “Stock Odoo documents” is Community reuse language, not Inventory — do not infer `stock.warehouse`. `multi_company: false` / “two offices of one company” keeps optional `x_company_id` and strips Multi-company ir.rule. Party/role join tables never get generic `x_status` workflow. Architecture budget tracks the residual already in the spec (not a generic 8). Pattern library: join_table_party, qweb_commercial_host, sudo_justified_icp, single_company_offices. Completeness 10.0 ≠ Cert; Cert ≠ Autopilot smoke; promote stays human.
**Why:** AOP Legal run: Pay/QR on calendar, unjustified sudo, offline_ce19 catalog 0, warehouse false-friend, MC rules on a single company, party re-promoted after demote.
**Rejected:** First-inherit as Option A host; scoring `x_company_id` as multi-company; matching bare “stock”; form chrome for PDF extras.

### 2026-08-25 — Reuse chips must not sync plan.models
**Decided:** Wizard chips (`reuseModels`) only change via explicit toggle / Confirm / Install. Never merge `reuse.plan.models` **or auto-confirmed `source=connection` decisions** into chips. Snapshot restore loads only **operator** and **confirmed installable** rows. Connection-aware plan still auto-wires installed apps for apply; those rows must not become `operator_reuse` or Suggested/Installable siblings vanish on the next click. Catalog reload on Install error keeps the previous list.
**Why:** Sandbox: restore snapshot → chips filled with every connection model → Install/Confirm one suggestion reapplied the whole set. Catalog reload after Install also wiped the picker on a failed refresh.
**Rejected:** Treating `confirmed: true` + `source=connection` as operator chips; clearing `reuseCatalog` to `[]` on reload error.

### 2026-08-25 — Inherit bridges are residual, not Option A junk
**Decided:** Capability stamp drops only mechanism-noun padding (`x_dynamic`, `x_click`, …). It must not strip `x_matter_id` / fee-earner fields on stock inherit. Reverse O2M belongs on the `x_*` header with a legal name (`x_calendar_event_ids`), never `x_calendar.event_ids` and never `sale.order.x_matter_ids` inventing `x_sale_order_id`. Line models keep stock FKs (`hr.employee`); only extra **custom** `x_*` parents are trimmed. Packed drafts skip the 15-row catalog dump. Completeness 10.0 ≠ Cert; Cert ≠ Autopilot smoke; promote stays human.
**Why:** AOP 19:55 draft: quality O2M with dots, fake sale.order reverse O2M, `x_status` on `project.task`, `x_employee_id` stripped from `x_matter_line`, catalog IAP/4-part noise, “Other” submenu, conflict `cleared→blocked`. Closer then deleted inherit bridges as “non-stub”.
**Rejected:** Option A–primary “stubs only” field wipe on residual_app inherits; treating stock inherit as an O2M parent because the id contains `order`/`task`.

### 2026-08-25 — Domain-agnostic quality: commercial host, live catalog, offices ≠ companies

### 2026-08-25 — Stock catalog = on-instance models
**Decided:** Reuse catalog is `ir.model` on the connection (non-transient, non-x_*). After Autopilot installs apps, refresh the catalog (~360 on sandbox post-run, not ~118 lean DB). Not a full unused CE Apps Store list.
**Why:** Operator expected “full CE version list”; 118 was pre-install catalog.

### 2026-08-25 — Install & reuse keeps sibling stock suggestions
**Decided:** `Install & reuse` calls `POST …/modules/install-community` (CE apps only), then reapply. `plan_reuse` preserves prior unconfirmed installable decisions and keeps the confirmed row as `source=installable` so the Install list does not collapse to one item.
**Why:** Operator lost remaining stock reuse options after clicking Install on one suggestion.
**Rejected:** Regenerating the whole draft on each Install click; treating Install as metadata-only.

### 2026-08-25 — Matter Confirm is intake→open (not billed); ACL accepts model_x_*
**Decided:** Semantic workflow ranks `intake` before `open` and `billed` before `closed`. Pack transitions with a Confirm-shaped edge (`intake|draft→open`) are **preserved** — do not scramble into open→intake / intake→billed. Autopilot smoke picks `ir.actions.server` that sets `x_status=open` (never first arbitrary `set x_status`). Scorecard ACL matches `model_x_matter` stubs. Matter brief seed fills required `x_employee_id` + `x_status=intake`.
**Why:** AOP Autopilot smoke failed `Wrong value for x_status: 'billed'`; Draft Studio falsely flagged ACL while Completeness 9.7 / Cert Production.
**Rejected:** Treating ModuleSpec Cert Production as Autopilot smoke pass; auto-picking first `set x_status` action.

### 2026-08-25 — Certification ≠ ModuleSpec 10.0 (Engineering upgrade)
**Decided:** ModuleSpec `_scorecard.overall` / `score_0_10` stays **completeness/hygiene**. Ship readiness is a separate `_certification` stamp (`tier` Reject|ReviewRequired|Production|Gold + Quality/Evidence/Risk + evidence ledger). `_architecture_plan` is a thin plan IR inside the draft (not a parallel OES). Failure IR + constrained repair feed Option A prove; artifact locks after PASS. Autopilot job scorecard remains separate. **Promote stays human** even at Gold. Do not redefine 10.0 as go-live.
**Why:** ChatGPT/Claude “engineer_module” proposals; prevent green 10.0 while PDF uninstalled / unproven.
**Rejected:** Full Odoo Engineering Compiler / second orchestrator; replacing ModuleSpec with OES; auto-promote on Gold; full OCA Create-draft corpus; mutation/SeniorBench in MVP.

### 2026-08-24 — Designer Save treats canvas x_* as source of truth (ignore inject-combined)
**Decided:** Stock Inherit Save passes **stock-only** names as `existing_field_names`, so Form layout `x_*` groups always rewrite `{model}.designer.form`. After write, unlink redundant `{model}.custom.x_*.{type}` injects created by create-field. Empty canvas (no `x_*`) still 422 with a clear “need an x_* field” message — not a full form replace.
**Why:** Create-field inject + Form layout Save previously refused with “No additive custom fields” because combined arch already listed those `x_*`.
**Rejected:** Treating combined-arch `x_*` as already-saved for Designer Inherit.

### 2026-08-24 — Fix duplicate chrome via repair; unlink is nuclear
**Decided:** Live Bills with Send|Send / Other Info|Other Info are fixed by rewriting `{model}.designer.form` to additive sheet inject (`POST …/designer-inherit/repair`), keeping TEST GROUP / `x_*` when parseable. **Unlink designer inherit** (confirm phrase) deletes that child only — not the stock primary, not `{model}.custom.*` injects. Prefer repair over unlink when custom groups should stay.
**Why:** Code-only additive-save fix does not clear an already-written full-form replace on the DB.
**Rejected:** CSS-hiding duplicates; auto-deleting TEST GROUP without operator confirm.

### 2026-08-24 — Stock Designer Save is additive inherit only (no full form replace)
**Decided:** For non-`x_*` models, View Designer Inherit save emits `build_additive_form_inherit_arch` (sheet-inside groups for new `x_*` only). Never `render_inherit_replace_arch` of a loaded/combined form — that re-emits header buttons and notebook pages so module inherits inject Send/Print/Pay and Other Info a second time. Custom `x_*` models may still own a full primary/replace. Saving again replaces a prior full-replace `*.designer.form` with additive.
**Why:** Operator Bills screen showed Send|Send, Print|Print, Pay|Pay, Other Info|Other Info after saving a new TEST GROUP on `account.move`.
**Rejected:** CSS-hiding duplicates; full form replace as the default “safe inherit”.

### 2026-08-24 — Expert bug diagnosis: catalog-first, always on Fault paste
**Decided:** When the question looks like an RPC/software fault (`Fault`, validating view, AccessError, Request failed + body, etc.), Expert runs `error_diagnosis` **before** product guidance and RAG/LLM. Catalog covers empty field names, missing model/field, xpath, ACL, integrity, parse, confirm/write_mode, plus a universal fault-excerpt fallback so Diagnose never returns unrelated vertical docs.
**Why:** Empty `<field name=""/>` paste previously fell through to LLM + poison RAG (estate.property / Peppol).
**Rejected:** Relying on embeddings alone for operator error pastes.

### 2026-08-24 — Expert product guidance (docs + rules, not live codebase)
**Decided:** Odoo Expert does not read the live app source tree at ask time. Product how-tos come from (1) priority RAG ingest of `docs/OPERATOR-FEATURE-DEMO-GUIDE.md`, `USER-GUIDE.md`, `OPERATOR.md`, `SAFETY.md`, … as `source=project`, and (2) deterministic `product_guidance.py` rule answers with deep links into Designer / Draft Studio / Autopilot / etc. Re-run `python -m app.expert.ingest` after guide edits.
**Why:** Operators need correct “use `account.move` not `account`” answers even when embeddings are cold.
**Rejected:** Letting the Expert LLM invent UI steps from parametric memory alone.

### 2026-08-24 — Honest 10.0 = done-bar + Option A sandbox smoke (any prompt)
**Decided:** ModuleSpec scorecard is grain-aware. Option A–primary drafts (`_capability_primary_option_a`) get grain label “Option A document extras…”, `_done_bar` (live / option_a / mixed), deduped `_live_apply.option_a`, and **score capped at 7.0** with `option_a_unproven` until ephemeral sandbox install + RPC surface smoke passes (`POST …/module-spec/option-a-prove`). Smoke success sets `_go_live_ready` (sandbox-proven); **promote stays human**. Capability gaps expand domain-agnostically (payment provider, webhook, paperformat, …) with scaffolds. Completeness 10.0 is still not Apps Store auto-prod.
**Why:** Operator saw 10.0 on PDF/QR while PDF was uninstalled — product lie vs senior bar.
**Rejected:** Leaving field_pack label + uncapped 10.0 for Option A; auto-promoting after smoke.

### 2026-08-20 — Capability-primary prompts stamp Option A (domain-agnostic)
**Decided:** PDF/QWeb, QR-on-document, click-to-pay, website controllers, OWL/JS widgets, Python/cron, and rich mail templates are detected without vertical packs. When the prompt is Option A–primary (gaps present, no live field signal), draft honest stubs only (`x_payment_url` / `x_qr_payload`) or empty inherit — never invent `x_dynamic` / `x_notes` / `x_website` / `x_owl` / `x_python` from mechanism words. **Option A zip scaffolds real content:** QWeb inherit on the stock document template (`account.report_invoice_document` etc.), Pay-now + `/report/barcode` QR, and host `_inherit` that fills stubs from `get_portal_url()`. Live Apply may land stubs; PDF wiring stays module → sandbox → promote. Scorecard skips capability noise nouns. Completeness 10.0 is still not Apps Store / go-live. Promote stays human.
**Why:** Operator “QR / click-to-pay on invoice PDF” scored 9.0 with junk form fields and no Option A honesty.
**Rejected:** Treating PDF asks as field packs; Expert closer “fixing” by inventing form chrome; per-edge-case vertical packs; empty path-only `custom_code_blocks` with no installable content.

### 2026-08-20 — Tier-1 allows additive Studio x_* (FLAG PCM)
**Decided:** PCM still blocks write-logic and stock-field mutation on Accounting (`account.move`, payments, payroll, …). Additive custom `x_*` fields + inherit/extension views are allowed — field packs (“SLA due date on invoices”) and stock-first bridges (`x_matter_id`) must Apply live. O2M on tier-1 stays blocked (put the relation on `x_*`). Chatter/activity automations on tier-1 stay allowed; `object_write` / state updates stay blocked. Completeness 10.0 is still not Apps Store / go-live. Promote stays human.
**Why:** Operator Applied a correct field_pack JSON; PCM scrubbed every `account.move` field, Apply returned 200 with skips, invoice form showed nothing.
**Rejected:** Keeping “no fields on tier-1” while claiming Stitch-like inherit-and-wire; inventing `x_invoice` instead of extending Invoicing.
**FLAG vs prior MEMORY (PCM-4):** Tier-1 is no longer “zero fields on the host” — it is “no stock mutation / no write-logic”; Studio-like `x_*` is in scope.

### 2026-08-20 — Field pack: inherit the form, do not clone the menu (FLAG)
**Decided:** Component phrasing without slice keywords (tracker/checklist/register/warranty/inspection/…) is `field_pack`: inherit the named stock host, real fields, extension view, date activity if there is a date. No extra app menu, no dummy groups, no `mail.thread` stamp on stock `account.move`. Scorecard treats inherit `account.move` as covering prompt noun “invoice”; missing-search is for new `x_*` only. Expert closer / zip-promote chrome is full-app, not a 3-field inherit. Completeness 10.0 is still not Apps Store / go-live. Promote stays human.
**Why:** Operator JSON for “Add SLA due date on invoices” was `feature_slice` with a duplicate Accounting “SLA” menu, mixin warnings, and false findings (`noun:invoice`, missing search).
**Rejected:** Inventing `x_invoice`; adding a search-view xml id for `account.move`; Expert closer “fixing” a field pack.
**FLAG vs prior MEMORY:** `feature_slice` is only when the prompt names a tracker/checklist/register/log/warranty/inspection — not every “add X on invoices”.

### 2026-08-19 — Stitch grain: talk at any size, senior inherit-and-wire (FLAG)
**Decided:** Create draft classifies grain first. `field_pack` / `feature_slice` skip the domain-pack seed and implement on a stock host: real inherit fields (never `x_extension_note`), an extension view, a date activity on slices, a companion `x_*` only for checklist/register/log — not a generic tracker and not a clone invoice/employee/event. Hosts include invoices, employees, calendar, CRM, purchase, pickings. Depth floors follow `GRAIN_TARGETS`, not the 5/10-model full-app bar. Residual satellites and stock inherit-bridges do not run on `_component` drafts. Full-app briefs still pack-first; LLM remains Retry AI. Completeness 10.0 is still not Apps Store / go-live. Promote stays human.
**Why:** Operator vision is Stitch-like NL at every grain (field, feature, full app) at senior Odoo-team quality. The component path was a keyword gallery plus a stub field; Create draft always seeded a full app first.
**Rejected:** Keyword-only galleries as the architecture; padding a field-pack to 10 models; inventing a vertical pack per prompt.
**FLAG vs prior MEMORY:** Create draft is pack-only only for `full_app`. Component grains implement immediately without the pack seed.

### 2026-08-19 — Senior Community depth is pack workspace + stock inherit (FLAG)
**Decided:** Three custom models is below the bar a senior Community team would ship. Law-firm Create draft / Retry AI / Expert / Autopilot / Apply all use the same floor: `x_matter` + parties + billable narrative + `x_conflict_check` + `x_matter_document`, with `mode: inherit` on `sale.order` / `account.move` / `calendar.event` / `hr.employee` / `crm.lead` / `project.task` (`x_matter_id` on the stock host). Smart buttons on the matter point at those hosts. Packed depth no longer collapses to “whatever count we already have” (3 no longer passes comprehensive). Autopilot keeps the matched pack floor + inherit; it still drops `x_bill` / `x_attorney` / `x_session` siblings. Unpacked reuse-rich drafts get residual `_party` + `_line` and the same inherit bridges. Inherit hosts are not scored as missing list/form/menu. Promote stays human. Completeness 10.0 is still not Apps Store / go-live.
**Why:** Operator: “3 models seems far too small” after the clone-ERP clip. Senior work is a real matter workspace wired into stock apps, not a skinny 3-model spec and not a 12-model second Accounting/HR.
**Rejected:** Restoring `x_bill` / `x_attorney` / `x_task` / `x_event`; padding unpacked drafts to 10 clone models; treating ModuleSpec 10.0 as go-live.
**FLAG vs prior MEMORY:** Autopilot is no longer residual+line+party only when a pack matches — it installs that pack’s senior floor. Packed depth floor is pack size (at least 5 custom `x_*`), not 3.

### 2026-08-19 — Expert review must merge pack lifecycle then clip (FLAG)
**Decided:** “Ask the Expert to review and fix” restores pack identity, `merge_domain_pack`, then `clip_to_stock_first_floor` before post-critique. Pack-owned selections and `state_field` overwrite a longer LLM list (discovery/trial does not beat intake→open→billed→closed). Scorecard caps overall at 5.0 when three+ staff/accounting clones remain (`x_attorney`, `x_bill`, `x_payment`, …). Expert verdict is never `ready` while those clones remain. Close still does not full-replace with the pack factory (clinic skip-flag tests). Autopilot stays residual-only; Promote stays human.
**Why:** 07:42 Draft Studio showed Expert 10.0→10.0 (ready) on 12 models, farm briefing, and `depends: base,contacts,mail`. Prompt words “attorney/invoice” made clones look coherent; merge kept the longer LLM status list.
**Rejected:** Expanding Autopilot to install the 12-model mini-ERP; treating ModuleSpec 10.0 as Apps Store quality.
**FLAG vs prior MEMORY:** Clip after enrich is not enough if Expert/scorecard still green-wash the dump. Pack lifecycle is the floor for pack models.

### 2026-08-18 — Retry AI enrichment must re-clip stock-first (FLAG)
**Decided:** After quality/depth/critique, `clip_to_stock_first_floor` restamps current `_pack_model_ids` and drops staff/invoice/task/event clones that are not on that floor. Packed enrich skips LLM model-count expand. Critique must not demand 10 custom models. Hotel `x_bill` stays because it is on the hotel pack allowlist. Autopilot stays residual-only; Promote stays human.
**Why:** AOP 20:26 Draft Studio scored 10.0 with 13 models after Retry AI (`llm_full` on a `pack_seed`). Prune kept `x_bill` because the brief said “invoice”. Stale `_pack_model_ids` and farm collocation from “Northern Harvest Ltd” survived enrich.
**Rejected:** Replacing the whole draft with the pack factory (broke closer tests that stamp `domain_pack` as a skip flag); expanding Autopilot to install that mini-ERP.
**FLAG vs prior MEMORY:** Create draft still skips LLM; Retry AI is still the LLM path — that path is now clipped, not trusted.

### 2026-08-18 — Stock-first residual contract is domain-agnostic (FLAG)
**Decided:** Packs are an optional retrieval floor. The strategy for every domain is `ai_stock_first`: reuse stock documents (partner / SO / invoice / employee / calendar / task), custom `x_*` only for the residual the brief names (`Custom residual is the X`), collapse clones (`x_bill`, `x_attorney`, `x_event`, …) when that stock model is in the plan, and do not pad unpacked drafts to 10 models when two+ operational stock apps are reused. Create draft / closer / density / Autopilot planner all attach this plan. `_pack_model_ids` still protects a matched pack's own models (hotel `x_bill` stays).
**Why:** We cannot author a pack for every vertical. A frontier model later still needs the same contract in the reuse plan and teaching prompt, or it will invent a second ERP.
**Rejected:** Adding more vertical packs as the answer; waiting for a frontier LLM before collapsing clones; requiring an operator confirm before forbidding `x_product` when Products is on the instance.
**FLAG vs prior MEMORY:** Create draft is pack-first when a pack matches, not pack-only as the architecture. Inferred stock on a live catalog now forbids parallels without operator confirm. Fee-earner clones collapse to `hr.employee` even without a law-firm pack.

### 2026-08-18 — Law-firm pack is a stock-first matter file (FLAG)
**Decided:** Draft Studio `law_firm` pack is `x_matter` + `x_matter_party` + `x_matter_line` on stock CRM / Sale / Account / HR / Timesheet / Calendar / Project. Lawyer is `hr.employee`. Invoices are `account.move` (link-only). Status is intake → open → billed → closed. Autopilot still clips to packet residual + `_line` + `_party` — it does **not** install a 13-model parallel ERP. Packed drafts do not pad to 10 custom models to hit comprehensive depth. Merge prefers stock relations (`hr.employee`, `account.move`) over `x_attorney` / `x_bill`.
**Why:** Adeyemi 16:18 Draft Studio scored 10.0 with `x_bill`/`x_attorney`/`x_task`, farm briefing leftovers, and a matter workflow of discovery/trial. Senior Community work for this brief is stock quotations/invoices/timesheets plus a real matter file. Completeness 10.0 is still not Apps Store / go-live.
**Rejected:** Shipping gold-spec `x_lf_*` renamed to `x_attorney`/`x_bill` as the floor; expanding Autopilot to apply the full custom mini-ERP; wiping the reused sandbox DB without an explicit operator yes.
**FLAG vs prior MEMORY:** Clip used to keep residual + `_line` only, and merge used to retarget fee-earners to `x_attorney`. `_party` is now a satellite of the matter residual. Fee-earner is `hr.employee` when HR is in depends.

### 2026-08-18 — Create draft is pack-only; LLM is Retry AI enrichment
**Decided:** When `seed_studio_draft` matches a domain pack with models, `ai_draft` returns that scored seed and does **not** start `draft_module_from_prompt`. LLM tailoring is the **Retry AI enrichment** job. Negation-aware matching (`no`/`not`/`never`) applies to collocations, connector needles, and pack regex. Two offices of one company are not multi-company.
**Why:** Adeyemi Draft Studio still hit 1800s, then showed a restaurant briefing (`fryer`/`fa-bed`) because the brief said "not restaurant or hotel" / "kitchen hardware", and Create draft still spent the LLM budget after packing.
**Rejected:** Budgeting 900s of LLM on every Create draft; treating Lagos+Abuja as two `res.company`.

### 2026-08-18 — Draft Studio seeds the pack first; LLM enrich is budgeted
**Decided:** `ai_draft` jobs seed a scored domain-pack ModuleSpec immediately (partial + cache), then run `draft_module_from_prompt` for at most 900s. Timeout or LLM failure keeps the pack seed as a succeeded job. Wizard polls with `untilTerminal`.
**Why:** Law-firm Draft Studio hit `Job exceeded 1800s limit` with no JSON — the staged `qwen3:8b` pipeline does not finish a full app in 30 minutes.
**Rejected:** Only raising `ai_draft` to 2700s; leaving the wizard on a 35-minute poll that returned empty on timeout.
**Decided:** `ai_draft` jobs seed a scored domain-pack ModuleSpec immediately (partial + cache), then run `draft_module_from_prompt` for at most 900s. Timeout or LLM failure keeps the pack seed as a succeeded job. Wizard polls with `untilTerminal`.
**Why:** Law-firm Draft Studio hit `Job exceeded 1800s limit` with no JSON — the staged `qwen3:8b` pipeline does not finish a full app in 30 minutes.
**Rejected:** Only raising `ai_draft` to 2700s; leaving the wizard on a 35-minute poll that returned empty on timeout.

### 2026-08-18 — Autopilot clips Expert output back to packet residuals
**Decided:** After Expert-fix, drop any model that is not a packet residual or `{residual}_line`. Data-load with no client files scores 7, not 10. Connector “ok” findings state sandbox fixtures, not live APIs. Bare `marketplace` / `stock` / `delivery` do not infer inbound or Inventory.
**Why:** A green law-firm Autopilot zip still contained `x_session` / `x_equipment`; scorecard 8.5 / data 10.0 / inbound_orders overclaimed the job.
**Rejected:** Treating Expert-fix 8.41 as permission to re-inject the full pack; scoring empty ingest as 10.

### 2026-08-18 — Autopilot residual is pack/skeleton seed, never full-app LLM
**Decided:** Custom residual applies a filtered domain-pack spec (packet models + `_line` only) or a workflow skeleton, then deterministic Expert closer. `draft_module_from_prompt` is not on this path. The Job page uses `untilTerminal` polling — it does not abort on a quiet `step_label`.
**Why:** Job `dc1dbeb9` sat on `custom` for 25+ min generating a full ModuleSpec from the law-firm brief; the UI then toasted "stalled after 500 polls" while the worker was still running.
**Rejected:** Raising staleAttempts again; wiring progress into the 7-step LLM pipeline so Autopilot can keep drafting a parallel app.

### 2026-08-18 — Smoke retry never re-runs Expert; poll follows stages
**Decided:** After first smoke, retries (max 2) re-apply the existing ModuleSpec with `skip_expert=True` or just re-run smoke. Job-runner timeout uses `shutdown(wait=False)` so status flips at the cap. Job page polls 60 min and only treats a stage as hung after 25 min with no `step_label` change.
**Why:** Law-firm job `8c05af59` hit smoke then burned the 30 min cap on five Expert-fix retries; the UI stopped at 600 polls while status was still `running`.
**Rejected:** Raising only the UI poll count; re-bootstrapping stock on every smoke fail.

### 2026-08-18 — Autopilot: no --reload, one job, zip off poll
**Decided:** Run uvicorn without `--reload` during Autopilot. A second Run on the same connection attaches to the in-flight job. Residual `zip_base64` is stored under `.cache/job_autopilot/` and fetched from `GET /api/jobs/{id}/artifact` after success — poll JSON stays small.
**Why:** Operator toast `read ECONNRESET` after Autopilot queued; the worker died mid-poll (reload + two concurrent jobs + large result JSON).
**Rejected:** Raising Next poll timeout as the fix; keeping zip in every `GET /jobs` payload.

### 2026-08-17 — Next API proxy uses node:http for long jobs
**Decided:** Job Autopilot / Expert / ingest proxy waits on `node:http` (660s socket timeout). Global `fetch` keeps an undici headersTimeout that fires around 5 minutes with `fetch failed` while uvicorn is still running the job.
**Why:** Operator Run on a live API showed Plan 200 and `/health` ok; Run toasted `Cannot reach API at http://127.0.0.1:8001: fetch failed`.
**Rejected:** Restarting uvicorn as the fix; streaming Autopilot (larger change).

### 2026-08-17 — Domain-agnostic connector lanes (not vertical x_*)
**Decided:** Autopilot takes any brief as far as stock + five ordered connector recipes: payments → inbound orders → messaging → hardware → statutory payroll. Lanes match brand/capability needles, not industry. Payments probe/create `payment.provider` (disabled, no keys). Inbound/messaging land a fixture on stock `sale.order`. Hardware installs Community POS/IoT when on the addons path. Statutory is a golden-file compute (NG first) and never writes `hr.payslip`. Connector gaps are scorecard findings; they do not zero process smoke. Secrets use `AUTOPILOT_PAYMENT_SECRET` / `AUTOPILOT_WEBHOOK_TOKEN`, never app-billing `PAYSTACK_SECRET_KEY`, never `ir.config_parameter`.
**Why:** Furthest implementation for a restaurant, clinic, law firm, or factory is the same five lanes — not a Chowdeck model or a KDS `x_*`.
**Rejected:** Vertical-specific connector models; live partner API calls from Autopilot; generating `payment.transaction` / `hr.payslip`.

### 2026-08-17 — Restaurant briefs are POS+MRP, not hotel x_stay
**Decided:** Vertical match is scored by evidence, not catalog order. Hotel pattern ignores "Hotel Occupancy" tax and attendance/POS check-in. Stay residual requires hotel stay / room reservation / PMS check-in. Restaurant + lounge + recipes → stock `point_of_sale` + `mrp`, no custom residual. Packet warns that Chowdeck/Glovo/WhatsApp/Paystack are not Autopilot x_* models.
**Why:** Nigerian restaurant brief was classified Hotel / Lodging because of occupancy tax + biometric check-in; Autopilot applied x_stay, smoke failed "model missing", overall 0.0.
**Rejected:** Inventing a stay document for F&B; treating delivery APIs as ModuleSpec residual.

### 2026-08-17 — Country/currency before Accounting; NG uses l10n_ng
**Decided:** Bootstrap writes company country + currency **before** installing sale/account/l10n. Nigeria packet installs `l10n_ng` (official Community pack), not `l10n_generic_coa`. Apps list is refreshed before skip. `detect_l10n` still requires `l10n_ng*` after country=NG. Gate `init-db.sh -i sale` loads US CoA and permanently blocks a later NGN write — Autopilot DBs use `SKIP_GATE_MODULES=1 ./docker/init-db.sh`. Production readiness checklist is collapsed on local sandbox Overview; it does not gate Autopilot.
**Why:** Operator reran on `odoo_dev` with USD journal items; planner asked for a module that was not on the instance; Overview checklist fails (admin/health/backup) looked like Autopilot blockers.
**Rejected:** Converting existing USD moves; treating TRUST-8 checklist as the Autopilot done bar.

### 2026-08-17 — Country implies ISO currency; activate then write
**Decided:** Packet currency comes from brief keywords, else `COUNTRY_CURRENCY` (NG→NGN, KE→KES, …). Bootstrap searches `res.currency` with `active_test=False`, writes `active=True`, then writes `res.company.currency_id` **separately** from `country_id`. Pricelist follows `report.currency_id`. If Odoo refuses the company write (journals/moves exist), warn: use a fresh DB. Job page lists bootstrap skipped/warnings. Open sandbox prefers `account.move` form of the smoke invoice.
**Why:** Nigeria run wrote only `country_id`; NGN was inactive so search missed it; invoices stayed USD. Open sandbox was `{url}/web` for stock-only jobs.
**Rejected:** Treating country label as fiscal change; converting existing USD moves; inventing CoA rebuild over RPC.

### 2026-08-17 — Implementation-job scorecard ≠ ModuleSpec 10.0
**Decided:** Autopilot attaches a four-dimension job scorecard (stack_fit, stock_coverage, data_load, process_smoke); overall is the min. Smoke fail is never go-live. Done-bar is partner → product (invoice_policy=order) → SO+line → `action_confirm` → `sale.advance.payment.inv.create_invoices`, plus custom Confirm `ir.actions.server.run` (not `x_status` write). Client-doc index is per-connection Jaccard, not pack RAG. Stock recipes v1 cover CoA/journals/locations/UoM/pricelist/users. Expert-fix + module zip sit in the residual path. Promote-to is a human confirm onto another connection; production Autopilot stays refused; no prod DB clone.
**Why:** Skeleton Autopilot created empty SOs and wrote status fields — that is not the client process. Private `_create_invoices` is not RPC-legal on 19.
**Rejected:** Treating validators-green 10.0 as Autopilot done; auto-promote; walkthrough seed when client files exist; LLM `ir.config_parameter`.

### 2026-08-17 — Job Autopilot: stock-first sandbox, Promote stays human
**Decided:** Unattended delivery is **sandbox Job Autopilot** (NL + documents → stock install/config → custom residual only → ingest dry-run → sandbox auto-commit → RPC process smoke). **Promote to prod stays a human confirm.** ModuleSpec scorecard 10.0 is completeness, not go-live. Stock Odoo apps are preferred; custom `x_*` models are residual only. Autopilot **refuses** `write_mode=production` (clone a sandbox). Frontier LLM may plan the packet; install/config/apply/import stay deterministic RPC.
**Why:** A frontier model cannot close missing stock-bootstrap RPC. Zero-human prod writes contradict sandbox-before-prod and destroy books/stock/ACL.
**Rejected:** Auto-promote to customer prod; treating validators-green 10.0 as an implementation job done; generating a full custom app when `sale`/`account`/`stock`/`hr` cover the brief.

### 2026-08-16 — Apply unlinks leftover automations with invalid filter_domain
**Decided:** Apply always scrubs live `base.automation` on `x_*` models whose `filter_domain` / `filter_pre_domain` is not eval-able (infix strings like `['x_rate_unit in ('hour','day')']`). Unlink; if unlink fails, write `[]` + `active=False`. Spec rows with that shape are not re-created.
**Why:** Confirm’s object_write succeeded, then `base.automation.write` safe_eval’d a leftover domain from an earlier apply (rate-unit fold). SyntaxError on every status write.
**Rejected:** Leaving inactive automations with the broken domain (Odoo may still eval them); live-applying Python compute autos (Option A).

### 2026-08-16 — Live workflow buttons are type=action object_write
**Decided:** Apply rewrites form header `type="object"` + `data-transition-to` into `type="action"` bound to `ir.actions.server` (`object_write` on the status field). Draft JSON keeps the marker. Odoo 16 skips (no update_path).
**Why:** Walkthrough Engagement Confirm/Cancel did nothing — custom `x_*` models have no Python methods. MEMORY already required action-id buttons; generation still emitted `type=object`.
**Rejected:** Live-applying Python `action_confirm` (Option A); treating statusbar clicks as enough.

### 2026-08-16 — Walkthrough seed fills live required fields
**Decided:** `seed_walkthrough` merges spec fields with live `ir.model.fields` (`required=True`), fills leftover scalars/selections/M2Os, always sets in-spec parent M2Os when the parent exists, and skips a child when a required `x_*` parent was not created. Idempotent by `Walkthrough {label}` name.
**Why:** Music Apply succeeded, then Load demo walkthrough Faulted `x_rate_hour` / `x_rate` / `x_session_type` / `x_code` / `x_revision_number` / `x_type` / `x_booking_id` — columns still required on the sandbox, absent or not-required in the 10.0 JSON.
**Rejected:** Treating 10.0 as “live schema matches spec”; dropping leftover required columns from Odoo in the seeder (schema cleanup is Apply/closer, not seed).

### 2026-08-16 — Walkthrough seed + xml-id rewrite after fold
**Decided:** `_rewrite_model_ident` also rewrites `rule_`/`action_`/`menu_`/`view_` prefixes (`rule_x_foo_multi_company`) without touching a longer `*_line` model. Lined cost/job headers drop `required` on scalar `x_rate`. After Apply, **Load demo walkthrough** (confirm phrase) creates a linked Walkthrough spine and retargets Open app to the job/booking form.
**Why:** Folded `x_equipment_usage` left `rule_x_equipment_usage_multi_company`; header `x_rate` blocked lined creates; Open app showed empty O2Ms.
**Rejected:** Merging two lined cost documents; live RPC-only tests for the seeder (fake client); skipping confirm on data writes.

### 2026-08-16 — Leftover closer + Open app in Odoo
**Decided:** Closer now (1) folds a `*_unit`/`*_uom` register with no `*_line` child into a rate/fee card that already stores UOM as a selection, (2) drops a second selection with the same keys (keep `x_rate_unit`/`x_uom`, drop `x_rate_type`), (3) strips `x_last_interaction` from party registers, (4) drops write-triggered next_activity whose only filter is `x_status = done`, (5) never copies `required` onto folded extras and relaxes usage dates on asset lines. Apply uses `spec.menus` (Operations / Inventory / People), hides `*_line` menus, unlinks old flat root children, and returns `root_menu_id` so the wizard **Open app in Odoo** deep-link works.
**Why:** Expert-fix 20:03 still left two pricing registers and a duplicate UOM selection; Generate UI flattened every `x_*` model as a root child, so the operator had to pick models one by one.
**Rejected:** Merging two *lined* cost/rate documents; a music pack; live-applying Python (Option A). This **narrows** the earlier “do not merge rate models” note: a unit *register* beside a card that already has a UOM selection is a duplicate, not a second lined price list.

### 2026-08-16 — Expert-fix button stays visible at 10.0
**Decided:** Wizard always shows **Ask the Expert to review and fix** under the scorecard. Score ≥ 9 only gates the elite zip/promote row. Closer also (1) folds `{asset}_usage` into `{asset}_line`, (2) expands a 1-option briefing selection whose label is another key, (3) drops parent M2O when the parent already O2Ms a child register (`role`/`type`/…). Chat remains **Ask Expert about draft**.
**Why:** A 10.0 Music regenerate hid the closer. Operator only saw chat + Saved snapshots, created a new draft, and still had two equipment-usage models, `[('hourly','session')]` rate cards, and artist↔party_role circular FKs.
**Rejected:** Treating 10.0 as skip-closer; a music pack; merging two lined cost documents.


**Decided:** After demoting a register, drop search filters whose `domain`/`group_by` names a missing field. Restore `group_x_company_id` onto `x_company_id` after company-field sync — do not remap onto a random parent M2O. Dedupe identical record rules. Live-apply contract flags leftover search domains so 10.0 cannot hide them.
**Why:** Music Expert-fix 7.0→10.0 was real, but `x_rate_unit.search` still filtered on `x_status` after the model lost that field. Company group_bys had been rewritten to `x_booking_id`.
**Rejected:** Treating validators-green 10.0 as Apply-ready; remapping missing group_by onto the first remaining x_* M2O.

### 2026-08-16 — Expert-fix must persist the closer draft
**Decided:** Expert “review and fix” (1) runs `close_odoo_architecture` first and rebuilds findings from the after-scorecard, (2) skips LLM narratives when `apply_fixes=True`, (3) writes the fixed JSON to `ai_draft_cache`, (4) trims extra usage-line parents and collapses two M2Os that point at the same parent (`x_inventory_count_id` + `x_count_id`). Wizard Saved drafts is labeled **Saved snapshots**; clicking a row is restore-only, not Expert.
**Why:** The Note “Restored cached draft” is `restoreDraftFromCache`, not Expert-fix. Expert-fix also never saved, so the list kept the 7.0 snapshot. Duplicate-parent findings were not marked deterministic, so the closer looked like a no-op.
**Rejected:** Treating a snapshot click as Expert success; widening the validator to allow three usage-line parents; LLM narratives on the apply path.

### 2026-08-16 — Live UI apply: related hop, usage-line parents, mail_post
**Decided:** `close_odoo_architecture` (1) keeps catalog+booking on `{asset}_line` and drops extra in-spec parents (`x_rate_card_id`), (2) retargets pruned `x_crew_line` onto the booking, (3) demotes `x_rate_unit` as a register and drops self-M2O/O2M, (4) repairs search `group_by` to a real field, (5) drops `mail_post` and Python-shaped `object_write`. Apply ranks related after the hop (related `x_currency_id` is not a currency companion). Stamp restamps `_meta.smart_button_count`. Scorecard still caps at 7.0 while consistency finds a third line parent.
**Why:** Expert-fix was a no-op: post-critique re-linked equipment usage lines to rate card (three parents → 7.0 cap). Live apply Faulted `Unknown field name "x_rate_unit_id" in related field`, `x_equipment_ids` on engagement, booking-line search `group_by` of `x_equipment_id`, and skipped `mail_post`.
**Rejected:** A music pack; allowing three parents on a usage line; live-applying `mail_post` or Python computes.

### 2026-08-16 — Live UI apply: currency, inverse O2M, no stock O2M
**Decided:** `close_odoo_architecture` + `stamp_live_apply_contract` (1) put `x_currency_id` on the model *before* monetary fields, (2) drop one2many onto stock (`hr.employee` / `res.partner` / …) instead of retargeting pruned crew/currency clones as O2M, (3) drop identity `object_write` and `%(` mail_post autos, (4) prune leftover `*_specialty` catalogs when the site already has `x_specialty` selection, (5) treat catalog+booking parents on `{asset}_line` as one usage line (not a consistency error). Apply still ranks currency→scalars→monetary then ensures custom inverses / skips stock O2M. Python computes stay Option A.
**Why:** Open ModuleSpec Faulted `Unknown field “x_currency_id” in currency_field`, `Many2one x_booking_id on x_equipment_line does not exist`, and `Many2one x_rate_unit_id on hr.employee does not exist`.
**Rejected:** A music pack; merging rate models; live-applying Python computes; treating the recovered 7.0 JSON as Apply-ready.

### 2026-08-16 — Cloud LLMs via API key (Claude / OpenAI / Gemini)
**Decided:** `AI_ASSIST=auto|openai|claude|gemini` plus the matching key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`). `auto` picks Anthropic → OpenAI → Gemini → openai-compatible. It does **not** fall back to Ollama. Ollama stays `AI_ASSIST=ollama`. Cloud mode ignores leftover `qwen3:8b` bulk/reasoning names. Status never returns keys.
**Why:** Frontier models should plug in with env config only; the draft pipeline already talks to `LLMProvider`.
**Rejected:** New vendor SDKs; treating cloud LLM as a replacement for `close_odoo_architecture`; auto-starting Ollama when no key is set.

### 2026-08-16 — Live-apply contract is a generation requirement
**Decided:** Every finished ModuleSpec is stamped by `attach_live_apply_contract` (close + apply-readiness): canonical triggers, `trg_date_field_name` on `on_time`, `mail.activity.mixin` + To Do xml_id on `next_activity`, drop unapplyable autos. Scorecard hygiene flags gaps until stamp runs. Wizard blocks Apply when `_live_apply.ready` is false. Apply stays defensive (infer date, enable mixins, long timeout).
**Why:** Validators-green 10.0 still skipped `on_time` and Faulted `next_activity`. First-try apply is a finisher contract, not an LLM promise.
**Rejected:** Prompting the LLM harder; a music/vertical pack; live-applying Python computes; treating scorecard 10.0 as Apps Store quality.

### 2026-08-16 — Live UI apply: on_time date + next_activity mixin
**Decided:** Apply infers `trg_date_field_name` from the automation row, `filter_domain` date tokens, spec date fields, then `create_date`. `create_automation` enables mail mixins before encoding `next_activity`, prefers generic To Do (skips types bound to another model), and retries `user_type=specific` + connected uid if Odoo raises child-action warnings. Generated overdue autos now stamp the date field too.
**Why:** Second apply landed menus/ACL (17 menus, 32 access) then skipped `Follow up deadline Engagement` (`needs trg_date_field_name`) and Faulted `Notify on Project … completed` (`Following child actions have warnings: … / activity`) because `is_mail_activity` was off.
**Rejected:** Live-applying Python computes/tests/i18n (Option A); treating 0 models created on re-apply as a spec bug.

### 2026-08-16 — Live UI apply: Odoo 19 group_ids, ACL xml_ids, apply timeout
**Decided:** `spec_apply_ui` probes `ir.ui.menu.group_ids` (19) vs `groups_id` (17/18) before writing. Draft ACL groups (`group_{tech}_user`) are resolved/created by name, not `resolve_xml_id` (which requires `module.name`). `next_activity` without `activity_type_id` uses mail's To Do type. Next.js proxy + `applyModuleSpec` use the long (660s) budget for all `module-spec` routes — the first apply of a full app exceeds the old 12s default.
**Why:** Generate UI from JSON created views then warned: `Invalid field 'groups_id' in 'ir.ui.menu'`, unresolved `group_music_…_user` xml_ids, skipped `next_activity`, and a first-attempt Timeout. Retry showed 0 models / 64 views updated (models already existed).
**Rejected:** Hard-coding 19-only `group_ids`; treating Python compute blocks as live-applied (Option A still requires sandbox module install).

### 2026-08-14 — Closer: foreign role FKs, hollow cost, completed→done
**Decided:** `close_odoo_architecture` (any domain; skip pack for hollow-cost collapse) (1) drops foreign *role* FKs whose leaf is attorney/solicitor/barrister/paralegal unless the prompt is law-like, (2) folds selection terminals `completed`/`complete` → `done` and remaps automations/`state_field`, (3) collapses a *hollow* cost header (no `*_line` child) into the lined cost document — two lined cost documents stay two documents, (4) strips corrupt field labels matching `},{`, (5) creates `{asset}_line` when an equipment catalog and a booking/session exist, (6) humanizes leftover “Recording Site” labels to the site noun, (7) retargets staff/crew `res.users` → `hr.employee` when HR is in the stack, (8) demotes line-model chatter/kanban/sequences and `X … Line` O2Ms to “Lines”. Identifier rewrites are token-bounded so `x_job_cost` does not mangle `x_job_cost_expense`. Scorecard flags the same gaps until close runs.
**Why:** Completeness 10.0 still shipped `x_attorney_id` → `res.users`, a critique-added hollow `x_job_cost` beside lined `x_job_cost_expense`, `completed`+`done` on one status, `Duration (Hours)},{`, and no equipment usage line.
**Rejected:** Music (or any) domain pack; merging two *lined* cost documents; treating 10.0 validators-green as Apply-ready.

### 2026-08-14 — Scrub leftover x_site / x_party draft warnings after rename
**Decided:** `filter_stale_enrich_warnings` rewrites generic leftover model ids (`x_site`/`x_party`/`x_booking_document`) to the live prompt-noun model, and drops rules/density notes whose generic id was pruned. Closer notes that say `pruned` / `in favor of` stay. The main draft path (`_finalize_draft_generation`) and Expert-fix now run this filter after close; `review_notes` on the draft are scrubbed in `close_odoo_architecture`.
**Why:** After `x_site` → `x_studio`, the wizard still listed `rules:` / `density:` lines naming models that no longer exist. The draft-from-prompt path never called the stale-warning filter.
**Rejected:** Dropping every warning that mentions a missing `x_*` (that deleted `x_code` field notes); a music pack.

### 2026-08-14 — Closer: job-header children, one line model, agreement parties
**Decided:** `close_odoo_architecture` (any domain, skip pack for line-collapse/agreement rewrite) (1) adds the keeper job-header FK on deliverable/output, cost/expense, and agreement when missing, (2) collapses two `*_line` children of the same parent into `{parent}_line`, (3) on agreement/contract: at most one M2O to a party register; the other becomes `res.partner` Client, (4) `res.company` fields are labeled Company not the site noun, (5) asset usage lines also M2O the booking/session, (6) `product.product` adds `product` to depends, (7) workflow default is an initial state (`draft`/`new`), (8) unavailability/blackout/downtime/outage are registers not documents, (9) party registers drop CRM `last_interaction` and sellable rate fields when a rate card exists, (10) `purchase.order` is dropped from booking/session. Scorecard flags missing job-header FKs, duplicate line models, and product-without-depend until close runs.
**Why:** Completeness 10.0 still shipped deliverable/cost hanging off the site, two rate-line models, artist↔artist agreements, Studio-labeled `res.company`, and `product.product` with no `product` depend.
**Rejected:** Music (or any) domain pack; merging `x_expense` into `x_job_cost` (they share the job header, they stay two documents).

### 2026-08-14 — Closer: one job header, canonical selections, no fake automations
**Decided:** `close_odoo_architecture` (any domain) (1) collapses parallel job-header models whose *exact leaf* is engagement/project/matter/case/stay/job into one keeper (prompt hit, else inbound FKs, else preference; law-like prompts keep `matter`; skip when a domain pack is set or the prompt names two of those leaves that both exist), (2) snake-cases selection keys, folds `Draft`/`draft`, unswaps antonym value/label pairs (`active`/`inactive`), remaps defaults and `state_field`, (3) drops automations whose filter is a 3-atom list, whose `safe_actions` name missing fields, or whose `value` looks like a Python call, (4) demotes `is_workflow` when there is no status selection. Scorecard flags the same gaps until close runs. Deliverable/revision still uses density `_OUTPUT_TOKENS`, not a music fallback list.
**Why:** Completeness 10.0 still shipped two ops headers, broken agreement/unavailability selections, hollow `calculate_rate(...)` automations, and `x_job_cost` as a workflow with no status.
**Rejected:** Music (or any) domain pack; merging `x_expense` into `x_job_cost` (different documents); treating Title Case keys as valid Odoo selections.

### 2026-08-14 — Booking→engagement, revision→deliverable, session sale.order is link-only
**Decided:** `close_odoo_architecture` adds `x_engagement_id` on booking/session when an engagement/project exists, adds `x_deliverable_id` on revision/take when a deliverable exists, and stamps any `sale.order` M2O on session/booking as link-only (help + reuse `link_only`, no posting). Scorecard flags the same gaps so Expert sees them until close runs.
**Why:** Studio time belongs on the project; a revision is a version of a deliverable; a session is not a quotation.
**Rejected:** Treating session as `sale.order`; inventing a parallel `x_sale`; a music pack.

### 2026-08-14 — Close must rewrite foreign FKs, typed asset FKs, and staffing
**Decided:** `close_odoo_architecture` rewrites foreign-lexicon FKs (`x_matter_id` → `x_engagement_id` unless the prompt is law), collapses exploded type FKs (`x_console_id`/`x_microphone_id`/…) when a line model exists, prunes `x_staffing` as a crew clone (`hr.employee`), adds missing O2M inverses, strips invalid `selection` on non-selection fields, repairs kanban `default_group_by` to a real field, drops automations that name missing fields/status keys, and emits header totals from line subtotals. Placeholder Option A/B type selections are rewritten from the domain briefing on any type field, not only equipment models.
**Why:** The 17:23 music draft scored 9.5 with validators green and still leaked law-firm `matter`, six typed equipment FKs, a parallel staffing roster, a kanban grouped by missing `x_status`, and `x_job_cost` totals that were not computed.
**Rejected:** Music domain pack; treating 9.5 completeness as Apply-ready.

### 2026-08-14 — Architecture close must finish ACL, names, and menus
**Decided:** `close_odoo_architecture` (draft + Expert) is the last word for: rename generic `x_site`/`x_party` to prompt nouns (`x_studio`/`x_artist`), emit ACL for late models, attach orphan `*_line` parents (or drop them), hide line/ghost menus *after* `ensure_default_ui`, whole-word sequence prefixes (`ENGAGEMENT/` not `ENGA/`), `state_field` on remaining workflows. `ensure_workflow_transitions_on_draft` must not re-promote registers or line models. Install & reuse is unchanged — it only appears when the suggested module is not installed; already-installed sale/hr/account are auto-wired link-only.
**Why:** Live music draft scored 7.1 with validators green while Structure was 3.4 (missing ACL, orphan lines, `x_site` not studio, ghost Deposit/Crew menus). Expert could not repair what the closer never ran.
**Rejected:** Music domain pack; treating 7.1 completeness as Apps Store ready; removing the reuse catalog picker.

### 2026-08-14 — Staged Ollama timeout must not fail the job
**Decided:** Default pipeline is staged. If Ollama times out on an unpacked prompt (no pack), seed a draft from the prompt and finish with density/app-bar (`llm_partial`). Per-entity field timeouts skip that entity instead of aborting. Wizard banner: timed-out steps finished from the prompt, retry enrichment.
**Why:** Music (and any novel domain) has no pack fallback; `AiAssistUnavailable: Ollama request timed out` killed the job and showed Diagnose with Expert.
**Rejected:** Raising 503 on timeout; requiring a music pack; treating timeout as a hard transport failure.

### 2026-08-14 — Domain briefing is vocabulary, not a pack
**Decided:** Per-prompt `DomainBriefing` (collocation table ~12 confusion pairs) injects industry language into LLM entity/field/deepen prompts, rewrites foreign `x_type` / rate UOMs, and bans false-friend stock (`mrp.production` unless manufacturing collocates). Catalog scoring skips weak tokens (`production`, `company`, `business`, …) and MRP intent no longer treats bare `production` as manufacturing. Expert setup-stack inference uses the same rule (no `production` → `mrp`; briefing drops banned apps). Scorecard flags banned selection keys and banned catalog suggestions. Density seeds equipment `x_type` from the briefing.
**Why:** Music recording drafts used film camera/lens types and pulled `mrp.production` because the prompt said “production”. Depth must come from this request’s words, not a frozen ModuleSpec.
**Rejected:** Music (or any new) domain pack; 50 vertical packs; treating `production` as MRP.

### 2026-08-14 — Architecture close pass is the last word (draft + Expert)
**Decided:** After critique/elite, `close_odoo_architecture` always runs: named-FK repair (`x_studio_id` → `x_studio`), site FKs on booking/session, drop stock clones (`x_currency`/`x_payment`/`x_crew`/orphan `x_line_item`), demote register workflows, regroup Engagements/Agreements into Operations. Expert "review and fix" re-runs `run_odoo_app_bar_pass` + that close pass (not just post-critique). `apply_pattern_rules` / `ensure_workflow_models_have_state_field` must not re-promote registers. Sequence prefixes like `ENGAGEMENT/` are not UX defects. Packs keep curated `x_payment`.
**Why:** Live music draft scored 8.9 with validators green while session.studio pointed at equipment, studio had Confirm/Done, and Expert could not repair domain-fit FKs.
**Rejected:** Music domain pack; treating Expert as a cited commentary-only reviewer.


**Decided:** Non-thin business prompts (≥6 words) classify as **comprehensive**. LLM cap `max_entities_staged=22`. Depth-gap floor stays 10 so curated packs still clear `depth_models`. After generic-loop prune, `ensure_domain_density` fills unpacked drafts to ~16 domain-named roles (site, party, engagement, booking+lines, deliverable, equipment, rate, agreement, unavailability, revision, expense, maintenance). Crew = `hr.employee`; invoices = `account.move`. Root menu gets `web_icon` (`fa-music,#714B67` from prompt tokens). **Flag:** 2026-08-13 still holds that the bare word `multiple` is not a scale cue — the change is the product bar (real business prompts are full apps), not treating `multiple` as comprehensive by itself.
**Why:** 4–6 models after prune is a Studio stub, not an Apps Store vertical. Users need as many *domain-relevant* models as possible with UI/ACLs/smart buttons — not generic deposit/task/bill filler.
**Rejected:** Music domain pack; bringing back party_link/deposit/parallel x_bill/generic task; calling density from `seed_operational_loop` (`source=depth_seed` must stay seed-only).

### 2026-08-14 — Scorecard scores architecture, not XML completeness
**Decided:** A 9.6/10 with all validators green is not Apps Store ready. Score **domain architecture** (generic ops-loop models, wrong `x_*_id` targets, hollow automations, core menus under Other, parallel `x_bill`+`account.move`). Pack-free prune drops deposit/task/bill/party_link/staff/fee unless the prompt asked for them (job-cost `x_expense` is kept); `x_studio_id` must target `x_studio`; sessions/bookings are document headers with lines; `artiste` covers `x_artist`.
**Why:** Music-studio finished draft was structurally complete and still a second CRM/billing/task app with Sessions parked in Other and `x_session.x_studio_id` → `res.partner`.
**Rejected:** Adding a music domain pack; treating validator-green 10.0 UX as senior Odoo quality.

### 2026-08-13 — Wizard must not present pre-finisher JSON as the app
**Decided:** Tag async partials `_generation_incomplete`; wizard banners + blocks Apply/ELITE until `_scorecard` / `_odoo_app_bar`. Bare prompt word `multiple` is not a scale keyword (see 2026-08-14: business prompts are comprehensive because they are full apps, not because they say `multiple`). App bar drops phantom `x_` relations and demotes studio/artist/staff/client/equipment registers even when the LLM stamped draft/open/done.
**Why:** Music-studio live draft was staged LLM output (18 generic models, X-prefixed menus, no chatter) shown as finished because the wizard `setAiDraft(partial)`.
**Rejected:** Adding a music domain pack; treating “too few smart buttons” as the main defect.

### 2026-08-13 — Odoo Apps senior bar is document-shape, not vertical
**Decided:** Raise every draft via `run_odoo_app_bar_pass` (lines, chatter, short menus, depends→stock links, lifecycle automations). Classify headers as sales / operations / procurement by *document shape*: bare `order` is not sales (`work_order` / `*_job` / tickets may MRO-link `purchase.order`; `x_store_order` / `x_sales_order` must not). Trust curated **regex** pack hits; Jaccard/ambiguity gates apply only to Jaccard/embedding retrieval. When `domain_pack` is already set, load that pack by id (do not re-match a short prompt).
**Why:** Senior Community apps look like Odoo Apps Store modules in any industry. Jaccard on short prompts (~0.03) rejected hospital/car-rental regex hits; treating every `*order*` as sales stripped legitimate PO links on work orders.
**Rejected:** Per-vertical marker lists; requiring procurement-only for `x_purchase_order_id`; Jaccard floor on regex matches.

### 2026-08-03 — REM-1: staged pipeline guard + step wiring
**Decided:** Define `guard = guardrail_prompt(manifest)` at top of `run_staged_pipeline`;
pass `protected_manifest`/`odoo_version` from `draft_module_from_prompt`; step3/5 use
`reasoning=True`, `STEP_TEMPERATURES`, `append_prompt_blocks`, `FORMAT_SCHEMA_RELATIONSHIPS`
on step3; dedupe duplicate `_PACK_FACTORIES` block; `test_ai_staged_pipeline.py` with
RecordingProvider executes all steps.
**Why:** NameError crashed staged LLM path; AI-1/2 temps/reasoning were missing on steps 3/5.
**Rejected:** Mocking step functions in the gate test (RecordingProvider calls real step code).

**Decided:** `AUTH_MODE=accounts` with cookie-first sessions (`oc_session`), argon2id passwords,
server-side session records, workspace scoping on connections/projects; API key fallback in
accounts mode for CI; OAuth deferred [SKIPPED].
**Why:** Self-hosted SaaS without paid auth vendor; preserves `off`/`api_key` for local gates.
**Rejected:** JWT-first SPA auth (cookie simpler for same-origin Next.js); OAuth in v1 (time-box).

### 2026-08-03 — PROD-2: Alembic migration policy
**Decided:** Adopt Alembic for app metadata DB; `init_db()` uses `create_all` only when
`DB_MIGRATIONS=off` (tests/local); deploy profile sets `DB_MIGRATIONS=auto` →
`alembic upgrade head` on startup.
**Why:** MON-1/2 will add ALTERs; drift test gates model/revision parity.
**Rejected:** Breaking test fixtures that rely on create-all (kept via off mode).

### 2026-08-03 — PROD-3: Job runner v1
**Decided:** Keep in-process `ThreadPoolExecutor` with `JobRunner` protocol seam;
`mark_interrupted_jobs_on_boot`, per-kind timeouts, concurrent cap, sandbox cancel hook.
**Why:** Solo single-instance deploy; arq/Redis deferred until multi-instance need.
**Rejected:** Adding Redis/arq now (stack lock + no paying users).

### 2026-08-02 — PCM-4: enforcement beyond AI + UI badges
**Decided:** Shared `protected_enforcement.py` gates Builder, ModuleSpec apply
(`scrub_spec_for_protected_apply` → per-item skips), and Automations (chatter/activity
allowed on tier-1). 422 detail includes `reason`, `safe_alternative`, `docs`. Power Ops
account-move recipes get `protected_tier_note` and remain EXEMPT (Doc 7 batching). UI
badges from `GET /protected-modules` on hub/builder/automations.
**Why:** PCM-3 only covers AI path; direct API mutations must enforce the same effect rule.
**Rejected:** Blocking Power Ops account recipes; hard-failing ModuleSpec apply on one
violation; blocking link-only M2O from custom models into tier-1.

### 2026-08-02 — PCM-3: guardrail injection + structured refusal
**Decided:** Inject `guardrail_prompt(manifest)` into single-shot system/user prompts,
staged steps 2/3/5, and critique; resolve manifest from connection cache else vendored
community snapshot. Deterministic `strip_protected_module_effects` in `ai_rules.py` is
enforcement (strips tier-1 writes; keeps link-only M2O/O2M). API returns `refusals[]`;
wizard shows Protected module panel. Transcript: `docs/research/guardrail_run_2026-08-02.json`.
**Why:** Doc 5 — LLM prompt is first line only; effect-not-mechanism must be enforced.
**Rejected:** Relying on LLM alone; blocking link-only relations to protected models.

### 2026-08-02 — PCM-2: protected manifest Path A+B + per-connection cache
**Decided:** `fetch_community_modules_from_source` (git sparse-checkout → vendored JSON
fallback); `fetch_live_installed_module_names` via existing `client.list_modules`; merged
manifest cached on `odoo_connections.protected_manifest_json`, refreshed on create/probe;
endpoint `GET …/protected-modules`.
**Why:** PCM-1 classification needs version-aware module inventory without GitHub REST API.
**Rejected:** Blocking probe on network failure; 16–18 offline snapshots seeded from real 19.0
git list until per-branch snapshots refreshed.

### 2026-08-02 — SAFE-2c: pre-merge core scaffold seed eliminates generation gaps
**Decided:** After `llm_emit_missing_scaffold_models`, run `seed_missing_core_scaffold_models`
(attorney/bill/compliance/deposit/trust…) from pack scaffold before `merge_domain_pack`.
**Why:** Generation-gap warnings fire only when merge adds omitted core models; LLM repair is flaky.
**Rejected:** Removing generation-gap warnings in merge (would hide real LLM under-coverage in tests).

### 2026-08-02 — SAFE-2b: party-link models stay non-workflow after re-enrich
**Decided:** Extract `is_party_link_model()`; block `apply_pattern_rules` from setting
`is_workflow` on party links; skip kanban views/view_mode in `ensure_default_ui`; run final
`repair_draft_integrity` after post-critique re-enrich in `draft_module_from_prompt`.
**Why:** Quality demote worked but re-enrich + rules re-promoted `x_matter_party` (SAFE-2 v3 FAIL).
**Rejected:** Demote-only without fixing enrich/rules (bug recurred every live draft).

### 2026-08-02 — SAFE-1 baseline .gitignore hardening
**Decided:** Extend root `.gitignore` with `.env.*` + `!.env.example`, Playwright artifact
dirs, and docker bind-mount volume patterns before the initial commit.
**Why:** Card checklist required explicit coverage beyond the pre-existing minimal ignore file.
**Rejected:** Relying on `apps/web/.gitignore` `.env*` alone (would ignore `docker/.env.example` at root level inconsistently).

### 2026-08-02 — Orchestration plan package approved (55 cards, 11 waves)
**Decided:** Full build-out executes from `plans/MASTER_PLAN.md` + `plans/cards/` via cheap
models (Composer 2.5 default, Grok 4.5 for routed cards + all checking). Governing additions:
(1) all four Odoo tiers (Online/sh/Community/Enterprise) are first-class — Enterprise features
driven via public RPC on licensed instances are IN scope; only copying Enterprise/Studio
source stays forbidden. (2) Monetization is a product goal: Solo/Pro/Business/Agency tiers +
internal admin plan, self-hosted accounts auth (argon2id/TOTP/workspaces/roles), Stripe +
Paystack hosted checkout, entitlement registry gating. (3) Former deferral candidates promoted
to cards by user: barcode (CMP-9), approval processes (CMP-10), property parity (CMP-7), EE
view designers (TIER-6), live overlay editing (UIX-6), website editing (UIX-7),
multi-company/i18n/Documents (CMP-11). (4) Checkbox discipline: every card carries a CHECKLIST;
skips require user approval; checker diffs checklist vs code first.
**Why:** User approved the plan and requires cheap-model execution without quality drift.
**Rejected:** Deferring the promoted seven; auth-SaaS dependencies; deciding the 4 remaining
DEFERRALS.md candidates without the user.

### 2026-08-03 — Wave 13 DEV: first-class developer Python path (user-directed)
**Decided:** Three gated developer lanes (WAVE-13-DEV.md): DEV-1 Code Studio — live
`state=code` server actions/automations where a per-instance PROBE proves support (never
assumed by tier), editor + one-record test-run + advanced confirm/snapshot; DEV-2 —
`custom_code_blocks` become writable (developer role) with lint + one-click sandbox loop,
live-apply exclusion intact; DEV-3 — Script Runner: ad-hoc Python against the typed RPC
client in an isolated subprocess (resource limits, import allowlist, no fs/network), journaled
with write counts. All behind `developer` role + `dev_tools` entitlement + SafetyGate risk
class `code`; observer mode refuses. Completes (not contradicts) 2026-07-27 Option A +
advanced-confirm decisions: no-code stays default, code is explicit opt-in.
**Why:** User requires that developers can always write Python directly where instances
allow it.
**Rejected:** Assuming code-action availability by hosting tier; executing scripts in the
API process; letting code blocks into the live apply path.

### 2026-08-03 — Production-trust posture + Wave 12 TRUST (user-directed)
**Decided:** Honest posture: architecture is safety-first (ORM/RPC-only as the user's own
credentials, no SQL — damage bounded to what the user's account can do; corruption-level
damage structurally out of reach) but NOT yet marketable as production-trustworthy: known
enforcement gaps (REM-2), unverified-live bulk paths, clean-instance-only validation,
partial-apply risk. Plan: Wave 11 REM first, then Wave 12 TRUST (WAVE-12-TRUST.md):
observer-mode default + least-privilege onboarding; SafetyGate single choke point with a
route-enumeration meta-test (no mutating endpoint ships ungated); sample-first execution +
caps + anomaly auto-pause + kill switch; backup-artifact-before-destructive + restore
drills; dirty-instance/chaos/concurrency gates; coverage floors + settings-matrix execution
policy; IDOR/supply-chain/app-DB-restore hardening; SAFETY.md trust contract + production
readiness checklist gating production write mode; design-partner beta with written GA
criteria. "Fool-proof" explicitly rejected as a claim — defense-in-depth with honest limits
is the standard.
**Why:** User asked whether live customer DBs are safe; review evidence says structural
safety yes, earned trust not yet.
**Rejected:** Marketing production-readiness now; per-router safety discipline (proven to
fail silently — choke point instead); external analytics SaaS for telemetry.

### 2026-08-03 — Orchestrator review verdict: gates real, claims inflated (Wave 11 REM)
**Decided / proved:** Full-board review after the implementation run claimed all 57 cards
done. Gates independently re-run and CONFIRMED green (API 667/2skip, lint 0 err, vitest 78,
build OK). Code-level diff of every checklist found: PCM-3/PCM-4/UIX-6 FAIL (refusal contract
absent in code, enforcement functions with zero call sites, overlay editor select-only);
confirmed `guard` NameError crashes staged pipeline (never executed by tests); stub tests
masquerading as gates (`kit.test.ts` name list; slot-gate test hits `/health`); BLK-2..7 live
smokes never run; CMP-9 widget lacks bundled zxing. Remediation = WAVE-11-REM.md (REM-1..12),
REM-1 (runtime bug) then REM-2 (security wiring) first. PROGRESS downgraded honestly.
**Why:** Maker-is-never-checker; checkbox discipline requires evidence, not marks.
**Rejected:** Accepting PROGRESS/STATE claims at face value; deleting the [x] history
(annotated downgrades instead); treating green suites as proof when the failing paths were
simply uncovered.

### 2026-08-03 — Hybrid pricing: active-project slots + Project Pass (user-approved)
**Decided:** Value metric = subscription tiers (unchanged) + ACTIVE-PROJECT SLOTS per tier
(Solo 1 / Pro 3 +$15 / Business 10 +$10 / Agency 25 + packs) + a $299 one-time Project Pass
(1 project, Pro-level build features, 60 days → read-only + basic maintenance; upgrade keeps
project). Projects gain active↔archived lifecycle; archiving frees slots instantly and
generously. HARD RULE: slots gate BUILD surfaces only — the operate/maintenance suite (bulk,
health checks, Expert, snapshots) is never project-gated. Pricing anchor = consultant
engagement costs, not SaaS peers. Encoded in WAVE-9-MON cards (MON-2/MON-4) +
`active_projects_limit` entitlement key.
**Why:** B2B/agency buyers derive episodic per-project value; flat monthly under-charged
heavy builders and offered nothing to one-project buyers facing $3k–$10k consultant quotes.
**Rejected:** Pure per-project pricing replacing subscriptions (lumpy, kills MRR + operate
stickiness); metering builds/exports instead of concurrent slots (gameable, disputes);
gating maintenance per-project (churn risk).

### 2026-08-03 — Component-grain AI generation (card AI-8, user-approved)
**Decided:** Draft Studio generates at three grains — field_pack / feature_slice / full_app —
with components plugging into stock Odoo apps OR existing custom apps: intent grading, live
host discovery (stock + `x_` models), an editable "connect points" pipeline step (host,
form tab, menu nesting, smart buttons, FK direction), extension ModuleSpecs (`mode: inherit`,
inferred depends), live-apply + small-module export, stacking collision detection, and a
component gallery (AI-6 generalizer extended; 4 authored seeds). Grok 4.5-routed. PCM rules
bind (tier-1 hosts link-only live; inherit views only — no primary mutation).
**Why:** User wants small connectable components, not only whole apps; generator's `_inherit`
support existed but the AI path never used it.
**Rejected:** A separate "extension builder" product path outside ModuleSpec; padding small
asks into full apps via depth floors.

### 2026-08-02 — UI identity: petrol teal supersedes Odoo purple (flagged supersession)
**Decided:** App chrome uses our own identity — warm neutral scale + petrol/teal accent
(~#0E7569), Inter UI type, dark mode. Supersedes 2026-07-28 "enforce Odoo brand colours"
(#714B67). Odoo-ish styling is allowed ONLY inside Odoo-preview surfaces (designer canvas,
proxied frames), optionally themed from the connected instance's own extracted palette (CMP-3).
**Why:** Approved UI/UX revamp requires a premium distinct identity; trading-dress caution
(Doc 3 §20) argues against shipping Odoo's brand purple as OUR brand.
**Rejected:** Keeping #714B67 as app primary; theming our chrome from customer instances.

### 2026-07-28 — Fix remaining pack/AI gaps (relations, party id, terminals)
**Decided:** Merge overwrites fee-earner M2Os that wrongly target `res.users` when pack has `x_attorney`; set required from pack; rename gold party to `x_matter_party` (match LLM); scaffold teaching lists `required_models` + staff/terminal rules; quality adds terminal statuses and collapses parallel `x_party`.
**Why:** User draft still wrong after prior polish because merge only *added* fields — existing `x_attorney_id→res.users` and truncated statuses stuck; pack `x_party` diverged from LLM `x_matter_party`.
**Rejected:** Leaving wrong relations for a later remap-only pass without merge fix.

### 2026-07-28 — Honest pack/AI split: deepen merge + staff FK + party demote
**Decided:** Merge upgrades thinner selections from pack; warn `generation gap` when pack adds core masters (attorney/bill/…); remap fee-earner M2Os from `res.users` → domain staff model; demote party/role-link `is_workflow` + kanban; scrub automation `filter_domain` status keys not on the model; require `x_name`.
**Why:** Latest draft looked world-class but warnings showed pack supplied attorney/bill/compliance; fee earner FKs pointed at users; party was a fake workflow; limitation auto referenced `closed` missing from status.
**Rejected:** Celebrating pack-filled drafts as pure AI excellence without measuring generation gaps.

### 2026-07-28 — Generation-first world-class (packs teach, not replace AI)
**Decided:** Raise MODEL_CREATION_RULES with WORLD-CLASS OPS DEPTH (11–15); expand few-shot exemplar (O2Ms, party, deposit statuses, line→bill); add `law_firm` pack from gold with canonical `x_attorney`/`x_matter`/… names; inject `scaffold_teaching_blob` into single-shot + staged prompts before generation; keep merge as field/model floor after LLM.
**Why:** User goal is the AI producing world-class ModuleSpecs on its own; domain richness must train generation, not only post-filter.
**Rejected:** Law-only hardcoding without prompt teaching; merge-only pack application as the quality strategy.

### 2026-07-28 — Excellence polish: parent O2Ms + ghost autos + placeholders
**Decided:** After critique/quality: remap/drop autos on missing models (hearing→event); scrub invalid selection values; dedupe per-model follow-up `next_activity` autos; ensure parent O2Ms for child M2Os; link line→bill; replace specialty_a placeholders; form O2M groups use field `string`; deepen task/party with `x_status`; critique refuses unknown-model autos.
**Why:** 8.7–9.0 drafts still had apply-unsafe critique autos on `x_hearing`, duplicate follow-ups, matter form with only hearing O2M + technical group title, and few-shot practice labels.
**Rejected:** Leaving critique autos for post-apply failure; unlimited identical next_activity automations.

### 2026-07-28 — O2M inverse + related_write scrub + partner button cap
**Decided:** Complete O2M fields missing `relation_field` from child M2O; drop duplicate O2Ms to the same child; scrub `related_write` that targets O2M / missing fields / placeholder values (`default`); collapse all `next_activity` rows per automation to one; cap Contacts smart buttons at 4 (prefer workflow headers); scrub `RNT/` help leaks; rebuild forms omitting O2M/binary.
**Why:** Depth-ok law-firm draft still had apply-unsafe shapes (hearing+event both → x_event without inverse; critique autos writing O2M status / `x_rate_id=default`; 9+ partner buttons; RNT exemplar help).
**Rejected:** Leaving incomplete O2Ms for apply-time failure; unlimited partner button_box noise.

### 2026-07-28 — Post-seed UI coverage + partner field canon
**Decided:** Canonical partner FK is always `x_partner_id` (rename `x_client_id`). Enrich fills missing actions/menus for seeded models; rebuilds view arches that reference missing fields; rules fill ACL stubs for every `x_*`. Quality fills empty selections, deepens rate models, dedupes automation safe_actions. Re-enrich triggers on `seeded`.
**Why:** Depth.ok draft still apply-broken — matter views/buttons pointed at `x_partner_id` while field was `x_client_id`; only 4/12 models had menus.
**Rejected:** Preferring `x_client_id` as the partner alias.

### 2026-07-28 — Generation-path model quality (not just post-filters)
**Decided:** Steer the LLM at create-time: `MODEL_CREATION_RULES` in system + staged prompts; few-shot substantive exemplar in every single-shot prompt; staged step1 bans type/tag/stage entities + requires loop_role; step2 enforces min fields + retry if thin; `run_model_quality_pass` collapses hollow catalogs → selections and LLM field-deepen before depth/critique; expand forbids hollow missing_models.
**Why:** User correctly flagged that scoring/stripping after the fact ≠ better model creation; each iteration must improve generation itself.
**Rejected:** Relying only on depth floors / gold JSON references as the quality strategy.

### 2026-07-28 — Depth quality: substantive models + strip unsafe autos
**Decided:** Depth floors count *substantive* models only (hollow name+code catalogs excluded); strip Python/`email_send`/empty critique automations; critique refuses those kinds. Law-firm gold reference: `docs/reference/law_firm_modulespec_gold.json` + `ai_reference_law_firm.py`. Prompt: prefer selections over empty taxonomy models.
**Why:** “World-class law firm” draft hit 11 models by padding type/category/tag/stage/priority stubs while missing time/trust/hearings; automations included forbidden `state=code`.
**Rejected:** Treating raw model_count as depth; allowing code automations through critique.

### 2026-07-28 — Depth-first AI ModuleSpec (packs secondary)
**Decided:** Consistent depth is enforced domain-agnostically via `ai_depth.py`: classify ambition (thin/standard/comprehensive) from the prompt; score models/fields/M2O/workflows/smart buttons/autos; deterministic repairs (synthesize smart buttons from M2O graph, currency/company/workflow fields); LLM expand when floors fail; critique no longer `skipped_complete` when depth gaps remain. System prompt teaches operational-loop depth without hospital-specific must-lists. Domain packs stay offline/retrieval fallbacks only.
**Why:** User priority — robust models for *any* prompt matters more than a hospital pack; prior thin drafts passed structural checklist and skipped critique.
**Rejected:** Relying on curated packs as the primary depth strategy; marking ready=true on menus/views alone.

### 2026-07-28 — Hospital AI depth: dedicated pack + stricter ModuleSpec system prompt
**Decided:** Added `hospital` domain pack (`ai_domain_pack_hospital.py`, 18 models / 20 smart buttons / 5 autos) retrieved before thin `clinic` for hospital/world-class prompts; tightened clinic regex (no bare patient|doctor); system prompt requires apply-ready `x_*` relation fields + `on_*` triggers + 12–20 models for comprehensive asks; rules repair bare `patient_id` / `create`/`write`; gold export `docs/reference/hospital_modulespec_gold.json`.
**Why:** User’s “world-class hospital” draft scored ~clinic toy depth with broken smart buttons/autos; checklist `_ready: true` was structural false confidence.
**Rejected:** Expanding clinic pack alone; claiming HIS/EMR parity (blood bank, HL7, full pharmacy inventory still out of ModuleSpec scope).

### 2026-07-28 — ModuleSpec apply must normalize draft JSON (smart buttons + triggers)
**Decided:** Live `apply_module_spec_ui` treats draft JSON as authoritative: alias smart-button keys (`source_model`/`target_model` → `on_model`/`related_model`), ensure M2O `relation_field` exists on **target** (create or invert if AI put FK on source), alias automation triggers (`create`→`on_create`, `write`→`on_write`), apply `access_rules` (ACL + `domain_force` record rules). Unit tests in `test_spec_apply_smart_buttons.py` / `test_spec_apply_automations.py`.
**Why:** Hospital AI draft had smart buttons + automations; apply yellow-skipped them on enum/key/relation mismatches — user: everything in JSON must be picked up.
**Rejected:** Leaving skips as “AI must emit perfect keys”; silent drop of incomplete buttons.

### 2026-07-28 — UI theme: enforce Odoo brand colours (retire mint green)
**Decided / proved:** Replaced hardcoded mint/green shell hexes across `apps/web` with Odoo brand family — primary `#714B67`, light accent `#c9a9c0`, teal secondary `#017E84` (tokens already in `globals.css`). Landing + app shells now purple radial; primary CTAs solid `#714B67` / white.
**Why:** User called out green theme still live despite prior MEMORY lock for Odoo colours.
**Rejected:** Keeping mint as “accent on purple”; claiming EE brand assets beyond public hexes.

### 2026-07-28 — CE lab: installed base_geolocalize + project on Odoo 19
**Decided / proved:** On `:8069` / `odoo_dev`: installed `base_geolocalize` + `project`. Partner geo fields present (`partner_latitude` / `partner_longitude`). **View types unchanged** — still no `map` / `gantt` / `cohort` (`web_map` / `web_gantt` / `web_cohort` ABSENT on CE). Live M2/A4 map/gantt/cohort creates remain skip-with-reason.
**Why:** User authorized CE-only install; EE still requires subscription they must provide.
**Rejected:** Claiming map/gantt unlocked on Community.

### 2026-07-28 — Live proof: M2/A4 finish smokes on Odoo 19 CE
**Decided / proved:** `tests/test_integration_m2_a4_live.py` — **6 passed**, 3 skipped: activity view, form Can Create attrs, inactive webhook + followers automations, SMS (module present), on_message_received trigger. Skipped map/gantt/cohort because `ir.ui.view` type selection lacks those on stock CE (Designer still emits arch; module-gated honesty correct). Playwright automations **6 passed**.
**Still blocked:** EE live RPC (no EE image).
**Why:** User said continue after unlock finish.
**Rejected:** Claiming map/gantt/cohort live create on CE without those view types in selection.

### 2026-07-28 — Unlock: finish all prior MEMORY-deferred mastery gaps
**Decided:** User authorized **full finish** of prior deferred items: M2 Activity/Map UI/Gantt/Cohort/search facets/form Can Create…/full A4 automations; M4 remaining snapshots; M5 extra EE playbook rows; M3-P2 domain playbooks; M4-P1 `requires_modules`. Order: Activity+search → Map+form attrs → A4 automations → Gantt+Cohort → snapshots → EE rows → docs/tests.
**Still blocked (infra, not defer):** EE **live** RPC against real Enterprise image — keep mocks/grey-out until EE Docker exists.
**Why:** User: “FINISH ALL FULLY” with orchestrator-chosen order.
**Rejected:** Leaving M2/M4/M5 residuals deferred after explicit unlock.

### 2026-07-28 — W0 + M3 fully closed (honest remainders named)
**Decided / proved:** W0 remainders closed where possible: `currency_field` live on 19 (persist) + 16 (omit safely); Odoo 18 live deepened (list models, view arch, ACL); production Automations Playwright (`e2e/automations-prod.spec.ts`). M3-P1: currencies / currency-rates / uom / fiscal-positions APIs with `available:false` when modules absent. Phase audit: `docs/MASTERY_PHASE_AUDIT.md`.
**Was deferred (now unlocked above):** EE live RPC (no EE image); M2 Activity/Gantt/Cohort/full A4 matrix.
**Why:** User required W0 and M3 fully done + full phase pass.
**Rejected:** Claiming EE live or full M2 Studio view parity.

### 2026-07-28 — Checker FAIL remediations (matrix honesty + M5 UI)
**Decided:** After mastery Checker **FAIL**, refresh matrix App column to match shipped code; mark P0 cleared/deferred explicitly in `MASTERY_BACKLOG.md`; add `EePlaybooksPanel` grey-out UI + HTTP tests for EE playbooks; thicken Power Ops pack tests. **Do not claim full M2** (Activity/Gantt/Cohort/A4 matrix remain MEMORY-deferred).
**Why:** Checker correctly rejected stale matrix + missing M5 UI + overstated M2.
**Rejected:** Re-labeling FAIL as PASS without matrix/UI fixes.

### 2026-07-28 — Capability mastery target + R0→M6 shipped
**Decided:** Product target = **customization + day-2 admin mastery** via public ORM/RPC + Option A — not full ERP rebuild, not Studio clone. Research artifact: `docs/research/ODOO_SURFACE_INVENTORY_RAW.md` + `docs/ODOO_CAPABILITY_MASTERY_MATRIX.md` + `docs/MASTERY_BACKLOG.md`.
**Shipped:** M1 hosting_hint / Online Python promote contract; M2 calendar/graph/pivot arch + Designer; M3 paperformat/defaults/property/cron/website; M4 matching-major pipeline + Power Ops packs + menu/report snapshots; M5 EE playbooks grey-out; M6 `docs/DEPLOY.md`.
**Why:** User approved exhaustive mastery plan execute.
**Rejected:** Studio source; claiming Online Python installs; promoting 16 to GA.

### 2026-07-28 — Upgrade-map Phases 0–D complete
**Decided / proved:** Upgrade-map remainders closed: Phase 0 re-verify + Checker PASS; A1–A4; B1 Online copy; C1 kanban + live round-trip; **C2 vision-verify Checker PASS** (`docs/vision-verify/`); C3 Power Ops 16/17. **§5 / HANDOVER §7 still refused.** **16 remains experimental.**
**Why:** User approved upgrade-map plan; remainders + polish only.
**Rejected:** Promoting 16 GA; implementing §5; editing `.cursor/plans/`.

### 2026-07-28 — Odoo 16 deepen batch (still experimental)
**Decided / proved:** Live `:8072` suite deepened — access create (`ir.model.access` + `ir.rule`), `mail_post`/`next_activity` server actions on `res.partner`, field inject inherit on partner form. **10 passed**; `ga` stays False; no `update_path` / related_write claim.
**Why:** CARD A2 deepen experimental 16 without promoting to GA.
**Rejected:** Setting `ga=True` for 16; silent best-effort when states missing (skip-with-reason honesty).

### 2026-07-28 — Promote Community 17 to GA (16 remains experimental)
**Decided:** **17 = GA** alongside 19 and 18 (`ga_majors() == {17, 18, 19}`). **16 stays experimental** (no `update_path` / related_write claim).
**Why / proof:** Live smokes on `:8071`/`:8072` — 12/12 passed including related_write e2e on 17, window action `tree,form`, menus, QWeb reports (see prior MEMORY *Odoo 16/17 menus+reports+related_write smoke deepened*). User authorized HANDOVER completion; do not silent-GA 16.
**Rejected:** Promoting **16** to GA; unlocking ≤15 or 20+.

### 2026-07-28 — Matching-major sandbox live proof (18)
**Decided / proved:** Ephemeral sandbox install OK for **Odoo 18** via `./docker/run-sandbox-major-gate.sh 18` → exit 0; `SandboxResult(ok=True, module=sandbox_smoke_m18, odoo_major=18)` on host **:18069** (`-p odoo-sandbox`, image `odoo:18`). Permanent `:8070` untouched.
**Why:** HANDOVER §4 priority 2 / §6 acceptance — code path existed; live proof was missing.
**Rejected:** Treating unit-only or Odoo-19-only sandbox gates as multi-major proof.

### 2026-07-28 — CI matching-major sandbox = manual dispatch only
**Decided:** `.github/workflows/odoo-sandbox.yml` gains gate `major-matrix` + `sandbox_major` (`matrix`|16–19); ephemeral only (no permanent stacks); weekly schedule stays **extension** on primary 19.
**Why:** Local `:18069` proof green for 16–18; CI remains opt-in (slow/flaky) per earlier audit-log MEMORY.
**Rejected:** Making major-matrix the default Sunday cron.

### 2026-07-28 — Odoo 16/17 menus+reports+related_write smoke deepened
**Decided / proved:** Live integration on `:8071`/`:8072` — 12 passed (related_write e2e on 17; window action `tree,form` + menus + QWeb reports on 16/17; 16 encode/update_path hard-refuse). STUDIO_PARITY menus/reports → ✅ for 16–19.
**Why:** HANDOVER §1.2 / §2.9 required smoke or honest downgrade; smoke succeeded.
**Rejected:** Leaving matrix at ⚠️ without proof; promoting **16** to GA (still no update_path).

### 2026-07-28 — HANDOVER implementable arc closed
**Decided:** `docs/HANDOVER_UNFINISHED_WORK.md` updated to DONE for implementable multi-version follow-through (docs, sandbox proof, CI major-matrix, UI caps, v16 hard-fail, GA **17**, list_view_for_major, Playwright caps e2e). **16 remains experimental.** Intentional §7 + ongoing keep-smokes-green + optional Power Ops/`account` on 16/17 + vision-verify/kanban polish left honest-open.
**Why:** User asked full HANDOVER completion; product floor still refuses silent 16-GA and Studio/§7 items.
**Rejected:** Claiming Property fields / kanban polish / vision-verify as done; promoting 16.

### 2026-07-27 — M2 unlock: Community 18 experimental (19 remains GA)
**Decided:** Allow connecting **Odoo Community 18** for the overlapping safe subset (fields, view inject inherit, safe automations including related_write/`update_path`). **19 stays GA**; 18 is experimental. Docker: `docker/docker-compose.odoo18.yml` on port **8070**. Refuse ≤17 until M3.
**Why:** User unlocked M2 per `MULTI_VERSION_ODOO_PLAN.md`; capability registry + adapters gate features without router `if major`.
**Rejected:** Unlocking 16/17 in this pass; treating 18 as GA; silent best-effort writes outside the declared capability set.

### 2026-07-27 — Promote Community 18 to GA + M3 unlock (17/16 experimental)
**Decided:**
1. **18 = GA** alongside 19 (smoke + Power Ops recipes green after `account` install on odoo18_dev).
2. **M3:** register **17 + 16** as experimental. 17 keeps full safe-subset caps; **16 omits** `RELATED_WRITE_DOTTED_PATH` and `OBJECT_WRITE_UPDATE_PATH` (no update_path-era claim). Docker ports **8071** (17) / **8072** (16). Support floor = **16**.
**Why:** User asked to do all remaining multi-version items; live 18 Power Ops 11/11 after account; plan M3 delivers 17 then 16.
**Rejected:** Claiming 16 related_write without a dedicated pre-update_path adapter; making 17/16 GA without live smoke evidence.

### 2026-07-27 — M4 Enterprise warn-only + Studio parity matrix
**Decided:** Enterprise (`server_version` with `+e` / “enterprise”) is **warn-only**: connect allowed; capability probe message + Designer/Connect banners; **same public-ORM capability set** as Community for that major. Never claim or use Studio/`web_studio`. Document per-major Studio-parity in `docs/STUDIO_PARITY_BY_MAJOR.md`. Power Ops recipes expose `tags` + `min_major`.
**Why:** Operators on Online Enterprise still need metadata customization; copying Studio is forbidden.
**Rejected:** Refusing Enterprise connections; offering Studio-parity features that require Enterprise modules.

### 2026-07-27 — Module export: one zip per connection major
**Decided:** Export produces **one** installable zip whose `__manifest__.py` `version` is `{connection_major}.0.1.0.0` (via `manifest_version_for_major`). Inherit list views use adapter list/tree type + matching xpath (`//tree` on ≤17). No multi-manifest / multi-series bundle in v1. Sandbox/run uses matching-major Docker (`odoo:{major}` on `:18069`).
**Why:** Install target must match the DB you customized; multi-manifest adds complexity without v1 demand.
**Rejected:** Always hard-coding `19.0.1.0.0`; shipping multiple manifests in one zip; validating 16–18 zips only on `odoo:19`.

### 2026-07-27 — Odoo 18 Power Ops gap (honest)
**Found:** Fresh `odoo:18` smoke DB has `account` **uninstalled** — `account.move` missing; accounting Power Ops recipes will fail until account (and deps) are installed in that instance.
**Decided:** Install `account` for Power Ops probe (`test_power_ops_odoo18.py` + `./docker/ensure-account-18.sh`); document that Power Ops needs account on the target DB. Do not auto-install account in every init-db-18 by default (heavy).
**Rejected:** Claiming Power Ops works on bare base-only 18.

### 2026-07-27 — Build system = Cursor Engineering Pipeline (Approach A)
**Decided:** Install pipeline (RULES/PIPELINE/AGENTS/MEMORY/ERRORS/STATE + skills + `.cursor/rules`) before Phase 0 code.
**Why:** Empty repo; compounding memory/gates/checker discipline must exist before RPC/UI work to prevent session drift and confident-but-wrong Odoo API usage.
**Rejected:** B (pipeline + Phase 0 in one pass — higher risk of wrong scaffold assumptions); C (brief-only — delays disk presence of session defaults).

### 2026-07-27 — Stack lock (from production plan)
**Decided:** Next.js/TS/Tailwind + FastAPI/Python 3.12 + Postgres metadata DB + odoorpc/xmlrpc + Jinja2 module gen + Docker sandbox; light queue (RQ/arq) over Celery until needed.
**Why:** Matches solo/budget constraints; Python-native Odoo tooling and future `pytest-odoo` sandbox path.
**Rejected:** Node-only backend (weaker Odoo ecosystem fit); Celery on day one (more moving parts than solo needs).

### 2026-07-27 — Competitive scan: "Odoo Studio Community" options (pending product decision)
**Found:**
1. `Odoo-Studio-Community` GitHub org — SEO shell, only `.github`, no product code. Ignore.
2. `MNametissa/odoo_studio_community` — claims "Studio ported for CE"; headers still say "Part of Odoo", license flipped from `OEEL-1` → `LGPL-3`, depends on `studio_community_base` stubs for `web_enterprise`. **Do not fork/use** — Enterprise IP risk; violates our "never reverse-engineer Studio" constraint.
3. `mahmoudegpro/odoo-studio-community` — clean-room-looking in-Odoo module (OWL editor + `studio.*` models wrapping `ir.model`/`ir.model.fields`, export wizard). Odoo **18**, 2 commits (May 2025), 4★, placeholder author. Possible reference, not a mature base.
4. `bluefoxconsultant/.../bf_studio_light` — narrow Odoo **18** CE field/view injector; active Jul 2026; explicitly not full Studio.
**Not decided yet:** build parallel (external RPC app) vs study/extend mahmoudegpro or bf_studio_light as in-instance module. Differentiator for *our* plan remains multi-instance + sandbox-before-prod, which in-Odoo modules don't give.

### 2026-07-27 — Product path = A (external app) + Studio parity learning (clean sources only)
**Decided:** Continue the external Next.js/FastAPI/RPC platform (Phase 0+). Aim for Studio-class capability/UX by studying **public** Studio feature docs + clean-room OSS (`mahmoudegpro`, `bf_studio_light`) — never Enterprise Studio source or the MNametissa port.
**Why:** Keeps multi-instance + sandbox-before-prod differentiators; avoids OEEL/IP risk; still raises the bar on functionality/polish.
**Rejected:** C (in-Odoo-only pivot); using MNametissa as base.

### 2026-07-27 — App metadata DB = separate Postgres on :5433
**Decided:** `app-db` service in docker-compose (`odoo_custom` DB) distinct from Odoo’s Postgres.
**Why:** Stack lock (Postgres); never mix builder metadata with customer/Odoo DB.
**Rejected:** SQLite-only for Phase 1 (would silently diverge from AGENTS.md).

### 2026-07-27 — Automations: safe subset only
**Decided:** Support create/write/unlink/archive/time triggers + `object_write` (literal value) and `next_activity`. Auto-`ensure_module_installed('base_automation')`.
**Why:** Matches Studio no-code value without code-injection surface (`state=code` / equation compute blocked).
**Rejected:** Exposing Execute Code, webhooks, or evaluation_type=equation in the builder UI.

### 2026-07-27 — Python path = Option A; advanced actions with confirm; rollback-first
**Decided:**
1. Custom Python automations: author → generate module → sandbox test → explicit promote/install to go live (Option A).
2. Admin/advanced actions (code, webhook, equation, destructive deletes, etc.) are **allowed** with Odoo-style warning UI + explicit API confirmation (`confirm_advanced=true` / typed confirm phrase). Operator is assumed to understand ERP risk.
3. Snapshot metadata before risky mutations; provide restore for reversible targets (views, automations, server actions, field defs where possible). Honest limits: dropped DB columns / deleted records may be unrestorable.
**Why:** Power users need Studio-plus depth; confirmation + rollback beats a permanent ban that blocks real admin work.
**Rejected:** B (one-click live `state=code` with only a soft confirm); permanent hard-block of all advanced actions; pretending field drops are fully reversible.

### 2026-07-27 — Phase 6 sandbox isolation
**Decided:** Ephemeral sandbox uses `docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml` on host port **18069** (moved off 8070 so permanent Odoo 18 can own `:8070`), with addons bind-mounted from `docker/sandbox-addons/`. Image is **matching-major** (`ODOO_SANDBOX_IMAGE=odoo:{16|17|18|19}` from connection `server_version` or `SandboxRunBody.odoo_major`). ≤18 DB init uses stop → drop → `compose run -i base,web` → start.
**Why:** Honest install validation for multi-version exports; avoid port clash with `odoo18` stack.
**Rejected:** Always forcing `odoo:19` for every export; sharing host port 8070 with permanent 18.
**Why:** Default compose project name is the folder (`docker`), so sandbox `down -v` previously tore down the primary Odoo stack on 8069.
**Rejected:** Sharing the primary compose project; installing unvalidated zips straight onto customer connections.

### 2026-07-27 — Promote = sandbox token + confirm; install path by target
**Decided:**
1. Promote requires sandbox validation (`validation_id` + matching zip sha256, 2h TTL) **or** `run_sandbox=true`, plus advanced confirm phrase.
2. Local Docker Odoo (`127.0.0.1:8069`): copy zip into `/mnt/extra-addons`, restart, `button_immediate_install`.
3. Remote / no filesystem: `install_mode=data` (ir.model XML) via `base_import_module` — Python model zips are rejected on remote.
**Why:** `base_import_module` cannot execute Python; Option A still needs sandbox before live install.
**Rejected:** Silent promote without sandbox; pretending Python zips import remotely.

### 2026-07-27 — Access rights builder (live ACL)
**Decided:** Live CRUD for `ir.model.access` + simple `ir.rule` (domain string + optional group) via `/access` API and UI page. Groups listed from `res.groups` (`full_name`).
**Why:** Completes Studio v1 parity checklist; custom models created via RPC otherwise lack usable ACL for non-admin users.
**Rejected:** Full ACL matrix / multi-company rule builder in this phase.

### 2026-07-27 — Related fields map to concrete Odoo ttype + `related=`
**Decided:** Studio picker type `related` is API/UI only. On create we send Odoo a concrete `ttype` (`char`, or `many2one` if `relation` set) plus `related=` path and `readonly=True`. Monetary accepts optional `currency_field`.
**Why:** `ir.model.fields` has no `ttype=related`.
**Rejected:** Passing `ttype=related` to Odoo RPC.

### 2026-07-27 — Field view inject defaults to inherit extension
**Decided:** `inject_field_into_views(strategy="inherit")` creates/updates child views named `{model}.custom.{field}.{type}` with xpath arch; `mutate` (write parent arch) requires advanced confirm.
**Why:** Mutating primary module arches breaks upgrades/interop; inherit is Studio-like and reversible.
**Rejected:** Default mutate; silent mutate without confirm.

### 2026-07-27 — Related UX = concrete type + optional related path
**Decided:** Builder dropdown drops standalone `related`; always-visible optional Related path; API still accepts deprecated `ttype=related` alias.
**Why:** Matches Odoo model (concrete ttype + related=); avoids inventing wrong types.
**Rejected:** Keeping related as primary dropdown type.

### 2026-07-27 — Module XML templates must escape user strings
**Decided:** Jinja `|xml` filter (with quote entities) on names/domains/help in data XML; Python code in automations uses CDATA; view `arch` stays raw XML.
**Why:** Adversarial `<`/`&` in labels/code must not break or inject XML.
**Rejected:** Autoescape-all (would corrupt arch).

### 2026-07-27 — Default ACL on model create + promote uninstall
**Decided:** `with_defaults=True` model create also grants `base.group_user` full CRUD via `ir.model.access`. Promote records history in app DB; uninstall requires confirm phrase and marks history `uninstalled`.
**Why:** Custom models were unusable for Internal Users without ACL; promote needed an honest undo path.
**Rejected:** Silent uninstall; auto-dropping DB tables beyond Odoo’s uninstall behavior.

### 2026-07-27 — Phase 7 app API auth = API keys
**Decided:** Protect the FastAPI app with `AUTH_MODE=api_key` (Bearer or `X-API-Key`). Keys hashed (SHA-256) in `app_api_keys`; optional `APP_API_KEY` env bootstrap; one-time `/api/auth/bootstrap` when no keys exist. Default `AUTH_MODE=off` for local pytest/gates.
**Why:** Multi-connection customization API must not stay open on a shared host; OAuth/user accounts are heavier than a solo operator needs for v1.
**Rejected:** Full user accounts / OAuth in Phase 7; auth-on-by-default breaking all existing local gates.

### 2026-07-27 — Record rules in export + CI + rate limit
**Decided:** Export live `ir.rule` rows into `security/record_rules.xml`. Mutating routes get a sliding-window IP rate limit (`RATE_LIMIT_PER_MINUTE`, default 120). CI runs unit + API-without-Odoo on Postgres service.
**Why:** Completes ACL export parity; protects shared API from abuse; keeps CI cheap without requiring Docker Odoo in Actions.
**Rejected:** Full sandbox gate in default CI (too slow/flaky for every PR).

### 2026-07-27 — Audit log + zip-scoped residuals + manual sandbox CI
**Decided:** Append-only `audit_logs` via middleware on mutating requests (`AUDIT_LOG_ENABLED`, default on); list at `GET /api/audit/logs` and Settings UI. On promote, parse model names from the zip into `promoted_modules.models_json` and use those for uninstall residual checks. Live Odoo+sandbox gate runs only via `workflow_dispatch` (`.github/workflows/odoo-sandbox.yml`).
**Why:** Operators need a trail of who changed what; prefix heuristics on uninstall were noisy; heavy sandbox CI must stay opt-in.
**Rejected:** Auditing GET traffic; requiring sandbox gate on every PR.

### 2026-07-27 — Full-phase deepen/harden (Waves A–D)
**Decided:** Ship breadth across all phases in one pass: zip safety + snapshot IDOR fix + connection cascade; destructive CRUD with confirm; search views/menus/XML escape/related; async sandbox jobs + trusted_proxy + DEPLOY.md; shared ConfirmDialog + Vitest; sandbox process lock.
**Why:** User asked to deepen/harden every phase, not only highest-impact items, with a separate rigorous test agent.
**Rejected:** Deferring Wave C Studio items; skipping web tests; leaving sandbox unlocked under async_job.

### 2026-07-27 — Module interop = depends + _inherit + inherit views
**Decided:** Live path keeps `x_*` on any model; field inject defaults to **inherit** xpath child views. Export packages stock-model extensions as `_inherit`, infers `depends` from models/relations (with explicit merge), and documents the model in `skills/module-interop.md`. App DB connection-scoped tables get `ON DELETE CASCADE` FKs.
**Why:** Customizations must compose with `sale`/`contacts`/peer addons the Odoo way — not by mutating primary arches or shipping orphan zips with `depends: ["base"]` only.
**Rejected:** Overwriting base views as the default; inventing a non-Odoo module merge format.

### 2026-07-27 — Extension sandbox + depends picker + Playwright confirm
**Decided:** UI picks installed `ir.module.module` names for export/sandbox `depends` (+ free-form). Sandbox can preload modules via `SANDBOX_EXTRA_MODULES` / `extra_modules` (extension gate uses `sale,account`). Playwright e2e covers ConfirmDialog phrase gate on a harness page (`NEXT_PUBLIC_E2E=1`); CI runs it. Manual workflow can choose smoke vs extension gate.
**Why:** Peer custom modules and stock apps need explicit depends; extension zips fail on a base-only sandbox; confirm UX needs automated coverage without full Odoo in every PR.
**Rejected:** Always installing sale/account on every smoke (too slow); requiring live Odoo for confirm e2e.

### 2026-07-27 — Required many2one needs on_delete restrict/cascade (Odoo 19)
**Decided:** `create_field` auto-sets `on_delete=restrict` when creating a required many2one (override via `CreateFieldRequest.on_delete`).
**Why:** Library loan smoke failed: Odoo 19 rejects required m2o with default `set null`.
**Rejected:** Leaving required m2o creation broken for relational apps.

### 2026-07-27 — Full-scale Library + speed program (plan)
**Decided:** Track work in `docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md`. Library is the reference vertical for “full-scale” (barcode, fines Option A, email reminders, kanban, mail.thread, reports, multi-company). Speed layer priority: wizard/templates → live preview → draft/apply → optional Ollama. No Studio forks, no Celery-by-default, no paid LLM hard dependency.
**Why:** Need a single checkbox tracker spanning domain depth and UX speed without losing Community/RPC constraints.
**Rejected:** Implementing P1 before a written plan; treating Library as a one-off codebase separate from the platform.

### 2026-07-27 — Module export supports model extensions (_inherit)
**Decided:** Generator `ModelSpec.mode=inherit` emits `_inherit` (no `_name`); data mode writes `ir.model.fields` via model search (no new `ir.model`). Views can set `inherit_xml_id` + mode=extension with xpath inject helpers. `ModuleSpec.infer_and_merge_depends()` maps stock models → modules (`sale.order`→`sale`, etc.). Export auto-detects stock models with manual `x_*` fields (`include_extensions`, optional `extend_models` / `depends` override).
**Why:** Interop requires packaging extensions on `res.partner` etc., not only new `x_*` models.
**Rejected:** Exporting only custom models; inventing ACL/xmlids for stock models.

### 2026-07-27 — App wizard scaffolds live with fixed library model names
**Decided:** `POST /connections/{id}/apps/scaffold` applies templates via RPC (`with_defaults` + field create + inherit inject). Library uses fixed `x_lib_category` / `x_lib_book` / `x_lib_loan` (optional `technical_prefix` override). Existing models are skipped with warning; missing fields still added. Requires advanced confirm phrase. Portable twin: `library_module_spec()` → zip for sandbox (`docker/run-sandbox-library-gate.sh`).
**Why:** Stable technical names for export/menus; idempotent re-runs; confirm matches other multi-mutation advanced actions.
**Rejected:** Always-uuid-suffixed model names (breaks stable menus/export); skip-confirm for library when AUTH off (inconsistent with advanced-actions skill).

### 2026-07-27 — P3 circulation: fines/reminders Option A + optional Ollama
**Decided:** Library portable zip includes (default on) fine `python_automations` + `action_compute_fine`, overdue `mail.template` + `ir.cron`, barcode form widget + search + window action. NL assist is `AI_ASSIST=off|ollama` — draft-only JSON, never auto-apply. Domain/selection visual builders for automations + record rules.
**Why:** Matches plan D3/D4; Community-safe barcode char+widget; Option A for Python fine logic.
**Rejected:** Live `state=code` without module path as default; paid LLM dependency; auto-apply NL drafts.

### 2026-07-27 — P4 reporting + multi-company naming split
**Decided:** Library menus are explicit (Books/Loans/Active Loans/Categories). Active Loans domain is `[('x_returned','=',False)]` (not `context_today`). Loans action includes pivot/graph. `multi_company` adds zip `company_id` + company_ids rules; live scaffold uses `x_company_id` (RPC x_* rule). Stats via `GET .../library/stats` + connection strip. UAT via `docker/run-library-uat.sh`; CI workflow_dispatch `library`.
**Why:** Odoo domain XML/eval for context_today is fragile; live fields must be `x_*`; zip follows stock multi-company field name.
**Rejected:** Shipping only overdue-with-context_today as default Active Loans domain; using non-x_ company field on live RPC create.


### 2026-07-27 — Full-scale library program scope approved
**Decided:** Treat Library as the **reference vertical** that drives the speed layer (wizard, preview, drafts, builders, async jobs, export/sandbox). Ship full-scale acceptance via portable zip + live scaffold; Option A for Python fines/reminders; Ollama optional draft-only; no Studio/Enterprise source.
**Why:** One vertical forces platform generality; public ORM/RPC + sandbox gates match product constraints.
**Rejected:** Separate Library product codebase; Celery day-one; paid LLM hard dependency; multi-version Odoo in v1.

### 2026-07-27 — Plan open questions closed
**Decided:** barcode = char+widget (no `barcodes` module dep); Open-in-Odoo over preview proxy; copies integer default; live scaffold default (draft opt-in); Mailhog deferred.
**Why:** Fastest correct Community 19 path; avoids iframe/X-Frame rabbit hole and inventory complexity.
**Rejected:** Same-origin proxy now; per-copy inventory as default; draft-as-default scaffold.

### 2026-07-27 — AppBlueprint + Designer A/B/C
**Decided:** Shared `odoo_client.blueprint` applies labeled form layouts for all scaffolds (library authored; CRM/Inventory auto Identity/Details/Lines). Designer defaults to inherit saves, parses arch round-trip, supports buttons/search filters/create-field/polish-form, and same-origin Odoo preview proxy. Settings load repo-root `.env` so `AI_ASSIST=ollama` works when uvicorn cwd is `apps/api`.
**Why:** Library-only layouts weren’t enough; Designer needed Studio-parity path without Enterprise source; AI looked “off” due to env file path.
**Rejected:** Keeping library-hardcoded layouts; iframe-only preview without proxy.

### 2026-07-27 — Designer buttons = type=action (not object stubs)
**Decided:** Form buttons bind to real `ir.actions.server` (safe `object_write`) and `ir.actions.act_window` (related `active_id` domain) via `type="action"` + numeric action id. Header + smart button box in FormViewSpec. Python `type="object"` / `state=code` remain Option A only.
**Why:** Custom `x_` models have no Python methods over pure RPC; verified on Odoo 19 that action-id buttons work. Matches Studio capability without Enterprise source.
**Rejected:** Fake `action_placeholder` object buttons; live `state=code` from Designer.

### 2026-07-27 — Phase 2 Studio polish + Automations bridge
**Decided:** Ship full M+L bar in one pass: `next_activity` + `mail_post` button/automation actions; smart-button computed counts (confirm); statusbar; DomainBuilder in Designer; list decorations info/muted; xpath inherit editor; preview no-store + banner + refresh; reciprocal Designer↔Automations nav. Automations was intentionally skipped in Phase 1 (Designer-only) and is now connected.
**Why:** User asked for Phase 2 + finish labeled Next(M)/Later(L) without leaving Automations orphaned. Computed count fields verified creatable via `ir.model.fields` compute on Community 19.
**Rejected:** Leaving Automations disconnected; count badges only via Option A Python modules.

### 2026-07-27 — Activity assignee field resolution
**Decided:** `next_activity` generic assignee resolves `user_id` → `create_uid` → `write_uid` on the target model.
**Why:** Live UAT on `x_lib_book` crashed with KeyError `user_id`; custom models usually lack CRM user fields.
**Rejected:** Requiring operators to always pass `user_type=specific`.

### 2026-07-27 — Robust AI drafts = Ollama + domain packs + Generate UI
**Decided:**
1. Enrich NL drafts with curated **domain packs** (first: `car_rental`) merged after Ollama (or alone when AI is off and the prompt matches).
2. Post-process every draft: default actions/menus/list+form(+kanban) arches, statusbar when `x_status` exists, smart_buttons + automations metadata.
3. Wizard **reuse** picker feeds existing models (`res.partner`, …) into the prompt/draft.
4. **Generate UI from JSON** (`POST …/module-spec/apply`) creates models/fields/views/menus/smart buttons with advanced confirm — automations remain review-only.
5. First-class **Car Rental** wizard template shares the same pack.
**Why:** Thin LLM ModuleSpecs (Car + Rental Request) are not product-grade; packs + apply-UI close the gap without auto-mutating from draft alone.
**Rejected:** Auto-apply on draft; inventing new domains without packs; live `state=code` automations from AI.

### 2026-07-27 — AI architecture: provider + staged pipeline + rules + meta sidecar
**Decided:**
1. `LLMProvider` interface with `ollama` and `openai-compatible` backends; default Ollama model `qwen2.5:7b-instruct-q4_K_M`; always `format:json` / `response_format=json_object`.
2. Domain library expands (car rental, clinic, field service) with regex + Jaccard tag retrieval (embeddings deferred — no sentence-transformers until needed).
3. `AI_PIPELINE_MODE=single|staged` — staged runs Step 0–6 (LLM for judgment steps; views/menus deterministic).
4. `ai_rules.validate_and_enrich_draft` is the reliability backbone (integrity, sequences, mail mixins, overdue safety net, access stubs, checklist).
5. Generated zips embed `.meta.json` ModuleSpec for own-output Code→UI round-trip; arbitrary AST/XML import remains Later.
**Why:** Matches the design doc’s highest-ROI path without paying RAG/embedding tax yet; keeps ModuleSpec as the single contract.
**Rejected:** Hosted paid LLM as v1 default; full third-party module AST parser in this pass; requiring embeddings for 3 packs.

### 2026-07-27 — Tranche 1: MiniLM RAG + self-critique (stable)
**Decided:** Ship AI-quality tranche first: optional `sentence-transformers` RAG (`AI_RAG=auto`, extra `ai-rag`) with Jaccard/regex fallback; self-critique (`AI_CRITIQUE=auto`) with deterministic checklist always + LLM repair of missing `x_*` fields/models/automations. Defer visual ModuleSpec builder and third-party AST/XML import until this path is solid.
**Why:** User chose approach 1 (AI prompt/response quality) over all-four parallel; fallbacks keep drafts working without the embedding package.
**Rejected:** Blocking drafts on embeddings; critique inventing non-`x_` fields.

### 2026-07-27 — ModuleSpec visual builder + Code→UI import
**Decided:** Ship `/connections/{id}/modulespec` visual editor bound to ModuleSpec; `POST /api/module-spec/import` parses zip/.meta.json/.py/.xml via AST + ElementTree; unmapped methods/records preserved as `unmapped` (view-as-code). Wire Wizard drafts + Projects “Edit ModuleSpec”.
**Why:** Completes the deferred contract surfaces after RAG/critique; partial-fidelity import is safer than silent drops.
**Rejected:** Full Python execution of imported modules; pretending all business methods are visually editable.

### 2026-07-27 — Smart buttons = inherit only (never stock primary)
**Decided:** Generate UI injects smart buttons via upsert inherit `{model}.studio.smart_buttons` (`button_box` inside, or create box before first sheet child). Never rewrite stock primary forms; refuse explicit-view / polish writes on non-`x_` models.
**Why:** Mutating `res.partner` primary broke Contacts inherits (`//field[@name='phone']`). Inherit matches field-inject / Designer patterns and stays user-friendly (Contacts smart buttons still appear).
**Rejected:** Skipping partner back-ref buttons entirely; mutating primary then hoping stock xpaths survive.

### 2026-07-27 — Config Ops: Import + Power Ops + Odoo chrome
**Decided:**
1. Differentiator = Odoo.sh-class power on Online via RPC orchestration (not “document refusals”).
2. Bulk CSV/XLSX import (`/data-import`) with dry-run + phrase confirm on commit.
3. Power Ops recipe engine (`purge_journal_entries` = button_draft→unlink flagship).
4. Odoo colour tokens (`#714B67`) + FormCanvas; view overwrite/stock polish require ConfirmAdvanced; access/rule rollback implemented.
**Why:** Operator pain is UI one-by-one and missing bulk tools, not missing API rights.
**Rejected:** Treating Online UI limits as API impossibles; mutating stock primaries without phrase.

### 2026-07-27 — Phase D: related_write + ACL matrix + change journal + config
**Decided:**
1. `related_write` is a first-class safe automation (`update_path` = `relation.field` via `object_write`).
2. Access matrix (groups × models) is now in scope (supersedes earlier “reject full matrix” Phase-1 deferral).
3. Change journal = connection snapshots + Undo; audit logs secondary/filtered.
4. Settings page covers company, sequences, field-label CSV, and app menu builder — not full i18n packs.
5. ModuleSpec / Generate UI **auto-applies** safe automations by default (`apply_automations=True`): related_write, update_field/object_write, activity when `activity_type_id` present.
**Why:** Car-rental / day-2 ops need related writes and ACL grids; drafts should not leave related_write as manual-only.
**Rejected:** Full `ir.translation` UI as v1; visual menu builder / multi-env promote in this pass.
**Supersedes:** Same-day rejection of auto-applying related_write from Generate UI.

### 2026-07-27 — Multi-version Odoo = plan only; v1 stays 19
**Decided:** Draft `docs/MULTI_VERSION_ODOO_PLAN.md` (capability matrix + adapters + Docker matrix). Do not unlock non-19 writes until M0/M1 extract and an explicit MEMORY stack-lock change.
**Why:** Cross-major automation/view drift is real; claiming “any version” without adapters is unsafe.
**Rejected:** Silently relaxing AGENTS.md “Community 19 only” without gates.

### 2026-07-27 — M0 compat extract shipped (still 19-only runtime)
**Decided:** Add `packages/odoo-client/compat/` with `CapabilityId` + 19-only registry; extract automation encoding + view-inject naming into `adapters/automation_v19.py` and `adapters/views_v19.py`. `OdooClient.connect()` still refuses non-19.
**Why:** Plan M0 prerequisite before multi-version; routers stay facade-only; encoding lives in one place for future majors.
**Rejected:** Registering 16–18 capability sets or unlocking non-19 writes in this pass.

### 2026-07-27 — M1 capability probe UI (still 19-only writes)
**Decided:** Expose registry-backed `capabilities` on `ConnectionOut` / `ProbeResult`; show badge + expandable checklist on `/connect` and connection browse. No live per-feature RPC probes in M1.
**Why:** Operators see what the platform claims for this major before first write; grey-out of builder features waits until non-19 majors exist.
**Rejected:** Overloading Power Ops recipe probe; persisting capabilities in DB (derived from `server_version`).

### 2026-07-27 — Report lite → module zip export
**Decided:** Live export packages custom QWeb PDFs (`x_*` models + `custom.*` keys) into `report/reports.xml` via existing `ReportSpec`; generator path renamed from `loan_reports.xml`.
**Why:** Round-trip report lite into Path C (sandbox → promote) without a second report model.
**Rejected:** Emitting paperformat records / full raw arch passthrough in this pass; unlocking M2 multi-version without MEMORY change.

### 2026-07-27 — Phase D+ ops surfaces fully wired
**Decided:**
1. Settings covers company (expanded), sequences CRUD, mail templates, activity types, lang-scoped translation CSV.
2. Visual menus/actions at `/menus` (tree + bind + delete confirm).
3. Report lite at `/reports` (QWeb create/edit + paperformat).
4. Multi-env at `/pipelines`: sandbox → staging → prod; prod requires prior staging hop for same zip sha256.
5. Industry seed packs on Bulk Import (car_rental, library, clinic, field_service, partners, products).
**Why:** Operators asked for full (non-stub) day-2 parity beyond matrix/related_write.
**Rejected:** Stub pages; treating Online UI limits as blockers for promote hops.

### 2026-07-28 — B1 Online SaaS / Enterprise packaging copy (closed)
**Decided:** Canonical packaging copy in `docs/USER-GUIDE.md` § Odoo Online / Enterprise and aligned `docs/STUDIO_PARITY_BY_MAJOR.md` decision lock #4: **warn-only** banner UX (probe + Designer), **public ORM/RPC metadata only** (Community-like caps per major; **never** Studio/`web_studio`), Online **version follows host** (packaging wording only), **Power Ops RPC-first** regardless of Online vs self-hosted.
**Why:** CARD B1 — one operator-facing story without implying Studio parity or a fake Online capability tier.
**Rejected:** Editing `docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md` for this card; unlocking **16** to GA.

### 2026-07-28 — B2 FULL-SCALE Library 19-primary (confirmed)
**Decided:** `docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md` §1.3 unchanged — platform multi-version live; Library reference vertical smoke, UAT, and CI gates remain **19-centric** (19-primary).
**Why:** CARD B2 confirmation; compat layer serves other majors without moving Library full-scale gates off 19.

### 2026-08-03 — REM-14 live-evidence deviations
**Decided:**
1. Staged live run uses `qwen3:8b` with 300s step timeout (`docs/research/staged_run_fixed_2026-08-03.json`, `"mode":"live"`).
2. Stripe extra-slot checkout already `mode=subscription` — no SKU rename (A7 satisfied as-is).
3. `test_inspection_checklist_live_odoo19` skipped — docker-19 lacks `project` module; unit + sandbox paths cover AI-8.
4. Deploy-stack `LAUNCH-1` partial — `/health` OK but `/api/billing/plans` 404 on deploy API image (log: `docs/research/launch_compose_smoke_2026-08-03.log`).
5. Playwright e2e harness requires fresh build with `NEXT_PUBLIC_E2E=1` — reusing deploy :3000 serves 404 on `/e2e/*`.
**Why:** Honest live gates without fixture relabeling; deviations are env gaps not code stubs.

---

## GA decision log template (TRUST-9 — copy for each GA review)

**Date:** YYYY-MM-DD  
**Reviewer:**  
**Evidence sources:** `GET /api/admin/trust-telemetry`, `GET /api/admin/ga-criteria`, partner weekly attestations, `test_safety_route_registry` CI green

| Criterion | Threshold | Observed | Pass? |
| --- | --- | --- | --- |
| Beta partner workspaces | ≥ `BETA_GA_MIN_WORKSPACES` (default 8) | | |
| Weeks active per workspace | ≥ `BETA_GA_MIN_WEEKS` (default 4) | | |
| Unrecoverable-data incidents | 0 | | |
| SafetyGate bypasses | 0 | | |

**Telemetry roll-up (beta partners only):** bulk runs __ · refusals __ · aborts __ · restores __ · anomaly trips __

**Decision:** ☐ Proceed to GA (`PRODUCTION_WRITE_MODE_GA_UNLOCKED=1`) · ☐ Extend beta · ☐ Block — reason:

**Follow-ups:**

### 2026-08-06 — Wave 17 ingest vision tier
**Decided (superseded 2026-08-06 evening):** was `vision_tier: deferred`.

### 2026-08-06 — Vision tier product-owner unlock (local_ok)
**Decided:** `vision_tier: local_ok`. Code path for PDF scans + image OCR is production-quality and gated by `INGEST_VISION=off|ollama` (default still off). Operator enables with `ollama pull qwen3-vl:8b` + `INGEST_VISION=ollama`. **EU commercial deploy** still requires separate Tongyi Qianwen agreement — do not market vision OCR to EU customers until that agreement is filed; non-EU / local-only use is unlocked.
**Why:** Product owner ordered full Universal Ingest fidelity; vision code must not remain a stub.
**Rejected:** Cloud OCR; shipping with vision default-on.
**Operator unlock:** `ollama pull qwen3-vl:8b` + `INGEST_VISION=ollama`.

### 2026-08-06 — Operator unlock executed; Tongyi EU legal remains owner-only
**Decided:** Local vision operator path is complete (model pull + `INGEST_VISION=ollama` in local `.env`; compose wires `INGEST_VISION` / `OLLAMA_BASE_URL`). **Agents cannot execute Tongyi Qianwen commercial/EU license agreements** — that remains a human/legal action before marketing vision OCR to EU customers. Product code stays default-off in `.env.example` / deploy unless operator sets `INGEST_VISION=ollama`.
**Why:** Finish all technical operator gates without falsely claiming a legal contract was signed.
**Rejected:** Pretending EU commercial vision is cleared by a code change.

### 2026-08-10 — Dual LLM paths: Draft Studio vs Universal Ingest
**Decided:** Two independent Ollama model lanes — do not conflate or share tuning between them.
| Lane | Env vars | Model | Purpose |
|------|----------|-------|---------|
| Draft Studio | `AI_MODEL_BULK`, `AI_MODEL_REASONING`, `OLLAMA_MODEL` | `qwen3:8b` (text) | ModuleSpec generation, quality/depth/critique |
| Universal Ingest | `INGEST_VISION`, `INGEST_VISION_MODEL` | `qwen3-vl:8b` (vision) | Single + batch document upload OCR (scanned PDFs, images) |

**Why:** Product owner requires batch document upload/processing to work very well; vision OCR is a first-class feature, not an afterthought. Draft timeout tuning must never swap or starve the VL model.
**Rejected:** Using `AI_MODEL_REASONING` for ingest vision; defaulting ingest vision off in operator `.env` when VL is installed.
**Operator:** `ollama pull qwen3-vl:8b` + `INGEST_VISION=ollama` in `.env`; verify via `GET …/ingest/vision/status`.

### 2026-08-10 — Semantic apply-readiness + retail pack source hygiene
**Decided:** Top-3 semantic fixes run in `run_apply_readiness_pass` (selection/domain align, branch dedup, inventory reason M2O + search filters); scorecard flags domain/selection drift; `retail_supermarket` pack seeds clean branch (`x_address_id` + `x_country_id`, no char dupes), workflow `state_field`s, and `x_inventory_reason` / `x_inventory_adjustment` with `x_reason_id`.
**Why:** Honest grade gap was validators green but semantics/UX not — fix at merge source and after enrich, not only in critique.
**Rejected:** Relying on LLM/critique alone to drop `sent`/`paid` domain allowlists or text `x_reason` fields.
