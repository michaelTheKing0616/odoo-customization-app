# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of this session.

## Last run
- Date: 2026-09-14
- **Shipped:** Track C session undo/redo + draft/published chrome on `cursor/view-designer-field-inspector-e8e2` (PR #3). `useDesignerHistory` + `DesignerSessionBar`. Save to Odoo still inherit-default publish. Snapshots labeled published checkpoints.
- **Proof:** `designerHistory.test.ts`, `DesignerSessionBar.test.tsx`.
- **Rule:** Session Cmd+Z never RPC-rollbacks. Empty undo points at published checkpoints.

## Next (operator)
1. Designer: edit a field, ⌘Z / ⌘⇧Z, watch Unpublished → Published after Save to Odoo.
2. After save, session undo is empty; **Roll back last publish** restores the snapshot.
3. Do **not** start Track D (overlay deepen).
4. Completeness ≠ Cert ≠ Autopilot. Promote stays human.

## Docket (later — do not start)
- **PROD-FAULT-LOG:** Production log of **in-app** faults with a founder dashboard/export. **Blocked on** honest diagnosis. See `docs/PRODUCTION-PLAN.md` § Docket.
- Tracks D from View Designer premium (overlay deepen).

## Rule to keep
- Evaluate Odoo inherit `//expr` as `.//expr` in ElementTree only. Never emit positional `[n]` when a unique `@name`/`@id` locator exists.
