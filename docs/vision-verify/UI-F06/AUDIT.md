# UI-F06 — Tooltip on Base UI evidence (2026-10-05)

Scope: `apps/web/src/components/ui/Tooltip.tsx`. That is the only file the card allows. Its public API (`Tooltip({ label, children })` and `TooltipProvider`) is unchanged, so none of the nine callers changed.

- The Base UI swap (`@base-ui/react` 1.8.0) and the Radix removal landed in `ba38ac9`. `rg -l "@radix-ui" apps/web/src` returns nothing, and `package.json` has no `@radix-ui/react-tooltip`.
- This pass adds three things:
  - The open popup is linked from the trigger through `aria-describedby`. Base UI 1.8.0 does not set this. Any `aria-describedby` the child already had is kept.
  - Motion on `transform` and `opacity` uses the UI-F09 constants: enter is 200 ms (dropdown range), exit is 150 ms, and the easing is `EASE_ENTER_EXIT`. Base UI `instant` opens use 0 ms.
  - With reduced motion, the transition is opacity only at 200 ms.
- Open delay is 200 ms through `TooltipProvider`. Close delay stays at Base UI's 0 ms because the card names no close timing.

Evidence comes from `apps/web/e2e/a11y-ui-f06.spec.ts`. It ran against `pnpm dev` on `:3002` (`NEXT_PUBLIC_E2E=1`) on the `/e2e/expert` harness, with the API mocked by `mockConnectionApi`. The tooltip under test belongs to `ExplainThisButton`. Desktop is 1440×900 and narrow is 390×844. Screenshots are viewport only and taken with the tooltip open.

## axe (wcag2a/aa, 21a/aa; same rule set as `a11y-primary.spec.ts`), tooltip open

Raw results: `axe-results.jsonl`.

| Route / state | Desktop | 390 |
|---|---|---|
| `/e2e/expert`, tooltip open from keyboard Tab focus | 0 | 0 |
| `/e2e/expert`, tooltip open from hover, reduced motion | 0 | 0 |

The same spec also asserts the following:

- With keyboard focus, `aria-describedby` on the trigger equals the tooltip `id`.
- Escape removes the tooltip, drops `aria-describedby`, and keeps focus on the trigger.
- With reduced motion, the computed `transition-property` is `opacity` and `transform` is `none`.
- With full motion, it is `transform, opacity` and every duration is under 300 ms.

## Screenshots

- `expert-tooltip-keyboard-{desktop,390}.png`: open from Tab focus. The trigger shows its focus ring.
- `expert-tooltip-hover-reduced-{desktop,390}.png`: open from hover with reduced motion emulated.

The red "1 Issue" badge in the corner is the Next.js dev overlay. It reports a pre-existing hydration `id` mismatch on the Base UI trigger in this harness. An SSR-then-hydrate vitest of `Tooltip` alone hydrated with identical ids, so the mismatch comes from an ancestor in the harness tree, not from this card.

## UX audit (12 rows, `T7_UI_MOTION_COPY.md`)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | The tooltip is a small `text-xs` overlay. It does not compete with the page and sits 4 px off its trigger. |
| IA | Not observable | No navigation or labels changed. |
| Interaction | Pass | It opens after 200 ms on hover and right away on keyboard focus. Escape closes it. The child's click handler is preserved (characterization test). |
| Feedback | Pass | Opening is a 200 ms scale-and-fade from the trigger side (`--transform-origin`). The exit is shorter at 150 ms. CSS transitions reverse mid-flight, so the motion is interruptible. |
| Errors | Not observable | The tooltip has no error states. |
| Accessibility | Pass | `role="tooltip"` is linked through `aria-describedby` only while open, so there is no dangling id. axe is 0 at both widths. The trigger keeps its accessible name, and the tooltip only adds a description. |
| Cognitive load | Pass | One short line. No extra controls. |
| Trust | Pass | The label text is unchanged from the callers. |
| Copy | Not observable | No visible strings changed in this card. |
| Forms | Not observable | No form fields were changed. |
| Performance | Pass | Only `transform` and `opacity` animate, never `all`. Reduced motion is opacity only at 200 ms or less. |
| Business goal | Pass | Keyboard and screen-reader users now get the same hint that mouse users see. |

Not observable from screenshots: screen-reader announcement wording, latency.

## Pre-existing, not counted against this card

- `Sidebar.tsx` wraps an `sr-only` `<span>`, and `ExpertSources.tsx` wraps a `<sup>`, as tooltip triggers. Neither is focusable, so keyboard users never open those two tooltips. The fix belongs in those callers, which are outside this card's "Change".
- `e2e/shell-expert.spec.ts` › "expert panel opens from harness" fails. The "Before your first write on this connection" safety modal opens over the Expert panel and makes its "Ask Expert" button inert. The tooltip trigger click (`open-expert`) in that test passes.
