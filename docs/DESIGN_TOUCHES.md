# Ingenium design touches (ideas for approval)

Date: 17 Oct 2026. Research only, nothing built.
Goal: the best-looking app anywhere, with a character nobody else has. That character comes from the brand story: Odoo is the arch, and the change you build is the keystone that locks it in place.

Sources (short names used below):
- Playbook = DESIGN_SYSTEM_PLAYBOOK.md (laws and sections 3 to 15). Brand = ingenium-v2 BRAND_GUIDE.md.
- Emil = emil-design-eng. JK = Jakub Krehel pack (typography, ui, colors, writing, accessibility). Imp = impeccable. Taste = design-taste-frontend. HIG = apple-design-hig. Rive = rive skill. WMD = web-motion-design / motion-art-direction. UXC = ux-copy-evidence. Agentic = agentic-ux-design skill. Dataviz, VT (view transitions), Dembrandt and Color-expert are cited in Playbook section 15. MS = motionsites GRAMMAR.md.
- Real apps: Figma, Framer, Webflow, Stripe, Arc, Raycast, Vercel, Apple, Things, Notion, Superhuman, Craft, Family, Teenage Engineering (TE), Nothing, Sonner (Emil), Rauno Freiberg-style craft.

Tags: QW = quick win (days). BIG = bigger build (a week or more, or needs new assets).
"Refines" = builds on something already in SPEC.md, CONFIG_SUITE_SPEC.md or FEATURE_AUDIT.md, so it is not counted as brand new.

---

## 1. Signature identity and Keystone motifs
1. **Keystone loader.** The only loading mark in the app is the arch with the keystone easing down and locking. It shows only after 1 second of waiting, so fast actions never flash it. [Brand, Rive] BIG
2. **"Locked in" moments.** The one-time keystone settle (planned for first layout publish) also marks the other two big commitments: a plan applied to Live and a Bridge flow going live. Still rare, never on routine saves. Refines SPEC 7. [Brand, Emil frequency rule] QW
3. **Cinnabar means committed.** Cinnabar appears at most once per screen, and only where something has been locked in (the logo, the publish confirmation, the "live" seal). People learn the meaning without being told. [Brand section 2, JK one colour one meaning] QW
4. **The 15 degree rule.** The keystone's 15 degree side angle is reused in tiny places: the ends of the active tab indicator, the notch on the "Draft" ribbon, the skeleton shimmer angle, the corner of the selected-card marker. One geometric rule everywhere is what makes Nothing and TE products recognisable. [Brand construction, Nothing] QW
5. **Voussoir progress.** Multi-step work (Job Autopilot, Bulk Setup runs, Bridge backfill) shows progress as arch stones filling from both legs toward the top, with the keystone dropping last. [Brand, TE segmented displays] BIG
6. **Arch health gauge.** Database and integration health scores use a segmented arch instead of a generic donut. Missing stones show exactly which area is weak. [Brand, Apple Activity rings as precedent for an ownable gauge] QW
7. **Arch-masked bot avatars.** Every Ingenium bot and Expert sits inside an arch-shaped mask; humans stay in circles. You can tell AI from people at a glance in any list, comment or history entry. Refines the planned avatar set. [Brand, Agentic] QW
8. **Stone grain.** A barely visible limestone grain (about 2 percent) on large surfaces in light mode and a basalt grain in dark mode, so the app feels made of material, not flat pixels. Off in high contrast. [TE, Things, Family] QW
9. **Logo built from its construction lines.** On the marketing site and the very first launch, the mark draws from its real geometry (circles and joints from construction.png), then fills in. [Brand construction, Rauno-style craft, WMD] BIG
10. **Empty-state arch.** Empty states use a quiet line arch missing its keystone, and the main action button sits where the keystone goes. [Brand, Imp] QW
11. **Living favicon.** The tab icon gets a tiny count when approvals wait, and the keystone dims while a long run is in progress, so you can work in another tab and still know. [Figma, Slack, Vercel] QW

