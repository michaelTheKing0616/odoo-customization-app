# Odoo Custom — Complete User Guide

**Who this is for:** Anyone who will use the product day to day — operators, admins, consultants — **not** developers.

**What this product is:** **Odoo Custom** is a web app that lets you customize **Odoo Community 19, 18, and 17** (GA; **16 experimental**) without Odoo Enterprise Studio. You connect your Odoo database, then build models, fields, screens, buttons, automations, and security through a guided UI. You can test changes in a sandbox and export a real installable Odoo module.

**Confirm phrase you will see often:** type exactly:

```text
I understand the risks
```

That phrase unlocks actions that change live data or install modules. It is intentional — ERP mistakes can affect real business records.

---

## Table of contents

1. [Big picture: how the app is organized](#1-big-picture-how-the-app-is-organized)
2. [Before you start](#2-before-you-start)
3. [Home page](#3-home-page)
4. [Connect your Odoo](#4-connect-your-odoo)
5. [API settings](#5-api-settings)
6. [Connection hub (browse + export)](#6-connection-hub-browse--export)
7. [App Wizard (scaffold Library / CRM / Inventory)](#7-app-wizard-scaffold-library--crm--inventory)
8. [Builder (models & fields)](#8-builder-models--fields)
9. [View Designer (screens, buttons, polish)](#9-view-designer-screens-buttons-polish)
10. [Automations](#10-automations)
11. [Access rights & record rules](#11-access-rights--record-rules)
12. [Reminders](#12-reminders)
13. [Bulk data import](#13-bulk-data-import)
14. [Power Ops (Online power parity)](#14-power-ops-online-power-parity)
15. [Change journal](#15-change-journal)
16. [Settings, sequences & menus](#16-settings-sequences--menus)
17. [Draft projects](#17-draft-projects)
18. [Export, sandbox, promote, uninstall](#18-export-sandbox-promote-uninstall)
19. [Typical end-to-end journeys](#19-typical-end-to-end-journeys)
20. [What lives in this app vs what lives in Odoo](#20-what-lives-in-this-app-vs-what-lives-in-odoo)
21. [Warnings, confirmations & safety](#21-warnings-confirmations--safety)
22. [Troubleshooting](#22-troubleshooting)
23. [Glossary](#23-glossary)

---

## 1. Big picture: how the app is organized

Think of the product as a **toolbox around one Odoo connection**.

```text
Home
  └─ Connect your Odoo          ← save URL + database + login
       └─ Connection hub        ← browse metadata; export / sandbox / promote
            ├─ Wizard           ← create a starter app (Library, CRM Lite, Inventory Lite)
            ├─ Builder          ← create models & fields
            ├─ View Designer    ← design forms/lists; bind real buttons
            ├─ Automations      ← rules that run when records change
            ├─ Access           ← who can read/write which records
            ├─ Reminders        ← email templates + optional scheduled jobs
            └─ Drafts           ← offline specs you can diff & apply later
```

**Also available:** **API settings** (keys for the *app’s* API — separate from your Odoo password).

Everything you build for a given Odoo database is reached under:

```text
/connections/<connection-id>/…
```

You get that ID automatically when you open a connection from **Connect**.

---

## 2. Before you start

### What you need

| Item | Typical local setup |
|------|---------------------|
| Odoo Community **19** | `http://127.0.0.1:8069` |
| Database name | e.g. `odoo_dev` |
| Odoo login | e.g. `admin` / `admin` |
| This web app | `http://127.0.0.1:3000` |
| App API | `http://127.0.0.1:8000` |

Someone on your team may already have Docker and servers running. If pages fail to load, ask them to confirm Odoo and the API are up (see [Troubleshooting](#18-troubleshooting)).

### Mental model (important)

| Concept | Plain meaning |
|---------|----------------|
| **Connection** | Saved link from this app → your Odoo (URL, database, user). Credentials are stored encrypted in the app. |
| **Live customization** | Changes applied **immediately** to that Odoo database (models, fields, views, automations). |
| **Module zip** | A downloadable Odoo addon package you can install elsewhere — the “escape hatch” / portable copy. |
| **Sandbox** | A disposable Odoo used to **test** a zip before installing it on a real database. |
| **Promote** | Install a **sandbox-validated** zip onto a connection (after confirm). |
| **Inherit (views)** | Safer way to customize screens: add an extension layer instead of overwriting the original form. |
| **Open in Odoo** | Always the source of truth for how screens look and whether buttons work. |

### What this app is **not**

- Not Odoo Enterprise **Studio** (and it does not copy Studio).
- Not a replacement for logging into Odoo for day-to-day book loans, CRM, etc. — after you customize, **users work inside Odoo**.
- Multi-Odoo-version: **19 + 18 + 17 GA**; **16 experimental** (capability matrix).

### Odoo Online / Enterprise / Odoo.sh / self-host (connections)

**All tiers can be connected.** The app uses **warn-only** UX (not a hard refusal) plus hosting honesty on the capability probe.

| Tier | Metadata RPC | Custom Python modules | Notes |
|------|--------------|----------------------|--------|
| **Self-hosted CE/EE** | ✅ | ✅ Option A (sandbox → filesystem/data promote) | Local Docker / VPS |
| **Odoo.sh** | ✅ | ✅ via Git/filesystem | Staging branches; matching-major sandbox before prod |
| **Odoo Online** | ✅ | ❌ | Data/XML (`base_import_module`) only; probe shows **No Python module install** |
| **Enterprise (`+e`)** | ✅ same caps as CE major | Same as host tier | Never Studio / `web_studio` source |

- **Banner UX:** Capability probe shows hosting badge (Online / Odoo.sh / Self-hosted), Enterprise notice when `server_version` contains `+e`, and warnings when Python install is blocked or Studio modules are present.
- **Community-like metadata only:** Changes go through **public ORM/RPC** (`ir.model`, fields, views, menus, automations, access rules, module zip export). Same capability set as Community for that major.
- **Version follows the host:** Capability badges follow the host’s major (GA **17 + 18 + 19**; **16** experimental).
- **Power Ops stays RPC-first:** Bulk recipes ([§14](#14-power-ops-online-power-parity)) run over RPC on Online and Enterprise the same as self-hosted Community. **Online UI limits are not API limits.**
- **Promote contract:** Python-containing zips targeting Online raise a clear error — re-export `install_mode=data` or use sh/self-host.

---

## 3. Home page

**URL:** `/`

**What you see**

- Product name: **Odoo Custom**
- Short pitch: no-code customization for Community without Enterprise Studio
- Two buttons:
  - **Connect your Odoo** → start connecting a database
  - **API settings** → manage app API keys / audit (usually for shared or hosted APIs)

**What to do:** Click **Connect your Odoo** for normal product use.

---

## 4. Connect your Odoo

**URL:** `/connect`

### Create a connection

Fill in:

| Field | Meaning |
|-------|---------|
| **Name** | Friendly label (e.g. “Local Odoo 19”, “Acme Production”) |
| **URL** | Odoo base URL (e.g. `http://127.0.0.1:8069`) |
| **Database** | Exact database name |
| **Username** | Odoo user (prefer an admin or API-capable user) |
| **Password** | Password or API key |

Click **Save connection**. The app **verifies** login before saving. On success you see the connection in the list, plus an **Odoo 19 Community** capability badge (expand for the supported feature checklist). Use **Re-probe** anytime to refresh version capabilities.

v1 **GA** is **Community 19, 18, and 17**. **16** is experimental (does not claim related-write / `update_path`). Accounting Power Ops needs the `account` app on that database. Majors ≤15 fail at verify. See `docs/MULTI_VERSION_ODOO_PLAN.md`.

### Connection list actions

For each saved connection you can:

| Action | Goes to / does |
|--------|----------------|
| **Browse** | Connection hub (metadata + export) |
| **Build** | Builder (models & fields) |
| **Views** | View Designer |
| **Automations** | Automations |
| **Access** | Access rights |
| **Edit** | Update name / URL / credentials |
| **Delete** | Remove **this app’s** saved connection (see warning below) |

Also: link back to **Home** and **API settings**.

### Delete connection — read this

Deleting a connection:

- Removes the connection record, stored credentials, and app-side snapshots for that connection.
- **Does not** uninstall models, fields, or apps inside Odoo.

You will be asked to confirm with the risks phrase.

---

## 5. API settings

**URL:** `/settings`

**Who needs this:** Usually only when the app API is locked down with `AUTH_MODE=api_key` (shared/deployed environments). Local demos often leave auth **off**.

**What you can do**

- See whether API auth is on or off
- Store an API key in the browser (sent as Bearer on requests)
- Bootstrap / create / revoke app API keys
- View a simple **audit log** of API activity

**Note:** These keys authenticate **this customization app’s API**, not your Odoo login.

---

## 6. Connection hub (browse + export)

**URL:** `/connections/<id>`

This is the **home base** for one Odoo connection.

### Top navigation (typical)

- **Wizard** — scaffold a starter app  
- **Builder** — models & fields  
- **Drafts** — draft projects  
- **View designer** — screens & buttons  
- **Automations**  
- **Access**  
- **Reminders**  
- **← Connections** — back to the connect list  

Exact labels may be short links in the page header; they all stay under the same connection.

### Browse tabs

| Tab | What it shows |
|-----|----------------|
| **Apps** | Installed Odoo applications / modules |
| **Models** | Business objects (filterable); custom ones often start with `x_` |
| **Fields** | Columns on a selected model |
| **Views** | Screens (form, list, search, kanban, …) for a selected model |

This area is mainly for **inspection** — understanding what already exists in Odoo.

### Library stats strip

If a Library app is present (`x_lib_book` model), the hub may show quick counts such as **Books**, **Loans**, **Active**, **Overdue**. That confirms the Library scaffold is live.

### Export / sandbox / promote (on the same page)

See [§14](#14-export-sandbox-promote-uninstall) for the full flow. Short version:

1. Choose technical + display names for a module zip  
2. **Download zip** and/or **Sandbox install**  
3. After a successful sandbox validation, **Promote** to a connection (with confirm phrase)  
4. Optionally **Uninstall** a promoted module later (with confirm — residuals possible)

---

## 7. App Wizard (scaffold Library / CRM / Inventory)

**URL:** `/connections/<id>/wizard`

**Purpose:** Create a **starter application** on the connected Odoo in a few clicks (live metadata), or export a Library module zip without writing to Odoo.

### Inputs

| Control | Meaning |
|---------|---------|
| **Display name** | Human name (e.g. **Acme Library**) — appears in menus |
| **Technical prefix** (optional) | Advanced; leave blank for standard template model names |
| **Multi-company aware** | **Only applied for the Library template** (scaffold + Library zip export). If you check it and then scaffold **CRM Lite** or **Inventory Lite**, the flag is **ignored** (`multi_company: false` is sent). It does **not** mean those apps cannot be multi-company later — you can still add a company field + Access record rules yourself in Builder/Access. It means the **one-click toggle is wired for Library only** today. |

### Templates

| Template | What you get (plain language) |
|----------|-------------------------------|
| **Library** | Categories, Authors, Books, Loans; menus; labeled book forms; circulation fields; optional multi-company |
| **CRM Lite** | Lightweight lead-style model for simple pipeline work |
| **Inventory Lite** | Simple items with quantity / location style fields |

Click a template card → confirmation dialog → type **`I understand the risks`** → scaffold runs on **live** Odoo.

### After a successful scaffold

You typically see:

- Checklist of created pieces (models, menus, etc.)
- Links to open each model in **Builder** or **Designer**
- Shortcuts back to the connection hub or sandbox

Then open **Odoo** (home / apps / menus). For Library, look for the app menu (e.g. **Acme Library**) with **Categories**, **Authors**, **Books**, **Loans** — not the Odoo “Apps” store catalog.

If the menu is missing after scaffold, try a hard refresh. Advanced tip (someone technical can run this in the browser console on Odoo):

```js
localStorage.removeItem('webclient_menus');
localStorage.removeItem('webclient_menus_version');
location.reload();
```

### AI draft + Generate UI from JSON

**Draft ModuleSpec** turns a plain-language prompt into a rich JSON blueprint (models, fields, menus, list/form/kanban arches, statusbars, smart-button specs, automation *ideas*).

How it stays robust:

1. **LLM provider** — `AI_ASSIST=ollama` (recommended: `qwen2.5:7b-instruct-q4_K_M`) or `openai-compatible` (vLLM / LM Studio / OpenAI). JSON-mode on every call.  
2. **Domain template library + RAG** — curated packs (car rental, clinic, field service). Retrieval uses regex, then optional **MiniLM embeddings** (`AI_RAG=auto`; install with `uv sync --project apps/api --extra ai-rag`), else Jaccard tags. Packs work even if AI is off.  
3. **Pipeline modes** — `AI_PIPELINE_MODE=single` (one JSON call + merge) or `staged` (entities → fields → relationships → automations → deterministic views).  
4. **Rules engine** — after the LLM: referential integrity, `x_code` on workflows, mail.thread, partner back-ref smart buttons, overdue automation safety net, access stubs, completeness checklist.  
5. **Self-critique** (`AI_CRITIQUE=auto`) — checklist + optional LLM evaluation; can add missing `x_*` fields/models/automations before you review the JSON.  
6. **Reuse existing models** — pick Contacts / products / invoices so the draft *links* them.  
7. Draft is **preview only** until you confirm **Generate UI from JSON**.

Generated module zips include a `.meta.json` sidecar (ModuleSpec) so Code→UI can round-trip our own output without parsing Python.

**ModuleSpec builder** (`/connections/<id>/modulespec`): visual editor for the same JSON contract — models/fields, relations, smart buttons/automations metadata, unmapped “view as code” blocks. Import an Odoo module zip / `.py` / `.xml` / `.meta.json` (AST + XML parsers), save as a Draft project, or **Generate UI from ModuleSpec**. Wizard AI drafts and Projects → **Edit ModuleSpec** open here.

**Generate UI from JSON** (confirm phrase required) applies that draft live: models/fields, views, menus, smart buttons. Smart buttons are injected via a stable **inherit** view (`{model}.studio.smart_buttons`) so stock forms like Contacts are never rewritten. Automations stay review-only on the Automations page.

Also: scaffold **Car Rental** from a template card. Prefer sandbox before production.

### Export library zip (no live write)

**Export library zip** downloads a portable Library module (with options such as fines) **without** creating live models. Use this when you want Path C (sandbox → promote) instead of live wizard scaffold.

---

## 8. Builder (models & fields)

**URL:** `/connections/<id>/builder`

**Purpose:** Create and manage **custom models** and **fields** on live Odoo (Studio-like, via public APIs).

### Create a model

1. Enter a **label** (e.g. “Ticket”)  
2. Enter a **technical name** starting with `x_` (e.g. `x_ticket`)  
3. Optionally enable **Chatter & activities** (mail / activities support when available)  
4. **Create model**

Custom models appear in the list. You can **Delete** a model later — this is **destructive** (confirm phrase; data/views may not fully restore).

### Create a field

1. Choose the **model**  
2. Choose a **type**:

| Type | Everyday meaning |
|------|------------------|
| char / text | Short / long text |
| integer / float | Whole / decimal numbers |
| boolean | Checkbox |
| date / datetime | Date / date+time |
| html | Rich text |
| binary | File / image style storage |
| selection | Fixed list of choices |
| many2one | Link to one record of another model |
| many2many | Link to many records |
| one2many | List of related lines on this form |
| monetary | Money amount (needs currency field) |

3. Set label, required, readonly, help as needed  
4. For relations: pick the related model; for one2many, name the inverse many2one  
5. For selection: enter the allowed values  
6. For many2one: set **On delete** (`restrict` / `cascade` / `set null`). On Odoo 19, **required** many2one cannot use “set null”  
7. Optionally **inject into views** so the field appears on form/list/search  
8. Optional **barcode** widget for char fields  

### Link one2many (parent ↔ child)

Use the dedicated helper to connect a parent model to child lines (names for the one2many and the child’s many2one), optionally injecting into views.

### Safety

- Prefer trying field/model experiments on a **sandbox / non-production** connection first.  
- Deleting fields/models can break views and automations; confirm carefully.

---

## 9. View Designer (screens, buttons, polish)

**URL:** `/connections/<id>/designer`  
Optional: `?model=x_lib_book` to pre-focus a model.

**Purpose:** Design how people see and act on records — forms, lists, search, kanban — and bind **real Odoo actions** to buttons.

This is the closest screen to “Studio for views.”

### Setup bar

| Control | What it does |
|---------|----------------|
| **Model** | Technical model name (e.g. `x_lib_book`) |
| **Load fields** | Pull field list into the palette |
| **Load existing view** | Load the current Odoo view into the canvas (preferred start) |
| **View type** | `form` · `list` · `search` · `kanban` |
| **Title** | View title string |
| **Save strategy** | **Inherit (safe)** (default) or **Overwrite primary** |
| **Save to Odoo** | Write the designed screen |
| **Polish form layout** | Apply a clean Identity / Details / Lines style grouping when possible |
| **Undo last save** | Restore from a snapshot when available |
| **Open in Odoo** | Open the real Odoo UI for this model (authoritative) |
| **Toggle / Refresh preview** | Best-effort iframe preview (prefer Open in Odoo if blank) |

**Production tip:** Keep **Inherit (safe)** unless you fully understand overwrite. Overwrite asks for an extra browser confirmation and snapshots first.

### Form designer

**Palette (left):** Drag or click fields onto groups/pages. You can also **create a new field** here (confirm phrase) and inject it.

**Canvas (center):**

| Tool | Meaning |
|------|---------|
| **+ Group** | Add a labeled group of fields |
| **+ Notebook** | Add tabs (pages) |
| **+ Header button** | Button in the form header (workflow style) |
| **+ Smart button** | Stat button in the button box (e.g. “Loans”) |
| **+ Inline button** | Button inside a group |

**Statusbar:** Pick a selection (or suitable) field to show as Odoo’s chevron status widget; optional visible stages list.

**Field properties (right):** Required, Readonly, Invisible (with **domain builder**), Widget (e.g. barcode).

**Generated arch:** Technical XML preview for transparency — you do not need to edit it for normal use.

### Binding buttons to real actions

When you add a header / smart / inline button, a **bind panel** opens. Modes:

| Mode | What gets created / used | Result in Odoo |
|------|--------------------------|----------------|
| **Update field** | Safe server action | Button sets a field to a value (e.g. status → Available). Selection fields show a real dropdown of allowed values. |
| **Open related** | Window action | Opens related records filtered to this form (e.g. loans for this book) |
| **Next activity** | Activity server action | Schedules an activity on the record (needs mail/activities support on the model) |
| **Send mail** | Mail post action | Posts/sends using a template (or a simple auto-created one) |
| **Smart button** | Related window + optional count | Stat button; optional **computed count** (advanced — confirm phrase) |
| **Existing action** | Pick from list | Reuse an action already on this model |

Then **Create & bind**, then **Save to Odoo**, then verify with **Open in Odoo**.

**Important limits (honest):**

- Buttons use Odoo `type="action"` (real action IDs).  
- Custom Python **object methods** and dangerous **code** actions are **not** the default path — those go through module packaging / advanced confirm flows elsewhere.  
- Do not stack many one-off “test” saves that each inject the same header — prefer one inherit and edit it (duplicate “Mark Available” buttons usually mean two inherits doing the same job).

### List designer

- Click fields to build columns  
- Optional row coloring expressions: **decoration-danger**, **decoration-info**, **decoration-muted** (e.g. highlight open loans)

### Search designer

- Add searchable fields  
- **+ Add search filter** with the **domain builder** (rules like field = value)

### Kanban designer

- Choose **group-by** field (columns)  
- Add fields shown on each card  

### Domain builder (invisible & filters)

Used for:

- Field **invisible** conditions  
- Search **filters**  
- (Also used on Automations and Access)

You add rules (field + operator + value). You can switch to **raw** domain text if needed. Operators include equals, not equals, greater/less, like, in, etc.

### XPath inherit (power users / precise patches)

For surgical view changes:

1. Enter an **xpath** expression (default often `//sheet`)  
2. Choose position: inside / after / before / replace / attributes  
3. Paste a small XML **body**  
4. **Preview** (validation messages)  
5. **Use as arch override** and/or **Save xpath inherit**  

Most users never need this if Groups / Notebook / Buttons cover the job.

### Snapshots & undo

Successful risky saves often create a **snapshot**. Use **Undo last save** / snapshot list when offered. Undo restores **definitions** (views, etc.), not every business side effect.

---

## 10. Automations

**URL:** `/connections/<id>/automations`  
Optional: `?model=x_lib_book`

**Purpose:** Rules that run when records are created, updated, deleted, archived, or based on dates — without writing Python in the default path.

Cross-link: **form header buttons** for the same kinds of actions are built in the **Designer**; Automations are for **background rules**.

### Create a rule

1. **Name** the automation  
2. Choose **model**  
3. Choose **trigger**:

| Trigger | When it runs |
|---------|----------------|
| On create | New record |
| On update | Record written |
| On create and edit | Create or write |
| On deletion | Record deleted |
| On archived / unarchived | Archive toggles |
| Based on date field / after creation / after last update | Time-based |

4. Optional **filter domain** (DomainBuilder) — only matching records  
5. Choose **action kind**:

| Action | Safe default? | Meaning |
|--------|---------------|---------|
| **Update field** | Yes | Set a field to a value |
| **Related write** | Yes | Write a field on a linked Many2one record (e.g. contract confirm → vehicle status = rented) |
| **Create activity** | Yes | Schedule an activity |
| **Create record** | Yes | Create a related record |
| **Send / post mail** | Yes | Email / chatter note via template |
| **Custom Python → module zip** | Option A | Packages code for sandbox → install later |
| **Custom Python → live now** | Advanced | Runs live code — confirm phrase; high risk |

6. Save / create  

Presets: **Car rental: vehicle → rented**, Library fine-on-return (Option A), etc.

### Managing rules

- **Activate / Deactivate**  
- **Delete** (confirm — side effects already done are not magically undone)  
- **Snapshots / undo** for definition restore when available  

---

## 11. Access rights & record rules

**URL:** `/connections/<id>/access`

**Purpose:** Control **who** can do **what** on a model.

### Access matrix

Enter comma-separated models → **Load matrix**. Rows are groups; cells are R/W/C/D toggles. Clicking creates or updates `ir.model.access` lines immediately.

### Access rights (ACL)

Per model + security group (also available as list/forms below the matrix):

- Read / Write / Create / Delete checkboxes  

Use this so non-admin users can open your custom app.

### Record rules

Narrow which **rows** a group sees (domain), with permission flags.

Example idea: “Users only see loans for their company.”

Deleting ACL or rules requires confirm — mistakes can **lock people out** or **expose** records.

---

## 12. Reminders

**URL:** `/connections/<id>/reminders`

**Purpose:** Create mail **templates** and optional **scheduled jobs (crons)** for due / overdue style reminders (common for Library loans).

Typical inputs:

- Name  
- Model (often loans)  
- Date field  
- Mode: overdue vs due soon  
- Interval  
- Email expression  
- Whether to create a cron  

Requires confirm phrase. Misconfigured email expressions can spam or fail silently — test on non-production first.

---

## 13. Bulk data import

**URL:** `/connections/<id>/import`

**Purpose:** Upload a **CSV or XLSX** spreadsheet and bulk **create** or **upsert** records on any Odoo model (Contacts, products, custom `x_*` models).

### Flow

1. Pick target model (e.g. `res.partner`)  
2. Download a CSV template (optional)  
3. Upload your file → **Parse**  
4. Map CSV columns → Odoo fields  
5. **Dry-run** (no writes)  
6. **Commit writes** — type `I understand the risks`

Upsert can match on fields you choose (e.g. `email`) or external ids. Many2one values resolve by id, `module.xml_id`, or name search — ambiguous matches fail that row loudly.

Creates are batched (default 50 rows per RPC). Seed templates exist for partners, products, and common custom models (e.g. rental vehicles, library books).

Prefer a sandbox connection for first imports.

---

## 14. Power Ops (Online power parity)

**URL:** `/connections/<id>/power-ops`

**Purpose:** Run **multi-step bulk RPC recipes** that Odoo Online’s UI often forces one-by-one — the same class of power you’d use on Odoo.sh.

**Flagship recipe:** *Purge journal entries* — reset `account.move` to draft (`button_draft`), then unlink, with per-record error reporting (locked periods / reconciliation still apply).

Also included: mass archive/unarchive, mass unlink, cancel/post moves, mail/attachment cleanup, deactivate users. Always **Dry-run** first; **Execute** requires the confirm phrase.

**Philosophy:** Online UI limits are not API limits. Capability probe shows which recipes the connected database can run via RPC. Rare true platform blocks (e.g. some Online plans cannot install custom Python modules) are called out with workarounds — not treated as “everything is impossible.”

View **overwrite** / stock form polish also use the same advanced confirm gate (inherit remains the safe default).

---

## 15. Change journal

**URL:** `/connections/<id>/journal`

**Purpose:** One place for **metadata snapshots** with **Undo**, plus filtered API audit lines for this connection’s mutating routes.

Use after Power Ops, access deletes, view overwrites, or automation deletes. Not every change is reversible (e.g. deleted business records).

---

## 16. Settings, sequences & menus

**URL:** `/connections/<id>/config` · Menus: `/connections/<id>/menus` · Reports: `/connections/<id>/reports` · Promote: `/pipelines`

**Purpose:** Day-2 company polish and navigation without leaving the app.

- **Company** — name, email, phone, address, ZIP, VAT, company registry  
- **Sequences** — create + edit prefix / padding / next number  
- **Mail templates** — create/list `mail.template`  
- **Activity types** — create/list `mail.activity.type`  
- **Translations CSV** — lang-scoped field labels + root menu names (`context lang=`)  
- **Menus & actions** — visual tree for `ir.ui.menu` + window actions (create, bind, reorder sequence, delete with confirm)  
- **Report layout lite** — create QWeb PDF reports, edit arch, pick paper format  
- **Multi-env promote** — sandbox → staging → prod pipeline with hop history (prod requires successful staging for the same zip sha256)  
- **Industry seed packs** — Bulk import lists car rental / library / clinic / field service / partners / products CSVs  

---

## 17. Draft projects

**URL:** `/connections/<id>/projects`

**Purpose:** Keep an **offline draft** of intended models/fields (ModuleSpec), then:

- **Diff vs live** — see what’s missing  
- **Apply** — create missing models/fields on live Odoo (confirm phrase)  
- **Delete** draft  

**v1 limit:** Apply focuses on **models & fields**. Views, menus, and full ACL from a draft are **not** the full story here — use Wizard / Designer / Access for those, or export a full module zip.

Create drafts from a **library** template or blank.

---

## 18. Export, sandbox, promote, uninstall

All of this lives on the **connection hub** (`/connections/<id>`), in the export / sandbox section.

### Download zip

Packages customizations into an installable module:

- Technical name (e.g. `acme_library`)  
- Display name  
- Install mode: **python** (full addon) vs **data** (metadata-oriented for some remotes)  
- Options for stock extensions / extend models / depends  
- **Reports:** custom QWeb PDFs for exported models (`x_*` models and `custom.*` report keys) go into `report/reports.xml`  

**Download zip** saves the file to your computer.

### Sandbox install

Runs the zip in a **disposable Odoo** (Docker sandbox). Watch job status / log tail. Cancel if needed.

**Why:** Catch install errors before touching production.

### Suggest depends

Helps pick Odoo modules your zip should depend on (e.g. `mail`, `contacts`).

### Promote

After a **successful sandbox validation** (within the UI’s validity window):

1. Open promote confirm  
2. Type **`I understand the risks`**  
3. Promote installs to the target connection  

Risks: live metadata change; uninstall may leave residual data.

### Uninstall promoted module

From the promoted list, uninstall with confirm. Understand that Odoo uninstall is not always a perfect rewind of business data.

---

## 19. Typical end-to-end journeys

### Journey A — “I want a Library app today” (live)

1. **Connect** your Odoo 19 database  
2. Open connection → **Wizard**  
3. Name it (e.g. Acme Library) → choose **Library** → confirm phrase  
4. Open **Odoo** → find the Library menu → create Categories, Authors, Books, Loans  
5. Optional: **Designer** on `x_lib_book` → add **Mark Available** header button + **Loans** smart button → Save (inherit) → Open in Odoo and click them  
6. Optional: **Automations** / **Reminders** / **Access** for polish  

### Journey B — “Customize an existing model’s screen”

1. Hub → **View designer**  
2. Enter model → **Load existing view**  
3. Rearrange groups, set required/invisible, add buttons  
4. **Save** with **Inherit**  
5. **Open in Odoo** to verify  

### Journey C — “Safe release with a zip”

1. Build via Wizard and/or Builder/Designer on a **dev** connection **or** export Library zip from Wizard  
2. Hub → **Sandbox install** until green  
3. **Promote** to the intended connection with confirm  
4. Verify in Odoo; keep the zip as a versioned artifact  

### Journey D — “Automation without a button”

1. **Automations** → model + trigger + filter  
2. Choose Update field / Activity / Create record / Mail  
3. Activate and test with a sample record in Odoo  

### Journey E — “Button that updates status”

1. Designer → form → **+ Header button** → **Update field**  
2. Pick status field → choose allowed value (e.g. Available)  
3. Create & bind → Save → Open in Odoo → click **Mark Available**  

---

## 20. What lives in this app vs what lives in Odoo

| In **Odoo Custom** (this web app) | In **Odoo** |
|-----------------------------------|-------------|
| Connection list & encrypted credentials | Actual business data (books, loans, …) |
| Snapshots for undo of definitions | Menus users click every day |
| Draft projects | Installed modules |
| Export zips & promote history metadata | Forms, lists, kanban users see |
| API keys / audit for the app API | Automations that fire on records |

**Rule of thumb:** Customize here; **operate the business in Odoo**.

---

## 21. Warnings, confirmations & safety

### Always require the phrase `I understand the risks`

Examples:

- Wizard scaffold onto live Odoo  
- Create field from Designer (and smart-button computed counts)  
- Automations: live Python; delete/deactivate where gated  
- Reminders create  
- Draft **Apply**  
- Builder delete model/field  
- Access delete ACL/rule  
- Promote / uninstall module  
- Delete connection  

### Prefer these safe habits

| Prefer | Avoid |
|--------|--------|
| Inherit view saves | Overwriting primary views casually |
| Sandbox then promote | Installing untested zips on production |
| Open in Odoo to verify | Trusting iframe preview alone |
| Dev/test database first | First experiments on production |
| One stable header inherit for buttons | Many stacked test inherits (duplicate buttons) |

### What rollback can and cannot do

| Usually restorable via snapshot/undo | Often **not** fully restorable |
|--------------------------------------|--------------------------------|
| View XML | Dropped columns / deleted records’ data |
| Automation definitions | Side effects already emailed / written |
| Some server action definitions | Business process outcomes |

The UI tries to be honest when something is irreversible.

---

## 22. Troubleshooting

| Symptom | What to try |
|---------|-------------|
| Web page won’t load | Confirm web app on port **3000** |
| “Failed to fetch” / API errors | Confirm API on **8000**; check **API settings** if auth is on |
| Connection verify fails | Odoo up? Correct URL, **database name**, user/password? |
| Wizard succeeded but no menu in Odoo | You may be in **Apps catalog** — go to home/menus; hard refresh; clear `webclient_menus` cache (see Wizard section) |
| Designer iframe blank | Expected sometimes — use **Open in Odoo** |
| Button does nothing | Confirm you **Saved** the view; open form of a **saved** record; check action binding in Designer |
| Two identical header buttons | Duplicate inherits — remove extras; keep one `…studio.header_actions` / designer inherit (ask a technical helper if needed) |
| Activity button errors | Model may need chatter/activities enabled (Builder mail option / mixins) |
| Status update fails | Use a **real** selection value (Library book status is `available` / `loaned` / `lost`, not “borrowed”) |
| Confirm always rejected | Phrase must match **exactly**: `I understand the risks` |
| Promote blocked | Need a recent **successful sandbox** validation for that zip |

---

## 23. Glossary

| Term | Plain meaning |
|------|----------------|
| **Model** | A type of record (Book, Loan, Contact) |
| **Field** | A column / property on a model |
| **View** | A screen layout (form, list, search, kanban) |
| **Form** | Single-record page |
| **List** | Table of records |
| **Kanban** | Columns of cards |
| **Menu** | Entry in Odoo’s navigation |
| **Server action** | Automated action Odoo can run (update field, email, …) |
| **Window action** | Opens a list/form of records (often behind menus & smart buttons) |
| **Smart button** | Stat-style button on a form (often with a count) |
| **Statusbar** | Chevron stages at the top of a form |
| **Automation** | Rule: when X happens, do Y |
| **ACL** | Access Control List — group permissions on a model |
| **Record rule** | Domain filter limiting which records a group sees |
| **Inherit view** | Extension layer on top of an existing view |
| **Module / zip** | Installable Odoo addon package |
| **Sandbox** | Throwaway Odoo for testing installs |
| **Promote** | Install validated zip onto a real connection |
| **Snapshot** | Saved definition for undo |
| **Domain** | Filter expression (field, operator, value) |
| **`x_` prefix** | Naming convention for custom models/fields |

---

## Quick reference — where to click

| I want to… | Go to |
|------------|--------|
| Add my Odoo database | **Connect** |
| Create Library / CRM / Inventory starter | **Wizard** |
| Add a new business object or column | **Builder** |
| Change how a form looks / add buttons | **View Designer** |
| Run logic when records change | **Automations** |
| Restrict who sees data | **Access** (matrix) |
| Email due/overdue reminders | **Reminders** |
| Bulk CSV/XLSX load | **Bulk import** |
| Multi-step destructive RPC | **Power Ops** |
| Undo metadata snapshots | **Change journal** |
| Company / sequences / menus | **Settings** |
| Keep an offline draft | **Drafts** |
| Test zip safely then install | Hub → **Sandbox** → **Promote** |
| See the real result | **Open in Odoo** (from Designer) or log into Odoo directly |

---

*Document version: aligned with the Odoo Custom web app for Odoo Community 19+18+17 GA (16 experimental; Designer Phase 2 features included). For local operator checklists and technical UAT steps, see also `docs/LOCAL-UAT.md` and `skills/library-app.md`.*
