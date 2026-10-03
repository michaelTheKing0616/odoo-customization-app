# Track 7 — UI, motion, and copy

D12: Base UI, Sonner, `motion/react`. `cmdk` stays. Operate screens are dense and calm. Marketing is the only place that uses a louder visual system.

Load before any UI card: `ui-craft-dense-dashboard` (operate), `accessibility` / `frontend-a11y`, `form-design` or `error-handling-ux` when the screen has a form, `feedback-patterns`, `no-ai-slop`, and the motion skills named on the card. Marketing cards load `frontend-design` and `landing-page` instead of the dense-dashboard skill.

## Dials

Operate: design variance low, motion intensity 2–3, visual density 9. Body 13–14px, tables may use 12px, titles 18–20px, `tabular-nums` for figures, mono for ids. Spacing only 4, 8, 12, 16, 24. Sidebar 200–240px. One accent. Status colors: red, amber, green, blue, one meaning each. No pie charts. No purple gradient. No cards nested more than two deep.

## Motion

| Rule | Value |
|---|---|
| Purpose | feedback, spatial continuity, state, or preventing a jump. Delight only on rare moments (first approval success) |
| Frequency | 100+ times a day or keyboard: no animation. Command palette open is instant |
| Properties | `transform` and `opacity` only. Never `transition: all`. Never animate `backdrop-filter` |
| Easing | Enter and exit `cubic-bezier(0.23, 1, 0.32, 1)`. Drawers `cubic-bezier(0.32, 0.72, 0, 1)`. Never ease-in for UI |
| Press | 100–160ms, `scale(0.97)`. Never `scale(0)` |
| Tooltip | 125–200ms |
| Dropdown | 150–250ms |
| Modal | 200–300ms. Product UI stays under 300ms |
| Exit | about 75% of the enter duration |
| Stagger | 30–80ms. Not inside tables |
| Tables | row hover 80ms. No scroll-reveal |
| Interruptible | yes. Pointer-down responds immediately |
| Reduced motion | opacity only, ≤ 0.2s. Content is visible without waiting for JS |
| Blur | ≤ 8px and one-shot, or not at all |

`motion/react` is for layout shifts in the approval inbox and diff panes, and for drawer and sheet motion that must be interruptible. Everything else stays CSS.

## Feedback

Inline first, then the component, then a toast, then a system banner. Toasts 3–5s via Sonner. Errors persist. Undo beats a confirm dialog except for destructive actions. Destructive confirms keep the existing phrase requirement where the screen already uses "I understand the risks". Color is never the only signal.

## Copy

Verb plus object on buttons. Errors say what happened, why, and the next step. Empty states teach and offer one action. No "Oops". No fake urgency. A score of 1 on Accuracy or Ethics in the copy rubric blocks the card no matter the other scores. Do not average the nine scores into one number.

AI output is labeled as AI, shows provenance, and asks before an irreversible step. The agent does not claim to be human.

## Accessibility target

WCAG 2.2 AA.

- Contrast 4.5:1 for text, 3:1 for large text and UI components (1.4.3, 1.4.11).
- Keyboard (2.1.1). Focus visible (2.4.7) and not obscured (2.4.11). Focus ring ≥ 2px.
- Target size 24×24 CSS pixels minimum (2.5.8). Prefer 40–44px where density allows.
- Errors in text (3.3.1) with suggestions (3.3.3). No redundant entry (3.3.7).
- Accessible authentication: paste and password managers work (3.3.8). `input-otp` for TOTP.
- Name, role, value (4.1.2). Status messages (4.1.3). Toasts are polite. Alerts do not steal focus unless they are blocking.
- Native elements before ARIA. Dialog traps Tab, Escape closes, focus returns.
- INP at or under 200ms. Sort and filter under 100ms. Acknowledge input under 100ms. No spinner flash under 400ms; use a skeleton that matches the layout.

## UX audit (apply to every restyled screen)

Each item is Pass, Issue, or Not observable.

| Area | Check |
|---|---|
| Hierarchy | One clear primary action per view; reading order matches importance |
| IA | Labels use the user's words; title, breadcrumb, or selected nav shows where they are |
| Interaction | Controls look interactive; targets at least 24 by 24 CSS px |
| Feedback | Every action gets a visible response; status messages announced |
| Errors | Prevention first; errors in text; suggestions; recovery; undo where possible |
| Accessibility | Contrast, focus visible and not obscured, keyboard, labels, name/role/value |
| Cognitive load | No memory across steps; recognition over recall; no redundant entry |
| Trust | Real details, clear prices, no fake urgency |
| Copy | Passes the copy rubric with no blocker |
| Forms | Visible labels, correct input types and autocomplete, few fields |
| Performance | Responsive to input |
| Business goal | The design supports the goal without harming users |

A screenshot cannot prove focus order, keyboard traps, screen reader output, or latency. Say "not observable" instead of passing those.

## Copy critique dimensions

Score 1, 3, or 5: Clarity, Task fit, Actionability, Accuracy and proof, Tone fit, Concision, Accessibility, Ethics, Slop-free.

Output the quoted string, the nine scores, the biggest problem, a revision, a confidence level, and what would settle it. A 1 on Accuracy or Ethics is a blocker.

## Foundation order

1. Tokens stay in `globals.css`. Fix `.odoo-form-alert--*` so dark mode does not use light-only hex.
2. Add `loading.tsx`, `error.tsx`, and `not-found.tsx` at the app root and under `connections/[id]`.
3. EmptyState and Skeleton on every page that can be empty or loading.
4. Migrate Radix families one at a time: Dialog, Tabs, Tooltip, Slot. Kit tests and `/e2e/kit` stay green.
5. Sonner replaces `components/ui/Toast` only after the screen-reader check. If the current toast already announces, the card records that and still moves, because D12 chose Sonner.
6. `motion/react` primitives: drawer, sheet, approval-list layout.
7. `input-otp` on TOTP enroll. `react-virtuoso` on tables that can exceed 50 rows.
8. Split god pages before restyling them: wizard, studio, designer, bulk-suite, connection overview, config, and `api.ts` by domain with no behavior change.
9. Extend axe from 8 specs to every operate route.

## Per-screen specs

`13_UI_SCREEN_SPECS.md` is the route list. A UI card is not done until its route block's states exist and the audit table is filled in the progress log.
