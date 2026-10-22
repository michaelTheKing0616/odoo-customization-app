# UI-S-21 Wizard (`/connections/[id]/wizard`): vision verify

Spec: `docs/plans/next-phase/13_UI_SCREEN_SPECS.md` UI-S-21. Primary: **Generate the draft**. Clarify asks one
question at a time. Scorecard labels Completeness, Certification, and Autopilot separately.

## Design read
- **Chrome:** Basalt neutrals, one teal accent (`--color-accent`), no cinnabar on this page, no purple, no orange primary.
  Warning callouts (Online, Option A) use the shared semantic warning tone, not an action color.
- **Hierarchy:** PageHeader, then a quiet IA note, the stage rail, and a folded "Switch build mode" disclosure.
  The brief hero ("What should we implement?") owns the page; reuse, identity, and the component gallery are folded.
- **One primary per stage:** prompt stage shows only "Generate the draft". Review shows Regenerate, Open ModuleSpec,
  Open View Designer, and Download zip as secondary, with Apply to Odoo as the only filled button (module zip or
  Job Autopilot take the slot when the draft calls for them). If the primary is disabled, visible text says why.
- **Honesty kept:** live-apply and unfinished banners, Option A callout, gate callouts, and confirm dialogs are all
  still there. New: an Odoo Online banner, and on Online the Option A prove and Promote actions are turned off,
  with the reason shown in visible text.

## Harness
`capture.cjs` drives the real route with Playwright route mocks (no live Odoo, no live LLM):

```
NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-21/capture.cjs http://127.0.0.1:<port> docs/vision-verify/UI-S-21 after
```

States: `empty brief progress error review clarify online stock unprobed` × `desktop` (1440×900) and `narrow`
(390×844, isMobile). On narrow it collapses the AppShell sidebar (see gaps) and also saves
`after-review-scorecard-narrow.png` (the Scorecard tab). `before-*` shots are the pre-pass baseline.
Canonical: `desktop.png` = after-review-desktop, `narrow.png` = after-brief-narrow. All after shots: overflowX = 0.

## UX audit (12 rows)

| # | Area | Before | After |
|---|------|--------|-------|
| 1 | Primary CTA | "1. Create draft" sat under the reuse panel. The dock had 3 disabled buttons (Create, Apply, ModuleSpec). | One filled "Generate the draft" right under the composer. Apply and ModuleSpec appear only once a draft exists. |
| 2 | Disabled reason | Only a hover tooltip. | Visible reason linked with `aria-describedby` (`create-draft-reason`, `apply-to-odoo-reason`). |
| 3 | Review actions | "1. Create draft" primary competed with Apply. | Regenerate is secondary. Apply is the only primary. After apply it becomes "Apply again" (secondary). |
| 4 | Scorecard | Headline fused "Completeness … · Cert …". | Three labeled tiles: Completeness X/10, Certification tier, Autopilot measured on Job Autopilot (with a link). |
| 5 | Clarify | Read-only bullet list. | One question card: radio options, the default marked "Suggested", then "Answer and regenerate" (draft only). |
| 6 | Odoo Online | No banner. Option A prove and Promote were enabled. | `wizard-online-honesty` banner. Prove and Promote are disabled on Online, with the reason in visible text. |
| 7 | Error | Generic "Request failed" plus the raw message. | `WizardErrorNotice`: what happened, why (timeout, network, or permissions), and the next step. Diagnose with Expert and Dismiss. |
| 8 | Empty / unprobed | Every template card printed its own orange capability reason with an em dash. | One "Templates stay locked until this connection is probed" note with Open Connect, skeleton cards while loading, and an empty state. |
| 9 | Reuse panel | Always open, duplicate empty plus error line, uppercase eyebrow. | `<details>` that opens only when there are suggestions, "N selected" meta, one error row, no eyebrow. |
| 10 | Chrome above hero | IA banner sat above the title. BuildSpineBar showed a row of chips. | PageHeader first, quiet IA note, spine folded into "Switch build mode". |
| 11 | Phone review | Scorecard hidden below 768px (no tab switch). The 1fr grid track clipped the footer. The rail scrolled "Review" off-screen. | Preview / Scorecard switch. `minmax(0,1fr)` track. The rail names only the current stage. |
| 12 | Copy | "Create draft", "(AI)" suffix, em dashes in hook notes and hints. | "Generate the draft" throughout, provider suffix only when it adds information, em dashes removed from wizard UI copy. |

## Gaps (not fixed here)
- AppShell sidebar stays open at 390px (global shell, not this screen). The harness collapses it before capture.
  The top bar chips also wrap on phones (global).
- `wizard-scorecard.spec.ts` › "shows scorecard chip…" expects `/Semantics 8\.0/`, but `formatHygieneScore(8)`
  returns "8" (locked by `draft-studio-journey.test.ts`). This failed before this pass too; the test was not changed.
- `src/lib/capabilities.ts` reasons still contain em dashes and are locked by exact-string tests. They show up in
  "Apply to Odoo blocked" and VersionAwarenessBanner.
- Server notes (e.g. API `note: "Draft only — does not apply."`) come from the backend and are shown as-is.
- On narrow, the review preview pane scrolls internally (max-height 52vh, from shared review CSS).
