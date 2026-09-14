# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of this session.

## Last run
- Date: 2026-09-14
- **Shipped:** Track A View Designer field properties inspector (elite rail) + FieldNode chrome round-trip (`help`, `placeholder`, `class`, `groups`). Related path picker uses public field metadata. Remove-from-view ≠ drop column.
- **Proof:** `test_field_chrome_attrs_round_trip`, `DesignerFieldInspector.test.tsx`, widget catalog groups helpers.

## Next (operator)
1. Open View Designer, select a form field, edit label/help/placeholder/class, widget presets, Off|Always|When modifiers, group xml ids; Save inherit.
2. Do **not** start Tracks B/C/D in this PR (xpath upgrade-safety, draft/publish, overlay).
3. Completeness ≠ Cert ≠ Autopilot. Promote stays human.

## Docket (later — do not start)
- **PROD-FAULT-LOG:** Production log of **in-app** faults with a founder dashboard/export. **Blocked on** honest diagnosis. See `docs/PRODUCTION-PLAN.md` § Docket.
- Tracks B/C/D from View Designer premium.

## Rule to keep
- View-layer field chrome lives on `FieldNode` parse/render; related paths are ORM metadata. Do not invent dotted `name=` in arch.
