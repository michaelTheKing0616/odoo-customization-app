# Cards — PDF Studio (premium printouts)

**Why this is in the queue.** Odoo's own AI, step 6, tells the user to "design custom PDF printouts using drag-and-drop" and then stops. The comparison note (`ingenium-vs-odoo-ai-comparison.docx`) flags that Ingenium must actually compile the printout, not hand back a tutorial. A seeded editor already exists. These cards upgrade it. They do not start a second designer.

**Seeded today (do not rebuild):**
- Page: `apps/web/src/app/connections/[id]/reports/page.tsx` (list, paper formats, visual/code tabs, render probe, delete confirm).
- Editor: `apps/web/src/components/reports/ReportDesigner.tsx` and `ReportCanvas.tsx`.
- Blocks: heading, text, field, label_field, o2m_table, image, divider, page_break.
- Modes: `primary` and `inherit` (base report key + a raw XPath string, default `//div[@class='page']`).
- Reorder is up/down buttons, not pointer drag.
- Ops that must carry the result: `report.inherit`, `report.action.create`, `report.action.update` (R2). See `cards/T8_ENGINE_CORE.md` family T8-OP-UI.

**Bar.** A person can create a printout from scratch or extend a stock PDF / QWeb report, on a paper canvas, and save it as a real `ir.actions.report` plus QWeb. The canvas should feel more deliberate than Odoo 20's report editor: true paper ratio, type hierarchy, grounded fields, and a preview of the actual PDF. Public ORM/RPC only. Never read Studio source.

**Skills, read `SKILL.md` before PDF-01 and PDF-06** (`~/.cursor/skills/prime/<name>/SKILL.md`): `high-end-visual-design`, `design-taste-frontend`, `better-typography`, `better-layout`, `no-ai-slop`, `ui-craft-dense-dashboard`, `accessibility`, `frontend-a11y`. Motion: paper does not animate. Only the inspector drawer moves, using the UI-F09 constants.

**Shared do-not:** no second report editor; no business logic in the canvas; fields only from the live schema (unknown field refused); no `t-raw` of user HTML; no XPath that replaces the root or a large subtree (RT-22); no XXE; no `x_studio_*` xmlids; Odoo 16 stays experimental (the page caveat stays); sandbox render before any production apply; do not claim this is done because the block list exists; do not copy Odoo brand chrome.

**Shared commands:**

```bash
pnpm --filter @odoo-custom/web test -- src/components/reports
pnpm --filter @odoo-custom/web test:e2e e2e/a11y-primary.spec.ts
```

---

### PDF-01 — Premium paper canvas
- **Status:** OPEN. **depends_on:** UI-F09 (motion constants; drawer only).
- **Pressure:** C2 U1 F1 K2 V2 I0 +0 = 8 → Grok standard. Route: `cursor-grok-4.6-high-fast` if the first cheap pass looks generic.
- **Change:** `ReportCanvas.tsx` and its CSS module. Not the save API.
- **Steps:** (1) Read the six skills. (2) Screenshot the current canvas. (3) Draw the page at the paperformat ratio (A4 default), with margins from the selected paper format. (4) Type scale: one display style for the document title, one for section headings, body at 10–11 pt, tabular figures for amounts. Hairline rules, not heavy cards. Quiet header and footer bands. (5) Reduced motion: no page transition.
- **Acceptance:** [ ] canvas matches paper ratio within 2%; [ ] amounts use tabular numerals; [ ] empty state is one sentence plus "Add a block"; [ ] light and dark both ≥ 4.5:1 for text on the page (the page surface stays paper-colored in both themes); [ ] before/after shots in `docs/vision-verify/PDF-01/`.
- **Negative:** no purple gradient, no nested cards, no stock illustration, no drop shadow on the paper.
- **Rollback:** revert `ReportCanvas.tsx`.

### PDF-02 — Pointer drag and drop
- **Status:** OPEN. **depends_on:** PDF-01, UI-F13. Use `ReorderableBlocks`. Do not add a second drag implementation.
- **Pressure:** C2 U1 F1 K1 V1 I0 +0 = 6 → cheap first (`composer-2.5-fast`).
- **Change:** `ReportDesigner.tsx`, `ReportCanvas.tsx`.
- **Acceptance:** [ ] a palette item drops onto the page and lands where it was dropped; [ ] blocks reorder by drag; [ ] keyboard still moves a selected block (arrow keys) so drag is not the only path; [ ] up/down buttons may remain as a fallback.
- **Negative:** a drop outside the page does not insert a block.

### PDF-03 — Extend a stock report
- **Status:** OPEN. **depends_on:** T8-OP-UI (`report.inherit` handler proven). If that card is still SEEDED, this card stops after the UI and does not apply.
- **Pressure:** C2 U2 F3 K3 V2 I1 +0 = 13 → Grok high (`grok-4.7-xhigh`).
- **Change:** inherit mode in `ReportDesigner.tsx`. Replace the raw XPath input with a slot picker: header, before the page body, after the page body, footer. The compiler emits one inherit xpath for that slot.
- **Acceptance:** [ ] user picks an existing `ir.actions.report` from the connection and adds blocks in one slot; [ ] save emits `report.inherit` with exactly one anchor; [ ] stock template body is unchanged except that slot; [ ] round-trip: reload shows the same blocks.
- **Negative:** position `replace` on `/` or on the root template node is refused (RT-22). A base report key that does not exist is refused. Odoo 16 shows the experimental caveat and does not offer "apply to production".

### PDF-04 — Create from scratch, grounded
- **Status:** OPEN. **depends_on:** PDF-02, T1-A1 (schema client).
- **Pressure:** C2 U1 F2 K2 V2 I1 +0 = 10 → Grok high.
- **Change:** field picker and the QWeb emitter used by the designer (find it from `ReportDesigner.tsx` before adding a new one).
- **Acceptance:** [ ] "New printout" creates `report.action.create` bound to a real model; [ ] external layout is on by default; [ ] every field token is `model_exists` + `fields_get` on that connection; [ ] a line table only offers fields of the related model; [ ] sandbox render of one record returns a PDF (the page's existing render probe).
- **Negative:** a field name not on the model is refused and not written into the arch. An empty spec does not create a report.

### PDF-05 — Unsafe template gate
- **Status:** OPEN. **depends_on:** PDF-03, PDF-04.
- **Pressure:** C2 U1 F3 K3 V2 I1 +0 = 12 → Grok high, plus a reviewer (QWeb safety).
- **Acceptance:** [ ] pasted arch containing `t-raw`, `<script`, external entity, or `t-call` to a non-allowlisted template is rejected before save; [ ] tests named in the progress log.
- **Negative:** RT-22 root replace; XXE; a block whose text is interpreted as QWeb.

### PDF-06 — Reports screen (UI-S-17)
- **Status:** OPEN. **depends_on:** PDF-01, PDF-02, PDF-04, UI-F03.
- **Pressure:** C1 U1 F1 K2 V2 I0 +0 = 7 → Grok standard, after the skills in the header.
- **Change:** `reports/page.tsx` only as composition. Split first if it grows past 500 lines.
- **Acceptance:** the UI-S-17 block in `../13_UI_SCREEN_SPECS.md`. Primary action label is "Save the printout".
- **Vision:** `docs/vision-verify/PDF-06/desktop.png` and `narrow.png`, plus a shot of inherit mode and of a render error.
