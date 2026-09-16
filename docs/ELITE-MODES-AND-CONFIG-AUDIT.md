# Elite modes & Odoo configuration audit

**Date:** 2026-09-16  
**Tip:** `premium-local-tip` @ post-`8d57c9d`  
**Goal:** Judge each product mode for function / UI / UX eliteness, and map how far Instance Config + Data + Ops go toward *consultant configuration as few clicks*.

Scoring (1–5): **F**unction effectiveness · **U**I craft · **X** UX clarity · **C** consultant-speed (clicks-to-outcome)

---

## Executive verdict

Ingenium already has **more Odoo configuration surface than most Studio clones** (company, sequences, mail, paperformats, defaults, cron, translations, menus API, bulk suite, CSV/XLSX import). What is *not* elite yet:

1. **Config is a long settings dump**, not a guided “job to be done” flow (few clicks).
2. **Module / company setup recipes are missing** as first-class UI (install CRM+Sales+Accounting presets, multi-company bootstrap, chart of accounts packs).
3. **Batch + import are powerful but expert-shaped** (phrase confirms, mappings, dry-run) — correct for safety, heavy for daily consulting.
4. **Discoverability**: Instance Config lives under Safety & History; consultants hunt Settings in Odoo, not “govern.”
5. **API ahead of UI** in places (menus create, currencies/UoM/fiscal probes, system parameters) — backend exists or stubs; UI incomplete.

**North star:** every common consultant configuration task should be: pick recipe → review → dry-run → apply (≤4 clicks), with blast-radius + snapshot already wired.

---

## Mode scorecard (shipped sidebar)

| Mode | F | U | X | C | Notes |
|---|---|---|---|---|---|
| Overview / Browser | 4 | 4 | 3 | 3 | Strong fingerprint, playbooks, sandbox stages; still dense; Develop tab is power-user |
| Models & Fields (Builder) | 4 | 4 | 4 | 4 | List→composer kit; delete/confirm mature; still not “wizard for add field to Sales” |
| View Designer | 4 | 4 | 3 | 3 | Studio-like canvas after strangler; visual UAT + live RPC still founder-gated |
| Menus | 4 | 4 | 4 | 4 | Shared list→composer; session Draft/Unsaved/Saved |
| Website | 3 | 3 | 3 | 2 | Gated on module; thin vs Odoo Website Builder |
| Automations | 4 | 4 | 4 | 3 | Safe triggers; not full Studio automation breadth |
| Approvals | 3 | 3 | 3 | 2 | Useful; EE/studio coupling varies by instance |
| Reports | 3 | 3 | 3 | 2 | Exists; QWeb authoring still specialist |
| Access | 4 | 4 | 4 | 3 | Rights + record rules composer; matrix is power |
| Code Studio | 3 | 3 | 2 | 2 | Developer lane — fine, not consultant-primary |
| App Studio | 4 | 4 | 4 | 4 | Chat polish + Option A gates; Promote human |
| Draft Studio / Job Autopilot | 3 | 3 | 3 | 3 | Restored in IA; overlap with App Studio still cognitive load |
| Projects | 3 | 4 | 3 | 3 | Continuity good; not a config accelerator |
| Odoo Expert | 4 | 4 | 4 | 3 | Dedicated route; contextual, not competing door |
| Live Demo Co-Pilot | 3 | 3 | 3 | 2 | Pilot-ready path; real meeting still open |
| Import | 4 | 3 | 3 | 3 | CSV/XLSX + mapping + dry-run + images — **elite bones**, needs recipes & fewer steps |
| ID Generator | 4 | 3 | 4 | 4 | Narrow, clear job |
| Bulk Suite | 4 | 3 | 3 | 3 | Mass edit, dedupe, activities, portal, security — **powerful**, UI is a control panel |
| Power Ops | 3 | 3 | 2 | 2 | Recipe runner for experts |
| Cron Manager | 4 | 3 | 3 | 3 | Overlaps Scheduled actions on Config |
| Housekeeping | 3 | 3 | 3 | 3 | Hygiene jobs |
| Reminders | 3 | 3 | 3 | 3 | |
| Script Runner | 3 | 2 | 2 | 1 | Dev only |
| Snapshots & Journal | 4 | 4 | 4 | 4 | Trust spine — keep |
| **Instance Config** | **3** | **3** | **2** | **2** | Feature-rich API + long page; **not few-click** |

---

## Instance Config — deep dive

### What works today (well-built pieces)

Backend `config_ops` is serious:

- Companies CRUD-ish (patch)
- Sequences create/patch
- Mail templates + activity types
- Paperformats
- `ir.default` field defaults
- Languages + translations CSV import/export + i18n probe/spec
- Field-labels CSV
- App menu create API
- Cron list/patch active
- Website pages/menus availability
- System parameters
- Currencies / rates / UoM / fiscal positions (availability/master-data style)

