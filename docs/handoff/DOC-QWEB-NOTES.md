# DOC-QWEB handoff — general QWeb views studio (2026-10-05)

## Why a dedicated operate route (not Designer mode)
View Designer (UI-S-12) owns **form / list / kanban** structural canvases (field widgets on a desk). General `ir.ui.view` `type=qweb` arches are **document templates** — same craft family as Reports / Mail / Website (paper pasteboard + grounded blocks + Source XML). Mixing those paradigms inside Designer would create a parallel unsafe path or a wrong canvas. This surface still reuses:

- Server `qweb_unsafe_gate` family via `qweb_view_blocks.gate_qweb_view_save`
- Client `reportUnsafeGate` patterns via `qwebUnsafeGate` (grandfathered t-call)
- RT-22 `refuse_root_replace` on inherit xpath
- `ReorderableBlocks` + `ReportFieldPicker`
- Prefer **inherit** writes; overwrite needs advanced confirm

## Shipped
- Operate route: `/connections/[id]/qweb-views` (nav: Build → QWeb views).
- List / create / open / edit `ir.ui.view` where `type=qweb` via `/api/connections/{id}/qweb-views`.
- Optional hide of report-bound keys (those stay owned by Reports studio).
- Paper pasteboard preview (cream letter on gray desk) — teal-only accent.
- Grounded blocks (`heading` / `paragraph` / `field` / `divider` / `locked`) + Source XML tab for foreign bodies.
- Unsafe gate: client `qwebUnsafeGate` → server `refuse_unsafe_qweb_view_arch` / `gate_qweb_view_save` (script / t-raw / t-out / XXE / on* / javascript: / invent t-call; grandfather loaded t-calls).

## Honesty limits (do not claim otherwise)
- Not a freeform QWeb invent studio — gate refuses unsafe directives.
- Complex foreign arches fall back to Source XML (no silent lossy rewrite).
- Report-bound keys are flagged; prefer Reports for print layouts.
- Website pages stay on Website; mail.template stays on Mail templates.
- t-field preview chips are not live Odoo merge.

## API
- `GET /qweb-views` — list (optional `exclude_report_bound`, `model`, `key_prefix`)
- `GET /qweb-views/{id}` — detail + best-effort blocks + `existing_t_call_targets`
- `POST /qweb-views` — create primary keyed qweb
- `PUT /qweb-views/{id}` — inherit (default) or overwrite (confirm)

## Vision
- Harness: `/e2e/qweb-views` (`NEXT_PUBLIC_E2E=1`).
- Shots: `docs/vision-verify/DOC-QWEB/` (capture when Playwright sweep is run).

## Not touched
- Designer (`components/designer/**`), designer-cmp3 e2e specs, Reports rewrite, Mail/Website rewrite, `odoo_addons/`, git commit/push/stash/checkout, card DONE marks.
