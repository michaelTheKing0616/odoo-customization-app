# Reference notes (written by card UI-REF-STUDY; skeleton until then)

One entry per reference in `UI_REFERENCE_MAP.md`, **≤ 8 lines each**, in this exact shape. Spec cards paste only their two entries. Sources: `docs/design/references/ingenium-ui/` (`MANIFEST.md`, `motion/MOTION_NOTES.md`, `_contact/`, `inapp/`) plus official public pages. Anything not observed in the pack is `[Inferred]`. Screenshot requests to Tope are batched, minimum set.

```
### <Product> (areas: 01, 08)
Better 1: <specific, observable pattern; file in the pack>
Better 2: …
Better 3: …
Principle served: <§1 principle number and name>
Motion: <clip file · measured duration · what to borrow>
Do not copy: <asset/colour/copy/layout that stays theirs>
```

Entries to write (19 areas): Linear · Stripe Dashboard · Raycast · Arc · Vercel · Apple Wallet · Superhuman · Linear Inbox · Stripe (Connect/test mode) · Claude app · Cursor agent · v0 · Figma · Framer · Webflow · Attio · Notion · Airtable · n8n · Make · Zed · Warp · Grok app · Granola · Fathom · Mercury · Linear settings · Stripe billing · Linear Insights · Things 3 · Linear mobile · Superhuman mobile · Things mobile · Stripe docs · Linear docs.

_(entries follow)_

### Linear (areas: 01, 02)
Better 1: Issue list keeps a slim nav, a filter row, and full-width rows. Hover is a background tint only (`_contact/inapp-linear.jpg`, `inapp/linear/01-issue-list-light-sidebar.png`, `inapp/linear/motion/06-hover-list-rows.mp4`).
Better 2: Command palette sits centred over the list, with a search field and grouped commands. The list behind stays readable (`inapp/linear/04-command-menu-cmdk-dark.png`).
Better 3: The same list exists in light and in dark, and the nav stays the anchor (`inapp/linear/11-issue-list-dark-sidebar.png`). Area 02 uses this palette because Raycast has no clip.
Principle served: 3. Instant and certain
Motion: `inapp/linear/motion/01-cmdk-open.mp4` · median 183 ms (167–200) · centred palette, light backdrop, grouped commands, open under 200 ms. Row hover: `06-hover-list-rows.mp4` · median 100 ms (67–133) · tint only.
Do not copy: wordmark, dark chrome, or the issue-row layout.

### Stripe Dashboard (areas: 01, 14, 16)
Better 1: Payments are a dense table with status pills, a date range, and a filter that picks a field, then a value (`_contact/inapp-stripe.jpg`, `inapp/stripe/21-payments-list.png`, `inapp/stripe/motion/06-filter-pill.mp4`).
Better 2: A payment opens with the amount and status first, then a timeline, then a metadata column (`inapp/stripe/22-payment-492-detail-timeline.png`).
Better 3: Home keeps summary charts beside the list. A failed load names the failure and offers a retry (`inapp/stripe/20-home-charts.png`, `inapp/stripe/a01-home-sandbox-load-error.png`). Radar is a separate controls page (`inapp/stripe/25-radar-risk-controls.png`).
Principle served: 4. Trust made visible
Motion: No vendor clip (gap). In-app `inapp/stripe/motion/02-payment-detail-open.mp4` · median 133 ms (67–200) · amount and status first, then timeline. `05-chart-hover.mp4` · continuous, no burst · tooltip follows the pointer.
Do not copy: wordmark, accent colour, gradient art, or the dashboard column layout.

### Raycast (areas: 02)
Better 1: Marketing still shows one search field and grouped results in a floating palette (`02-cmd-k/raycast-live-2.png`, `02-cmd-k/raycast-img-1.png`).
Better 2: The changelog is a dated list of short improvements (`02-cmd-k/raycast-changelog-live-1.png`).
Better 3: [Inferred] Recents on an empty query, and the focus order inside the palette. No in-app capture shows them.
Principle served: 5. Keyboard-first, mouse-friendly
Motion: No clip (gap). Measured stand-ins on map row 02: Linear `inapp/linear/motion/01-cmdk-open.mp4` · median 183 ms · and Vercel `inapp/vercel/motion/01-cmdk-open.mp4` · 200 ms. [Inferred] Do not invent a Raycast duration.
Do not copy: red-on-black field, wordmark, or the hero lockup in `02-cmd-k/raycast-live-1.png`.