Frontend page (~930 LOC) covers: Company, Sequences, Mail, Activities, Paperformats, Defaults, Scheduled actions, Website note, Translations CSV.

Safety patterns (confirm phrases, write-mode) align with product doctrine.

### Gaps vs “few clicks for consultants”

| Consultant job | Today | Elite target |
|---|---|---|
| New DB day-1 setup (company, currency, language, timezone) | Manual fields on Config | **Day-1 recipe** wizard: 1 form → apply |
| Install Sales + CRM + Accounting pack | Overview/sandbox module install (expert) | **Apps pack** cards: “Sales desk”, “Retail POS”, one click + dry-run deps |
| Chart of accounts / fiscal | Probe endpoints weak in UI | CoA country pack import (CSV) with preview |
| Multi-company | Single company editor | Add company + share/ chart wizard |
| Sequences for invoices/orders | Manual sequence form | **Document numbering pack** (INV/, SO/, …) one apply |
| Email templates for SO/PO/Invoice | Manual mail template create | Template library with placeholders + install set |
| Users + access for client team | Access composer + Import users template | **Team bootstrap**: CSV of users → groups → invite |
| Master data (products, customers, UoM) | Import tool (generic) | Named packs: “NG retail starter”, “EU services” |
| Turn off noisy crons on staging | Cron toggles on Config + Bulk | Staging profile: “silence mail/cron” one toggle |
| Translate labels | CSV paste in Config | Upload .po/.csv + model filter + dry-run |
| Settings that live in `res.config.settings` | Mostly missing | Settings search + toggle board (read/write safe fields) |

**UI problems:** one scrolling mega-page; no job-based IA; Config buried under govern; cron duplicated with Cron Manager; menus API without first-class Menus-settings UX beyond Menus builder.

---

## Data & batch — deep dive

### Import (strong foundation)

Upload → map → dry-run → commit (+ image manifest). Risk phrase on write. Seed packs API exists.

**Elite upgrades:**

1. Visible **seed pack gallery** (not buried).
2. Saved mapping profiles per model.
3. “Fix errors in grid” instead of only error CSV download.
4. One-click **Upsert partners/products** presets.
5. Post-import “open in Odoo” deep link (partially pattern-exists elsewhere).

### Bulk Suite (powerful, not effortless)

Mass edit, workflow buttons, dedupe merge, attachments hygiene, activities, portal, security, recompute — with dry-run.

**Elite upgrades:**

1. **Recipe chips** above the control panel: “Archive inactive partners”, “Assign salesperson”, “Recompute prices”.
2. Domain builder visual (partial DomainBuilder exists — wire as default).
3. Progress + undo via snapshot made primary CTA after apply.
4. Collapse advanced into disclosure; lead with recipes.

---

## Cross-cutting elite gaps (all modes)

1. **Job-to-be-done IA** — consultants think “set up accounting”, not “Instance Config → sequences”.
2. **Recipe / playbook layer** — Domain + EE playbooks exist on Overview; Config/Import/Bulk don’t share that metaphor.
3. **Empty → first success** — First-win path exists; Config has no first-win.
4. **Density tokens** — shell chrome tokenized; Config/Bulk still form-soup.
5. **Res.config.settings** board absent — huge Odoo Settings parity hole.
6. **Batch across companies** — weak.
7. **Documentation in-product** — Operator demo guide exists; Config needs inline “why this matters”.

---

## Recommended build order (few-click config)

### P0 — Config Command Center (2–3 weeks)

1. Re-home **Instance Config** under Operate (or dual-link from Overview “Configure instance”).
2. Replace mega-page with **job cards**: Day-1 · Numbering · Mail · Master data · Staging silence · i18n.
3. **Day-1 Setup** wizard (company name, currency, language, country, timezone) → one Apply (dry-run + snapshot).
4. **Document numbering pack** (SO/INV/PO/payment prefixes) one Apply.

### P1 — Apps & packs (2 weeks)

5. **Apps Pack installer** UI (deps preview → install/upgrade) wrapping existing module install.
6. Import **seed pack gallery** + mapping profiles.
7. Bulk **recipe chips** + DomainBuilder default.

### P2 — Settings parity (2–3 weeks)

8. `res.config.settings` searchable toggle board (capability-gated, dry-run).
9. Multi-company add + basic sharing.
10. CoA / fiscal / UoM pack imports with preview.

### P3 — Polish

11. Unify Cron Manager vs Config scheduled actions.
12. Menus “create app tile” from Config menus API into Menus builder CTA.
13. Continuity: every Apply writes Project/journal breadcrumb.

---

## What not to do

- Don’t clone full Odoo Settings page field-for-field.
- Don’t remove dry-run / confirm phrases for mass writes.
- Don’t bury recipes behind Code Studio.

---

## Immediate next engineering slice (suggested)

**Ship P0.2–P0.4:** Config job-card shell + Day-1 wizard + numbering pack, reusing `ConfirmDialogV2`, snapshots, and write-mode. Highest consultant wow per LOC after current tip.
