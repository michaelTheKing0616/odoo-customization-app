# Ingenium Builders: SPEC

Source: `IDEA.md` (approved by Tope). Scope: one shared view engine, then View Designer (priority), then Reports/PDF, then App Studio and Draft Studio on the same engine.
Design Read [taste] [imp]: *Operate-mode builder for Odoo admins. Light by default with the existing dark theme, one teal accent, real Odoo render as the hero, calm and fast motion, Figma-grade precision.*
Dials [taste]: DESIGN_VARIANCE 3 / MOTION_INTENSITY 3 / VISUAL_DENSITY 7 (dense tool, trust-first).
References (patterns only, never copied) [playbook §1 Step 3, §12 "Copy vs extract"]: Figma editor (primary: canvas, layers, inspector, keyboard, comments); Webflow Designer (structure-true nesting and drag rules); Framer (instant preview, motion feel); Stripe dashboard (reports, PDF and data screens). Never Linear.

Standing rules this spec obeys: AI proposes, code authorizes. Stock Odoo first. Meaning, not word lists. Plain language on screen. Every stage verified live on Odoo 17, 18, 19 and 20.

---

## 1. What exists today (build on it, don't rebuild)
| Area | Existing code (apps/web/src, apps/api/app) | Spec action |
|---|---|---|
| Arch parsing | `parse_form_arch/list/kanban` (used by `preview_views.py`), `/views/parse`, `/views/preview` | Becomes engine parser core; add QWeb + version adapters |
| React Odoo render | `components/odoo-preview/*` (`OdooViewRenderer`, FormView, ListView, KanbanView, Notebook, StatusBar...) | Becomes engine "edit render"; extend node coverage |
| True Odoo render | `routers/preview_proxy.py` (same-origin iframe), `DesignerLiveCanvas` live/structure modes | Becomes engine "proof render" |
| Inherit edits | `/views/xpath/preview`, `/designer-inherit/repair`, `/designer-inherit/unlink`, `XPathInheritPanel`, `lib/xpathLocator` (isFragile / isPositional) | Becomes engine edit compiler + safety lint |
| History | `lib/designerHistory` (cap, coalesce, publish mark), `useDesignerHistory` | Extend: named versions, compare, revert |
| Designer UI | `components/designer/*` (Shell, Toolbar, Rail, StructuralCanvas, AdvancedStructureCanvas, FieldInspector, FieldPalette, OverlayEditor, PointerGhost) | Re-shell into the Figma-led layout (section 4); keep logic hooks |
| Reports | `report_design.py` (block spec to QWeb, `INHERIT_SLOT_MAP`, grounding, unsafe gate), `/reports/design/preview` with `odoo_client.report_render.render_report_pdf`, `/paperformats`, `ReportDesigner`, `ReportCanvas`, `QwebPaperPreview` | Keep compiler; add live proof pane, checks, compare |
| Studio previews | `StudioFormPreview`, `DraftOdooPreview`, `StockAppInstallCard`, `HostInstallDialog` | Swap to engine render in "draft mode" (stage 4) |
| Metadata | `odoo_snapshot.py` (metadata only, 17-20 supported) | Source for fields, groups, versions |
| Tokens / libs | `styles/globals/tokens.css`, `theme.css`; motion 14, cmdk, sonner, lucide-react, Tailwind 4 | Reuse; add builder tokens (section 6) |

## 2. Shared view engine (foundation)
**Job:** show any Odoo form, list, kanban or QWeb report exactly as Odoo will, with real records, and turn every visual edit into the smallest safe inherited view.

### 2.1 Pipeline
1. **Load.** `get_views` (fallback `fields_view_get` where needed) for model + view type returns the *combined* arch Odoo actually uses, plus `fields_get`. Record its major version from the snapshot.
2. **Normalize.** Version adapter maps the arch into one internal tree (`ViewNode`, stable node ids derived from `name`/`string`/path, never array index). Adapter table per major (17/18/19/20) is filled from live probes on disposable DBs, not assumed. Known example: `<tree>` vs `<list>` root naming. Unknown nodes render as a labelled "Odoo element" block and stay editable as a whole, never dropped.
3. **Render (two paths, one truth).**
   - *Edit render:* React (`odoo-preview`) draws the tree with Odoo's real CSS classes inside `OdooPreviewScope`, so selection, drag and badges are possible.
   - *Proof render:* Odoo itself (proxy iframe for views, `render_report_pdf` for reports). It is the reference for fidelity.
   - *Fidelity check (code):* after every publish to preview, re-read the combined arch from Odoo, normalize, and diff against the expected tree. Any difference blocks Publish and shows "Odoo shows this differently" with the node highlighted.
