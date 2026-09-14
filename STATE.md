# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium Models & Fields (Builder) on `cursor/builder-models-fields-premium-9e03` (off Automations premium). PR: https://github.com/michaelTheKing0616/odoo-customization-app/pull/5
- List → model detail → field composer; session chrome; Designer/Automations links; stacked form+list teaser; currency/inject gates; view-vs-model remove.
- **Proof:** Vitest 288 (builder helpers, list, session bar, field composer gates, preview, ModelDetail success path).
- **Failed:** Radix tabs hid the list teaser in jsdom (`fireEvent.click` does not activate). Stacked both views instead.

## Next (operator)
1. Open `/connections/{id}/builder`, create an `x_` model, follow Customize layout in View Designer.
2. Add/edit a field; confirm Hide in View Designer vs Remove from model.
3. Do not start Menus, Access, App Studio, Draft Studio, Job Autopilot, ModuleSpec, Projects, Expert in this PR.

## Rule to keep
- Builder layout teasers stay stacked (form + list). Do not hide them behind Radix tabs. Session chrome is dirty/save only — reuse field/model snapshots, do not copy Designer undo.
