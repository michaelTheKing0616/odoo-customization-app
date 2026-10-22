# UI-S-25 Expert (`/connections/[id]/expert`): vision verify

Spec: `docs/plans/next-phase/13_UI_SCREEN_SPECS.md` UI-S-25. Primary: **Ask**. Skill: `conversational-ux`.
Must not: let the drawer and the page drift apart. They are now one component.

## Design read
- **One conversation, two surfaces.** `useExpertConversation(surface)` holds all state and `ExpertConversation`
  is the only view (context bar, StageProgress, thread, composer). The shell drawer (`ExpertPanel`) and the page
  (`ExpertPanel variant="page"` inside `ExpertDestination`) both render it, marked with `data-surface`. On the
  Expert route the drawer and the floating launcher stand down, and `openExpert()` prefills answer inline.
- **Chrome:** basalt neutrals, one teal accent (`--color-accent`), no cinnabar on this page, no purple, no orange
  primary. The error callout uses the shared danger tone, not an action color.
- **Hierarchy:** PageHeader (title + connection + honesty line), then a two-column grid: the conversation surface
  (fixed height, the thread scrolls inside it, never the page) and a 320px sticky rail: intent router, "What Expert
  will not do" (honesty line and legend kept), and a folded "Build it in a studio" disclosure.
- **One primary:** "Ask Expert" is the only filled button. Find feature, Open, Ask again, Copy, New thread and
  starters are secondary or quiet.
- **Calm, dense, honest:** neutral user bubble, assistant answers run full width next to a neutral avatar, meta
  row (grounding badge, N sources, Copy) above the answer, sources as indexed rows, the log-as-note action last.

## Harness
`capture.cjs` drives the real route with Playwright route mocks (no live Odoo, no live LLM). The thread is seeded
via sessionStorage `expert-thread-demo-conn`.

```
NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-25/capture.cjs http://127.0.0.1:<port> docs/vision-verify/UI-S-25 after [states]
```

States: `empty answer loading error route unsupported drawer` x `desktop` (1440x900) and `narrow` (390x844).
`drawer` is the `/e2e/expert` harness with the shell drawer open; `/e2e/expert?surface=page` renders the page twin.
`before-*` is the pre-pass baseline (empty, answer, route, unsupported, drawer).
Canonical: `desktop.png` = after-answer-desktop, `narrow.png` = after-empty-narrow. Every after shot has overflowX = 0.

## UX audit (12 rows)

| # | Area | Before | After |
|---|------|--------|-------|
| 1 | Drawer vs page | The page had no conversation: intent router plus an overview card whose "Open Expert" opened the drawer. All logic lived in `ExpertPanel`. | One hook, one view. Page and drawer share `ExpertConversation`. Drawer and launcher hide on the Expert route (tested). |
| 2 | Primary CTA | Page: "Find feature" and "Open Expert" competed for the primary; the ask itself lived in the drawer. | Only "Ask Expert" is filled. Find feature and Open are secondary, starters are quiet pills. |
| 3 | Error | "Expert unavailable" callout with the raw message, no retry. | "Expert could not answer", the raw reason, the next step, then Ask again (re-sends once, no duplicate turn) and Dismiss. |
| 4 | Loading | Only in the drawer; the page had nothing to show. | StageProgress with a details toggle plus a typing row with `role="status"`; reduced motion respected. |
| 5 | Empty | Starter buttons with full questions, nothing when the API returned none. | h2 title, honest body, label + truncated question rows, curated fallback (max 4), skeleton rows while loading. |
| 6 | Answer reading | Prose classes without the typography plugin, so lists collapsed. Scroll jumped to the end of long answers. | `.expert-answer` typography (lists, code, citations). A new answer lands with its question pinned at the top. |
| 7 | Sources | Tooltip used an em dash, chips not focusable. | Indexed rows, focusable chips with aria-labels, "source · version · breadcrumb". |
| 8 | Context | "Page context on" next to a "Page context" label; on the Expert page it showed the route name "expert". | `role="switch"` toggle, mono value, "Nothing to share on this page" or "Not shared"; the Expert route is not reported as context. On phones the value gets its own line. |
| 9 | Composer | Plain textarea, error paste always visible, double focus ring. | One rounded box with a single accent focus ring, "Add an error log" disclosure (`aria-expanded`), "⌘ Enter to send" hint (hidden on phones), 16px input on phones. |
| 10 | Intent router | Eyebrow, arrows, em dashes, "Go" buttons, long paths wrapping mid-word. | Sentence case, "Open" with aria-label, rail layout with full-width input, paths truncated with a title. |
| 11 | Accessibility | Page had no thread; in the drawer it was a plain div. | Thread `role="log"` with `aria-busy`, focus-visible outlines, hover gated to fine pointers, composer focus on top-bar open. axe passes (a11y-primary Expert). |
| 12 | Copy | Em dashes in legend, empty body, overview, caution flags, bubble tooltip; kicker eyebrows. | No em or en dashes in Expert copy (locked by `expert-copy.test.ts`), kickers removed, honesty contract unchanged. |

## Must-not list (held)
- Drawer and page do not diverge: one component, tested in `ExpertSurfaces.test.tsx`.
- Honesty banners and legend kept ("Completeness ≠ Cert ≠ Autopilot. Expert never auto-promotes.").
- Motion: transform and opacity only, 150 to 160ms `var(--ease-out)`, a reduced-motion block, SheetMotion for the drawer.
- No test loosened. Typecheck error count unchanged (19, none in Expert files).

## Gaps (not fixed here)
- `ExpertOverviewCard.test.tsx` expects "View Designer" and "Projects" links, but BuildSpineBar (commit 80b78f9)
  renders "Prefer / Designer". It failed before this pass too; the test was not changed.
- `e2e/shell-expert.spec.ts` › "expert panel opens from harness with mocked ask" fails because the overview page's
  FirstWriteInterstitial (commit 3ceeaa4) opens over the drawer: the spec's catch-all mock returns `[]` for
  production readiness. With `first-write-ack:demo-conn` set, the same flow passes. Spec not changed.
- BuildSpineBar's own eyebrow is hidden only by rail-scoped CSS; `components/build` was not edited.
- AppShell sidebar stays as an icon rail at 390px and the top-bar chips wrap (global shell).
- The `/e2e/expert` drawer harness still shows an "Open Expert" primary on its overview card (harness only).
- Server strings (answers, intent notes, caution text from the API) are shown as-is.
- The Sparkles icon stays the Expert icon (shared `icons.ts`).
