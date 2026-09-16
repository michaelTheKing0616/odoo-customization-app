# Odoo Customization App — Visual System Upgrade Proposal (design only)

**From:** UI DESIGN BOT PRIME  
**For:** Odoo Customization App Bot Builder → Fabian + Claude refine before build  
**Date:** 2026-09-16  
**Spec basis:** `PREMIUM-WORLD-CLASS-UPGRADE-SPEC.md` §2.3, §4–5, §7.1–7.10, §8  
**Bar:** Linear / Figma properties / Intercom / Stripe Dashboard  
**Hard reject:** anything that looks worse than today; no decorative gradients; no purple nostalgia `#714B67`; no random hex; no cluttered “premium” chrome; never break honesty/safety dialect

---

## North star (one sentence)

Quiet density: **more signal per pixel, less chrome per decision** — same safety voice, Figma-grade inspectors, Stripe-grade lists, Linear-grade shell.

---

## 0. Non-negotiables (visual)

| Do | Don’t |
|---|---|
| Token-only color (`text-ink`, `bg-surface`, …) | Raw hex in product pages |
| ≤2 accents (e.g. `accent` + `danger`) | Rainbow status chips, Odoo purple nostalgia |
| 150–200ms ease-out motion | Carnival springs, parallax, marketing blobs |
| Progressive disclosure | Banner piles, always-open mega sidebars |
| Empty/loading/error/forbidden as designed states | Spinners in place of structure |
| Honesty labels stay visible and calm | Softening “sandbox / confirm / not done” to look pretty |

---

## 1. Type scale (freeze)

Propose Inter (or current sans) only — **no display serif in product chrome** (marketing site can differ).

| Token | Size / line / weight | Use |
|---|---|---|
| `text-display` | 20/28 · 600 | Page title only (Overview, Designer) |
| `text-title` | 16/24 · 600 | Panel titles, composer headers |
| `text-body` | 13/20 · 400 | Default UI |
| `text-body-em` | 13/20 · 500 | Emphasized rows, selected |
| `text-label` | 12/16 · 500 | Section labels in inspectors |
| `text-meta` | 11/16 · 400 · tracking 0.02em | Caps, IDs, xpath crumbs, timestamps |
| `text-mono` | 12/16 · mono | XML attrs, technical keys |

**Before→after:** Today mixes sizes per page → after, inspectors and lists share one scale so Designer no longer feels “different product” from Automations.

**Acceptance:** Spot-check 5 surfaces; no one-off `text-[13px]` / arbitrary leading outside tokens.

---

## 2. Density & spacing

| Token | Value | Use |
|---|---|---|
| `space-1`…`4` | 4 / 8 / 12 / 16 | Internal control padding |
| `space-5`…`6` | 20 / 24 | Section gaps |
| Row height (lists) | **36px** default, 32 compact | Stripe tables |
| Inspector row | **label 12 + control 32** stacked or 120px label column | Figma properties |
| Sidebar width | **220** collapsed icons **56** | Linear |
| Right inspector | **280–320** fixed | Figma |

**Before→after:** Tall padded cards → compact rows with hairline dividers; more fields visible without scroll in View Designer props.

**Acceptance:** Designer properties show ≥12 field attrs above fold at 1440×900 without feeling cramped (8px rhythm intact).

---

## 3. Elevation & borders

Keep **flat-first** (Stripe/Linear):

| Level | Recipe |
|---|---|
| 0 page | `bg-surface` |
| 1 panel | `bg-elevated` + `border-subtle` 1px |
| 2 popover/menu | same + shadow-sm (token) |
| 3 modal | shadow-md + scrim `bg-ink/40` |

**Reject:** multi-stop gradients, glassmorphism on product chrome, colored shadows.

---

## 4. Motion (150–200ms)

| Pattern | Spec |
|---|---|
| Panel open / list→composer | `opacity + translateY(4px)`, 180ms ease-out |
| Sidebar collapse | width 180ms; content reflow no bounce |
| Toast / confirm | 160ms |
| Live canvas selection HUD | 120ms opacity only |
| Reduced motion | instant opacity; no travel |

