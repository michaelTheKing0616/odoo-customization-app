# Ingenium feature audit (everything not already planned)
Read-only audit, Oct 17 2026 (WAT). No code changed, no screenshots. Source: page sizes, headings, API calls and backend endpoints in the repo on Tope's Mac, plus nav (`apps/web/src/lib/nav.ts`).
Excluded because they already have plans: View Designer, Report Designer, email designer, App Studio, Draft Studio, Configuration Suite / Bulk Setup, code runner (Script Runner, Code Studio), Bridge, Overview.
Already decided in the suite spec (section 17, decision 1): Bulk Suite, Power Ops, Cron Manager, Housekeeping and Odoo Expert fold into the suite. Below, ideas for those only cover what the suite spec does NOT already cover (checked against suite tools 1-15 and ideas 1-34).

Tags: **QW** = quick win (hours to a day), **BIG** = big job (several days or more).

---

## 0. App-wide findings (affect every page)
1. **The menu is crowded and mixed up.** 33 items in 6 groups. Build holds 11 items, several duplicates (Reports vs Report Designer, Mail templates vs email designer, QWeb views, Designer classic). Some pages exist but aren't in the menu (Ingest, Wireframe, Reminders is buried, Operations hub). "Instance Config" sits in Operations, "Live Demo Co-Pilot" sits in Operations, "Projects" and "App plan" sit in AI Studio although they're developer plumbing.
2. **Jargon on screen.** Lines with internal words per page: Power Ops 65, Import 47, Ingest 31, Access 15, Menus 13, Housekeeping 12, ID Generator 10, Reminders 9, QWeb 8. Examples: "Mutations blocked", "arch", "grounded fields only", "unsafe gate family", "commit", "Philosophy", "TRUST-9 beta evidence", "T4-DASH", "Same zip sha256 required across hops".
3. **Four different page frames** (OperateStudioChrome, OperateStudioBar, PageHeader, custom `<main>`), so pages look and behave differently.
4. **Each page has its own snapshot/undo panel** (Access, Automations, Menus, Builder, Projects each call `listSnapshots` + `rollbackSnapshot`). Undo should be one shared History, the same one the suite uses.
5. **Not every write goes through Check → Approve → Run → Undo.** Builder, Menus, Access, Automations, Reminders, Website publish, Instance Config and ID Generator write directly with a confirm dialog.

App-wide upgrades:
- A1 **New menu (BIG, but mostly moves):** five plain groups: *Home* · *Build* (Models & fields, Screens, Menus, Website, Automations, Access, Documents & emails) · *Data* (Bring data in, Record editor, Numbering) · *Run & look after* (suite) · *AI* (Ask, App Studio, Autopilot) · *History & safety*. Old links redirect.
- A2 **One page frame (QW per page):** same header, version chip, Writes On/Off, state guide, error notice, empty state on every page.
- A3 **Jargon sweep (QW):** replace every internal word with the suite glossary; a test fails the build if banned words appear on screen.
- A4 **One History for everything (BIG):** every write from every page lands in the change store with receipt, diff and undo; the per-page snapshot panels go.
- A5 **Every write uses the shared Run sheet (BIG):** same check, approval rule, money guard and undo as the suite.
- A6 **Global "Find anything" (Cmd-K) (QW+):** jump to any page, model, record, menu, automation or past run.
- A7 **"Edit with AI" everywhere it fits:** same propose-then-check pattern planned for the designers, extended to Access, Automations, Menus and Models.

---

## 1. Models & fields (`builder`, 789 lines, router 1010)
**Today:** list models, add/edit custom models and fields, invoicing link panel, per-page snapshots. Direct writes after a first-write warning.
**Weak points:** plain list, no picture of how models connect; no fill-rate or usage data; field types shown in Odoo terms; no "what breaks if I change this"; overlaps with App Studio "extend an existing app".
**Upgrades:**
1. Relationship map: a zoomable diagram of models and links, click to open (BIG).
2. Field table with real fill rate, last used and "used by" (screens, automations, reports, emails) before rename or delete (suite idea 20 covers clean-up; this is the in-builder view) (QW using the Inspector data).
3. Field type picker in plain words with a live sample ("Money, in Naira, 2 decimals") (QW).
4. Safe rename and type change: shows the data migration and runs it through Check/Undo (BIG).
5. Computed fields in plain words ("Total = Qty × Price"), code generated and checked (BIG).
6. Add field straight from the record editor or View Designer canvas, one flow (QW once shared).
7. Merge with App Studio's "extend" flow so there is one way to add fields (BIG).