### Arc (areas: 03, 17)
Better 1: Official still shows a narrow side list beside one large content frame (`03-sidebar-switcher/arc-img-2.png`).
Better 2: Tidy-tabs clip regroups sidebar rows into folders with short slides (`motion/arc/04-tidy-tabs-sidebar.mp4`).
Better 3: Hover opens a preview card on the pointer and does not change the page (`motion/arc/01-hover-5s-preview.mp4`). [Inferred] An empty list that teaches the next step. The live pages are product marketing, not an empty workspace.
Principle served: 1. Calm confidence
Motion: `motion/arc/04-tidy-tabs-sidebar.mp4` · median 233 ms (133–333), ease-out · rows slide into groups. `01-hover-5s-preview.mp4` · median 267 ms (167–267) · peek card, no navigation.
Do not copy: gradients, photo grids, or the browser chrome in `03-sidebar-switcher/arc-live-3.png`.

### Vercel (areas: 02, 03, 04, 06, 16)
Better 1: A route change keeps the sidebar and swaps the main pane to skeleton rows that match the final layout (`inapp/vercel/motion/03-route-transition.mp4`).
Better 2: The team switcher is a popover on the breadcrumb. The page underneath does not jump (`inapp/vercel/02-team-switcher-open.png`, `inapp/vercel/motion/02-team-switcher.mp4`).
Better 3: Usage charts use a hover column plus a value. The home is a short project list with one create action (`inapp/vercel/08-usage-charts.png`, `inapp/vercel/01-dashboard-overview.png`). New project is a stepped import (`inapp/vercel/05-new-project-import-flow.png`).
Principle served: 3. Instant and certain
Motion: `inapp/vercel/motion/03-route-transition.mp4` · bursts 67 ms and 100 ms · skeletons, sidebar fixed. `01-cmdk-open.mp4` · 200 ms · dim backdrop, recent projects first. `05-chart-hover.mp4` · 100–500 ms · column band on bars.
Do not copy: triangle mark, black deploy card, or the hero type in `04-home-agency/vercel-live-1.png`.

### Apple Wallet (areas: 03)
Better 1: The phone still stacks several passes in one pile (`03-sidebar-switcher/apple-wallet-live-2.png`).
Better 2: [Inferred] Choosing a database should feel like picking one card from that pile. The pack has no desktop sidebar and no switcher control.
Better 3: [Inferred] The name sits on the card face. No in-app capture shows a settings form for it.
Principle served: 1. Calm confidence
Motion: No clip. [Inferred] A switch is opacity and transform under 200 ms. The marketing page has no measured UI timing.
Do not copy: wordmark, pass artwork, or the rewards panel in `03-sidebar-switcher/apple-wallet-live-3.png`.

### Superhuman (areas: 05)
Better 1: Marketing still presents mail, docs, and an assistant as separate cards in one suite (`05-approvals/superhuman-live-2.png`). An approvals queue is not in that still.
Better 2: The mail-hero clip stacks inbox, compose, and assistant cards (`motion/superhuman/04-mail-hero-ai-compose.mp4`). The measured median is 967 ms. Borrow the card, and cap the duration.
Better 3: The assistant arrives as a small card over the work (`motion/superhuman/01-go-desktop.mp4`, continuous, no measured burst).
Principle served: 8. Delight earned by craft
Motion: `motion/superhuman/04-mail-hero-ai-compose.mp4` · median 967 ms (400–1933), second peak · too slow to copy. `03-mail-desktop.mp4` · not measurable, continuous · draft appears in place.
Do not copy: photography, wordmark, or the suite-card grid.

### Linear Inbox (areas: 05)
Better 1: In-app inbox is two panes. The list stays put and the reading pane changes (`inapp/linear/03-inbox.png`, `inapp/linear/motion/05-inbox-navigate.mp4`).
Better 2: An empty inbox shows a quiet illustration, then the first item opens in the reading pane (same clip). A docs still shows ordering as a short control list (`05-approvals/linear-inbox-img-2.avif`).
Better 3: A status choice is a menu on the properties rail. The chip updates in place (`inapp/linear/motion/03-status-change.mp4`).
Principle served: 2. One job per screen
Motion: `inapp/linear/motion/05-inbox-navigate.mp4` · median 200 ms (67–333) · fixed list, reading pane changes. `03-status-change.mp4` · median 133 ms · chip updates in place.
Do not copy: inbox illustration, dark theme, or the notification-row layout.