**Reject:** shared-element morphs that fight honesty dialogs; skeleton shimmer longer than 1.2s.

---

## 5. Shell / sidebar

**Target:** Linear-like AppShell — nav groups Build / AI Studio / Operate stay, but **visual weight drops**.

| Before risk | After |
|---|---|
| Heavy section chrome, dual Expert launchers | One Expert entry; quiet group labels (`text-meta`) |
| Busy Overview | Mission control: connection health, **next action**, capabilities postcard (human), recent Projects |
| AI Studio 5 doors equal weight | **App Studio** primary CTA; Projects hub; Job/ModuleSpec secondary links; Draft demoted |

**Acceptance:** Untrained user names the AI entry door in ≤3s from shell screenshot.

---

## 6. List → composer (shared kit)

Unify Automations / Models / Menus / Access / ModuleSpec lists:

1. Left list (search + filters + density toggle)  
2. Right composer OR full-bleed composer with sticky back  
3. Session chip: `Draft` / `Unsaved` / `Saved` (existing language — keep)  
4. Sticky footer: primary + secondary; danger always ConfirmDialogV2  

**Properties density:** sticky section headers; 8px gaps; keyboard ↑↓ between fields; no card-in-card.

---

## 7. View Designer properties (P0 craft)

| Before | After |
|---|---|
| Orchestrator dump; uneven props | Extracted inspector: **Selection / Layout / Attributes / Inherit** accordion; only Selection expanded by default |
| Dual-canvas leftovers | Single live canvas + overlay HUD |
| Advanced XPath always loud | Progressive disclosure “Advanced inherit” |

**Acceptance (align §7.1 / §8):** Chrome UAT Designer ≥4.5 visual; props feel Figma-like; no purple harness in `/e2e/designer` for QA screenshots.

---

## 8. AI Studio journey chrome

| Intent | Chrome |
|---|---|
| Hero | App Studio staged journey; **collapse completed stages** to checkmarks |
| Hub | Projects board as home object |
| Power | ModuleSpec / Job linked, not competing heroes |
| Review | One review panel > banner stack |

**Acceptance:** ≤1 primary CTA per AI landing; stage rail collapses later panels (fix §5.1 P2 → P1 visual).

---

## 9. Overview mission-control

Blocks (top→bottom):  
1. Connection status + major/caps postcard  
2. **Next action** (first-win checklist if <1 customization)  
3. Health / recent faults → Expert handoff  
4. Recent Projects  

**Reject:** engineer dump of raw caps JSON as the hero.

---

## 10. Empty / loading / error kit

Mandatory skeleton per surface:

| State | Pattern |
|---|---|
| Empty | Icon + one sentence + one CTA (token illustration, not gradient art) |
| Loading | Structure-preserving skeleton (same density as loaded) |
| Error | Honest cause + retry + Expert link when Odoo/RPC |
| Forbidden | Capability postcard “why locked” |
| Success | Quiet toast; never fake “done” for sandbox-pending |

---

## 11. Priority sequence (visual only)

1. **Design system freeze doc** (this → Claude v2 tokens table) + hex lint  
2. **Designer inspector density**  
3. **AI Studio IA visual hierarchy** (App Studio hero / Projects hub)  
4. **Overview mission-control**  
5. Shared list→composer + empty states sweep  
6. Co-Pilot overlay Intercom-grade (after real pilot — don’t pretty-lie)

---

## 12. Open questions for Claude / Fabian

1. Confirm **Inter-only** product type vs keep any existing secondary family.  
2. Accent: keep current brand accent token or shift to a cooler Linear-blue — still **one** accent?  
3. Draft Studio: demote in nav only, or visually merge stages into App Studio in M1?  
4. Compact density default on or opt-in?  
5. Can we get 3 screenshots (Designer props, App Studio, Overview) from tip for before baselines?

---

## Hard reject checklist (paste into PR review)

- [ ] Looks better or equal to tip in side-by-side  
- [ ] No `#714B67` / decorative gradient / random hex  
- [ ] Safety copy not softened  
- [ ] Motion ≤200ms; reduced-motion OK  
- [ ] Token-only colors  
- [ ] No extra chrome that hides next action  
