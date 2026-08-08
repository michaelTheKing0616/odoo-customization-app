# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-08
- **Shipped:** apply-readiness v5–v6 + module export fixes + sandbox gate green on fixture5 (`test_fixture5_sandbox_install_smoke` PASSED, 31 apply-readiness tests).
- **Export fixes:** `groups.xml` before access CSV; strip invalid `base.module_category_custom`; prefix access groups; `normalize_menu_xml_references` for truncated menu parent ids; search filters get required `name` attrs (no duplicate group_by).
- **Honest grade:** live 14:59 draft ≈ **9.9/10** (v6 automations clean; 10.0 blocked on reuse/sandbox/process, not pipeline bugs).

## Next
- Re-save live supermarket draft (Retry enrichment) to pick up v6 + export fixes
- Optional honest-10.0: operator adds `sale.order`/`account.move` reuse; wire promo discount to line math
- EU Tongyi agreement still human/legal only

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
