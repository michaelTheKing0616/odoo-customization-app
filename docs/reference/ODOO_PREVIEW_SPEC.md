# Odoo Preview Spec (clean-room structural mimic)

Canonical reference for **OdooPreviewKit** — shared preview grammar across App Studio,
Draft Wizard, View Designer, and Models & Fields builder.

**Authoritative layout:** Open in Odoo / iframe preview. This kit is a **structural**
honesty layer only.

## Why not pixel-perfect Odoo UI?

We intentionally stop at **structural fidelity**, not pixel parity:

1. **Legal / clean-room** — Odoo Enterprise Studio (`web_studio`) and the OWL web client
   CSS/JS are copyrighted. Copying or reverse-engineering them is forbidden
   (`skills/studio-parity.md`, MEMORY). Public docs + generated ModuleSpec XML only.
2. **Wrong product surface** — Our app is an *external* builder (Next.js). The real Odoo
   form is rendered by Odoo’s own web client after apply. Pixel-matching that CSS would
   still drift every Odoo minor release and lie about what users see before Open-in-Odoo.
3. **Brand** — Preview uses our teal `--odoo-*` tokens, never Enterprise purple. Matching
   Odoo purple would make the product look like a Studio clone, not our builder.
4. **Authoritative path** — Open-in-Odoo / iframe is the truth. Preview teaches interaction
   grammar (sheet, statusbar, smart buttons, density) so operators recognize the layout —
   it is not a substitute for live Odoo.
5. **Maintenance** — Pixel parity means tracking Odoo 17/18/19 theme forks forever. Structural
   grammar ships once and stays honest across majors.

**Done bar:** “Looks like an Odoo *document*” (header, pipeline, stats, two columns, tabs) —
not “indistinguishable from Odoo 19 Community CSS.”

## Brand & scope

| Rule | Detail |
|------|--------|
| Structure | Match Odoo form/list/kanban *interaction grammar* (sheet, statusbar, stat buttons, two-column groups, control panel placeholders). |
| Brand | Teal product tokens via `--odoo-*` in `globals.css` — **never** Odoo Enterprise purple. |
| Source | Public Odoo docs + generated ModuleSpec XML only — **no** OWL / Studio Enterprise source. |
| Shell | App shell keeps WAVE-6 UIX tokens; preview lives inside `OdooPreviewScope` / `PreviewThemeScope`. |

## Component anatomy

### Form document

```
OdooControlPanel (placeholder breadcrumb, create, view switcher)
└─ OdooFormView
   ├─ OdooFormHeader
   │  ├─ title
   │  ├─ OdooStatusBar (pipeline stages, active emphasized)
   │  └─ header workflow buttons (primary / secondary)
   ├─ OdooFormSheet (workspace bg, centered white sheet)
   │  ├─ OdooButtonBox + OdooStatButton[] (value + label, max 6 visible)
   │  ├─ OdooFieldGroup[] (sibling groups → 2-col grid on desktop)
   │  └─ OdooNotebook (one active tab)
   └─ chatter stub (documents only)
```

### List view

Compact table, decoration hints as row classes (danger/info/muted). Sample row optional.

### Kanban view

Columns by `groupBy`; cards show title + status fields.

## CSS tokens (preview scope)

| Token / class | Role |
|---------------|------|
| `--odoo-canvas` | Workspace background (`#f4f5f6` light) |
| `--odoo-sheet` | White form sheet |
| `--odoo-statusbar` | Active pipeline stage accent |
| `--odoo-primary` / `--odoo-primary-hover` | Primary buttons (teal brand) |
| `.odoo-form-workspace` | Gray workspace wrapper |
| `.odoo-form-sheet` | Centered sheet, 2–6px radius |
| `.odoo-field-row` | 140px label + value column |
| `.odoo-form-grid-2col` | Sibling groups side-by-side |
| `.odoo-statusbar` | Horizontal stage pills |
| `.odoo-stat-value` / `.odoo-stat-text` | Smart button anatomy |
| `.odoo-btn-primary` / `.odoo-btn-secondary` | Header actions |

Radius inside preview: **2–6px** — override app `rounded-lg` within preview scope only.

## Preview schema (`PreviewViewSchema`)

Single JSON shape stamped by `preview_views.build_preview_views()` into
`_generation_engine.form_preview` (+ optional `list_preview`, `kanban_preview`).

See `apps/web/src/lib/draft-form-preview.ts` and `apps/api/app/preview_views.py`.

## MEMORY rules (renderer must enforce)

1. **`*_line` models:** no header statusbar, no chatter; `x_status` stays in sheet.
2. **Smart buttons:** related stock documents only; host buttons per `_operator_surface`;
   never duplicate notebook O2M children as stat buttons; identity M2Os stay on form.
3. **Line lists:** qty/hours/rate/amount columns preferred; no `ir.sequence` on lines.
4. **Preview ≠ production:** Completeness / Cert Gold ≠ preview fidelity — banner always shown.
5. **Max stat buttons:** show at most **6** in preview chrome.

## Forbidden patterns

- Cloning Odoo web client CSS or OWL components
- Functional search/filter/group-by in preview (placeholders only)
- Property fields UI (out of scope v1)
- Pixel-perfect Odoo 19 parity
- Odoo purple branding in preview scope
- Stat buttons for identity M2Os already on the form sheet

## Vision-verify checklist

Light mode screenshots should show:

1. Form header with statusbar pipeline + at least one primary button
2. Sheet with two sibling groups OR 2-col field rows
3. Smart buttons with label (and count when available)
4. Honesty banner: "Structural preview — Open in Odoo for authoritative layout"
5. Field widgets: boolean toggle / selection caret / M2O chip / monetary when ttype set
6. List: `list-preview-table`; Kanban: color swatch + state dots

See `skills/vision-verify-ui.md`.

## Test gates (must stay green)

| Suite | Command |
|-------|---------|
| API enricher | `cd apps/api && python -m pytest tests/test_preview_views.py -q` |
| Generation IR stamp | `python -m pytest tests/test_ai_generation_engine.py -q` |
| Web kit + normalize | `cd apps/web && pnpm exec vitest run src/lib/draft-form-preview.test.tsx src/components/odoo-preview/ src/components/designer/FormCanvas.test.tsx src/components/builder/BuilderModelPreview.test.tsx` |
| E2E harness | `pnpm exec playwright test e2e/studio-preview.spec.ts` |
