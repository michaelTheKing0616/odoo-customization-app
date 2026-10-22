# DOC-MAIL handoff — mail templates studio (2026-10-05)

## Shipped
- Operate route: `/connections/[id]/mail-templates` (nav: Build → Mail templates).
- List / create / open / edit `mail.template` via existing `config_ops` endpoints.
- Paper pasteboard preview (cream letter on gray desk) — same craft family as Reports.
- Grounded field picker (`ReportFieldPicker` + `api.listFields` / fields_get).
- Visual blocks (`ReorderableBlocks`) compile to HTML; Source HTML tab for foreign bodies.
- Unsafe gate family: client `mailUnsafeGate` → `reportUnsafeGate` / server `qweb_unsafe_gate` on create+patch.

## Honesty limits (do not claim otherwise)
- Not a ChatGPT freeform HTML editor — gate refuses script / t-raw / t-out / XXE / bad t-call / on* / javascript:.
- Placeholders are Odoo Jinja (`{{ object.field }}`); they render on send in Odoo, not as live merge in this preview (chips only).
- Complex foreign HTML falls back to Source tab (no silent lossy rewrite).
- Config → Mail paper defaults still has the quick create form; studio is the elite surface.

## Next surfaces (do not start here unless scoped)
1. **General QWeb views** — DONE 2026-10-05 (see `DOC-QWEB-NOTES.md`): dedicated `/qweb-views` operate route (not Designer mode — wrong canvas), paper+gate, inherit honesty, shared `qweb_unsafe_gate`.
2. **Website** — DONE 2026-10-05 (see `DOC-WEBSITE-NOTES.md`): pasteboard craft, shared gate, honesty banners, UI-S-14 what/why/next.

## Vision
- Harness: `/e2e/mail-templates` (`NEXT_PUBLIC_E2E=1`).
- Shots: `docs/vision-verify/DOC-MAIL/` (capture when Playwright sweep is run).

## Not touched
- Reports rewrite, `odoo_addons/`, git commit/push, card DONE marks.
