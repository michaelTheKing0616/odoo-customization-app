# Wave 7b — ADV: advanced designers & live editing (promoted by user)

Shared context: all three cards are clean-room — our own original code, public RPC + public
docs only. UIX kit + shell required.

---

## TIER-6 — Deep Gantt/Grid/Map/Cohort config designers

TASK: Designer configuration panels for the four Enterprise view types, emitting documented
arch attributes, edition-gated.

INPUT: TIER-5 (basic EE arch emission), designer inspector, TIER-1 matrix, Odoo public docs
for each view's arch reference (cite the doc page per attribute in code comments).

CHECKLIST:
- [ ] Gantt panel: date_start/date_stop fields, default_scale, progress field, color field,
      dependency arrows attr where documented per major, drag-schedule flag (attr only —
      behavior is Odoo's); precision/scales options.
- [ ] Map panel: res.partner field selection, routing toggle, default_order, marker popup
      field list.
- [ ] Cohort panel: date_start/date_stop, measure, interval (day/week/month/year), mode.
- [ ] Grid panel: row/col field selection, adjustment/measure attrs.
- [ ] Each emits valid arch (golden fixtures per major from public docs), save path via
      existing views/save; canvas shows structural preview + "Open in Odoo is authoritative"
      note (same honesty as kanban).
- [ ] Edition gating: panels visible only when matrix says the edition supports the type;
      Community connections see the honest Callout + what-unlocks note.
- [ ] Conditional live verification: with `ODOO_EE_TEST_URL` set, save+render smoke per view
      type; otherwise fake-tested + flagged pending-live-verify in return.

DONE MEANS: four panels emit doc-correct arches (golden tests); gating correct; live status
reported honestly.

DO NOT: consult Enterprise source; emit undocumented attrs.

GATE: pytest golden suite + designer e2e + conditional live.

RETURN: ≤10 lines + verification status.

DEVIATIONS: conservative + log.

---

## UIX-6 — Live overlay editor on the proxied Odoo frame (Grok 4.5 card)

TASK: In-place editing: click an element in the proxied Odoo view → edit via our inspector →
save as inherit view. Our own overlay, zero Studio code.

INPUT: `routers/preview_proxy.py` (same-origin frame), views parse/xpath endpoints, designer
inspector components, snapshots.

CHECKLIST:
- [ ] Proxy hardening: confirm same-origin delivery of the webclient frame incl. assets +
      session handling limits; document which Odoo screens render reliably through the proxy
      (form/list at minimum) — this REALITY CHECK is the card's first task; if the proxy
      cannot reliably render authenticated form views, STOP and report options (do not
      build the overlay on a broken base).
- [ ] Overlay: injected script (served by our proxy) draws hover/selection outlines over
      DOM nodes bearing field markers (`[name=...]`, o_field CSS hooks); postMessage bridge
      frame→app with the selected field/element descriptor.
- [ ] Mapping: descriptor → arch node via our parse endpoints (field name match within the
      current view's arch); ambiguity → picker listing candidate nodes.
- [ ] Edit operations v1 (explicitly bounded): move field (before/after sibling), hide field,
      edit label/placeholder/help, add existing field near anchor, set widget from curated
      list, edit group/page label. Each emits an inherit view via existing endpoints;
      snapshot-first; frame reloads on save showing the result.
- [ ] Honesty panel: capabilities NOT in v1 listed in-UI (add new model areas, complex
      restructures → "open View Designer"); every save shows the generated xpath (code
      peek).
- [ ] E2E: overlay select→hide-field→save→verify-in-frame loop against docker 19
      (Playwright driving the real proxied frame); vision-verify screenshots.

DONE MEANS: the full select→edit→inherit-save→reload loop works live on docker 19 for the
six v1 operations on a stock form (e.g. res.partner) AND a custom x_ form.

DO NOT: read Studio/web_studio client source; patch core views in place (inherit only);
proceed past a failed reality check.

GATE: e2e live loop + pytest for mapping endpoints + screenshots.

RETURN: ≤10 lines + reality-check findings.

DEVIATIONS: conservative + log — reality-check failure is a STOP-and-report, not a workaround
hunt.

---

## UIX-7 — Website page editing (block-based)

TASK: Edit website pages (text/image/section blocks + publish) via public RPC when the
`website` module is detected.

INPUT: config_ops website availability checks (exist), odoo-client, UIX kit.

CHECKLIST:
- [ ] Detection + gating: `website` installed → pages list (website.page + view arch);
      absent → honest Callout.
- [ ] Block parser: page arch → editable block tree for RECOGNIZED patterns (headings,
      paragraphs, images, buttons/links, simple section containers); unrecognized snippets
      preserved verbatim as locked blocks (partial-fidelity contract, same philosophy as
      AI-7).
- [ ] Editor: block list with inline text editing (plain + basic formatting), image replace
      (upload → attachment → src swap), link/button href+label, block reorder within a
      section, publish/unpublish toggle; save writes the view arch via RPC with
      snapshot-first.
- [ ] Explicit ceiling in-UI: "full drag-drop website building stays in Odoo's editor —
      this covers content edits" (documented DONE MEANS boundary).
- [ ] Tests: parser fixtures (real odoo homepage arch sample), locked-block round-trip
      (byte-identical), live smoke: edit a paragraph + publish toggle on docker 19 with
      website installed.

DONE MEANS: live content edit round-trip proven without corrupting unrecognized snippets.

DO NOT: rewrite snippet internals; attempt theme/asset editing.

GATE: pytest + RPC smoke 19 (website module) + e2e.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.
