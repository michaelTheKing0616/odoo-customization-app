# Wave 7 — CMP: compendium completions (Document 3, every remaining item)

Shared context: compendium (Doc 3) mechanisms are stable across 16–19; per-major differences
go through `packages/odoo-client/compat`. Live verification against docker Odoo before any
RPC claim (ERRORS.md #7). UI additions land on the UIX kit.

---

## CMP-1 — Manifest ordering, xpath completeness, ir.sequence verification

TASK: Regression-proof three generator correctness contracts.

INPUT: `packages/module-generator` (templates + spec), `spec_apply_ui.py`, views router.

CHECKLIST:
- [ ] Manifest data-file order test: generated modules always load security → data
      (sequences) → views → menus → reports (topological contract) — test asserts order for
      a spec containing all types; fix generator if violated.
- [ ] XPath positions: `move` and `$0`-wrap support verified in inherit-view creation +
      xpath preview endpoint (add if missing in odoo-client view_arch helpers); tests with
      real archs on docker 19.
- [ ] ir.sequence: workflow models in generated modules get sequence + default-ref field
      wiring (REF/0001 per compendium §10) — verify existing emission; add if missing; live
      test: install exported module in sandbox, create record, assert reference populated.
- [ ] Live-apply parity: spec_apply path creates the sequence via RPC too (config_ops
      sequences reuse).

DONE MEANS: all four contracts covered by named tests, green incl. sandbox install test.

DO NOT: reorder existing template blocks beyond the contract fix.

GATE: `uv run pytest tests/ -q -k "module_generation or spec_apply"` + sandbox gate script.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## CMP-2 — Widget coverage + sample data + conditional attrs

TASK: Complete the compendium §4 widget catalog in builder/designer and the conditional
expression builder; add `sample="1"`.

INPUT: builder + designer pages, `ai_enrich.py` (default arch generation), DomainBuilder,
odoo-client field/view helpers.

CHECKLIST:
- [ ] Field builder widget options per ttype: email/phone/url (char), float_time/progressbar/
      percentage (numeric), radio/priority (selection), checkboxes/many2many_tags (m2m),
      many2one_avatar (m2o), image with size options, pdf_viewer/signature (binary) —
      persisted into view arch on inject; designer inspector exposes the same curated set.
- [ ] Related (read-through) field creation UX: pick relation path (m2o chain browser, depth
      2) → creates related field via RPC with correct `related=` — compendium §4's "surface
      linked info without joins".
- [ ] Conditional attrs: required/readonly/invisible each accept a domain expression built
      with DomainBuilder (visual), emitted as modern syntax on 17+ (`invisible="expr"`) and
      `attrs=` on 16 via compat adapter — VERIFY per major live; designer inspector +
      builder both.
- [ ] `sample="1"` toggle on generated list/kanban/graph/pivot views (generator + designer
      view settings).
- [ ] Monetary correctness: adding a monetary field auto-ensures currency_id companion
      (builder + generator rule).
- [ ] Tests: widget emission matrix, attrs syntax per major (16 vs 17+), related-field live
      smoke, monetary rule.

DONE MEANS: matrix tests green; live smoke on 19 + 16 attrs check (16 experimental —
capability-gated failure acceptable and recorded).

DO NOT: expose the full internal widget registry (curated + Advanced only, §15 guidance).

GATE: pytest + RPC smoke 19 (+16 attrs probe) + designer e2e.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## CMP-3 — Niche widget palette + trigger capability checks + live palette extraction

TASK: Compendium §15 widgets in the designer, §7 trigger-per-major verification, §20 live
brand extraction for preview surfaces.

INPUT: designer palette, automations router, `preview_proxy.py`, capabilities.

CHECKLIST:
- [ ] Palette additions (curated list with recommended-per-type): kanban_state,
      color (fixed 11-color palette — names/indices stable contract; hexes sampled live),
      boolean_favorite, boolean_toggle, many2many_tags_avatar, many2one_avatar_user,
      activity_exception (list/kanban), state_selection; each with correct arch emission +
      any required supporting field auto-suggested (e.g. color integer field).
- [ ] Automation trigger availability per major verified live (webhook + on-UI-change
      recency): probe table recorded 16/17/18/19; builder offers only supported triggers per
      connection (matrix rows).
- [ ] Live palette extraction: on connect, fetch the instance's compiled web assets CSS,
      extract primary/accent custom properties (best effort, cached); used ONLY to theme
      Odoo-preview surfaces (designer canvas chrome, kanban preview) so previews resemble
      the customer's instance — our app chrome stays on our tokens; graceful fallback to
      neutral Odoo-ish defaults when extraction fails.
- [ ] Tests: arch emission per widget, trigger gating per major (fixtures), extraction parser
      on fixture CSS + live smoke.

DONE MEANS: palette renders + emits correctly (designer e2e); trigger probe table in return;
extraction demonstrably themes the preview on docker 19.

DO NOT: theme our own app from extracted colors; hardcode the 11 palette hexes as truth
(names/indices only).

GATE: pytest + designer e2e + RPC/CSS smoke 19.

RETURN: ≤10 lines + trigger probe table.

DEVIATIONS: conservative + log.

---

## CMP-4 — Visual QWeb report designer

TASK: Drag-drop print-layout designer producing QWeb report templates (compendium §8),
reusing the designer architecture.

INPUT: designer components (canvas pattern), `routers/reports.py`, `report_export.py`,
module-generator report templates.

CHECKLIST:
- [ ] Canvas: print-page frame (paperformat-aware dimensions), block palette — heading,
      field value (t-field with model-field picker), label+field row, table over an o2m
      (t-foreach with column picker), image (logo/record image), divider, free text,
      page break; `web.external_layout` wrapper toggle (header/footer preview placeholder).
- [ ] Output: valid QWeb template + ir.actions.report record via existing reports router;
      also exportable into ModuleSpec (report_export path) for module inclusion.
- [ ] Inherit mode: extend an EXISTING report (e.g. invoice) — pick base report, xpath
      anchor picker from parsed template, position, added block; emits inherit template
      (compendium §8 inheritance).
- [ ] Live preview: render via the working per-major render path (BLK-8's probe) into an
      inline PDF/HTML preview panel.
- [ ] Translation note surfaced (t-lang variant guidance link) — implementation of variant
      generation optional CHECK: if trivial with existing translation config_ops, include;
      else mark explicitly for CMP-11 i18n card.
- [ ] Tests: template emission (golden QWeb fixtures), inherit emission, live render smoke
      on 19; designer e2e for the canvas.

DONE MEANS: build a rental-agreement-style report visually, render it live on 19, export it
into a module — all in one e2e-recorded flow.

DO NOT: hand users raw QWeb first (visual first, code view secondary tab); break existing
reports CRUD.

GATE: pytest + RPC smoke 19 + e2e + vision-verify screenshots.

RETURN: ≤10 lines + screenshots.

DEVIATIONS: conservative + log.

---

## CMP-5 — Approval rules: button gating (Grok 4.5 card)

TASK: Studio-style approval rules on any button/action — Community-safe implementation, with
the Enterprise `studio.approval.rule` driver (TIER-5) as native mode when detected.

INPUT: TIER-5 driver, actions router (smart buttons/server actions), automations, access,
snapshots; compendium §17 semantics.

CHECKLIST:
- [ ] Community-safe engine: `x_approval_rule` data model IN OUR APP DB (not target) defining:
      target model + button/method, steps [{approvers: users/groups, exclusive, order,
      condition domain}]; enforcement via a generated server action wrapper on the target —
      the gated button is rebound to a wrapper server action that checks approval records
      (`x_approval_entry` records on the target instance via a generated helper model in an
      exported module, OR mail.activity-based tracking for the live-metadata path — decide:
      live path uses activities + a JSON param on ir.config_parameter for entries; module
      path generates a proper approval entry model; BOTH documented, live path is v1
      default). Unauthorized click → blocked with message + activity created for approvers
      (compendium §17 behavior); approve/reject logged to chatter.
- [ ] Semantics: exclusive steps (approver of step A can't approve step B on same record),
      ordered steps, conditional steps (domain evaluated per record).
- [ ] Enterprise mode: when web_studio detected, the SAME UI drives TIER-5's
      studio.approval.rule CRUD instead — one UI, two engines, engine badge shown.
- [ ] UI: Approvals page (nav Build group) — rule list, rule editor (model → button
      discovery via BLK-1's engine, steps editor), entries/audit view.
- [ ] Snapshot + rollback support for rule creation (both engines).
- [ ] Tests: semantics unit suite (exclusive/order/conditional), live smoke: gate a button
      on an x_ model on docker 19, verify block + activity + approve-then-pass flow;
      Enterprise engine fake-tested (live conditional per TIER-5's env).

DONE MEANS: full block→request→approve→proceed loop demonstrated live on 19 (Community
engine); one UI switching engines correctly.

DO NOT: consult Studio source; store approval state only in our app DB for the live path
(the TARGET instance must carry the evidence — activities/chatter — so Odoo users see it).

GATE: pytest + RPC smoke 19 + e2e.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## CMP-6 — Image pipeline

TASK: Compendium §14 conventions: multi-resolution variants, avatar vs content conventions,
bulk image import.

INPUT: builder (image field creation), generator field emission, data_import, designer.

CHECKLIST:
- [ ] Generated modules: image fields emit base `image_1920`-style max field + related
      resized variants (`image_128`/`image_256`) when the model has kanban/list usage —
      generator rule + spec flag; live-metadata path: create variants as related/computed
      per major capability (probe; where live computed isn't possible via RPC, document
      honestly — module path covers it).
- [ ] Kanban/list arches reference the small variant, form the large (enrich rule).
- [ ] Avatar convention: profile-like models (staff/partner-ish, heuristic + user choice)
      get `oe_avatar` class + widget image; content photos plain widget.
- [ ] Bulk image import: data-import extension — CSV/zip of images matched to records by
      name/code column → base64 RPC writes; progress + BulkResultTable; size guard
      (downscale client-side or via Pillow — Pillow already available? verify; if new dep,
      list it).
- [ ] Tests: generator emission fixtures, enrich arch tests, bulk import fake + live smoke
      (2 images onto x_ records on 19).

DONE MEANS: exported module shows variant fields installed in sandbox; kanban uses small
variant; live bulk import works.

DO NOT: fetch remote URLs server-side in v1 (upload only); skip the size guard.

GATE: pytest + sandbox gate + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## CMP-7 — Property fields full parity (probe-verified)

TASK: Full property-definition builder to the maximum each major verifiably supports
(compendium §18; promoted from deferral by user).

INPUT: config_ops properties list, odoo-client, introspection; TIER-1 matrix row hook.

CHECKLIST:
- [ ] Capability probe per major 16/17/18/19: does `ir.model.fields` accept ttype
      `properties`/`properties_definition` via RPC create? does writing definitions on the
      parent work? Record the truth table (this is the card's first task; everything below
      is gated on its results).
- [ ] Where supported: builder flow — create a properties field on a child model bound to a
      parent m2o (definition holder); definition editor UI (property list: name, type
      [char/bool/int/float/date/selection/tags/m2o/m2m], selection options, default) writing
      `properties_definition` on parent records via RPC.
- [ ] Guidance UX: the §18 decision helper — "same field everywhere → regular field;
      different per parent → property" copy in the builder chooser.
- [ ] Matrix row updated from probe results; unsupported majors show the honest Callout.
- [ ] Generator: properties fields representable in ModuleSpec + emitted for supported
      targets.
- [ ] Tests: probe harness, definition write/read live smoke on 19 (+18), builder e2e.

DONE MEANS: probe truth table recorded; on supported majors a full define→set-values flow
works live; unsupported majors gated honestly.

DO NOT: assume availability anywhere (probe is law); fake parity on majors that fail probes —
report instead.

GATE: pytest + RPC smoke 19+18 + probe table in return.

RETURN: ≤10 lines + truth table.

DEVIATIONS: conservative + log.

---

## CMP-8 — Connect to Invoicing (safe financial pattern)

TASK: The compendium §19 link-only billing pattern as a product flow.

INPUT: PCM (tier-1 enforcement), generator, builder, actions router.

CHECKLIST:
- [ ] Flow on any custom workflow model: "Connect to Invoicing" — adds invoice_ids O2M
      (m2o `x_invoice_origin_id`-style on account.move? NO — link via a m2o on the custom
      model + smart button, or o2m via a dedicated m2o field added to account.move is
      FORBIDDEN (tier-1 write). Correct pattern: custom model gets `x_invoice_ids` m2m or
      stores refs; module path: proper o2m with inverse m2o added by the module on
      account.move is standard Odoo practice — ALLOWED in module path with explicit review
      note since modules are developer artifacts; live-metadata path: m2m only. Document
      both, implement both).
- [ ] "Create draft invoice" server action: calls standard account.move create with lines
      from mapped fields (partner, amount/description mapping wizard) — creates DRAFT only,
      never posts; tier-1 rule satisfied (using standard flow, not new logic).
- [ ] l10n detection: prompt verifies a fiscal localization is installed for the company
      country before offering (matrix/introspection); missing → honest Callout, no
      generation.
- [ ] Manifest: module path adds `account` dependency automatically.
- [ ] Smart button (invoice count) both paths; PCM tests confirm no violation triggers.
- [ ] Tests: mapping wizard, draft-invoice live smoke on 19 (account installed in docker
      stack per existing ensure-account scripts), guardrail non-violation named test.

DONE MEANS: live flow produces a draft invoice linked to an x_ record on 19; PCM suite green.

DO NOT: post/validate invoices; touch taxes/accounts config; bypass PCM.

GATE: pytest + RPC smoke 19 (account module).

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## CMP-9 — Generic barcode scanning (promoted by user)

TASK: Scan-into-any-field, two lawful paths: in-app camera scanning (all tiers) + exported
OWL widget module (sh/on-prem).

INPUT: new OSS dep `@zxing/browser` (Apache-2.0) web-side; module-generator assets emission;
mass-edit endpoint (BLK-2) for writes.

CHECKLIST:
- [ ] In-app scanner: web component (camera permission flow, torch toggle where supported,
      barcode + QR formats) → "Scan to field" surfaces: (a) Bulk Suite: scan → find record
      by field match → open/edit; (b) single-record tool: pick model+field, scan, write via
      RPC; mobile-viewport tested.
- [ ] Exported widget module: our ORIGINAL OWL field widget (JS asset in generated module,
      wraps the same zxing lib bundled locally, no CDN) providing `widget="x_barcode_scan"`
      on char fields; manifest assets wiring; README section explaining install +
      that it's our add-on, not native Odoo (Doc 3 §16 honesty).
- [ ] Tier gating: module path hidden for Online targets (matrix), in-app path everywhere.
- [ ] Legal hygiene: license headers (our code LGPL-3 consistent with module license, zxing
      Apache-2 attribution in module README).
- [ ] Tests: scanner component unit (mock stream), widget module sandbox install + form
      render smoke (asset loads without console error — sandbox gate + screenshot),
      write-path test.

DONE MEANS: in-app scan writes a value to an x_ record live; exported module installs in
sandbox with the widget rendering.

DO NOT: ship CDN-loaded JS in modules; claim native-Odoo status in any copy.

GATE: pnpm tests + sandbox gate + RPC smoke.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## CMP-10 — Standalone approval processes (Grok 4.5 card, promoted by user)

TASK: Full request/approve workflow processes (Approvals-app class): multi-level chains,
minimum-approvals thresholds, role-based approvers — our own implementation + EE approvals
RPC mode.

INPUT: CMP-5 engine (extend), TIER-5 detection, app_templates pattern.

CHECKLIST:
- [ ] Process template: an installable/live-appliable "Approval Requests" mini-app
      (x_approval_request: type, requester, amount/subject fields, state workflow
      draft→submitted→approved/refused; x_approval_type: chain definition [level, approvers,
      min_approvals, role-group], conditional levels by domain) — generated via our own
      ModuleSpec (dogfooding the generator) + offered as an app template in the wizard.
- [ ] Chain semantics: sequential levels, min-approvals-per-level, refusal short-circuits,
      full chatter trail, activities to current-level approvers.
- [ ] EE mode: when the Enterprise `approvals` module is installed, the UI drives ITS models
      via RPC (approval.category/approval.request — field names live-verified per TIER-5's
      protocol, pending-live-verify flags where no EE instance available).
- [ ] Distinct from CMP-5 in UI: "Button approvals" vs "Approval processes" tabs on the
      Approvals page, cross-linked explainer (compendium §17's distinction).
- [ ] Tests: chain semantics suite, template applies live on 19 + full request→2-level
      approve flow smoke, EE fake-suite.

DONE MEANS: live two-level approval with min-approvals=2 demonstrated on docker 19 via our
template; EE mode gated + fake-tested.

DO NOT: consult Enterprise source; merge the two approval concepts into one muddled UI.

GATE: pytest + RPC smoke 19 + e2e.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## CMP-11 — Multi-company, i18n depth, Documents integration (promoted by user)

TASK: Compendium §21's remaining research items as features.

INPUT: access router (record rules), config_ops (translations), TIER-5 (documents driver),
generator security emission.

CHECKLIST:
- [ ] Multi-company: generator + access UI templates — company_id field rule pack
      (m2o res.company with default), record-rule template `['|',('company_id','=',False),
      ('company_id','in',company_ids)]` (verify exact modern syntax per major live),
      multi-company field-visibility guidance; wizard option "multi-company aware" on
      drafts adding these to workflow models.
- [ ] i18n depth: translation export/import round-trip for our generated artifacts (PO-style
      via RPC where supported — probe per major; else field-level translation write UI
      extension of existing config_ops translations); report t-lang variant emission for
      CMP-4 reports (invoice-partner-language pattern).
- [ ] Documents integration: when `documents` module detected — per-model "attach to
      Documents folder" config (folder picker via TIER-5 driver), generated workflow rule
      suggestion (module path); honest gating otherwise.
- [ ] Tests: rule template emission per major, translation round-trip live smoke 19,
      documents fake + conditional live.

DONE MEANS: multi-company draft option produces installing, rule-correct module (sandbox);
translation round-trip proven live; documents path gated + tested.

DO NOT: build a full DMS; assume rule syntax across majors without live check.

GATE: pytest + sandbox gate + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.
