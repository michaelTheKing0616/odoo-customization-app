# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium Draft Studio UX (surface 4) on `cursor/draft-studio-premium-6fd4` off App Studio:
  - Stage rail: prompt → enrich → review → apply
  - Extracted chrome: `DraftStudioShell`, prompt/reuse, honesty banners, scorecard, preview, apply bar
  - Wizard page ~3.5k → ~1.9k; e2e testids kept (`draft-studio`, `create-draft`, `draft-scorecard-chip`, …)
- **Tests:** journey + llm-status + reuse + scorecard/rail/shell vitest green
- **Not in this run:** Job Autopilot, ModuleSpec editor, Projects, Expert; live browser against Odoo; AI pipeline rewrite

## Next
- Verify Draft Studio on a probed connection: prompt → Create draft → scorecard → Apply / Open ModuleSpec
- Continue premium sweep only if asked (do not start Autopilot / ModuleSpec / Projects / Expert here)

## Rule
- Draft Studio premium is a stage journey + extracted chrome — do not copy App Studio chat/clarify or change Completeness / Cert / Autopilot semantics