### Stripe (Connect/test mode) (areas: 04, 06)
Better 1: The sandbox home keeps a test-mode banner. A failed load names the error and offers a retry (`inapp/stripe/a01-home-sandbox-load-error.png`).
Better 2: Hosted onboarding is a short stepped form beside a guide column (`06-connect-onboarding/stripe-onboarding-img-2.png`, `06-connect-onboarding/stripe-onboarding-live-1.png`).
Better 3: The in-app connect page is one explanation and one primary action (`inapp/stripe/32-connect-landing.png`). Area 04's Stripe folder is this connect set, not the signed-in home.
Principle served: 2. One job per screen
Motion: No vendor clip (gap). [Inferred] A step change keeps the shell and swaps the form. Measured cousin: Vercel skeletons at 67–100 ms (`inapp/vercel/motion/03-route-transition.mp4`) on `inapp/vercel/05-new-project-import-flow.png`.
Do not copy: wordmark, phone mock, or the onboarding field layout.

### Claude app (areas: 07, 12)
Better 1: The marketing page opens on one prompt field with a few starters under it (`07-app-studio/claude-live-1.png`).
Better 2: The clip streams the answer into a pane beside the thread (`motion/claude/01-chat-artifact-ui.mp4`).
Better 3: The download page splits desktop and phone into two choices (`12-bots/claude-app-live-1.png`). No in-app Claude capture is in the pack.
Principle served: 6. Bots are colleagues
Motion: `motion/claude/01-chat-artifact-ui.mp4` · 35 bursts, median 133 ms, near-linear · stream into a side pane. Other films on that site are live-action, not UI clips (gap in `MOTION_NOTES.md`).
Do not copy: mark, cream marketing field, or the prompt-card photos.

### Cursor agent (areas: 07, 11, 12)
Better 1: Agent chat sits beside the file it is changing, and the diff is readable before you accept it (`11-code-runner/cursor-projects-agent-chat-design-system.png`).
Better 2: The cloud-agent clip moves setup as panels and keeps you in the same place (`motion/cursor/01-cloud-agent-canvas.mp4`). Median 500 ms is above the cap.
Better 3: A finished pass leaves a review note on the change (`12-bots/cursor-agentic-security-review-pr-comment.png`). The app-studio page is a prompt plus a result frame (`07-app-studio/cursor-live-1.png`).
Principle served: 6. Bots are colleagues
Motion: `motion/cursor/01-cloud-agent-canvas.mp4` · median 500 ms (167–800), second peak · borrow the panel change. Cap the duration at 250 ms.
Do not copy: wordmark, editor theme, or the chat-beside-diff layout.

### v0 (areas: 07)
Better 1: The page opens on one prompt and a row of templates (`07-app-studio/v0-live-1.png`).
Better 2: Generated pieces appear in sequence inside a phone frame (`motion/vercel/01-v0-dashboard-build-mobile.mp4`).
Better 3: [Inferred] Progress is those pieces appearing. The still does not show a failed or empty generation.
Principle served: 8. Delight earned by craft
Motion: `motion/vercel/01-v0-dashboard-build-mobile.mp4` · median 467 ms (167–1933), ease-out · pieces appear in order. Cap the borrow at 250 ms.
Do not copy: prompt chrome, template thumbnails, or the phone-frame layout.

### Figma (areas: 08)
Better 1: A marketing still shows a canvas with a left tool rail and a right properties side (`08-designer-canvas/figma-live-2.png`).
Better 2: Another still keeps the canvas large, with frames on it and a prompt docked along the bottom (`08-designer-canvas/figma-live-3.png`).
Better 3: [Inferred] Selecting an object opens properties without leaving the canvas. No in-app capture and no clip, so zoom and an empty canvas are not shown.
Principle served: 5. Keyboard-first, mouse-friendly
Motion: No clip (gap). [Inferred] Selection and the properties side are opacity and transform under 200 ms. Do not invent a duration from the marketing page.
Do not copy: wordmark, cursor colours, or the canvas chrome.

