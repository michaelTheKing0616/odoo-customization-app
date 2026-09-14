# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium Menus + Access (surface 2 of the premium sweep) on `cursor/menus-access-premium-9cb8` off Designer/Automations/Builder:
  - Menus: tree → composer/detail (parent, sequence, action bind/create, visibility groups, snapshots, confirm-phrase delete)
  - Access: ACL + record-rule list → composer/detail (DomainBuilder, group grants, matrix as disclosure)
  - Shared: `GroupPicker`, `CrudPermitsControl`; Odoo 19 `group_ids` vs 17/18 `groups_id` on `ir.ui.menu`
- **Tests:** web vitest 314 passed; `test_menus_builder_groups.py` 2 passed
- **Not in this run:** App Studio / Draft Studio / Job Autopilot / ModuleSpec / Projects / Expert; live browser against Odoo

## Next
- Verify Menus + Access on a probed connection: create menu, create ACL + record rule, delete with phrase
- Continue premium sweep only if asked (do not start App Studio here)

## Rule
- Premium chrome is list→detail/composer + draft/unsaved/saved only — do not copy Designer undo/redo onto Menus/Access
