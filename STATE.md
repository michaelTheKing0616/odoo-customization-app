# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of this session.

## Last run
- Date: 2026-09-14
- **Shipped:** Track D live overlay deepen on `cursor/view-designer-field-inspector-e8e2` (PR #3). Form structure from overlay: add notebook page, add group, move field into named group/page. Semantic locators + Track B 422 guards. HUD + honest NOT_V1. Kanban/search add-field slice only.
- **Proof:** `test_overlay_ops.py`, `test_overlay_structure.py`, `OverlayEditor.test.tsx`, `OverlayHud.test.tsx`.
- **Rule:** Overlay structure injects use named `@name`/`@id` (new `x_page_*` / `x_group_*`). Do not claim kanban card designer or search filter domains.

## Next (operator)
1. Designer iframe overlay: click a field, HUD shows Named/Fragile/Positional; **Add notebook page** / **Add group** without a selection; **Save inherit xpath**.
2. Move a field **into a group or page** when the picker lists a named locator.
3. Completeness ≠ Cert ≠ Autopilot. Promote stays human. Stop — Track D done.

## Docket (later — do not start)
- **PROD-FAULT-LOG:** in-app fault log. Blocked on honest diagnosis.
- Search filter domain rows; kanban card templates/colors.

## Rule to keep
- Overlay form-structure ops are inherit xpath only. Validate locators against parent arch before apply. Empty ModuleSpec is not Cert Gold.
