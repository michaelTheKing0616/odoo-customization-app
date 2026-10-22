# UI reference map (Tope, 21 Oct): every screen, its bar, its cards

Verdict from Tope (21 Oct): the current UI is **really, really poor**. Every route is rebuilt to its area's bar. "Built" in the handover means the code exists. It does not mean the screen is at the bar. Built design touches are re-checked inside their area's rebuild (ledger `UIX-TOUCHES`).

Pack: `docs/design/references/ingenium-ui/<NN-area>/` (media is gitignored, `.md` notes are tracked), plus `_contact/` sheets and `motion/MOTION_NOTES.md`. The per-screen protocol (3-5 adopted patterns, the brand's own identity, measured motion, side-by-side before done) is in `07_UI_EXCELLENCE_PROTOCOL.md` (Stage 2).

| # | Area | References | Ledger | Cards |
|---|---|---|---|---|
| 01 | Shell, lists, History | Linear, Stripe Dashboard | UIX-01 | UI-SHELL-*, UI-HISTORY-* |
| 02 | Cmd-K | Raycast (no Raycast clips in the pack: use Linear/Vercel in-app, DEC-029) | UIX-02 | F1-CMDK |
| 03 | Sidebar, database switcher | Arc, Vercel, Apple Wallet | UIX-03 | F1-NAV, F1-SWITCHER, F1-SWITCHER-UX |
| 04 | Home, agency view | Stripe, Vercel | UIX-04 | UI-HOME-* |
| 05 | Approvals | Superhuman, Linear Inbox | UIX-05 | UI-APPROVALS-* |
| 06 | Connect, onboarding | Stripe, Vercel | UIX-06 | UI-CONNECT-*, UI-ONBOARD-* |
| 07 | App Studio | Claude app, Cursor, v0 | UIX-07 | UI-APPSTUDIO-* (+ App Studio Pack §UI) |
| 08 | View + Report Designer canvas | Figma, Framer, Webflow | UIX-08 | UI-VD-*, UI-RD-* |
| 09 | Records tables | Attio, Notion, Airtable (no Attio in-app capture: use official images, DEC-029) | UIX-09 | UI-RECORDS-* |
| 10 | Bridge flow canvas | n8n, Make (n8n in-app is a signup gate only) | UIX-10 | BR-CANVAS-* |
| 11 | Code Runner | Zed, Cursor, Warp | UIX-11 | UI-CR-* |
| 12 | Bots | Claude app, Cursor agent, Grok app | UIX-12 | UI-BOTS-* |
| 13 | Live Demo Co-Pilot panel | Granola, Fathom | UIX-13 | UI-COPILOT-* |
| 14 | Money guard, safety | Stripe, Mercury | UIX-14 | UI-SAFETY-* |
| 15 | Settings, billing | Linear, Stripe | UIX-15 | UI-SETTINGS-*, UI-BILLING-* |
| 16 | Charts | Stripe, Vercel, Linear Insights | UIX-16 | UI-CHARTS-* |
| 17 | Empty states | Things 3, Arc | UIX-17 | F1-STATES, UI-EMPTY-SPEC |
| 18 | Mobile | Linear, Superhuman, Things | UIX-18 | F1-RESPONSIVE, UI-MOBILE-* |
| 19 | Docs | Stripe docs, Linear docs | UIX-19 | UI-DOCS-* |

## Route → area (all 78 `page.tsx` outside `/e2e`, 21 Oct)
Each route is scored in `UI-AUDIT-ALL` (baseline contact sheet → gap list → owning card). A route that is being retired (DEC-024) is audited only for its redirect and the features it preserves.
- **01 Shell/lists/History:** `/` (frame), `/connections`, `/connections/[id]` (frame), `/connections/[id]/journal`, `/pipelines`, `/command`, `/admin`, `/connections/[id]/operations`, `/connections/[id]/housekeeping`, `/connections/[id]/cron-manager`, `/connections/[id]/suite` (shell), `/suite/upkeep`, `/suite/upkeep/[area]`, `/suite/states`, `/connections/[id]/menus`, `/connections/[id]/access`, `/connections/[id]/automations`, `/connections/[id]/reminders` (fold, DEC-024), `/connections/[id]/id-generator` (Numbering rename)
- **04 Home/agency:** `/` (content), `/connections/[id]` (overview), `/connections/[id]/client`
- **05 Approvals:** `/approvals`, `/connections/[id]/approvals`, `/suite/safety/approvals`
- **06 Connect/onboarding:** `/connect`, `/login`, `/signup`, `/verify`, `/reset-password`, `/connections/[id]/wizard`, `/connections/[id]/job`
- **07 App Studio:** `/connections/[id]/studio`, `/connections/[id]/builder`, `/connections/[id]/modulespec`, `/connections/[id]/projects` (App plan move), `/connections/[id]/wireframe`, `/connections/[id]/expert`, `/suite/ask`
- **08 Designer canvas:** `/connections/[id]/designer`, `/designer/classic` (redirect), `/connections/[id]/view-designer`, `/connections/[id]/report-designer`, `/connections/[id]/reports` (retire), `/connections/[id]/mail-templates` (retire), `/connections/[id]/qweb-views` (retire), `/connections/[id]/website`, `/studio/dashboards` (hide, DEC-024)
- **09 Records tables:** `/suite/explore`, `/suite/explore/models/[model]`, `/suite/explore/capabilities`, `/suite/explore/insights` (charts: 16), `/suite/change`, `/suite/change/[tool]`, `/suite/setup`, `/connections/[id]/bulk-suite`, `/connections/[id]/import`, `/connections/[id]/ingest` (redirect), `/connections/[id]/config`
- **10 Flow canvas:** `/bridge/flows`, `/bridge/gallery`, `/bridge/mapping`, `/bridge/contracts/new`
- **11 Code Runner:** `/connections/[id]/code-runner`, `/script-runner` + `/code-studio` (fold, DEC-024)
- **12 Bots:** bot surfaces inside Home, App Studio and suite Ask (no route of its own today; UI-BOTS-SPEC decides)
- **13 Co-Pilot:** `/connections/[id]/live-demo-copilot`, `/live-demo-copilot/overlay`
- **14 Money guard/safety:** `/suite/safety`, `/suite/safety/check`, `/suite/safety/money`, `/suite/safety/upgrade`, `/connections/[id]/power-ops`, `/settings/trust-safety`
- **15 Settings/billing:** `/settings`, `/settings/billing`, `/pricing`
- **19 Docs/marketing:** `/colophon`, `/privacy`, `/terms` (marketing rules, same tokens)
- **Cross-cutting:** 02 Cmd-K, 03 sidebar/switcher, 16 charts, 17 empty states and 18 mobile apply to every route above. Their cards own the shared component, and each area card owns its use of it.
