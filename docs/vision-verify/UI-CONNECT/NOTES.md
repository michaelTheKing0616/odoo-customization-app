# UI-CONNECT · Connect Odoo (UI-S-08) vision notes

Card: UI-S-08 `/connect` (auth / connect hub). Pressure 8. Primary: **Add connection** (teal).
Status: elite UI pass implemented and verified locally after bar-raise redesign. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md` + tokens
- Global rules + UI-S-08 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Craft bar: UI-S-20-premier App Studio (`premier.css` paper / hero / one teal CTA)
- Bar raise (Tope): reject stacked what/why/next banner formula; match App Studio / Designer density

## Design Read

Operate-mode connect hub as a Claude / ChatGPT / Stitch-class paper surface: quiet pasteboard, left-aligned hero brief (−0.03em), one cream paper sheet for credentials, one teal **Add connection**, amber Observer chip only (real risk: read-only default), API-key tip inline for Online only, danger/success panels only when state demands. No purple, no orange CTAs, no em dashes, cinnabar never on buttons.

## What the pass delivers (post bar-raise)

| Thesis item | Where |
|---|---|
| Paper-as-object, not banner stack | `.cn-paper` layered shadow + cream tint on quiet `.connect-operate-desk` |
| Hero type hierarchy | `.cn-hero` clamp title + 17px subtitle |
| One teal primary | `connect-add-btn` / `PRIMARY_CTA` = Add connection |
| Amber only for real risk | Single Observer chip (`connect-honesty`); Online secret tip is muted inline, not a twin banner |
| No always-on what/why/next twins | Error / success use `ConnectStateGuide` panels only when failed or connected |
| Quiet stage rail | Dot stages (Credentials → Probe → Summary), not firmware pills |
| Probe stages (UI-S-08) | Inside-paper progress + Reaching / Version / Rights |
| API key guide collapsed | Steps open only after auth-style failure; Online still recommends key |
| Checklist flattened | Hairline progress list, not nested success cards |
| Saved list as second paper | Dense rows / quiet empty (no third guide banner stack) |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Paper + Observer chip + teal Add connection; empty saved paper |
| credentials | `?state=credentials` | Online secret tip inline; API key guide collapsed |
| probing | `?state=probing` | Probe step current; inside-paper progress |
| error-auth | `?state=error-auth` | Danger panel; API key next |
| error-dns | `?state=error-dns` | Host / DNS panel |
| error-tls | `?state=error-tls` | TLS panel |
| success | `?state=success` | Connected paper; App Studio primary; Observer gone |

Canonical: `desktop.png` = after-empty-desktop, `narrow.png` = after-credentials-narrow.
Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```bash
cd apps/web
# Prefer isolated: INGENIUM_DIST_DIR=.next-uiconnect NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3080
# This pass final capture used shared :3002 after isolated mirrors kept dying under load; OUR :3080 stopped.
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-CONNECT/capture.cjs \
  http://127.0.0.1:3002 ../../docs/vision-verify/UI-CONNECT after
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/connectScreen.test.ts src/lib/connect-checklist.test.ts src/components/connect/ConnectStepRail.test.tsx` → **3 files, 18 passed**
- Playwright: `e2e/connect-craft.spec.ts` → **6 passed** (paper + one Observer; Online tip not twin banner; probing; error-auth; success; no em dashes)
- Isolated `.next-uiconnect` on `:3080` was started for earlier rounds and **stopped**; final evidence from shared `:3002`. No mirror left running for this card.

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | Hero + one paper; one teal Add connection |
| IA | Pass | Credentials → Probe → Summary; success swaps paper content |
| Interaction | Pass | 44px primary; press scale; focus rings |
| Feedback | Pass | Probe stages inside paper; success / error panels state-gated |
| Errors | Pass | Classified DNS / TLS / auth / network with Next line |
| Accessibility | Pass | Stage `aria-current`; probe `role=status`; error `role=alert` |
| Cognitive load | Pass | No twin honesty banners; API steps collapsed by default |
| Trust | Pass | Observer chip; encrypted hint; secret write-only copy |
| Motion | Pass | ≤160ms press; probe fill gated by reduced-motion |
| Copy | Pass | Sentence case; no em dashes on connect surfaces scrubbed |
| Density | Pass | Paper craft; flattened checklist; intentional desk space |
| Responsive | Pass | Narrow overflowX=0 |

## Bar-raise delta (vs first banner-stack draft)

- Removed always-on `ConnectStateGuide` honesty + API-key what/why/next twins.
- Replaced pill firmware rail with quiet dots.
- Switched shell to pasteboard + cream paper (App Studio premier language).
- Collapsed API key walkthrough by default; open on auth failure only.
- Flattened checklist nested cards via operate CSS.
- Checklist outer chrome flattened to transparent progress (no nested card border); API key guide collapsed by default.

## Known gaps / siblings not elevated

- `/login`, `/signup`, `/reset-password`, `/verify`, marketing `/` (UI-S-01–07) noted as siblings; only `/connect` got the full paper pass. Landing still carries brand-locked tagline punctuation from `brand.ts`.
- Live `/connect` still hits real `api.listConnections`; harness is `/e2e/connect`.
- Host capability bullets now gated to `showCapabilities` (post-save / explicit); not mid-form.
- Checklist component structure unchanged; visual flatten is CSS under `.connect-operate`.
- `tsconfig` / `.next-uiconnect` may linger on disk; process on `:3080` stopped.

## Files touched

- `apps/web/src/app/connect/page.tsx`
- `apps/web/src/app/e2e/connect/page.tsx`
- `apps/web/src/components/connect/connect-operate.css`
- `apps/web/src/components/connect/ConnectStepRail.tsx` (+ test)
- `apps/web/src/components/connect/ConnectStateGuide.tsx`
- `apps/web/src/components/connect/ConnectApiKeyGuide.tsx` (collapse default; em-dash scrub)
- `apps/web/src/components/connect/ConnectChecklist.tsx` (capabilities gate)
- `apps/web/src/lib/connectScreen.ts` (+ test)
- `apps/web/src/lib/connect-checklist.ts` (em/en dash scrub)
- `apps/web/src/lib/odoo-hosting.ts` (em/en dash scrub)
- `apps/web/e2e/connect-craft.spec.ts`
- `docs/vision-verify/UI-CONNECT/*`

## Not touched

`odoo_addons/`, plan-inbox, bots/bridge, settings/admin (UI-S-41), fleet/command, live-demo, journal, config, studio/designer internals, git state (no commit / stash / checkout / push / clean). **No DONE.**