4. **Live records.** `search_read` of only the fields on the view, limit 80, through the user's own connection; held in browser memory, never stored. "Longest" and "emptiest" record are picked by code (sum of rendered text length, count of empty visible fields) over that sample. See open decision 1.
5. **Edit ops.** Every UI action emits a typed op: `move`, `insert_field`, `remove_node` (becomes `invisible="1"` on stock nodes, true removal only on Ingenium-added nodes), `set_attr`, `wrap` (group / page / notebook), `set_condition`, `set_access` (groups).
6. **Compile (code only).** Ops fold into one minimal inherit view per (model, base view, Ingenium layer):
   - Anchors prefer `//field[@name=...]`, then named `group`/`page`/`button`; positional anchors are refused by `xpathLocator.isPositional`, fragile ones warn.
   - Attribute changes use `position="attributes"`; never `replace` on root (`refuse_root_replace` already exists); `replace` on stock nodes is refused.
   - Redundant ops collapse (move A then move A back = nothing).
   - Conditions compile to Odoo 17+ inline expressions (`invisible="stage_id.is_won"`), never `attrs`.
7. **Validate before anything touches the DB.** Field names against `fields_get`, groups against `res.groups`, QWeb through `qweb_unsafe_gate`, then a dry combine via `/views/xpath/preview`. Fail = Publish disabled with a plain reason.
8. **Publish = preview, then promote.** Write the inherit view with `active=False` and a named Ingenium key, run the fidelity check, then activate. Revert = deactivate (one click) or unlink (confirm). Stock views are never written.

### 2.2 Engine API (new or extended, `routers/views.py`)
`POST /views/engine/load` (arch + fields + version + node ids) · `POST /views/engine/records` (sample, stress picks) · `POST /views/engine/compile` (ops to inherit arch + lint) · `POST /views/engine/publish` (preview, check, promote) · `POST /views/engine/revert` · `GET /views/engine/history`. Same shapes for reports under `/reports/engine/*`.

## 3. AI steps (proposal only) [playbook §1 SPEC rule: prompts word for word]
AI output is always a *proposal object*. Code validates it; the user sees a before/after diff and presses the button. AI never calls compile or publish.

**3.1 Plain-English edit** (command bar). Model: gemini-3.8-flash on Vertex, server-side only (key lives in the API, never the page). Output: `{"ops":[...], "unclear": string|null}`.
System prompt, verbatim:
> You turn one request about an Odoo screen into edit operations. You receive the screen as a JSON tree of nodes with ids, and the model's field list with names, labels and types. Return only JSON matching the schema. Use only node ids and field names that appear in the input. Never invent fields, groups, records or facts not in the input. If the request needs something that is not in the input, return no ops and explain in "unclear" in one plain sentence a non-technical person understands. Prefer the smallest change that does what was asked. Do not change anything the request did not mention.

**3.2 Condition from words** ("Show when Stage is Won"). Output: condition AST (reuse `ai_constraint_ast` / `DomainBuilder` shape).
System prompt, verbatim:
> You turn one sentence about when a field should be shown, hidden, required or read-only into a condition tree. You receive the sentence and the model's field list with names, labels, types and selection values. Return only JSON matching the schema. Use only fields and values from the input. Never invent facts not in the input. If the sentence is ambiguous, return the two most likely readings, each with a one-line plain description, and no others.