## 2. Menus (`menus`, 503 lines)
**Today:** menu tree, create/edit/delete menus, link window actions, groups, snapshots.
**Weak points:** tree editing is form-based; "window action" is shown as an Odoo concept; deleting is direct; no preview of what each role sees.
**Upgrades:**
1. Drag-and-drop tree with live preview of the Odoo app bar (QW+).
2. "See it as": preview the menu as a chosen role or user (QW, uses access data).
3. Hide stock menus nobody uses, from real usage, with undo (BIG).
4. Create a menu + screen + list in one step ("Add a 'Late orders' menu under Sales") (QW).
5. Broken-link finder: menus pointing at missing actions or apps (QW).
6. Edit with AI in plain words (BIG, shares A7).

## 3. Access (`access`, 885 lines, router 503)
**Today:** rights per model, record rules, groups, multi-company guidance, Documents folders, client grants, matrix panel, snapshots.
**Weak points:** 15 jargon lines; record rules shown as Odoo domains; one of the biggest pages with many panels; overlaps with suite ideas 12-13 (Role x-ray, Access hygiene).
**Upgrades:**
1. Rules in plain words ("Sales people see only their own quotes"), domain built and checked by code (BIG).
2. "Test as user": pick a user and a record, see allowed / blocked and why (QW, joins Role x-ray).
3. Visual matrix: roles × apps with read/write/create/delete toggles and a diff before save (QW+).
4. Role templates (Sales rep, Warehouse, Accountant read-only) per Odoo version (QW).
5. Risk flags: who can delete, who can see salaries or bank details (QW).
6. Put Role x-ray and Access hygiene (suite 12, 13) as tabs here rather than a separate place (merge).

## 4. Automations (`automations`, 723 lines, router 669)
**Today:** list, create, edit, turn on/off, delete automations; gate checks; migration assist; activity types; snapshots.
**Weak points:** composer is form-based; no testing on a real record before turning on; no run history; overlaps with Reminders and suite idea 18 (catalogue).
**Upgrades:**
1. Plain-sentence builder: "When an invoice is overdue 7 days, email the customer and assign a task to the account owner" (BIG, AI proposes, code checks).
2. Test on a real record with a dry run showing exactly what would happen (QW+).
3. Run history: last fired, success/failure, records touched (joins suite idea 18) (QW).
4. Loop and clash detector: automations that trigger each other or fight over a field (QW).
5. Templates gallery by app (CRM, Sales, Inventory, Helpdesk) (QW).
6. Fold Reminders in as a template ("Remind me…") (merge, QW).
7. Visual flow view (trigger → conditions → actions) sharing Bridge's canvas (BIG, after Bridge).

## 5. Odoo approval rules (`approvals`, 286 lines, router 775)
**Today:** Odoo's own approval rules (Studio-style): list rules, create, approve entries, check an action, approval processes panel.
**Weak points:** name clashes with Ingenium's own approvals (designers, suite) and the top-level `/approvals` page; easy to confuse; rules made in forms.
**Upgrades:**
1. Rename clearly: "Approvals inside Odoo" vs "Approvals for Ingenium changes" (QW).
2. Plain-sentence rules ("Purchase over ₦500k needs the CFO") (QW+).
3. Flow preview: who approves at each step, with real user names (QW).
4. Bottleneck report: approvals waiting longest and by whom (QW).
5. Unify the three approval places into one Approvals inbox with two tabs (merge, BIG).

## 6. Reports (old) (`reports`, 125 lines) / Mail templates (`mail-templates`, 84) / QWeb views (`qweb-views`, 97)
**Today:** older paper-canvas editors ("Report layout lite"), each with create/list/edit; QWeb edits raw page templates.
**Weak points:** duplicates of the new Report Designer and email designer; copy full of jargon ("unsafe gate family", "type=qweb arches"); three menu items for one job.
**Upgrades:**
1. Redirect Reports and Mail templates to the new designers (already partly planned) and remove them from the menu (QW once edits land).
2. Keep QWeb views as an "Advanced: page templates" tab inside Report Designer, with a code view using the code runner's editor (merge, QW+).
3. One "Documents & emails" menu entry (QW).

## 7. Website (`website`, 81 lines, router 195)
**Today:** list website pages, edit page blocks, upload images, publish. Can't create pages, menus or SEO.
**Weak points:** thin; publish is direct; no preview on phone; no create page; error panel only.
**Upgrades:**
1. Create pages from templates, with the View Designer's drag-and-drop blocks (BIG).
2. Phone / tablet / desktop preview (QW).
3. Publish through approval and scheduled publish, as in the designers (QW, reuse).
4. SEO and speed check: titles, descriptions, image sizes, broken links (QW).
5. Website menu editor (config_ops already has `/website/menus`) (QW).
6. AI page from a brief ("a landing page for our bakery's catering") with brand presets (BIG).

