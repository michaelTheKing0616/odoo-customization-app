# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium App Studio UX (surface 3) on `cursor/app-studio-premium-e1e6` off Menus/Access:
  - Stage rail: brief → clarify → generate → review → apply
  - Extracted chrome: `StudioShell`, `StudioBriefScreen`, `StudioHonestyBanners`, `StudioOptionAPanel`, chat/refine, apply bar
  - Honesty: `surface: "studio"` banners; operator-surface summary; View Designer on primary `x_*`
- **Tests:** studio + journey + banners + odoo-preview vitest 62 passed in the scoped suites
- **Not in this run:** Draft Studio wizard, Job Autopilot, ModuleSpec, Projects, Expert; live browser against Odoo; AI pipeline rewrite

## Next
- Verify App Studio on a probed connection: brief → diagnosis lock → review canvas → View Designer link
- Continue premium sweep only if asked (do not start Draft Studio / Autopilot here)

## Rule
- App Studio premium is a stage journey + extracted chrome — do not copy list→composer or Designer undo/redo onto it