Code then: checks every field and value, type-checks operators, compiles to the expression, and renders the plain sentence back from the AST (the user approves the sentence code wrote, not the AI's wording). Meaning is read by the model plus validator, never by phrase lists.

Everything else (suggestions, layout checks, page-break warnings, version flags) is deterministic code.

## 4. View Designer (priority)
### 4.1 Layout (Figma-led, Webflow structure) [jk-layout] [imp/craft-floor]
```
┌ Top bar 48px ─────────────────────────────────────────────────────────────┐
│ ◂ Contacts / Form    ‹ Record 3 of 80 ›  Longest  Emptiest │ As: Admin ▾ │
│                      Desktop Tablet Phone   Odoo 17 18 19 20│ Preview  [Publish changes]│
├ Left 264px ────┬ Canvas (desk) ─────────────────────────────┬ Right 304px ──┤
│ Layers│Fields│+ │  real Odoo render, zoom 50-200%            │ Properties     │
│ ▸ Sheet        │  selection outline + node label            │ Show and hide  │
│   ▸ Group Info │  drop line / nest box while dragging       │ Who can see    │
│     Phone ●    │  ● condition badge  [lock] restricted badge    │ Checks (3)     │
│   ▸ Notebook   │  pinned comment dots (C to toggle)         │                │
└────────────────┴────────────────────────────────────────────┴────────────────┘
```
- One filled primary per view: **Publish changes** [jk-colors]. Preview is secondary.
- Phone width (<768px): canvas only, panels become bottom sheets with medium/large detents; editing limited to properties and conditions (drag needs pointer). [apple-design-hig sheets]
- URL holds state: record id, role, device, version, selected node, open panel [vercel-wig].

### 4.2 Features to components
| Feature (IDEA) | Behaviour | Code authority |
|---|---|---|
| Live canvas, flip records, stress test | ‹ › flips the sample; Longest / Emptiest jump to code-picked records | engine 2.1.4 |
| Preview as role | Role menu lists real groups; hidden nodes fade to 40% with a "Hidden for Sales rep" chip; read-only shows a lock | Evaluate `groups=` and conditions in code; labelled "Based on group rules" (we cannot log in as that user) |
| Plain-words conditions | Inspector "Show and hide": type a sentence or build with dropdowns; badge ● on the canvas node | 3.2 + compiler |
| Version view | 17 18 19 20 toggle; split view shows two side by side; flags "This won't work on Odoo 17: field not found" | Compile per adapter, validate against stock arch catalogue captured from disposable DBs per version |
| Devices | Desktop 1280 / Tablet 820 / Phone 390 frames on the desk, Odoo's own responsive classes | render width only |
| Upgrade-safe check + diff | Checks tab: anchors fragile? replaces stock? Diff = side-by-side tree with added/moved/hidden markers; raw XML only under "Advanced" (existing `XPathInheritPanel`) | lint in compiler |
| Usage suggestions | "Rarely filled: Fax (2% of 1,204)", "Most used fields first", "Required but hidden: Customer" | `read_group` counts only, no record contents; one-click fix emits ops |
| Layout checks | Too many fields in one tab (>12), long unlabeled fields, labels missing, tab order breaks reading order, contrast of custom colours | rules in code, each with one-click fix |
| History | Undo/redo (⌘Z/⇧⌘Z), named versions, compare any two, revert | extended `designerHistory` + engine history |
| Publish | Preview (inactive view + fidelity check) then promote; Sonner toast "Published" with Undo for 10 s [a-fd name continuity] | 2.1.8 |
| Comments | Pin to node id; survive moves; resolve/reopen | Ingenium DB, never Odoo |
| Command bar | ⌘K (cmdk): jump to field, run any action, or type an edit in plain English (3.1) | AI proposes, diff, user applies |

### 4.3 Direct manipulation rules (Webflow-style structure)
- Drag targets follow Odoo nesting: fields into groups/pages; groups into sheet/pages; pages only into notebooks. Illegal drops show a "not allowed" cursor and no drop line (no error toast).
- Drop indicator: 2px accent line between siblings; accent 1px box when nesting. Grab offset respected, pointer capture, 10px tap/drag hysteresis [emil-apple 6.5].
- Keyboard equivalent for every drag: select, then ⌥↑/⌥↓ reorder, ⌥←/⌥→ out of / into group, "Move to…" menu [jk-accessibility].
- Multi-select with ⇧/⌘, Enter to edit label inline, Delete hides (stock) or removes (Ingenium-added).

## 5. Reports / PDF (Stripe-grade proof)
### 5.1 Layout
Left: Blocks + Layers (existing block types: heading, field, label_field, o2m_table, image, divider, text, page_break). Center: paper canvas (existing `ReportCanvas`) at true page size from `report.paperformat`. Right: **Proof** pane, the real PDF from Odoo for the chosen record (pdf.js), page thumbnails, and Inspector tab. Top bar: record ‹ ›, Language, Currency, Company, Paper, then **Publish changes**.

### 5.2 Behaviour
- **Live proof.** Debounced 1.2 s after the last edit: compile, `render_report_pdf` on the selected record, swap in. Old proof stays visible with "Updating…" until the new one arrives; requests cancel when superseded. Failure keeps the last good PDF and shows what failed and how to fix it (`reportRenderError`).
- **Page checks (code).** From the rendered PDF: table rows split across pages, content entering header/footer zones, page count change vs published, images over 2 MB. Each warning links to the block.
- **Lang / currency / company.** Context `lang`, record currency, `company_id` switch; previews use installed languages and companies only.
- **Header/footer, paper** edited visually through stock `report.paperformat` and the slots in `INHERIT_SLOT_MAP` (never replace).
- **Brand once, stock first.** Logo, colours, font and layout set through Odoo's own document layout settings on `res.company` (the `base.document.layout` wizard fields). All stock and custom reports inherit them; mail templates use the same company logo and colours. No parallel brand system.
- **Before/after compare.** Server rasterizes both PDFs (poppler), Proof pane offers side by side or a slider (clip-path `inset()` reveal [emil 6.6]); changed regions outlined.
- **Starter gallery.** Invoice, quotation, delivery slip as inherit edits on the stock templates present on 17-20 (verified per version, hidden where the app isn't installed, with the install card from App Studio).

## 6. Tokens (ingenium-v2 + existing theme) [jk-colors] [hallmark lock the tokens]
No inline hex in builder code; new tokens live in `styles/globals/tokens.css`.
| Role | Light | Dark | Rule |
|---|---|---|---|
| Ink / surfaces | existing `--ink`, `--surface*` | basalt `#1A1C21` surface, limestone `#F3F4F6` ink | from kit |
| Accent (primary action, selection, focus ring) | `--accent` teal (`#0f766e` per brand guide) | `--accent` `#2dd4bf` | one accent, one meaning |
| Desk (canvas background) | new `--desk` = n2 tinted toward ink | n1 | content stays the hero |
| Condition badge | `--info` blue | `--info` | info only |
| Warning / error / success | `--warning` amber / `--danger` / `--success` | same | ≤4 status colours [dembrandt] |
| Keystone | `--brand-cinnabar` `#CF4527` | same | logo and the one publish moment only; never a button [BRAND_GUIDE §2] |
| Radius | `--r-sm 6` controls, `--r-md 10` panels, `--r-lg 16` sheets | | concentric [jk-ui] |
| Elevation | border for structure, `--shadow-raised` only for floating menus | | never border + wide shadow [imp/craft-floor] |
| Type | existing sans stack, 13px UI / 12px meta / 16px inputs on touch, `tabular-nums` in numbers, tables, page counts | | [jk-typography] |
| Icons | lucide-react, one stroke weight | | one set per project [§12 Icons] |
Odoo's own CSS inside the canvas is never themed by these tokens (fidelity).

## 7. Motion (Framer feel, Emil limits) [emil] [§6, §12 duration caps]
| Moment | Frequency | Motion |
|---|---|---|
| Select, hover outline, keyboard moves | 100+/day | none |
| Drag | tens/day | 1:1 tracking; drop settles with spring `{duration:.3, bounce:0}`; siblings reflow FLIP 180 ms `--ease-out` |
| Panel tabs, inspector sections | tens/day | 120 ms opacity |
| Menus, popovers | occasional | 150 ms scale .95→1 + opacity from trigger origin |
| Sheets, compare view | occasional | 240 ms `--ease-drawer`; exit 180 ms |
| Proof PDF swap | occasional | 150 ms crossfade with 2 px blur bridge |
| First publish of a layout | rare | keystone mark settles once (400 ms); never repeats |
Only transform/opacity; never `transition: all`; everything interruptible. Reduced motion: fades only, no drag spring overshoot. Reduced transparency: solid chrome.

## 8. States (every component) [taste] [imp/craft-floor] [§0 law 8]
Canvas: loading (skeleton matching the view shape), empty model ("No records yet. Showing sample values." with Sample chips), offline/Odoo unreachable (last loaded view, read-only, Retry), fidelity mismatch (blocks Publish), stale proof, error. Inspector rows and buttons: rest, hover (fine pointer only), focus-visible, active (scale .97), disabled with reason tooltip, loading (spinner in button, "Publishing…"), success, error. A states preview page for each new component (`/e2e/*` pattern already used) [hallmark 15.9].

## 9. Copy (plain language) [jk-writing] [ux-writing] [no-ai-slop]
Glossary on screen: inherited view → "your changes"; xpath → hidden (Advanced only); attrs/invisible → "Show and hide"; groups → "Who can see"; arch → never shown; QWeb → "print layout"; wkhtmltopdf → never shown.
Buttons verb + object: "Publish changes", "Preview as…", "Undo publish", "Compare versions", "Add field", "Install Helpdesk".
Errors: what, why, next. Example: "Can't publish. The field Delivery date isn't on this model in your database. Remove it or pick another field."
No em dashes, no "Oops", no "we" in errors, sentence case throughout.

## 10. Accessibility [jk-accessibility] [vercel-wig]
- Layers panel is an APG tree; canvas selection mirrors it, so everything on the canvas is reachable without a pointer.
- Every drag has a keyboard and menu equivalent (4.3); moves announced in a live region ("Moved Phone into Contact info").
- Focus ring 2 px accent with offset on every surface, including canvas nodes; dialogs have titles, trap focus, return focus.
- Contrast ≥4.5:1 text, ≥3:1 UI and badges; status never colour-only (badge icon + text).
- Works at 200% zoom; targets ≥24 px pointer, 44 px touch.
- Layout checks (4.2) also flag Odoo forms with missing labels, so users' own screens get more accessible.

## 11. Build stages (Tope's go after each) [playbook §1 Step 6]
Live checks always on disposable Odoo 17, 18, 19 and 20 DBs (existing install-real harness), dropped afterwards; tests + `tsc` + API restart each stage.

**Stage 1: Structure.** Engine load/normalize/records/compile/publish/revert endpoints; View Designer and Report Designer re-shelled into the new layout with no styling pass and no AI. Edit ops for move, insert, hide, wrap, set_attr.
Acceptance:
- Res.partner form, crm.lead form, sale.order list and one kanban load, normalize and render on all four versions; unknown nodes appear as blocks, none dropped.
- Move one field, add one field, hide one stock field: compiled inherit view has no positional anchors and no `replace`; publish then fidelity check passes; revert restores Odoo's combined arch byte-equal.
- Report: edit an invoice footer via slot; Odoo PDF renders on a real invoice on 17-20.
- Stock views unchanged after every test (arch hash before = after).

**Stage 2: Logic.** Conditions (3.2), role preview, version view, usage suggestions, layout checks, history/named versions/compare, comments, command bar (3.1), report proof loop, page checks, lang/currency/company, before/after compare, brand-once via document layout, starter gallery.
Acceptance:
- "Show when Stage is Won" on crm.lead compiles to an inline expression, publishes, and the field is visible only on won leads in Odoo itself on 17-20.
- AI given an unknown field returns no ops and a plain "unclear"; validator rejects any injected unknown field 100% in tests.
- Fill-rate suggestion numbers equal `read_group` counts; no record contents leave the session (network log check).
- Report page-break check flags a 40-line invoice whose table splits; brand colour change via document layout appears in invoice and quotation PDFs.
- Version view flags a field that exists only on newer versions.

**Stage 3: Styling.** Tokens (6), type, spacing 4 pt, states (8), copy pass (9), icons. Styling only from this spec; anything not covered is asked, not chosen [§1 Step 6 Build 3].
Acceptance: `impeccable detect` clean; no inline hex/font-family; contrast pairs measured; all copy through no-ai-slop; states preview pages exist; light and dark both pass.

**Stage 4: Polish + adoption.** Motion (7), accessibility (10), then App Studio and Draft Studio adopt the engine: `StudioFormPreview` and `DraftOdooPreview` render through the engine in draft mode (sample values labelled), uninstalled-app designs show the install card before build, and "Open in View Designer" after apply.
Acceptance: keyboard-only walkthrough of add/move/condition/publish; reduced motion and transparency checked; review-animations Before/After/Why table clean; one App Studio brief per version designs, installs, builds and opens in View Designer with fidelity check passing on 17-20; INP < 200 ms on a 60-field form.

## 12. Out of scope (v1)
Website/page builder, dashboards, spreadsheet reports, editing Odoo's JS widgets, real impersonation of other users, multi-user live co-editing (comments only), custom CSS inside Odoo views, Odoo 16.

## 13. Playbook rules applied
Laws 1 (Design Read), 3 (one accent), 5 (4 pt grouping), 6 (motion frequency), 7 (reduced motion/transparency), 8 (every state), 9 (slop tells); §1 SPEC rule (prompts verbatim, key server-side, out of scope); §1 Step 6 staged build with go after each; §4 shadcn principle via existing `components/ui` and tokens-only customisation; §6.1-6.6 durations, easing, interruptibility; §7 keyboard, forms, buttons, empty states; §12 rows Icons, Duration caps, Copy vs extract; §15.1 lock the tokens; §15.3 URL holds state; §15.4 error anatomy, name continuity, destructive confirm/undo; §15.9 states preview pages. Brand: BRAND_GUIDE §2 (cinnabar keystone-only, teal accent stays).

## 14. Open decisions for Tope
1. **Reading live records.** Live canvas and stress-test read up to 80 records' visible fields in the browser (never stored); fill-rate uses counts only. OK, or counts-only with sample values?
2. **One live reference page for DESIGN.md** (playbook asks for one pick): Figma's editor as the single page to take layout/spacing from, with the other three as patterns only?
3. **App orange `--brand` #f97316 next to the cinnabar keystone.** Keep builders free of it (teal + cinnabar only), or move `--brand` to cinnabar app-wide?

## 14. Stitch review (2026-10-15) — adopted / rejected
Adopt (reworded to plain language):
- Floating chip bar on the selected field showing its show/hide rule and who can see it.
- Labelled drop target ("Insert after Mobile").
- Pinned comment threads on fields, ⌘⏎ to send.
- Keyboard hint strip (reorder / indent) shown only while a field is selected.
- Tab badges with field counts; record stepper ("Record 3 of 80") next to Longest / Emptiest.
- Publish button carries the count of pending changes.
Reject:
- Developer terms in the UI (xpath, ops, base.group_user, is_company == False, memory cache, 12-col grid). Plain words by default; a "Show code" toggle for experts.
- Second accent colours (orange-red, brown); teal stays the only accent.
- Material Symbols; use the Keystone icon set.
- Drawing tools (pen, marquee, image, palette); Odoo layouts are structured, not drawn.
- An overloaded top bar; secondary controls (device, version, role, zoom) move to one compact "Preview as" group, with progressive disclosure.
- Default to Odoo 18; the version comes from the connected database, and all of 17–20 can be compared.
- A "migration verified" badge without a live check behind it; checks show only real results.

## 15. Ease-of-use additions (Tope, 2026-10-15)
- "Who can see it" is editable in place: pick roles by plain name (search), choose see / edit / hidden per role. Field-level visibility uses Odoo's groups on the field in the view layer; model-level access (read/write/create/delete) and record rules are reachable from the same panel via "Access to this record type".
- Before saving, code shows the impact in plain words ("14 users in Sales lose sight of Phone") and blocks changes that would lock out admins or hide required fields.
- "Can a person see this?" check: type a user's name and see exactly what they see and why.
- Hover "Why is this hidden?" explains the rule in a sentence.
- Multi-select fields to apply a rule or access setting once; "copy rules from another field".
- Every change gives an undo toast; empty states say what to do next; sensible defaults so most edits need one click.

## 16. Premium additions (Tope, 2026-10-15: "best visual builder anywhere")
View Designer
- Field widgets picker with live preview, filtered by field type and Odoo version (tags, badge, progress bar, priority stars, image, signature, etc.).
- Create a field inline from the Fields panel (plain type names, stock-first check first); related fields by drag ("Customer > Country").
- Smart buttons, status bar / stage pipeline, help tooltips, placeholders and default values editable in the inspector.
- "Tidy up": one click balances columns and groups fields by meaning and real usage (proposal + preview, code applies).
- Screen health score (crowding, hidden required fields, empty-field ratio, accessibility) with one-click fixes.
- List designer: column widths, optional columns, totals, row colours by condition, inline editing, default grouping.
- Kanban card designer: cover image, tags, progress, colour by condition.
- Search designer: filters and group-bys written in plain words.
- Translations: edit labels in every installed language side by side.
- History scrubber: slide back through any past version of a screen, compare, restore.
- Upgrade guard: when an Odoo update changes a stock screen, detect it, re-check the layer, and offer a fix.
- Reusable sections: save a block (e.g. "Audit info") and apply it to other screens.
- Move a layout between databases (staging to production) as a portable package.
- Presence: see who else is editing a screen; no silent overwrites.
- Performance hint for heavy fields (large related lists, slow computed fields).
Reports / PDF / email
- Place blocks anywhere in the body, not only top/bottom; line tables with chosen columns and totals.
- Conditional blocks ("only when there is a discount"); QR code, barcode, signature, page numbers, watermark (Draft / Paid).
- Email templates share the same blocks and brand, with desktop and phone email previews.

## 17. Full component library (Tope, 2026-10-15) — stage 2b
Drag-and-drop library covering at least Odoo Studio's set, filtered by connected version:
- New fields by type: text, multiline, number, decimal, money, date, date-time, checkbox, choice list, tags, priority, file, image, signature, HTML, link to another record, list of related records, related field.
- Existing fields of the model (with fill rate) and related-record fields.
- Layout: sheet, columns/groups, tabs, separator, title, header, ribbon, chatter, button box.
- Buttons: smart (stat) button, action button, status bar, link.
- Widgets per field type with live preview.
- Build a brand-new screen (form, list, kanban, search, calendar) from a blank or starter template, not only extend existing ones.

## 18. Approved ideas 1-19 (Tope, 2026-10-15)
Usage heatmap overlay; field dependency map before hide/remove; conditional required in plain words; step-by-step mode per role; "what blocks saving" per stage; labelled sample data; accessibility simulator; industry starter screens; report from photo/PDF (AI proposes, code maps); per-company brands; email client/dark-mode checks; manager approval before publish; scheduled publish; post-publish error watch + one-click undo; weekly change digest; layout comparison test between groups; dashboard (graph/pivot) designer; "explain this screen" tour; live co-editing with cursors.

## 19. Stage 2d (Tope, 2026-10-15): fixes + 20 follow-up ideas
Fixes: role-only layouts carry groups inside the layer (normal part `groups="!role"`, role copy `groups="role"`; Odoo 17-20 refuse groups on extension records); publishing other changes while one is on is refused plainly; ticker single-run across workers (Postgres advisory lock / SQLite file lock); co-edit rooms stored in the app DB; digest sent through the connected Odoo's outgoing mail (no server → log only, said); guard fix + package import under the approval rule (approvable via request-action).
1. Role-scoped layouts the supported way (= fix above).
2. "What changed" on each approval: before/after differences from Odoo's current screen.
3. Named approvers per record type (or `*`); needs sign-in to verify.
4. Pause scheduled publishing for an upgrade window (≤14 days); due changes wait.
5. After publish, watch flags records changed since then that miss a field the screen now requires.
6. Number tiles: count or sum for this week/month/quarter vs the last one (Odoo's own totals).
7. "Hide fields nobody fills in": fields empty on all records (≥20 records), not required/conditional, not read by rules → draft ops.
8. Stage checklist on the record: own layer; Odoo hides each line once filled.
9. Step-by-step progress badges worked out from the record's own fields (persist with the record).
10. Accessibility auto-fix: labels/tooltips Odoo already has → draft ops.
11. Sample data per industry (7 industries), labelled "Sample:".
12. Brand presets shared across databases (layout matched by xmlid; missing → left as is, said).
13. Send a real test email to one typed address (never the template's recipients), via Odoo's mail.
14. Report from a photo: the assistant transcribes; code maps to real fields (existing flow).
15. Starters: hotel & events, clinic, non-profit (stock fields only).
16. Digest to Slack/Teams incoming webhook (https + host allow-list; link masked).
17. Comments pinned to screen items (add/list/resolve).
18. Move a screen to another database: package from source, approval request in the target; nothing changes until approved.
19. Layout tests end themselves on a clear result or after 60 days (ticker, every 6 h); never auto-publish B.
20. Explain sheet as a PDF (built-in writer), translated by the assistant with numbers checked; falls back to English / printable page.

## 20. Added by Tope (Oct 16)
1. **Edit with AI (View Designer, builders job).** A plain-language box ("move Phone under Email, required for Sales"). The AI proposes typed layer ops only; code validates every op (fields exist on this version, name-based xpath, groups on inner elements); the result lands as a draft diff on the canvas with highlights, accept/undo per change, never a direct write. Publish keeps the normal fidelity check, approvals and revert. Ambiguous requests get one clarifying choice. Works for reports and emails too. Live 17-20.
2. **Ingenium Expert mode and bot avatars/icons.** A creative, distinctive avatar and icon set for "Ingenium Expert" mode and each Ingenium bot, in the Keystone family (brand/ingenium-v2), with light/dark, sizes, and states (idle, thinking, done, needs you). Load design-pack-mandatory.
