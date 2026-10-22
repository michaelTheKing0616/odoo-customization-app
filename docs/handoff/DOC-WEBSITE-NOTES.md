# DOC-WEBSITE handoff — website editor paper + gate (2026-10-05)

## Shipped
- Operate route: `/connections/[id]/website` (nav: Build → Website).
- Elevated `WebsiteEditor` to Reports/Mail craft family: gray pasteboard, cream paper preview, basalt chrome, teal primary Save.
- Shared unsafe gate family: client `websiteUnsafeGate` → `reportUnsafeGate` / server `gate_website_save` → `qweb_unsafe_gate` on PUT blocks.
- Honesty banners: Online limits / scope, locked XML count.
- UI-S-14: errors are what / why / next (`websiteError` + `website-error*` test ids), not bare strings.
- Grounded blocks only (heading / paragraph / link / button / image / section / locked) — no invented field schema.

## Honesty limits (do not claim otherwise)
- Not Odoo's full drag-drop website builder — recognized content blocks only.
- Locked unrecognized snippets stay verbatim; gate still refuses script / t-raw / t-out / XXE / bad t-call / on* / javascript: inside them on save.
- No freeform HTML invent surface; no second unsafe editor.

## Next surfaces (do not start here unless scoped)
1. **General QWeb views** — DONE 2026-10-05 (see `DOC-QWEB-NOTES.md`): dedicated `/qweb-views` operate route (Designer stays form/list/kanban), paper+gate, shared unsafe family.

## Vision
- Harness: `/e2e/website` (`NEXT_PUBLIC_E2E=1`).
- Shots: `docs/vision-verify/DOC-WEBSITE/` (desktop / empty / locked / error).

## Not touched
- Reports rewrite, Mail templates rewrite, Visual Designer (`components/designer/**`), `odoo_addons/`, git commit/push, card DONE marks.