## 8. Import (`import`, 776 lines, router 610) and Ingest (`ingest`, 752 lines, not in menu)
**Today:** Import: CSV/template preview and commit, bulk image import, seed packs. Ingest: multi-file upload, classification, commit order, chart-of-accounts remap, OCR, dry-run and commit, interview jobs.
**Weak points:** two importers plus the suite's new document import (spec 20.13) = three ways to bring data in; Import has 47 jargon lines, Ingest 31; Ingest is hidden; "commit" wording.
**Upgrades:**
1. Merge into one "Bring data in" flow: drop any files → we sort them → map → check → run → undo, built on suite 20.13 (BIG, high value).
2. Keep image import and seed packs as options inside it (QW once merged).
3. Mapping memory per database so the second import maps itself (QW, also helps caching).
4. Migration mode: import from another system's export (QuickBooks, Sage, Excel books) with a checklist (BIG).
5. Progress you can leave and come back to, resumable on failure (QW+).

## 9. ID Generator (`id-generator`, 703 lines, router 305)
**Today:** builds reference numbers: CSV preview/download, live assignment, create a sequence.
**Weak points:** name unclear (it's numbering); overlaps with Instance Config sequences and suite idea 15 (numbering check).
**Upgrades:**
1. Rename to "Numbering" and merge with Config sequences + numbering check (merge, QW).
2. Live pattern preview ("INV/2026/0001") with prefix, year, reset yearly (QW).
3. Backfill missing numbers through Check/Undo, never on posted accounting (QW+).

## 10. Snapshots & Journal (`journal`, 575 lines)
**Today:** audit log, health check runs, snapshots with rollback, plus batch panels (journal entries, documents, master data, orders) from batch_os.
**Weak points:** mixes history with batch tools; "Journal" clashes with accounting journals; per-page snapshots elsewhere.
**Upgrades:**
1. Rename to "History"; becomes the single timeline (A4) with filters by person, page, record type (QW+).
2. Move the batch panels into the suite's Change records (merge, QW).
3. Readable diffs for every change, with "Undo this" and "Undo from here" (joins suite 32) (BIG).
4. Tamper-proof export of the history for auditors (the audit chain exists) (QW).

## 11. Reminders (`reminders`, 425 lines, router 155)
**Today:** a wizard that creates an email template plus an optional scheduled job. Create only; can't list, edit or delete reminders.
**Weak points:** one-way; overlaps with Automations and Cron Manager.
**Upgrades:**
1. Fold into Automations as "Reminder" templates with list, edit, pause and test send (merge, QW).
2. Send a real test to my inbox (reuses the email designer idea) (QW).

## 12. Instance Config (`config`, 124 lines page, router 2067 / 35 endpoints)
**Today:** "Config Atlas" browser and command center: companies, sequences, field labels, translations, paper formats, defaults, parameters, currencies, units, fiscal positions, mail health, scheduled jobs.
**Weak points:** huge backend behind a small page; buried in Operations; overlaps heavily with Bulk Setup's catalog and workbook, the suite's Upkeep, numbering and mail health (suite 14).
**Upgrades:**
1. Make it the "Settings" view of the suite's Explore: every setting with current value, plain explanation (suite 34) and edit via Bulk Setup (merge, BIG but mostly wiring).
2. Settings search with "what this affects in your database" (QW).
3. Compare settings with another database or a template (joins suite 10) (QW once merged).

## 13. Job Autopilot (`job`, 775 lines, router 489)
**Today:** runs a client job end to end: brief, fingerprint, packet, sandbox run, config dry-run/apply, scorecard, delivery ledger, PDF report, promote to another connection.
**Weak points:** many panels and words ("packet", "fingerprint"); overlaps with App Studio, Bulk Setup and Pipelines (promote); unclear where it fits.
**Upgrades:**
1. Reframe as "Client project autopilot": one brief → plan made of App Studio apps + Bulk Setup steps + Bridge flows, with one progress view (BIG).
2. Use Pipelines' test → live promote as its last step instead of its own (merge, QW+).
3. Client-facing progress page and the handover PDF (suite 11) at the end (QW).
4. Time and cost estimate before the run (QW).

## 14. App plan (`modulespec`, 520 lines, router 841) and Projects (`projects`, 456 lines)
**Today:** App plan: edit/validate/apply app plan JSON, export zip/sandbox, demo walkthrough. Projects: saved drafts with diff, apply, archive.
**Weak points:** developer plumbing shown in the AI menu; raw JSON; overlaps with App Studio drafts.
**Upgrades:**
1. Move both under App Studio as "Saved drafts" and "Advanced: app plan" (merge, QW).
2. Projects become the one place for all saved work (apps, plans, flows) with versions and compare (BIG).

## 15. Wireframe (`wireframe`, 210 lines view, not in menu)
**Today:** upload a photo of a paper form; it reads the layout and shows a preview; cannot apply.
**Weak points:** dead end; hidden; "Gemini is not connected" names the provider.
**Upgrades:**
1. Hand off to View Designer as a draft screen (QW+), or to App Studio for a new app.
2. Merge with the planned "report from a photo" into one "From a picture" entry (merge).

## 16. Live Demo Co-Pilot (`live-demo-copilot`, 786 lines, router 540)
**Today:** a meeting bot joins a call with consent, transcribes, gives live answers, presenter overlay, leave and purge.
**Weak points:** numbered panels ("5. Live answers (Stage 1 to 2)"), feels like a test bench; sits under Operations; no after-meeting output.
**Upgrades:**
1. Calm presenter mode: one big "Start", overlay with answer cards, keyboard shortcuts (QW+).
2. After the call: summary, questions asked, follow-up email draft and a starter plan (App Studio or Bulk Setup) from what the client asked for (BIG, high wow).
3. Demo scripts: pre-built click paths per industry with talking points (QW).
4. Answers grounded in the client's own database, using the Ask workspace (QW once Ask is live).
5. Move to the AI group (QW).

## 17. Client (`client`, 27 lines, panel 165)
**Today:** open change sets, last snapshot and bot status for one connection.
**Weak points:** thin; overlaps with suite idea 28 (client mode).
**Upgrades:**
1. Become the client portal home of suite idea 28: status, what's pending their approval, recent changes in plain words, integration health (BIG).
2. Brandable for agencies (logo, colours) (QW once built).

## 18. Operations hub (`operations`, 76 lines) and Odoo Expert (`expert`, 56 lines)
**Today:** Operations is a card hub; Expert is the chat page. Both are being folded into the suite (Run & look after / Ask).
**Extra upgrades not in the suite spec:** a floating "Ask" button on every page that knows what screen you're on (QW); voice questions (BIG).

## 19. Power Ops (`power-ops`, 599 lines) — urgent safety point
**Today:** recipes run bulk calls: includes **"Purge journal entries", "Mass delete records", "Cancel journal entries / invoices", "Post draft journal entries", "Unreconcile and draft"**.
**Weak points:** these clash directly with the money guard ("accounting is never written in bulk") and bypass Check/Undo; 65 jargon lines; "Philosophy" panel.
**Upgrades:**
1. **Hide or lock the accounting and delete recipes now** until they run through the suite's money guard and approvals (QW, top priority).
2. Rebuild the rest as suite Change records actions (already planned in the suite merge).

## 20. Cron Manager (`cron-manager`) and Housekeeping (`housekeeping`)
Fully covered by suite Upkeep (tools 9, 10) and ideas 21, 25. Only extra: show both inside one "Health" score on Home (QW).

## 21. Top-level pages
**Home (`/`, 144 lines):** marketing page with prices hard-coded ("Pro $39/mo") and a link to Odoo 19 docs only.
1. Prices from one source shared with Pricing and Billing (QW). 2. Logged-in users land on a real dashboard: their databases, health, pending approvals, recent runs (merge with `/command`) (BIG). 3. A short live demo video or interactive tour (QW+).

**Connect (`/connect`, 661 lines):** connect form + saved connections, hosting tip.
1. Guided connect by hosting type (Odoo Online, Odoo.sh, self-hosted) with a live check list (version, rights, apps, mail) (QW+). 2. Connection health chips on each saved card (QW). 3. Groups/tags for agencies with many clients, search (QW). 4. "Connect a test copy" button (BIG).

**Command center (`/command`, 95 lines):** fleet tiles (clients, pending approvals, failed jobs, drift).
1. Make it the agency home: every client database with health, drift and pending items, sortable (BIG). 2. Click a tile → filtered list, not just a count (QW).

**Approvals inbox (`/approvals`, 194 lines):** hash-bound plan approvals.
1. Merge with the designers' and suite approvals into one inbox with before/after (see 5.5) (BIG). 2. Approve from email/Slack/Teams (suite 31) (reuse).

**Pipelines (`/pipelines`, 390 lines):** "Multi-env promote"; copy shows "Same zip sha256 required across hops".
1. Plain wording ("Test → Staging → Live, the exact same package each time") (QW). 2. Visual lanes with what's on each database and a one-click promote with approval (QW+). 3. Use it for designer screens, Bulk Setup plans and Bridge flows too, not only app zips (BIG).

**Dashboard Studio (`/studio/dashboards`, 83 lines, backend is a stub):** already covered by builders idea 17 (dashboard designer). Hide until that ships (QW).

**Settings (`/settings`, 595 lines):** status, API keys, sign-in providers, audit.
1. Tabs: Profile, Team & roles, Keys, AI & privacy (local vs cloud AI, cache), Notifications (email/Slack/Teams), Danger zone (QW+). 2. Team invites with roles per database (BIG). 3. AI usage and cache savings view (ties to the caching item) (QW).

**Billing (`/settings/billing`, 140 lines):** loads plan state.
1. Clear plan card, usage meter, invoices, upgrade/downgrade with proration preview (QW+). 2. Warn before limits, never block mid-run (QW). 3. Paystack/Flutterwave for Naira alongside cards (BIG).

**Trust & safety (`/settings/trust-safety`, 58 lines):** fine idea, short. 1. Make it the public "how we keep your Odoo safe" page with the money guard, undo, local AI and data handling (QW).

**Admin (`/admin`, 280 lines):** superadmin; copy "TRUST-9 beta evidence". 1. Plain wording and a real ops view: sign-ups, errors, AI spend per workspace, cache hit rate (QW+).

**Login / signup / reset / verify:** 1. Magic-link and Google sign-in on one screen, clear error words (QW). 2. First-run onboarding: connect → quick health check → "here are 3 things to fix" (BIG, high value).

---

## Top 5 to do first
1. **Lock Power Ops' accounting and delete recipes** behind the money guard now (safety, quick).
2. **New menu + one page frame + jargon sweep** (A1-A3): the biggest visible jump in quality across the whole app.
3. **One History and one Run sheet for every write** (A4-A5): reliability and undo everywhere, not just in the suite.
4. **Merge Import, Ingest and the suite's document import into one "Bring data in"** flow.
5. **Plain-sentence Automations (with Reminders folded in) and plain-words Access rules, each with "test on a real record / test as user"** before anything goes live.

Runners-up: logged-in Home/Command dashboard for agencies, Live Demo Co-Pilot after-call plan, guided Connect, Website page builder.

---

# Part 2: more ideas (Tope: no cap)
Numbering continues from Part 1 for each feature. QW = quick win, BIG = big job.

## 0+. More app-wide ideas
- A8 **Onboarding that adapts (BIG):** first run asks "Agency, in-house admin or developer?" and shapes the menu, Home and tips around that answer.
- A9 **Guided tours per page (QW):** a 3-step tour on first visit, skippable, remembered per person.
- A10 **One notification centre (BIG):** bell in the top bar for runs finished, approvals waiting, sync errors, drift, failed jobs. Each person chooses in-app, email, Slack, Teams or WhatsApp, plus quiet hours.
- A11 **Daily brief (QW+):** one morning email or Slack message per database covering what changed, what failed and what's waiting on you.
- A12 **Recent and pinned (QW):** pin favourite pages, models and plans. "Continue where you left off" on Home.
- A13 **Universal search that also acts (BIG):** Cmd-K searches pages, records, settings, docs and past runs, and also runs commands ("archive inactive contacts" opens a checked plan).
- A14 **Consistent states (QW per page):** every page gets the same loading skeleton, empty state with a next step, error with what / why / next, offline read-only with Retry, and a no-access state.
- A15 **Database switcher in the top bar (QW):** jump between client databases while staying on the same page.
- A16 **Version-aware everything (QW):** a small chip on each control that behaves differently on 17, 18, 19 or 20, with "why".
- A17 **Undo toast after every write (QW):** "Saved. Undo" for 10 seconds, backed by the shared History.
- A18 **Keyboard and accessibility parity (QW per page):** the builders' keyboard-only and 200% zoom tests run on every page.
- A19 **Speed budget (QW):** every page shows something useful in under 1 second. Slow sources load on their own. Data is cached per database.
- A20 **Mobile companion (BIG):** approvals, alerts, run status and Ask on the phone. No editing.
- A21 **Light, dark and high-contrast themes from the shared design tokens (QW once tokens are done).**
- A22 **Help that knows the page (QW):** a "?" opens plain docs for this page and this Odoo version, plus Ask.
- A23 **Feedback button with screen context (QW):** sends the page, the database version and recent errors, with no personal data.
- A24 **Workspace roles inside Ingenium (BIG):** Owner, Consultant, Junior (can't run without approval), Client and Viewer, set per database.
- A25 **Activity feed per database (QW):** who did what in Ingenium, in plain words, linked to History.
- A26 **"What's new" panel (QW):** short release notes inside the app.
- A27 **Health score on every database card (QW+):** combines Upkeep, access hygiene, mail, data quality and integrations, and links to the fixes.
- A28 **Templates library across features (BIG):** one gallery for app templates, setup plans, automations, screens, reports, Bridge recipes and scripts, with search and version tags.
- A29 **Offline-safe drafts (QW):** unsaved work in any composer survives a refresh or a lost connection.
- A30 **Shared AI cost meter (QW):** each AI action shows "cached, free" or its rough cost. Ties to the caching item.

## 1+. Models & fields
8. "Explain this model": what it's for, who uses it, how many records, which apps depend on it (QW).
9. Field clone across models: copy a field and its screen placement to similar models (QW).
10. Selection-list editor with usage counts, safe rename of options, and merging of options with remap (QW+).
11. Smart defaults from data: suggest required, default values and help text from how a field is really filled (QW).
12. Field-level history: when it was added, by whom, from which plan (QW once History is shared).
13. Constraints in plain words ("End date after Start date", "Email must be unique"), code generated and checked against existing data first (BIG).
14. Bulk add fields from a spreadsheet header or a pasted list (QW).
15. Related and lookup fields made easy: "show the customer's city on the order" (QW).
16. Data-type upgrade assistant: text → selection, char → many2one, with automatic matching and a review queue (BIG).
17. Model health: unused models, models with no screens, orphan fields after an app was uninstalled (QW).

## 2+. Menus
7. Favourites menu per role: build a "My work" app with only what a role needs (QW+).
8. Icon and colour picker for custom apps using the Keystone icon set (QW).
9. Reorder by usage: suggest an order from how often people open each menu (QW).
10. Menu diff between databases, with promote (QW, uses Pipelines).
11. Search-friendly names: warn about duplicate or confusing menu names (QW).
12. Quick links menu: saved filters as menus ("Overdue invoices > 30 days") (QW).

## 3+. Access
7. "Why can't I see this?": paste a record link and a user to get the exact blocking rule (QW, joins suite idea 23).
8. Field-level visibility in plain words (salary visible to HR only), across screens and exports (BIG).
9. Temporary access: give access until a date, then it's removed automatically (QW+).
10. Access requests: a user asks, a manager approves in Slack or Teams, and it's applied with undo (BIG).
11. Separation of duties check: flag people who can both create and approve the same thing (QW).
12. Access change review: a quarterly "confirm who still needs what" pack for owners (QW+).
13. Multi-company wizard: visual company switcher rules with a test (BIG).
14. Portal access designer: what customers and vendors see, with a live portal preview (BIG).
15. Login and security settings: 2-factor enforcement, password policy, session length, with plain guidance (QW).

## 4+. Automations
8. Suggested automations from real data: "Quotes sit 9 days on average before follow-up. Add a reminder?" (BIG, joins suite 33).
9. Conditions builder with live counts of matching records (QW, reuses suite idea 4).
10. Safe code steps: Python actions written in the code runner editor with dry run and checks (QW+ once the runner is live).
11. Rate limits and quiet hours per automation, so customers aren't spammed (QW).
12. Pause all automations on a model with one switch during imports (QW).
13. Webhook in and out as triggers and actions, sharing Bridge (BIG).
14. Version upgrade check: automations that will break on the next Odoo version (QW, joins after-upgrade check).
15. Ownership and notes: each automation has an owner, a purpose line and a review date (QW).
16. Simulation over history: "if this had been on last month, it would have fired 142 times" (BIG).

## 5+. Odoo approval rules
6. Delegation and out-of-office: approvals move to a deputy automatically (QW+).
7. Escalation after N hours (QW).
8. Approval by amount bands and by company (QW).
9. Approve from email, Slack, Teams and mobile, using Odoo's own action (BIG).
10. Audit pack: every approval with who, when and what changed (QW).
11. Templates: purchase, expense, discount, leave, credit limit (QW).

## 6+. Old Reports / Mail templates / QWeb views
4. Inventory of every report, email and page template in the database with "last used" and "customised or stock" (QW).
5. Upgrade-safety check for customised templates before an Odoo upgrade (QW, joins after-upgrade check).
6. Bulk restyle: apply brand presets to all reports and emails at once (BIG, builds on brand presets).

## 7+. Website
7. Forms builder: contact, quote and job application forms that create Odoo records (BIG).
8. Product page enhancer: AI-written descriptions from product data, reviewed before publish (QW+).
9. Translations side by side for each page (QW).
10. Version history and undo for every page (QW once History is shared).
11. Accessibility and contrast check on pages (QW, reuses builders checks).
12. Analytics glance: visits and form submissions per page from Odoo's data (QW).
13. Redirect manager for renamed pages (QW).
14. Blog post assistant with scheduling (QW+).

## 8+. Bring data in (Import + Ingest)
6. Cleaning step before import: fix casing, trim spaces, split names, standardise phones to +234, dedupe inside the file (QW+).
7. Match against existing records (update vs create), with a review queue for unsure matches (QW, reuses Bridge matching rules).
8. Opening balances wizard for accounting, done only through Odoo's own import and under the money guard (BIG).
9. Email-in importer: forward a spreadsheet to the bot's address and it starts an import draft (BIG).
10. Google Sheets and OneDrive live source with re-sync (BIG, joins Bridge).
11. Import from photos of documents (receipts, delivery notes) with OCR and review (exists in Ingest; polish and surface it) (QW+).
12. Big-file mode: millions of rows in batches with resume and time estimate (BIG).
13. Template downloads per model and version, with examples and validation rules (QW).
14. Import report PDF for clients (QW).

## 9+. Numbering
4. Per-company and per-journal patterns with a clear map (QW).
5. Barcode and QR generation for products and assets, with label printing (BIG).
6. Internal reference generator for products using rules (category prefix + counter) (QW).

## 10+. History
5. Time-travel view: what this screen, setting or record looked like on a date (BIG).
6. Weekly change report to owners (QW, joins the digest).
7. Search history in plain words ("who changed tax settings last month?") (QW+ with Ask).
8. Retention settings and export (QW).

## 11+. Reminders (folded into Automations)
3. Calendar view of all reminders and scheduled emails (QW).
4. Reminder for internal users through Odoo activities, not only email (QW).

## 12+. Settings (Instance Config)
4. Company setup wizard: logo, address, tax ID, bank, currency, fiscal year, country package (QW+, joins suite idea 29).
5. Multi-currency rates: auto-update source picker and a rate history chart (QW).
6. Languages: install, check coverage, edit labels inline (joins suite 17) (QW).
7. System parameters with plain explanations and risk levels; dangerous ones are locked (QW).
8. Settings snapshot and restore for a chosen group of settings (QW once History is shared).
9. Recommended settings by industry and country with reasons (BIG).

## 13+. Job Autopilot
5. Discovery questionnaire for clients that feeds the brief (QW+).
6. Scope guard: flags out-of-scope asks and estimates extra effort (QW).
7. Acceptance checklist the client signs off (joins suite idea "client sign-off") (QW).
8. Post-go-live watch: two weeks of daily health and usage checks after delivery (QW+).
9. Reusable "job recipes" per industry (BIG).

## 14+. Projects / App plan
3. Branching: try two versions of a draft and compare (BIG).
4. Comments and review on drafts (QW, reuses co-editing comments).
5. Export as an installable module with a readme for developers (exists as zip; polish) (QW).

## 15+. From a picture (Wireframe)
3. Multi-page forms and handwritten forms (BIG).
4. Whiteboard photo → app sketch → App Studio brief (QW+).

## 16+. Live Demo Co-Pilot
6. Practice mode: rehearse a demo with a simulated client asking typical questions (BIG).
7. Objection library: suggested answers to common pushback, grounded in Odoo facts (QW).
8. CRM link: meeting notes and next steps land on the lead in Odoo (QW+).
9. Demo database builder: spin up a demo database with industry sample data before the call (BIG, reuses sample data sets).
10. Language support for live answers (QW+).

## 17+. Client portal
3. Change requests in plain words from the client, turned into checked plans for the consultant (BIG, joins suite 28).
4. Monthly client report: what was done, health, integration uptime (QW+).
5. Support tickets linked to History entries (BIG).

## 18+. Ask everywhere
3. "Fix it" from any error banner in any page: opens Ask with the error and context (QW).
4. Saved answers as team notes, searchable later (QW, joins Copilot memory).

## 19+. Power Ops
3. Every remaining recipe gets rehearsal on five sample records (suite idea 1) (QW once merged).

## 21+. Top-level pages
**Home / Command:** 4. "Needs you" list across all databases (approvals, failures, expiring tokens) (QW). 5. Portfolio view for agencies: revenue tags, plan, renewal dates (BIG).
**Connect:** 5. Detect and explain common failures (wrong URL, 2-factor on, API key missing, IP blocked) with fixes (QW). 6. Rotate credentials and expiry warnings (QW). 7. Import many connections from a CSV for agencies (QW).
**Pipelines:** 4. Drift alarm when live and test databases differ (joins suite 10) (QW). 5. Release notes generated from what's being promoted (QW).
**Settings:** 4. Data export of everything Ingenium holds (QW). 5. Single sign-on for teams (BIG).
**Billing:** 4. Agency plans with per-client re-billing reports (BIG). 5. Free trial with a guided "first win" checklist (QW).
**Login / onboarding:** 3. Sample database to explore before connecting a real one (BIG). 4. Progress checklist on Home until setup is complete (QW).
**Marketing / Pricing:** 3. Interactive "what can it do on my Odoo version" page (QW+). 4. Case studies and a live changelog (QW).

## Bold new capabilities (not tied to one page)
- B1 **Odoo upgrade co-pilot (BIG):** before moving 17 → 18 → 19 → 20, scan every customisation (screens, automations, reports, apps, Bridge flows), predict breakage, rehearse on a copy and give a step-by-step plan.
- B2 **Process mining (BIG):** read Odoo's tracking data to draw how work really flows (lead → quote → order → invoice), where it stalls, and what to automate.
- B3 **Database "doctor" (BIG):** one weekly scan pulling all health checks into a ranked to-do list with one-click checked fixes.
- B4 **Ingenium agent mode (BIG):** give a goal ("get this database ready for go-live"), the agent builds a plan across Bulk Setup, App Studio, Access, Automations and Bridge, and waits for approval at each step.
- B5 **Knowledge capture (QW+):** every decision, plan and answer per client becomes a searchable client handbook (joins Copilot memory and the handover pack).
- B6 **Benchmarking (BIG):** anonymous comparisons like "databases like yours usually have X set up" (opt-in only).
- B7 **Training mode for end users (BIG):** generated walkthroughs and quizzes for the client's staff from their real screens (joins "Explain this screen").
- B8 **Compliance packs (BIG):** Nigeria (FIRS e-invoicing, VAT), EU (GDPR), with checks and setup plans, always behind the money guard.

---
## APPROVED: "all" (Tope, Oct 17). Adds to SPEC.md, CONFIG_SUITE_SPEC.md and BRIDGE_RUNNER_SPEC.md; replaces nothing.

### Tope's additions (Oct 17)
1. **Plain-word term card (app-wide).** Every plain-language label that stands in for an Odoo term gets a compact, beautiful hover/focus card (like Odoo's debug field tooltip, but premium). It shows: Odoo's own term and technical name (model/field/xmlid), type, where it lives (app/model), the Odoo version it applies to and any version differences, a one-line meaning, and links ("Open in Odoo", "Explain more", "Copy technical name"). Keyboard reachable (focus), touch = tap, reduced motion respected, no layout shift. One shared component plus a term registry (a single glossary source), with a test that fails if a mapped plain label renders without its card.
2. **Live Demo Co-Pilot as demo builder.** User submits a BRD/SOW (any format) plus a target Odoo DB (often free Odoo Online). Ingenium reads it, makes a demo plan (apps to install, configuration via Bulk Setup, App Studio/View Designer customisations within what the hosting allows, realistic labelled demo data via document import/seed packs, a demo script mapped to the BRD's requirements) and shows it for approval, then builds it with check/undo. Undo the demo data in one click after the demo.
   - Answers in the live call are not limited to the live DB. The answer order is: what exists in this DB (shown live); what Odoo can do on this version and edition, configured or not; what would need customisation or an integration (with effort and confidence); and honest "not possible / needs a partner app". Each answer is labelled "In your demo", "Standard Odoo, not set up yet", "Possible with customisation" or "Not available". Never claim something exists in the DB when it doesn't. The requirement-coverage view ticks off BRD items as they're shown.
3. **Connect page rebuild** (on top of audit Connect ideas 1-7): a clean, modern, uncluttered redesign to the highest bar (design-pack + brand/ingenium-v2): one clear primary action, guided by hosting type, saved connections as tidy cards with health, progressive disclosure for advanced fields, plain errors with fixes.

### Urgent quick fix (approved as part of "all")
Lock the Power Ops accounting and delete recipes behind the money guard now (no bulk accounting writes; route through suite check/approve/undo or remove).
