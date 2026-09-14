# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Automations premium UX on `cursor/automations-premium-011f` (off Designer A–D). List → composer/detail, DomainBuilder apply-on validation, grouped safe/advanced actions, Designer deep links, draft/unsaved/saved bar. PATCH name + filter_domain. Existing snapshots reused.
- **Proof:** Vitest 270 (incl. `automationForm`, DomainBuilder, session bar, list, action-kind). Playwright: `automations-prod`, `automation-caps`, `automation-gating` (7 passed).
- **Rule:** Automations session chrome is dirty/save only. Do not copy Designer undo/redo. Do not rewrite server actions on PATCH.

## Next (operator)
1. Open `/connections/{id}/automations`, create a safe update-field or activity rule, confirm list + session bar.
2. Open a listed rule, save name/domain, Open in View Designer for the same model (and back).
3. Completeness ≠ Cert ≠ Autopilot. Promote stays human.

## Rule to keep
- Python live stays advanced-confirm / Option A. Capability grey-outs fail closed. Confirm phrase unchanged.