### Framer (areas: 08)
Better 1: The clip lays generated layers onto the canvas (`motion/framer/01-ai-canvas-panel.mp4`). Median 800 ms is a marketing edit.
Better 2: Live stills keep the canvas as the page, with a short prompt under the work (`08-designer-canvas/framer-live-1.png`).
Better 3: [Inferred] A property change stays on the canvas. The clip does not show a properties form.
Principle served: 3. Instant and certain
Motion: `motion/framer/01-ai-canvas-panel.mp4` · median 800 ms (200–1400), ease-in-out · layers land in place. Borrow the in-place result. Cap at 250 ms.
Do not copy: sites inside the hero, wordmark, or the dark marketing canvas.

### Webflow (areas: 08)
Better 1: Designer marketing shows a visual canvas, a left element tree, and a right style side (`08-designer-canvas/webflow-live-1.png`).
Better 2: A later viewport keeps that canvas with a page on it (`08-designer-canvas/webflow-live-3.png`).
Better 3: [Inferred] Structure and style are two rails around one canvas. No in-app capture. The page's videos are testimonial reels, not UI clips (`MOTION_NOTES.md`).
Principle served: 2. One job per screen
Motion: No clip (gap). [Inferred] Opening a style control is under 200 ms and does not change the page.
Do not copy: wordmark, site screenshots, or the designer chrome.

### Attio (areas: 09)
Better 1: A marketing still shows a record table, a left nav, and a right detail column (`09-records-tables/attio-live-3.png`).
Better 2: Another still pairs a record list with an assistant thread (`09-records-tables/attio-live-2.png`).
Better 3: No in-app capture (gap). [Inferred] Filter, empty, and inline edit. Use the Notion and Airtable in-app stills for those states.
Principle served: 1. Calm confidence
Motion: No clip (gap). [Inferred] Opening a row is a direct swap under 200 ms. That duration is not an Attio measurement. The nearest measured swap is Linear peek, median 117 ms (`inapp/linear/motion/02-issue-peek-open.mp4`).
Do not copy: wordmark, table styling, or the assistant-column layout.

### Notion (areas: 09)
Better 1: Table and board are two views of one set, and the sidebar stays (`inapp/notion/01-database-table-sidebar.png`, `inapp/notion/02-board-view.png`).
Better 2: Opening a row is a peek over the table (`inapp/notion/03-row-page-peek.png`).
Better 3: Filter and sort are small menus on the view. Trash empty is one line and a way back (`inapp/notion/04-filter-menu-open.png`, `inapp/notion/09-empty-state-trash.png`).
Principle served: 7. Forgiveness
Motion: `inapp/notion/motion/00-app-hydration-sidebar-load.mp4` · continuous, no burst · main content first, sidebar fills from grey blocks to text. No other Notion clip.
Do not copy: mark, page title styling, or the peek layout.

### Airtable (areas: 09)
Better 1: The grid is dense. Editing a cell is a focus ring in place (`inapp/airtable/01-grid-view.png`, `inapp/airtable/motion/05-inline-cell-select-edit.mp4`).
Better 2: Filter is a popover anchored to its button. The grid behind stays bright (`inapp/airtable/03a-filter-menu.png`, `inapp/airtable/motion/03-filter-dropdown-open.mp4`).
Better 3: Expanding a row opens a centred record over a dimmed grid, title first (`inapp/airtable/02-expanded-record.png`). The interfaces-to-data clip holds a centred spinner for most of 5 s. Do not borrow that (`inapp/airtable/motion/02-route-transition-interfaces-to-data.mp4`).
Principle served: 3. Instant and certain
Motion: `inapp/airtable/motion/04-expand-record-open.mp4` · median 100 ms (67–133), ease-out · title first, fields after. `07-omni-sidebar-collapse.mp4` · 67 ms · the side panel snaps away and the table takes the width.
Do not copy: palette, coloured pills, or the grid chrome.