## 2. Typography and numerals
12. **A type family with character.** Page titles in Libre Franklin 600 (the wordmark's own family), the interface in a refined grotesque such as Geist or Onest instead of plain Inter, and a mono face for technical names. Three faces, no more. [Playbook 3, Brand 6, Taste] BIG
13. **Technical names as quiet mono chips.** Wherever an Odoo technical name appears (res.partner, x_delivery_date), it is set in mono, slightly smaller and muted, with one-click copy. Pairs with the planned term card. [Stripe docs, Vercel] QW
14. **Slashed zero in references.** Record references and IDs (SO0091, INV/2026/0042) use the slashed-zero form so O and 0 never get confused. [JK typography, Stripe] QW
15. **Money set properly.** The Naira sign gets a proper fallback and sits on the digit baseline, decimals are a shade lighter (1,250.00 with .00 muted), and amounts align on the decimal point in tables. [Playbook 3 currency note, Stripe] QW
16. **Rolling digits.** When a number changes (records affected, money saved by caching, queue size), each digit rolls on its own instead of the whole number flashing. [Family, Robinhood, WMD] QW
17. **Size-specific tracking tokens.** Titles tighter, body neutral, small caps labels opened up, so every size reads as designed rather than scaled. [Playbook 3, JK typography] QW
18. **No orphans.** Balanced wrapping on headings and "pretty" wrapping on body text, toasts and cards, so no single word hangs on its own line. [JK typography] QW
19. **Real keycaps.** Shortcuts shown as small keycap shapes, and they switch between Cmd and Ctrl by platform. [Raycast, Superhuman] QW
20. **Typographic care in copy.** Curly quotes, a real times sign, arrows, and a non-breaking space between a number and its unit ("48 records" never splits). [JK typography] QW
21. **Live relative times.** "4 min ago" updates on its own without shifting the layout, and the exact Lagos time shows on hover. [Vercel, GitHub] QW

## 3. Colour, material, light and depth
22. **Brand-tinted greys.** All neutrals tinted slightly toward basalt in perceptual colour steps, so the greys feel like Ingenium's greys. [Playbook 5, Color-expert] QW
23. **Three-layer hairline shadow** instead of flat 1 px borders on light surfaces: crisp edge, soft contact, faint lift. [JK ui] QW
24. **Machined top edge.** Floating panels (menus, command bar, term card) get a 1 px inner highlight on the top edge, like a milled aluminium edge. [Apple, Raycast, Playbook 4] QW
25. **Glass only where layers are real.** Frosted glass only on the command bar, floating canvas toolbars and the term card; everything else is solid. Solid automatically when the OS asks for reduced transparency. [Playbook 8, HIG Liquid Glass, Imp] QW
26. **The lamp-lit desk.** Builder canvases sit on the desk tint with a very soft light from the top left, so the Odoo screen reads like a sheet of paper under a lamp. [Figma canvas, Things] QW
27. **Focus dims the world.** When a sheet or a serious confirmation opens, the rest of the app fades and loses some colour rather than going black. [HIG dimming, Arc] QW
28. **Test vs Live you can feel.** Test copies get a faint diagonal hazard band along the top edge and tinted chrome; Live databases get clean chrome. Nobody publishes to the wrong place by mistake. [Vercel preview deployments, Heroku] QW
29. **A colour for each database.** Each connected database picks a colour from a curated set, used on its switcher chip, tabs and favicon dot, so you always know where you are. [Arc Spaces, Slack workspaces] QW
30. **Richer teal on good screens.** Wide-gamut accent on screens that support it, with a safe fallback. [Color-expert] QW
31. **Images that sit on anything.** Every logo and image gets a 1 px outline at 10 percent, so white logos on white cards still have an edge. [JK ui] QW
32. **Cursor-light on marketing cards.** On the public site only, feature cards catch a soft light that follows the pointer around their border. Never inside the app. [Vercel, Stripe] QW

## 4. Micro-interactions and motion choreography
33. **Tooltip warm-up.** The first tooltip waits a moment; while you sweep along a toolbar the next ones appear instantly. [Emil] QW
34. **Hold to confirm.** Risky actions (remove demo data, roll back a release) use a hold button that fills over about 1.2 seconds; letting go cancels. Calmer than "type DELETE". [Emil hold-to-delete] QW
35. **Shared-element morphs.** A row expands into its record sheet, a connection card grows into the database page, a script card opens into the editor. You never lose your place. [VT, Apple] BIG
36. **Perfect tab colour change.** The active tab's label colour changes exactly under the moving pill, with no colour flicker. [Emil clip-path tabs] QW
37. **Leave faster than you arrive.** Things open in about 200 ms and close in about 140 ms. [Emil Sonner principles] QW
38. **Capped stagger.** Lists cascade in only on first load, 30 ms per row, capped at 6 rows, and never on filtering or sorting. [Emil stagger] QW
39. **Flick to dismiss.** Sheets and panels can be flung away on touch and trackpad, with soft resistance at the edges. [Emil gestures, Vaul] QW
40. **Blur bridge for data swaps.** Charts and big numbers crossfade through a 2 px blur when the data set changes, app-wide (the proof PDF swap already uses this). Refines SPEC 7. [Emil] QW
41. **Sonner-quality toasts.** Toasts stack with depth, fan out on hover, swipe away, and pause their timer on hover or when the tab is hidden. Refines the planned undo toast. [Sonner] QW
42. **Snap feedback.** When dragging on the canvas, snapping gives a tiny 1 px nudge and a brief guide-line flash. [Figma smart guides] QW
43. **Drag with weight.** A dragged item lifts with a growing shadow, tilts slightly with speed (3 degrees at most) and settles flat on drop. [Things, Emil springs] QW
44. **Scrub numbers.** Drag left or right on any number label in an inspector to change it, hold Shift for bigger steps. [Figma, Framer] QW
45. **Checks that draw.** Checkmarks draw themselves in 150 ms and toggles squash a little when pressed. [Apple, motion vocabulary] QW
46. **Copy that confirms.** The copy icon turns into a check, says "Copied", and the copied text glows briefly. [Vercel, Stripe docs] QW
47. **Edit in place.** Click a label to edit it, Enter saves, Esc reverts, no separate edit mode. [Notion, Craft] QW
48. **Edges that fade.** Scrolling panels fade at the edges instead of using divider lines; a hairline appears only when content slides under a header. [HIG, Playbook 8] QW
49. **Honest page moves.** Sideways navigation crossfades; going deeper slides a few pixels; going back reverses. [VT] QW

## 5. Sound and haptics (off by default)
50. **A stone sound set.** A soft stone "tock" for a lock-in, a light click for toggles, a low muted knock for errors, two notes for an approval arriving. Recorded from real stone and wood, not synth beeps. [TE, Apple, Playbook 7 multimodal feedback] BIG
51. **A sound logo.** Three rising notes and a stone tap as the keystone lands. Used at first launch and in product videos only. [Brand sonics practice, Rive] BIG
52. **Sound follows importance.** Routine actions are always silent; only rare commitments make a sound. [Emil frequency rule] QW
53. **Quiet during demos.** Sounds mute automatically during Live Demo presenter mode and screen sharing, and follow the OS sound settings. [Zoom and Teams etiquette] QW
54. **Phone haptics.** In the phone companion: a crisp tap on approve, a double tap for warnings, light ticks while scrubbing through history. [HIG haptics] QW

## 6. Data visualisation
55. **Sparklines in cells.** Small trend lines in tables and cards (fill rate, error rate, sync volume), drawn in ink with the accent only on the latest point. [Stripe, Dataviz] QW
56. **Fill-rate micro bars.** A tiny bar next to every field name in the builders shows how full that field is in real data. [Stripe Sigma style] QW
57. **Before and after dumbbells.** When a plan changes counts, each row shows a dot moving from old value to new. [Dataviz] QW
58. **Record journey as a transit map.** Bridge traces show each system as a line and each step as a station, so "Shopify order 1043 to SO0091 to INV/2026/0042" reads like a metro map. [Stripe event timeline, transit diagrams] BIG
59. **A heartbeat for live flows.** Throughput is a calm line that moves only when data flows and lies flat when idle. [Vercel analytics, TE OP-1 displays] QW
60. **Synchronised crosshair.** Hovering one chart shows the same moment on every chart below it, with exact values. [Grafana, Stripe] QW
61. **History markers on every chart.** Publishes, imports and plan runs appear as tiny keystone markers on time charts, so cause and effect line up ("errors jumped right after this publish"). [Vercel, Datadog event overlays] BIG
62. **Ghost charts.** Before there is data, a faint outline of the chart says "This fills in after the first run". [Imp] QW
63. **Every chart has a table.** A "view as table" switch and patterns for colour-blind users on every chart. [Dataviz, JK accessibility] QW
64. **Nothing-style dot numerals in one place.** The single big number on Home (or the health score) uses a dot-matrix display style. Used once, so it stays special. [Nothing OS] QW

## 7. Empty, loading, error, success states and celebrations
65. **Shaped skeletons with the brand angle.** Skeletons match the real layout and shimmer once every 1.6 s on the 15 degree angle. Refines SPEC 8. [Playbook, Brand] QW
66. **Loading that tells the truth over time.** After 2 s "Reading your database", after 6 s "Odoo is answering slowly today", after 15 s a Cancel button. [UXC, Vercel build logs] QW
67. **Empty states with real starters.** "No automations yet" plus three one-click examples built from this database's own models, not generic ones. [Notion templates, JK writing] QW
68. **Errors that offer the fix.** What happened, why, what to do, a "Fix it" button where possible, and "Copy details for support" with a trace number. Refines SPEC 9. [Stripe errors] QW
69. **Calm offline band.** A thin top band: "Offline. Your changes are saved here and will send when you're back", with a count of waiting changes. [Figma, Notion] QW
70. **Success sized to the stakes.** Small things get a check; big firsts (first integration live, first module published) get the keystone landing and a summary card of what changed. [Emil frequency, Stripe Atlas completion] QW
71. **Stone-dust instead of confetti.** At real milestones, a dozen fine stone-dust particles fall from the keystone over 0.6 s, once. Reduced motion shows a still. [Things completion, Rive] BIG
72. **"All clear" screens.** When everything is healthy, show a composed, calm screen ("All 4 databases are healthy. Checked 2 min ago.") instead of blank space. [Things "Today is clear"] QW
73. **Inbox zero arches.** An empty approvals inbox shows a rotating set of line drawings of real Nigerian arches and gateways (Lagos Brazilian-style houses, the Kano city gates). Local, warm, unmistakably ours. [Superhuman inbox zero photos, Brand] BIG
74. **Partial success, plainly.** "48 of 50 updated. 2 need you", with the two shown right there. [Stripe batch results] QW
75. **A designed 404.** An arch with one stone missing and a search box. [Brand] QW

## 8. Cursor and selection
76. **Branded selection and caret.** Highlighted text in soft teal, a teal text caret, themed scrollbars. [JK typography, Playbook 3] QW
77. **Bot cursors.** In shared editing, people get named cursors and bots get a distinct dotted cursor with an arch label, so you can see when Expert is acting. Refines planned presence. [Figma] QW
78. **A refined canvas cursor set.** Custom grab, move, resize and insert cursors drawn in the same stroke as the icons. [Figma, Framer] QW
79. **Count while selecting.** Marquee selection shows "6 fields" next to the pointer. [Figma, Finder] QW
80. **Selection that survives.** Selected records stay selected when switching between list and board, with a floating bar ("6 selected") holding the actions. [Notion, Airtable, Gmail] QW
81. **Ghost-cursor guidance.** Short tours show a soft ghost pointer gliding to where you should click, instead of arrows and boxes. Refines planned page tours. [Arcade, Supademo] QW

## 9. Keyboard craft
82. **Hold for hints.** Holding Cmd or Ctrl for half a second shows small keycaps on every actionable element. [Superhuman, Vimium] QW
83. **Shortcut coaching.** After you click something three times that has a shortcut, a single quiet hint appears once ("Tip: press E"). [Superhuman] QW
84. **Go-to pairs.** G then H for Home, G then B for Bridge, G then R for the code runner, G then A for approvals. [Superhuman, GitHub] QW
85. **Cmd-K with depth.** Nested pages, recent items, a live preview pane on the right, and per-item actions (select a record, press Cmd-K, see only its actions). Refines planned Cmd-K. [Raycast] QW
86. **List navigation.** J and K or arrows move through any list, X selects, Enter opens, with a clear focus row. [Superhuman] QW
87. **Esc ladder.** Esc always steps back exactly one level: close popover, then deselect, then leave the mode. [Figma] QW
88. **Number keys in dialogs.** 1, 2, 3 pick options and Cmd+Enter confirms the main action. [Raycast, Slack] QW
89. **A beautiful shortcut card.** "?" opens a shortcut sheet laid out like a TE manual page, also printable. [TE manuals, Things] QW

## 10. Copy voice and microcopy
90. **A named voice.** "A calm senior consultant": short, specific, never hype, British spelling, one-page voice guide with do and don't examples. [UXC, Mailchimp voice guide practice] QW
91. **Buttons with numbers and places.** "Update 48 records", "Install Helpdesk on Staging". Refines SPEC 9. [JK writing] QW
92. **Confirmations name the target.** The title always says the database and environment: "Publish to Live (Acme Production)?" [GitHub danger zone, Vercel] QW
93. **Greetings with substance.** "Good morning, Tope. 2 approvals and 1 failed sync since yesterday." Never a greeting on its own. [Superhuman, Things] QW
94. **Reassuring undo lines.** "Published. You can undo this for 30 days in History." [Gmail undo] QW
95. **Specific loading verbs.** "Checking 12 fields against Odoo 18", never just "Loading". [Vercel, Raycast] QW
96. **Placeholders from real data.** The search box suggests something true for this database: "Try: Lagos customers without email". [Notion AI, UXC] QW
97. **Tone set by stakes.** Light wording for low-risk actions, firmer and fuller wording near money, deletes and Live. [JK writing, Playbook 7] QW

## 11. Iconography and illustration
98. **Ingenium's own icon layer.** Custom icons for Odoo ideas (model, field, view, automation, approval rule, Bridge flow, numbering, history) drawn on the Lucide grid and stroke so they sit alongside it seamlessly. [Lucide, Playbook one icon set] BIG
99. **15 degree terminals.** The custom icons' stroke ends carry a faint keystone angle, felt more than seen. [Brand] BIG
100. **Icons move only to show state.** The sync icon turns only while syncing; the bell swings once when an approval arrives. [Apple SF Symbols effects, Rive] QW
101. **Architectural line drawings.** Onboarding, empty states and handbooks use ink line drawings (elevations, plans, arches) with one cinnabar keystone, instead of generic blob illustrations. It ties straight to "ingenium, the root of engineer". [Brand, TE manuals, Swiss references in PATTERNS_DIGEST] BIG
102. **Uniform connector logos.** Real brand logos for Shopify, Paystack and others in identical tiles with a hairline, with a mono option for dense lists. [Simple Icons, Raycast store, Zapier] QW
103. **Odoo's icons stay Odoo's.** Odoo app icons always appear in a neutral tile and never next to the keystone, as the brand guide asks. [Brand section 5] QW

## 12. AI presence (how the bots and Expert feel alive)
104. **Avatar states as a live state machine.** Idle: still arch. Thinking: keystone hovering and breathing above the gap. Working: stones filling. Done: keystone drops in. Needs you: a fine cinnabar outline. One Rive file, used everywhere. Refines planned avatars. [Rive, Brand] BIG
105. **Visible steps, not a spinner.** While a bot works you see short live steps ("Reading 214 fields on Contacts", "Checking 3 automations") that fold into a one-line summary when done. [Agentic, Cursor, Perplexity] QW
106. **Phrase-by-phrase streaming.** AI text arrives in soft phrases with a gentle fade, not a typewriter effect. [Vercel AI SDK UI, Arc] QW
107. **Honest confidence.** AI suggestions carry a small three-bar confidence mark with the reason on hover, never fake percentages. [Agentic, UXC, Playbook law 9] QW
108. **Pencil-hatched drafts.** Anything the AI proposes shows with a faint pencil-hatching texture until you accept it, in every builder. The texture means "proposal, not real yet" across the whole app. Refines Edit with AI. [Figma branching, architectural drafting] QW
109. **Provenance chips.** "Drafted by Expert, checked by code" stays on AI-made items until a person edits them. [Agentic, Craft AI] QW
110. **Presence without nagging.** Expert stays docked; a single small dot appears when it has something useful for this page. No pop-ups. [Arc, Superhuman] QW
111. **Instant answers feel instant.** Cached answers show a small "instant, 0.04 s, free" tag, making the caching work visible and satisfying. Refines the planned cost meter. [Raycast speed culture] QW
112. **Steer while it works.** You can type to redirect a running bot without stopping it, and Esc always stops. [Cursor] QW
113. **Each bot has a face, one voice.** Each bot gets its own name, avatar tint and one-line specialty, but they all speak in the same calm voice. [Agentic] QW

## 13. Dark mode craft
114. **Basalt, never black.** Dark mode is built from basalt with its slight blue undertone; text is limestone at about 92 percent, never pure white. [Brand, Playbook 4] QW
115. **Weight and leading compensation.** Light-on-dark text goes up a weight step and gets a little more line height. [Dembrandt] QW
116. **Higher means lighter.** Raised surfaces step up in lightness instead of using shadows. [Dembrandt] QW
117. **Bright Odoo screens framed gently.** The Odoo canvas stays true to Odoo's light look, but sits in a soft bezel, with an optional dim setting so it doesn't glare at night. [Figma, Apple Preview] QW
118. **Theme switch reveal.** Switching theme spreads as a circle from the toggle; reduced motion uses a crossfade. [Telegram, VT] QW
119. **Sunset schedule.** Follow the OS by default, or switch at Lagos sunset. [macOS] QW
120. **Charts tuned for dark.** Chart colours lose 10 to 15 percent saturation in dark mode so they don't vibrate. [Dembrandt] QW

## 14. Density modes
121. **Three densities.** Comfortable, Compact and Dense (spreadsheet-like for consultants), changing spacing, never shrinking text below legible sizes. [Gmail, Superhuman] QW
122. **Density per area.** Lists can be dense while builders stay comfortable, remembered per person. [Notion, Airtable] QW
123. **Focus mode.** Cmd+. hides everything but the canvas or editor. [Figma, Craft] QW
124. **Presenter density.** In Live Demo presenter mode: larger type, technical details hidden, a soft halo around the pointer. Refines the planned calm presenter mode. [Keynote, Pitch] QW

## 15. Onboarding moments
125. **Onboarding builds the arch.** Each first-run step adds a stone (connect, health check, first fix); the keystone drops in when the first real improvement is done. [Brand, Family onboarding] BIG
126. **A sample company that feels local.** The planned sample database becomes a believable Nigerian business (for example a Lagos furniture maker) with real-looking naira prices, VAT and addresses. Refines the planned sample database. [UXC real content, Playbook taste] QW
127. **A welcome letter.** A short signed note from you, beautifully typeset, shown once. [Things, Superhuman, Arc] QW
128. **Power features revealed when ready.** Shortcuts, density and the code runner are introduced after the person shows they're ready, not all on day one. [Superhuman, Figma] QW
129. **Satisfying checklists.** Setup items strike through with a drawn line and the finished list folds into a single "Setup complete" stone. Refines the planned setup checklist. [Things] QW

## 16. Printed, PDF and email craft
130. **Print-grade proofs.** Report output with proper hyphenation, hanging punctuation, decimal-aligned money columns and no widows or orphans. [Stripe invoices, Craft PDF export] BIG
131. **True paper preview.** Proofs sit on the desk at true A4 or Letter proportion with a soft paper shadow and a margins overlay toggle. [Pages, Figma] QW
132. **Email previews in real clients.** Previews framed as Gmail, Outlook, iPhone Mail and dark-mode mail, plus "Send me a test". Refines planned email previews. [Litmus, Stripe email craft] BIG
133. **Ingenium's own emails at receipt quality.** Approval, digest and alert emails as plain and beautiful as Stripe receipts: one button, mono IDs, readable with images off, dark-mode safe. [Stripe, Vercel] QW
134. **Sealed handover documents.** Handover and audit PDFs get a cover, contents, and a keystone seal on the last page with a verification QR code. [Stripe Atlas documents, notary seals] BIG

## 17. Accessibility as craft
135. **A designed focus ring.** 2 px teal with offset, following each element's corner radius, appearing in 80 ms. Refines SPEC 10. [JK accessibility, Playbook 7] QW
136. **Screen-reader messages written like copy.** Announcements written and reviewed everywhere, not just on the canvas ("Moved Phone into Contact info"). Refines SPEC 10. [JK accessibility] QW
137. **Gentler motion, not none.** With reduced motion, slides become fades and the keystone drop becomes a fade-in. [Playbook law 7, Emil] QW
138. **Reading comfort option.** A toggle for more letter and line spacing in long texts like handbooks and help. [Kindle, Readwise] QW
139. **Big hit areas even when dense.** Invisible padding keeps every click target large enough in Dense mode. [JK accessibility] QW

## 18. Performance feel
140. **Optimistic safe actions.** Rename, pin, tag and reorder happen instantly and quietly roll back with a message if the server refuses. Writes to Odoo still go through check and approve. [Notion, Figma, Superhuman] QW
141. **Prefetch on intent.** Pages and records start loading when the pointer slows over a link. [Vercel, Superhuman] QW
142. **Instant shell.** The app frame paints from cache in under 100 ms and data streams in. [Superhuman, Arc] BIG
143. **Local-first search.** Recent records and the database schema are kept on your device, so search is instant and works offline. [Superhuman, Figma] BIG
144. **Zero layout shift.** Every loading area reserves its size, and a test fails if anything jumps. [Playbook 4 performance] QW
145. **Smoothness test.** A test fails if any key interaction drops frames on a mid-range laptop. [fixing-motion-performance skill] BIG
146. **Background work pill.** A small pill in the top bar shows running jobs and progress, and expands on click. [macOS downloads, Figma upload] QW

## 19. Delight and easter eggs
147. **Blueprint mode.** Shift+B on any canvas shows the screen as an architectural blueprint: blue ground, white lines, spacing and size labels. Useful and a joy. [Figma inspect, Rauno-style craft] BIG
148. **Loose keystone.** Click the logo seven times and the keystone pops out, wobbles and drops back (with the stone tap if sound is on). [Apple, TE playfulness] QW
149. **Type "ingenium" in Cmd-K** to see the logo build from its construction lines and the credits. [Arc, Things] QW
150. **Seasonal arches.** On days like 1 October, the inbox-zero drawing changes quietly. Nothing more. [Google doodle restraint] QW
151. **A year in review.** "This year Ingenium checked 12,400 changes for you and you undid 3", with real numbers only, shareable. [Spotify Wrapped, GitHub] BIG
152. **A colophon.** A credits page with the fonts, the keystone story and the team. [Things, Craft, TE] QW

## 20. Branding in Odoo output
153. **Generated modules look premium inside Odoo.** Each generated module gets a distinct icon in Odoo's own icon style (colour tile plus glyph), a tidy description and a readme, so client apps look native and finished. [Odoo app icon language, Raycast extension icons] BIG
154. **Code that reads like craft.** Generated code has a clean header, consistent style and plain comments, so a developer opening it feels the same care. [Vercel templates] QW
155. **Odoo screens stay Odoo.** No Ingenium chrome inside client Odoo, but custom fields ship with plain-language help and good placeholders. [Brand section 5, SPEC 9] QW
156. **Optional "Prepared with Ingenium" footer** on reports and handbooks, removable on paid plans and replaced by the agency's brand in white-label. Refines planned agency branding. [Typeform, Calendly] QW

## 21. Signature interactions borrowed from the best apps
157. **Split view.** Two databases, or two versions of a screen, side by side with a draggable divider. [Arc split view] BIG
158. **Show the request.** A "Developer" switch on any screen shows the exact Odoo calls Ingenium made, copyable. It builds trust with technical consultants. [Stripe "view API request"] BIG
159. **Snooze.** Snooze alerts and approvals until tomorrow morning or after a meeting. [Superhuman] QW
160. **Publishes as deployments.** Each publish gets its own status page: steps with timings, logs, who approved, and one-click rollback. [Vercel deployments] QW
161. **Wallet-style database switcher.** Databases appear as a stack of tactile cards in their own colours; flick through and pick one. [Family, Apple Wallet] BIG
162. **Live preview before saving, everywhere.** Every setting shows its effect in a preview before you save (Framer's "see it as you change it"), extended beyond the builders to Settings, Numbering and Access. [Framer, Webflow] QW

---

## Signature 10 (what would make Ingenium recognisable at a glance)
1. **The keystone state machine:** one living mark for loading, bot thinking, working, done and needs-you (ideas 1, 104).
2. **Cinnabar means committed,** shown at most once per screen, with the stone "tock" when something locks in (3, 50).
3. **Arch-masked bots and round humans** (7, 77).
4. **The 15 degree rule** carried into tabs, ribbons, shimmer and icon terminals (4, 65, 99).
5. **Architectural line drawings,** including Nigerian arches for inbox zero (73, 101).
6. **Pencil-hatched AI drafts** across every builder (108).
7. **Voussoir progress and the arch health gauge** instead of generic bars and donuts (5, 6).
8. **Onboarding that builds the arch** stone by stone (125).
9. **Blueprint mode** on every canvas (147).
10. **Test vs Live hazard band plus a colour for each database,** so you always know where you are (28, 29).

Playbook rules applied: law 3 (one accent, one meaning), law 6 (motion must earn its place, frequency first), law 7 (reduced motion gentler, not zero), law 9 (no slop tells: no confetti, no gradient text, no fake numbers), section 8 (glass only where layering is real), Brand sections 2 and 5 (cinnabar keystone only, no effects on the mark).

---
## APPROVED: all 162 (Tope, Oct 17), including idea 12 (new fonts: Libre Franklin titles, Geist or Onest interface, mono for technical names) and ideas 50-51 (recorded stone sound set and sound logo, off by default). Adds to SPEC, CONFIG_SUITE_SPEC, BRIDGE_RUNNER_SPEC and FEATURE_AUDIT; replaces nothing. Free tiers only for fonts and audio.
