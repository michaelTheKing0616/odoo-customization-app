# UI-S-20-premier — App Studio premier leap

Date: 2026-10-05 (Africa/Lagos). Branch: `premium-local-tip` (no commit).

## Design Read
Operate-mode App Studio as a ChatGPT / Claude / Stitch-class craft surface: calm left-aligned hero brief, one huge composer, restrained neutrals, one teal primary CTA, cinnabar keystone only, honesty banners kept, Completeness ≠ Cert ≠ Autopilot kept separate.

## Playbook rules applied
- **§0 law 3** One accent, one meaning — `btn-primary` / accent teal (`#0f766e`); remapped any `.btn-brand` orange under `.studio-refinement`.
- **§0 law 4 / §3** Display tracking −0.03em, body 16px+ on mobile inputs, `text-wrap: balance/pretty`.
- **§0 law 5 / §4** Inter-group spacing ≥ 2× intra; composer and diagnosis card use 4pt rhythm.
- **§0 law 6** Skeleton pulse ≤1.6s ease-out; reduced-motion kills it; press 160ms.
- **§0 law 9 / Favour no-ai-slop** No eyebrow kickers, no em dashes in operator UI copy, no orange CTAs, no Odoo purple chrome.
- **Brand guide** Cinnabar keystone only; app accent stays teal; never cinnabar buttons.
- **Canvas thesis** Paper-as-object on quiet pasteboard (Reports family): cream-tinted sheet, soft layered shadow, 16px dot desk.

## What changed (this leap)
1. **Fixed red ClarifyInterstitial vitest** — copy assertion matched human lead ("edit anything that looks wrong"); `afterEach(cleanup)` so failures no longer cascade into "multiple elements".
2. **Removed BuildSpineBar from App Studio shell** — stage rail carries journey; mode chip switcher felt like firmware chrome on a chat product.
3. **premier.css** — left-aligned hero, quieter spine CSS (defence in depth), cream paper tint on `.odoo-form-sheet`, brand-orange→teal remap under `.studio-refinement`.
4. **Copy** — replace em dash in Expert repair refine prompt (`StudioReviewSection`).
5. **Tests** — extended `StudioUiPass` with premier craft-panel singularity + failed recovery one-teal-primary checks.
6. **Vision** — `docs/vision-verify/UI-S-20-premier/` after shots for brief / diagnosis / generating / failed / review × desktop+mobile; before-brief copied from UI-S-20.

## Vision files
- `before-brief-{desktop,mobile}.png` (from UI-S-20)
- `after-{brief,diagnosis,generating,failed,review}-{desktop,mobile}.png`
- All captures `overflowX=0`
- Harness: `/e2e/studio?state=…` with `NEXT_PUBLIC_E2E=1` (no live LLM)

## Tests
`npx vitest run src/components/studio` → **10 files, 44 passed, 0 failed** (was 5 failed on ClarifyInterstitial).

## Remaining gaps / intentionally not touched
- Turbopack sometimes served a stale CSS chunk hash; component removal of spine is the reliable fix. Full CSS HMR restart not forced on the shared `:3002` server.
- `BuildSpineBar` still exists for other routes (Draft / Job / etc.); only App Studio shell dropped it.
- No git commit / push / DONE markers.
- `odoo_addons/` untouched.
- Did not invent live LLM calls in tests (stubs only).
