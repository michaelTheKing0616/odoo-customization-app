# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of this session.

## Last run
- Date: 2026-09-14
- **Shipped:** Track B upgrade-safe semantic XPath + broken-locator validation on the Track A branch (`cursor/view-designer-field-inspector-e8e2`). ElementTree eval maps Odoo `//` → `.//`; inherit XML still emits `//`. Designer XPath panel is elite severity UI; save/overlay block missing/ambiguous locators.
- **Proof:** `test_xpath_locator.py`, `test_xpath_preview_validation.py`, `xpathLocator.test.ts`, `XPathInheritPanel.test.tsx`.

## Next (operator)
1. View Designer → XPath inherit: Preview locator against the loaded parent arch. Positional `[n]` should warn with a named alternative; missing/ambiguous blocks Save xpath inherit.
2. Overlay: field candidates should be distinct named xpaths with upgrade-fragile hints.
3. Do **not** start Tracks C/D (draft/publish, overlay deepen).
4. Completeness ≠ Cert ≠ Autopilot. Promote stays human.

## Docket (later — do not start)
- **PROD-FAULT-LOG:** Production log of **in-app** faults with a founder dashboard/export. **Blocked on** honest diagnosis. See `docs/PRODUCTION-PLAN.md` § Docket.
- Tracks C/D from View Designer premium.

## Rule to keep
- Evaluate Odoo inherit `//expr` as `.//expr` in ElementTree only. Never emit positional `[n]` when a unique `@name`/`@id` locator exists.