### n8n (areas: 10)
Better 1: The only in-app capture is a company-email signup gate (`inapp/n8n/00-signup-company-email-gate.png`, `_contact/inapp-n8n.jpg`). No workflow was recorded.
Better 2: Docs stills show a node canvas, an assistant on the right, and a publish control (`10-flow-canvas/n8n-canvas-with-ai-assistant-panel.png`, `10-flow-canvas/n8n-canvas-publish-button.png`).
Better 3: [Inferred] Selecting a node opens its details beside the canvas. The signup gate does not show this.
Principle served: 2. One job per screen
Motion: No clip (gap). [Inferred] Pan is direct, and publish is a state change under 200 ms. The signup gate is not a motion reference.
Do not copy: wordmark, node art, or the docs canvas layout.

### Make (areas: 10)
Better 1: An empty scenario is a blank canvas with one add control (`10-flow-canvas/make-scenario-editor-empty-canvas.png`).
Better 2: A router shows every branch at once (`10-flow-canvas/make-scenario-router-branches.png`).
Better 3: Notes sit on the canvas next to the steps they explain (`10-flow-canvas/make-scenario-prospects-router-gmail.png`).
Principle served: 4. Trust made visible
Motion: No clip (gap; the vendor site blocked the fetch, `MOTION_NOTES.md`). [Inferred] Adding a step inserts it in place, under 200 ms.
Do not copy: purple chrome, module logos, or the scenario layout.

### Zed (areas: 11)
Better 1: The agent panel streams inside the editor (`motion/zed/01-agent-panel.mp4`, one burst of 967 ms).
Better 2: The editor clip barely moves. Speed is the instant response (`motion/zed/02-editor-ui.mp4`, not measurable).
Better 3: Settings and the diff stay in stable panels (`motion/zed/03-agent-settings-diff.mp4`). `11-code-runner/zed-live-1.png` is a product page, not the editor.
Principle served: 3. Instant and certain
Motion: `motion/zed/02-editor-ui.mp4` · not measurable, continuous · borrow the lack of motion. `01-agent-panel.mp4` · 967 ms · stream the text, and do not copy that burst length.
Do not copy: mark, editor theme, or the panel chrome.

### Warp (areas: 11)
Better 1: The live pages explain the product with a feature list and code blocks (`11-code-runner/warp-live-2.png`, `11-code-runner/warp-live-3.png`).
Better 2: Official assets are code samples on a plain ground (`11-code-runner/warp-img-2.png`, `11-code-runner/warp-img-4.png`).
Better 3: [Inferred] A runner reads as a transcript of commands and results. No in-app capture shows that transcript.
Principle served: 6. Bots are colleagues
Motion: No clip (gap; the page only had a talking-head video, `MOTION_NOTES.md`). [Inferred] Output appends in place, with no transition.
Do not copy: wordmark, block styling, or a terminal layout.

### Grok app (areas: 12)
Better 1: The live page in the pack is a block interstitial, not the product (`12-bots/grok-live-1.png`). Do not study that screen.
Better 2: Store stills show a dark thread and a composer along the bottom (`12-bots/grok-ios-appstore-1.png`, `12-bots/grok-ios-appstore-2.png`).
Better 3: [Inferred] The answer streams in the thread. No clip, and the live page never showed the app.
Principle served: 6. Bots are colleagues
Motion: No clip. [Inferred] New text appends in place. Do not invent a duration from the blocked page.
Do not copy: mark, store phone frames, or the thread layout.

### Granola (areas: 13)
Better 1: A marketing still puts raw notes beside an enhanced note (`13-copilot-panel/granola-live-2.png`).
Better 2: The clip rewrites notes in place and keeps the user's lines distinct from the enhanced lines (`motion/granola/01-notes-enhance.mp4`). The file is a May 2024 tweet video.
Better 3: [Inferred] The user can see which lines were added. The clip was not burst-measured, and there is no in-app capture.
Principle served: 6. Bots are colleagues
Motion: `motion/granola/01-notes-enhance.mp4` · not measurable, slow/continuous · source 2024-05-22 · text rewrites in place. Do not copy that slow pace.
Do not copy: wordmark, note-card layout, or the meeting-photo frame.

### Fathom (areas: 13)
Better 1: An official image shows a recap with a summary block and follow-up prompts (`13-copilot-panel/fathom-img-2.avif`).
Better 2: The live hero pairs a meeting scene with short prompt chips (`13-copilot-panel/fathom-live-1.png`).
Better 3: [Inferred] Live notes stay separate from the summary. No clip and no in-app capture.
Principle served: 6. Bots are colleagues
Motion: No clip (gap). [Inferred] Summary text settles in place, under 250 ms.
Do not copy: wordmark, astronaut art, or the recap-card layout.

