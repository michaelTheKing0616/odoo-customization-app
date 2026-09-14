# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** P0 UAT remediation PR https://github.com/michaelTheKing0616/odoo-customization-app/pull/14 off `cursor/premium-uat-world-class-595a`
  - Access live pack confirm-gated (API 403 without phrase; ConfirmDialogV2)
  - Job Autopilot resume from remembered job id + honest progress copy
  - Overview “Draft with AI” → App Studio; Draft Studio secondary
  - Projects Apply disabled until Review vs live
  - ModuleSpec chrome/handoff links Projects
- **Tests:** Vitest 34 targeted passed; pytest `test_access_live_pack_confirm.py` 4 passed (no app DB)

## Next
- Extract View Designer 5.7k dump (not this PR)
- Access matrix live CRUD confirm
- Founder live RPC UAT on `:8069`

## Rule
- Apply-live HTTP routes that create a global `ir.rule` must require `I understand the risks` before `_client` / RPC
