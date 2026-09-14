# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of this session.

## Last run
- Date: 2026-09-14
- **Shipped:** Track B semantic XPath (prior) + CI unblock on `cursor/view-designer-field-inspector-e8e2`. Nested `PreviewThemeScope` removed so CMP-3 has one `preview-theme-scope`. `test_llm_provider` forces `AI_LLM_TIER_FAST=auto`. Next 15.5.24 patches RCE; remaining pnpm GHSAs stay allowlisted. Primary teal is accent7 for WCAG AA.
- **Failed:** First CI unblock left Playwright a11y/wizard/expert and TRUST-6/7 red. Nested Odoo preview + Gemini-default tier were the Track B-adjacent causes.
- **Rule:** `OdooPreviewScope` owns theme vars — do not wrap it in another `PreviewThemeScope`. LLM routing tests must set tier `auto` (settings default is `gemini`).

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