### Mercury (areas: 14)
Better 1: Bill pay shows a queue with amount, due date, and an approve action on the row (`14-money-guard/mercury-approvals-live-1.png`, `14-money-guard/mercury-approvals-img-1.jpg`).
Better 2: The dashboard still leads with one balance, then the transaction list (`14-money-guard/mercury-live-3.png`).
Better 3: The only clip is a slow landscape reveal of that dashboard (`motion/mercury/01-hero-dashboard-reveal.mp4`). `MOTION_NOTES.md` records no other Mercury clip.
Principle served: 4. Trust made visible
Motion: `motion/mercury/01-hero-dashboard-reveal.mp4` · not measurable, slow/continuous · do not borrow scroll-scrub timing. [Inferred] Approve updates the row in place, under 200 ms.
Do not copy: wordmark, landscape hero, or the bill-pay table layout.

### Linear settings (areas: 15)
Better 1: Settings use a left section list and one form column (`inapp/linear/06-settings-workspace-general.png`).
Better 2: Billing compares plans, marks the current plan, then shows the billing email (`inapp/linear/07-settings-billing-plans.png`).
Better 3: Members is a person list with one invite action (`inapp/linear/08-settings-members.png`).
Principle served: 2. One job per screen
Motion: No settings clip. [Inferred] Changing section swaps the form and keeps the settings nav. The nearest clip is sidebar reflow at median 300 ms (`inapp/linear/motion/04-sidebar-collapse.mp4`). Keep the form swap under 200 ms.
Do not copy: settings labels, plan cards, or the billing panel in `15-settings-billing/linear-settings-live-1.png`.

### Stripe billing (areas: 15)
Better 1: The subscriptions empty state says what the list is and offers one create action (`inapp/stripe/31-subscriptions-empty.png`).
Better 2: Settings home is a directory of sections (`inapp/stripe/26-settings-home.png`).
Better 3: The marketing billing page pairs a plan picker with a usage chart (`15-settings-billing/stripe-billing-live-1.png`, `15-settings-billing/stripe-billing-live-3.png`).
Principle served: 8. Delight earned by craft
Motion: No vendor clip (gap). In-app cousin: `inapp/stripe/motion/04-create-menu.mp4` · median 100 ms (67–133) · menu anchored to the button.
Do not copy: billing gradient, plan-card layout, or wordmark.

### Linear Insights (areas: 16)
Better 1: Marketing stills show a few charts on one board, each with a one-line title (`16-charts/linear-insights-live-2.png`, `16-charts/linear-insights-img-3.png`).
Better 2: The build clip adds and resizes a chart in one short burst (`motion/linear/02-insights-dashboard-build.mp4`). The source is a July 2025 tutorial.
Better 3: [Inferred] A chart with no series explains the gap instead of drawing an empty axis. The clip does not show that state.
Principle served: 3. Instant and certain
Motion: `motion/linear/02-insights-dashboard-build.mp4` · one burst, 200 ms, ease-out · chart redraws as the size changes. July 2025 source.
Do not copy: chart palette, chart styling, or the dashboard grid.

### Things 3 (areas: 17)
Better 1: Marketing stills move from a few lists to the items inside one list (`17-empty-states/things3-live-2.png`, `17-empty-states/things3-img-2.jpg`).
Better 2: A new to-do expands in place into notes (`motion/things/02-new-todo-expand.mp4`, median 167 ms). Clips 01–04 are 2017 sources. Only `05-remastered-ui.mp4` is from 2026.
Better 3: The 2026 remaster is the current look: quiet lists and detail. Its bursts are too long to time-match (`motion/things/05-remastered-ui.mp4`, median 1267 ms).
Principle served: 8. Delight earned by craft
Motion: `motion/things/02-new-todo-expand.mp4` · median 167 ms (133–200), ease-out · 2017 source · row expands in place. Prefer this over `05-remastered-ui.mp4` · median 1267 ms (233–1300) · 2026-06-25.
Do not copy: checkmark mark, list colours, or the window chrome.

### Linear mobile (areas: 18)
Better 1: Store stills show one list per screen, then the item as the next screen (`18-mobile/linear-ios-appstore-1.png`, `18-mobile/linear-ios-appstore-3.png`).
Better 2: A bottom bar holds the main areas (`18-mobile/linear-ios-appstore-2.png`).
Better 3: [Inferred] At 390 px the desktop sidebar becomes that bar. These are store frames, not a responsive web capture.
Principle served: 10. Beautiful in dark and light, at 390 and 1440 px
Motion: No mobile clip. Nearest desktop cousin: `inapp/linear/motion/02-issue-peek-open.mp4` · median 117 ms (100–133) · direct swap. [Inferred] The phone push stays under 250 ms.
Do not copy: mobile theme, store frames, or the tab icons.

### Superhuman mobile (areas: 18)
Better 1: Store stills show an inbox list, then one message, with the reply composer at the bottom (`18-mobile/superhuman-ios-appstore-2.png`, `18-mobile/superhuman-ios-appstore-4.png`).
Better 2: Split inbox and reminders are shown as the phone's main views (`18-mobile/superhuman-ios-appstore-1.png`, `18-mobile/superhuman-ios-appstore-5.png`).
Better 3: [Inferred] One thumb action is primary. No clip.
Principle served: 2. One job per screen
Motion: No clip. The desktop mail hero median is 967 ms (`motion/superhuman/04-mail-hero-ai-compose.mp4`). [Inferred] List to message is a push under 250 ms.
Do not copy: photography, colour fields, or the phone-frame layout.

### Things mobile (areas: 18)
Better 1: Store stills show Today as one list, with headings you can collapse (`18-mobile/things3-ios-appstore-1.png`, `18-mobile/things3-ios-appstore-2.png`).
Better 2: Quick Find is a pull-down sheet that filters as you type (`motion/things/04-quick-find.mp4`). The source is a 2017 phone video.
Better 3: Magic Plus drag opens a gap where the new item will land (`motion/things/03-magic-plus-drag.mp4`, 2017). [Inferred] On the web, the same idea is an insert control until we measure a drag.
Principle served: 8. Delight earned by craft
Motion: `motion/things/04-quick-find.mp4` · median 500 ms (233–1367), second peak · 2017 · sheet plus a result on each keystroke. Cap the borrow at 250 ms.
Do not copy: blue chrome, checklist styling, or the phone sheet.

### Stripe docs (areas: 19)
Better 1: The docs home is a left guide, a short article, and a code sample on the right (`19-docs/stripe-docs-live-1.png`, `19-docs/stripe-docs-home-fullpage.png`).
Better 2: The payments guide leads with the outcome, then a sample you can try (`19-docs/stripe-docs-payments-fullpage.png`).
Better 3: The API page keeps a contents list and shows how to sign in before the endpoint list (`19-docs/stripe-docs-api-fullpage.png`).
Principle served: 9. Plain words
Motion: No vendor clip (gap). [Inferred] Changing section swaps the article and keeps the guide. No duration was measured.
Do not copy: docs theme, code colours, or the three-column layout.

### Linear docs (areas: 19)
Better 1: The docs home is a grid of topic cards, one job per card (`19-docs/linear-docs-home-fullpage.png`).
Better 2: An article keeps a left contents list and one reading column (`19-docs/linear-docs-inbox-fullpage.png`).
Better 3: A long article stays one column. The cycles capture is a full page, not a video (`19-docs/linear-docs-cycles-fullpage.png`).
Principle served: 9. Plain words
Motion: No docs clip. [Inferred] A jump inside the page is instant. Do not add a page transition.
Do not copy: docs theme, card grid, or the article chrome.

## Known gaps (UIREF-GAPS)

- Attio has no in-app capture. Marketing stills only (`09-records-tables/attio-live-1.png` through `attio-live-3.png`).
- n8n in-app is only a signup gate (`inapp/n8n/00-signup-company-email-gate.png`).
- No clips for Raycast, Figma, Webflow, Make, Stripe vendor pages, Attio, Fathom, or Warp. Stripe in-app clips exist. Vendor Stripe clips do not. Mercury has only the hero. Claude has one UI clip.
- Things clips 01–04 are 2017 sources (files touched 2021). Granola `motion/granola/01-notes-enhance.mp4` is a May 2024 tweet video.
- Grok's live page in the pack is a block interstitial (`12-bots/grok-live-1.png`). Store stills are the only product frames.
