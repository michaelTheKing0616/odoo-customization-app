# Feature Operator & Investor Demo Guide

**Audience:** operators, consultants, founders preparing demos.  
**Product:** No-Code Odoo Customization Platform (Odoo Custom) — Studio-like customization for **Odoo Community 17–19** via public ORM/RPC (not Enterprise Studio).  
**Local URLs (typical):** Web `http://127.0.0.1:3002` · API `http://127.0.0.1:8001` · Odoo sandbox `http://127.0.0.1:8069`

**Confirm phrase (when prompted):**

```text
I understand the risks
```

**Hard rules to say in every investor demo**
- Changes target **metadata** (fields, views, menus, automations) or **installable modules** — never reverse-engineered Studio.
- **Sandbox before promote.** Job Autopilot refuses `write_mode=production`.
- **ModuleSpec completeness 10.0 ≠ go-live.** Side-by-side **Certification** (Quality / Evidence / Risk → Reject | ReviewRequired | Production | Gold) is the ship bar. Option A needs sandbox smoke; promote stays human even at Gold.
- **Job Autopilot scorecard ≠ ModuleSpec 10.0.** Implementation-job done-bar is separate.
- **Model ≠ module.** `account` is a module; invoices live on model `account.move`.

---

## Table of contents

1. [Mental model](#1-mental-model)
2. [View Designer](#2-view-designer) — stock + existing custom forms ([Field properties](#field-properties-panel))
3. [Models & Fields](#3-models--fields)
4. [Website](#4-website)
5. [Automations](#5-automations)
6. [Approvals](#6-approvals)
7. [Reports](#7-reports)
8. [Code Studio](#8-code-studio)
9. [Draft Studio](#9-draft-studio)
10. [Job Autopilot](#10-job-autopilot)
11. [ModuleSpec](#11-modulespec)
12. [Projects](#12-projects)
13. [Investor demo scripts](#13-investor-demo-scripts)
14. [Quick reference — model technical names](#14-quick-reference--model-technical-names)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Mental model

| Grain | Typical tool | Writes to Odoo how? | Done when |
|---|---|---|---|
| Field / form polish | Models & Fields + View Designer | Live Apply (RPC) | Field on form in Odoo |
| Feature under a stock app | Draft Studio `feature_slice` + Apply | Live Apply | Host form + companion/activity |
| Full residual app | Draft Studio `full_app` / packs | Apply + optional zip | Menus + models + smoke |
| PDF / QR / pay / Python / OWL | Draft Studio Option A + Code Studio | **Module → sandbox → promote** | Sandbox smoke + human promote |

**Nav groups (connection shell)**  
- **Overview** — health, connection home  
- **Build** — Models & Fields, View Designer, Menus, Website, Automations, Approvals, Reports, Code Studio, Access  
- **AI Studio** — Draft Studio, Job Autopilot, ModuleSpec, Projects, Odoo Expert  

---

## 2. View Designer

**Path:** Connection → **Build → View Designer** (`/connections/{id}/designer`)

### What it is
A visual editor for Odoo **views** (form, list/search, kanban, calendar, graph, pivot, …). It loads the **existing arch** from the connected database, lets you place fields/buttons/groups/tabs, and **Applies** an inherit (or updates) via RPC. Preview is structural; **Open in Odoo** is authoritative.

### What it is not
- Not an Apps Store browser (do not type module names like `account`, `sale`, `website`).
- Not the invoice **PDF** designer (use Reports / Draft Studio Option A).
- Not a place to invent stock field names or rewrite Accounting core logic.

### How to add fields to a stock Odoo model

1. Ensure the app is installed on the connected DB (e.g. Invoicing / Accounting).
2. Open **View Designer**.
3. Enter the **technical model name** (see [§14](#14-quick-reference--model-technical-names)):
   - Invoices → `account.move`  
   - **Wrong:** `account`, `Invoice`, `Invoicing`
4. Set view type to **form**.
5. Click **Load existing view** so **Form layout (primary)** fills with the real invoice structure (groups, notebooks, buttons). The optional Odoo-style preview can stay collapsed.
6. From the **field list** (left of Form layout):
   - Pick an existing `x_*` field, **or**
   - Create a new custom field (`x_…`) with confirm phrase when required.
7. Drop the field into a group (or **+ Group**, then drag — the page auto-scrolls near the viewport edge).
8. **Save** (default **Inherit**) → confirm phrase if prompted.  
   On stock models this writes an **additive** inherit (new `x_*` groups/fields only) — not a full form replace.  
   If you **created** the field with inject-into-views, Save still rewrites `{model}.designer.form` from your Form layout and removes the redundant `{model}.custom.x_*.form` inject so the group label wins.
9. In Odoo: open a customer **Invoice** or vendor **Bill** → hard-refresh → verify the field.

**Bills vs Invoices:** Both use `account.move`. Odoo’s menu label is **Bills** for vendor bills (`in_invoice`) and **Invoices** for customer invoices (`out_invoice`). That naming is correct.

**If you already see duplicate Send/Print/Pay or Other Info:** an older Designer save replaced the whole form. Restart API → View Designer → `account.move` → **Fix duplicate chrome** (keeps TEST GROUP when possible). Or **Unlink designer inherit** (confirm phrase). Or in Odoo Technical → Views delete `account.move.designer.form`, then re-save Inherit if you still need custom fields.

### How to unlink a view

**In-app:** View Designer → stock model → **Unlink designer inherit** → type `I understand the risks`. Prefer **Fix duplicate chrome** first if you want to keep custom groups.

**In Odoo (developer mode):** Settings → Technical → User Interface → Views → search `account.move.designer.form` → open → Action → Delete. Do not delete the stock primary move form. Hard-refresh the Bill.

### How to add fields to an existing custom model

1. Model must already exist (`x_matter`, `x_booking`, …) — from Models & Fields, a prior Apply, or an installed module.
2. Enter that model’s technical name (e.g. `x_matter`).
3. Load **form** view → add fields → Apply.
4. If there is no form yet, Designer may seed from fields; create/save a form view, then open the app menu in Odoo.

### Expected vs unexpected layout

| Input | What you should see |
|---|---|
| `account.move` + Load form | Invoice-like chrome: statusbar, Send/Print/Pay, sheet, totals area |
| `account` | Wrong — module name; blank/seeded/error — **not** the invoice form |
| `sale.order` + Load form | Quotation/order form structure |
| `x_matter` after pack Apply | Your residual matter form |

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| D1 | Stock invoice field | Load `account.move` form → add `x_demo_note` (char) → Apply | Field visible on invoice form; `fields_get` has `x_demo_note` |
| D2 | Layout group | Add group “Demo” with 2 fields near header | Group string visible; no React console key errors on Send/Print/Pay |
| D3 | List view | Switch to list → load → add column → Apply | List shows column in Odoo |
| D4 | Custom model | Create `x_demo_card` in Models & Fields → Designer form → Apply | Menu/action opens form with fields |
| D5 | Rollback | After Apply, use snapshot rollback if offered | Prior arch restored |
| D6 | Wrong name | Type `account` → observe failure/seed | Operator learns to use `account.move` |
| D7 | Field properties | See [Field properties](#field-properties-panel) FP1–FP12 | Each property survives Save → Open in Odoo |

### Field properties panel

**Where:** View Designer → select a field on **Form layout (primary)** → right aside **Field properties** (`DesignerFieldInspector`).  
Do **not** rely on the collapsed Odoo-style preview’s simpler checkboxes — the aside is the full panel.

**What it changes:** View-layer attributes on the field node in the form/list arch (`string`, `required`, `readonly`, `invisible`, `widget`, `options`). After you edit, click **Save to Odoo** (Inherit on stock models), then **Open in Odoo** / hard-refresh.

**What it does not change:** Field **type**, selection keys, many2one relation, compute/ORM required — use **Models & Fields**. Python widgets / custom OWL → Option A / Code Studio.

#### Controls (full range)

| Control | Modes / values | What you get in Odoo |
|---------|----------------|----------------------|
| **Label** | Free text | `string="…"` on the field node (form label). Empty = use model field description. |
| **Required** | Off · Always · When… (domain) | Off = optional on this view. Always = `required="1"`. When… = conditional required (domain → Odoo 17+ expression). |
| **Readonly** | Off · Always · When… | Same pattern for `readonly`. |
| **Invisible** | Domain builder (AND rules) or **Edit raw** | Hides the field when the domain matches. Empty `[]` = always visible. |
| **Widget** | Curated list by field type, or **Advanced…** free name | e.g. `barcode`, `email`, `phone`, `url`, `radio`, `priority`, `many2many_tags`, `image`, `signature`, … |
| **Image size** | Only when widget = `image` | `options='{"size": [90,90]}'` (or 128 / 256). |

**Domain builder tips**

- Add rules: field name (technical, e.g. `state` or `x_status`) + operator (`=`, `!=`, `like`, `in`, …) + value.
- Values: plain text, numbers, `True`/`False`, or expressions like `user.id`.
- Use **Edit raw** for domains the simple AND UI cannot express.
- Required/Readonly **When…** uses the same domain builder under those toggles.

**Widget cheat sheet (curated)**

| Field type (`ttype`) | Common widgets |
|----------------------|----------------|
| `char` | email, phone, url, barcode |
| `integer` | priority |
| `float` | float_time, progressbar, percentage |
| `selection` | radio, priority, selection_badge |
| `many2one` | many2one_avatar, many2one_avatar_user |
| `many2many` | many2many_tags, many2many_checkboxes |
| `binary` | image, pdf_viewer, signature |
| `html` | html |

**Advanced…** accepts any widget name the instance supports; curated list is the safe default.

#### How to use (any operator)

1. Connection → **Build → View Designer**.
2. Model e.g. `account.move` or `x_matter` → **form** → **Load existing view**.
3. Put an `x_*` field on **Form layout** (create or drag).
4. **Click the field** so the aside shows its technical name.
5. Set Label / Required / Readonly / Invisible / Widget (and Image size if needed).
6. **Save to Odoo** (Inherit).
7. **Open in Odoo** → hard-refresh → verify behavior on a real record (draft vs posted, empty vs filled).

#### Comprehensive Field properties tests

| # | Goal | Setup | Actions | Pass criteria |
|---|------|-------|---------|---------------|
| FP1 | Label | Form + `x_demo_note` on canvas | Label → `SLA note` → Save | Odoo form shows **SLA note**; arch has `string="SLA note"` |
| FP2 | Required always | Same field | Required → **Always** → Save | Blank value blocks save / shows required in UI |
| FP3 | Required off | Field was Always | Required → **Off** → Save | Optional again |
| FP4 | Required when | Selection `x_status` + char | Required → **When…** → `x_status` `=` `done` → Save | Required only when status is done |
| FP5 | Readonly always | Any `x_*` | Readonly → **Always** → Save | Field not editable in Odoo |
| FP6 | Readonly when | Same | Readonly → **When…** → `state` `=` `posted` (or `x_status`=`done`) → Save | Editable in draft; locked when condition holds |
| FP7 | Invisible domain | Char field | Invisible → `x_status` `=` `draft` → Save | Field hidden in draft; visible otherwise |
| FP8 | Invisible clear | After FP7 | Clear rules / domain `[]` → Save | Always visible |
| FP9 | Widget barcode | `char` field | Widget → **Barcode** → Save | Barcode widget renders (scan UI / barcode chrome) |
| FP10 | Widget email/phone/url | Three chars or reuse | Set email / phone / url → Save | Matching input widgets in Odoo |
| FP11 | Selection radio / priority | `selection` field | Widget → radio or priority → Save | Radio buttons or stars/badges |
| FP12 | Image + size | `binary`/`image` field | Widget → Image → size 128×128 → Save | Image widget; options size in arch / sensible thumbnail |

**Automated gates (CI):** modifier helpers + arch emission — `apps/web` vitest `widgetCatalog.test.ts`; `packages/odoo-client` `test_field_attrs.py` + additive/widget arch tests. Manual FP1–FP12 against a live sandbox remain the done bar for UX.

### Investor one-liner
“We inherit Community forms the way a senior Odoo team would — additive `x_*`, no Enterprise Studio.”

---

## 3. Models & Fields

**Path:** **Build → Models & Fields** (`/builder`)

### What it is
Metadata builder for `ir.model` and `ir.model.fields`: create custom models, add fields (char, date, selection, M2O, monetary, …), widgets, and related helpers (invoicing connect panel, property fields where supported).

### How to use
1. Search/select a model (`account.move` or `x_…`).
2. Add field: name must be `x_…` for custom columns.
3. Choose type, string, required, selection keys, relation for M2O.
4. Save / Apply to the connected DB (confirm when prompted).
5. Optionally open **View Designer** to place the field on the form (creating a field alone may not put it on the UI).

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| M1 | Additive on invoice | Add `x_sla_due` date on `account.move` | Column exists; form may need Designer |
| M2 | New residual model | Create `x_asset_tag` with name + partner M2O | Model in Apps/menus after menu wiring |
| M3 | Selection | `x_priority` selection draft/open/done | Dropdown values in Odoo |
| M4 | Monetary | Amount + currency companion where required | No Fault on create |
| M5 | Tier-1 safety | Attempt stock field rename / O2M on tier-1 | Blocked or warned (PCM) |

### Investor one-liner
“Studio-class fields on Community Accounting — without forking Odoo.”

---

## 4. Website

**Path:** **Build → Website** (`/website`)  
**Prerequisite:** Odoo `website` module installed on that database.

### What it is
List and edit website page content via the platform (day-2 copy/structure), without claiming full Website Builder parity.

### How to use
1. Confirm Website is installed (nav unlocks; otherwise gating message).
2. Open Website → see page list.
3. Select a page → edit content → save.
4. Open the public URL on the same Odoo to verify.

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| W1 | Edit homepage snippet | Change a heading → save → browse site | Text updated |
| W2 | No website module | Connection without website | Clear gating / install guidance |
| W3 | Portal contrast | Mention portal pay URL is Draft Studio Option A, not Website editor | Story stays coherent |

### Investor one-liner
“Day-2 website edits on the same connection you use for ERP customization.”

---

## 5. Automations

**Path:** **Build → Automations** (`/automations`)

### What it is
`base.automation` authoring with **safe** triggers/actions suitable for live Apply (e.g. `object_write`, activities). **Python `state=code` is Option A** (module → sandbox → promote), not silent live code.

### How to use
1. Pick model (`sale.order`, `account.move`, `x_…`).
2. Choose trigger (on create / write / stage…).
3. Choose safe action (write field, schedule activity).
4. Apply → test by creating/updating a record in Odoo.
5. For Python computes: Draft Studio / Code Studio Option A path.

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| A1 | Activity on date | On `account.move` with `x_sla_due` → activity when due soon | Activity appears |
| A2 | Status write | Custom `x_status` on create → default `draft` | Value set without Python |
| A3 | Refuse live Python | Try code automation without Option A | Blocked / routed to module path |
| A4 | Cross-link Designer | Same model open in Designer + Automations | Shared model story |

### Investor one-liner
“Automate like Studio — dangerous code stays sandbox-gated.”

---

## 6. Approvals

**Path:** **Build → Approvals** (`/approvals`)

### What it is
Approval-oriented flows and gates for actions that need human sign-off (aligned with Odoo-style confirmations and platform confirm phrases).

### How to use
1. Open Approvals on the connection.
2. Configure or trigger an approval-style gate for a document/model.
3. Walk “request → approve/reject” in the UI and show the audit trail if present.
4. Tie the narrative to ERP risk: “we never hide confirms.”

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| P1 | Happy path | Submit → approve | State advances |
| P2 | Reject | Submit → reject | State blocked / returned |
| P3 | Confirm phrase | Destructive/advanced action | Requires `I understand the risks` |

### Investor one-liner
“Governance is productized — not a checkbox in a slide.”

---

## 7. Reports

**Path:** **Build → Reports** (`/reports`)

### What it is
Report layout lite: QWeb/PDF report surfaces, paper formats, design anchors/preview where exposed. Complements Draft Studio Option A scaffolds for invoice Pay now + QR.

### How to use
1. Open Reports for the connection.
2. Select or design against a report bound to a model (`account.move`).
3. Preview / adjust layout anchors.
4. For full Pay-now + QR inherit: prefer Draft Studio Option A zip → sandbox smoke, then promote.

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| R1 | Open invoice report tooling | Navigate Reports → invoice-related | UI loads without Fault |
| R2 | Contrast with Option A | Show Draft Studio PDF prompt scaffolds | Report XML + Python in ModuleSpec |
| R3 | Print after sandbox smoke | After Option A prove, Print invoice PDF | Pay now + QR present when stubs filled |

### Investor one-liner
“Documents and forms are both in scope — with an honest module path for PDF.”

---

## 8. Code Studio

**Path:** **Build → Code Studio** (`/code-studio`) · developer-oriented

### What it is
Author and lint `custom_code_blocks` (Python/XML), export installable zips, run sandbox install. This is the escape hatch for Option A (computes, QWeb inherits, controllers).

### How to use
1. Open a draft that already has Option A blocks (from Draft Studio), or author blocks here.
2. Run **lint** — syntax / import policy.
3. **Export sandbox** / prove Option A until install succeeds.
4. Human **promote** to another connection when ready (never Autopilot-to-prod).

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| C1 | Lint scaffold | Open QR/pay draft blocks → lint | `ok` for py/xml |
| C2 | Sandbox install | Export-sandbox or option-a-prove | Module installed on ephemeral sandbox |
| C3 | Relative import | `models/__init__.py` import extras | Allowed by lint |
| C4 | Forbidden import | `import os` in block | Lint flags |

### Investor one-liner
“When no-code ends, seniors still ship — through the same sandbox gate.”

---

## 9. Draft Studio

**Path:** **AI Studio → Draft Studio** (`/wizard`)

### What it is
Natural-language → ModuleSpec draft at three grains: **field_pack**, **feature_slice**, **full_app**, plus **Option A** when the ask is PDF/QR/pay/website/OWL/Python.

### How to use
1. Enter a prompt; optionally set connection, grain, host.
2. **Create draft** → review **Completeness** scorecard **and** **Certification** (tier + Q/E/R), done-bar, Option A callout. Never treat a lone 10/10 as shippable when Cert < Production.
3. **Apply** for live metadata (stubs/fields/views).
4. If Option A primary: score capped (~7) until **Sandbox install & smoke** → then `go_live_ready` + Certification can rise to Production/Gold (promote still human).
5. Open ModuleSpec / Designer / Odoo as needed.

### Prompt recipes

| Prompt | Expect |
|---|---|
| `Add SLA due date on invoices` | `account.move` field pack; live Apply; score can be high |
| `Add warranty dates on sale orders` | `sale.order` inherit fields |
| `Add dynamic QR codes or click-to-pay buttons directly on the PDF for Invoices` | Option A document extras; stubs + scaffolds; score ~7 until smoke |
| `Build a law firm management app` | Full app / pack floor + stock inherit |

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| DS1 | SLA live path | Draft → Apply → Odoo invoice | `x_sla_*` on form |
| DS2 | PDF honesty | QR/pay prompt | Grain label Option A; score ≤7; 3 Option A paths |
| DS3 | Sandbox smoke | Click Sandbox install & smoke | Score lifts; `go_live_ready` when RPC smoke ok |
| DS3b | Certification honesty | High completeness, Cert ≠ Production/Gold | UI shows Completeness + Cert; no “shippable 10” alone |
| DS4 | No junk fields | QR/pay draft JSON | No `x_dynamic` / `x_notes` padding |
| DS5 | Expert closer | On field pack, Expert closer muted | Copy says Apply, not full-app closer |
| DS6 | Snapshot restore | Save snapshot → restore | JSON replaced; does not re-run Expert |

### Investor one-liner
“Talk to the system at any size — and it refuses to lie about PDFs.”

---

## 10. Job Autopilot

**Path:** **AI Studio → Job Autopilot** (`/job`)

### What it is
Unattended **sandbox** delivery: brief (+ optional docs) → stock install/config → custom residual only → ingest → **RPC process smoke**. Refuses production write mode. Promote to another connection is human.

### How to use
1. Prefer a **local sandbox** connection (e.g. `127.0.0.1:8069`).
2. Paste a business brief (country, apps needed, residual).
3. Run Autopilot → poll until terminal.
4. Read implementation scorecard (stack / coverage / data / smoke) — separate from ModuleSpec 10.0.
5. Open smoke invoice / sale order deep links.
6. Promote only via explicit human flow.

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| J1 | Stock-only brief | “Sales + invoicing for a bakery in NG” | Stock apps; smoke quote→confirm→invoice |
| J2 | Residual | Brief needing a custom register | `x_*` residual + Confirm server action smoke |
| J3 | Refuse prod | Point at non-sandbox / production mode | Refused or strong gate |
| J4 | Dirty sandbox | Re-run on used DB | Warn reuse; don’t silent wipe |

### Investor one-liner
“Implementation autopilot on a disposable sandbox — books stay safe.”

---

## 11. ModuleSpec

**Path:** **AI Studio → ModuleSpec** (`/modulespec`)

### What it is
The JSON contract: models, views, menus, automations, `custom_code_blocks`, scorecard, live-apply contract. Apply UI, validate, export zip, walkthrough seed (confirm phrase).

### How to use
1. Open ModuleSpec with a draft from Draft Studio or paste JSON.
2. Review `_scorecard`, `_live_apply`, `_done_bar`, `_capability_gaps`.
3. **Apply** to connection (live metadata).
4. **Export** zip for sandbox/Code Studio.
5. Use walkthrough seed only with confirm on a safe DB.

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| MS1 | Apply field pack | Apply SLA draft | Fields + inherit view live |
| MS2 | Option A blocks present | QR/pay draft | Report XML + Python content non-empty |
| MS3 | Round-trip zip | Export → re-import if supported | Blocks preserved |
| MS4 | Validators | Break XML deliberately | Score/validators catch |

### Investor one-liner
“One spec from AI to Apply to installable module — auditable.”

---

## 12. Projects

**Path:** **AI Studio → Projects** (`/projects`)

### What it is
Work packaging across a connection: track customization initiatives (e.g. “Invoice SLA + PDF pay”) spanning Draft Studio, Designer, Autopilot, and ModuleSpec artifacts.

### How to use
1. Create a project with a clear outcome (“Go-live ready invoice SLA”).
2. Attach or reference drafts / ModuleSpecs as you work.
3. Use the project as the demo spine: “this is the customer engagement unit.”

### Comprehensive test scenarios

| # | Scenario | Steps | Pass criteria |
|---|---|---|---|
| PR1 | Create project | Name + description | Visible in list |
| PR2 | Link journey | Draft Studio → Apply → Designer polish under one project | Story is coherent for stakeholders |
| PR3 | Multi-grain | Field pack + Option A PDF under same project | Done-bars differ; no confusion |

### Investor one-liner
“Customer work is a project — not a chat transcript.”

---

## 13. Investor demo scripts

### Script A — 12 minutes (forms + honesty)

1. **Overview** — Community 19 sandbox connected.  
2. **Draft Studio** — “Add SLA due date on invoices” → Apply → Odoo invoice form.  
3. **View Designer** — `account.move` → polish group.  
4. **Draft Studio** — PDF/QR prompt → show **7.0 + Option A + Sandbox install & smoke**.  
5. Close: promote is human; score 10.0 after smoke ≠ silent prod install.

### Script B — 20 minutes (delivery)

1. Script A (compressed).  
2. **Job Autopilot** — short stock brief → process smoke.  
3. **ModuleSpec** — show JSON + zip.  
4. **Code Studio** — lint Option A blocks.  
5. **Projects** — wrap as “Acme Invoice Readiness”.

### Script C — Website + ops (if website installed)

1. Website page edit.  
2. Automations safe activity.  
3. Approvals confirm narrative.  
4. Reports contrast with Option A PDF.

---

## 14. Quick reference — model technical names

| Business object | Technical model | Module (install in Apps) |
|---|---|---|
| Customer invoice / bill | `account.move` | Accounting / Invoicing (`account`) |
| Sales order | `sale.order` | Sales (`sale`) |
| Purchase order | `purchase.order` | Purchase |
| Contact | `res.partner` | Contacts |
| Task | `project.task` | Project |
| Lead/opportunity | `crm.lead` | CRM |
| Employee | `hr.employee` | Employees |
| Delivery | `stock.picking` | Inventory |
| Custom residual | `x_*` | Your module / Apply |

---

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Designer layout “not invoice” | Typed `account` (module) | Use `account.move` + Load form |
| Apply 200 but form empty | PCM stripped tier-1 fields (old) / wrong view | Verify `fields_get`; additive `x_*` allowed; check inherit arch |
| Draft score 10.0 on PDF ask | Stale API / old draft | Hard-refresh; expect ~7 until sandbox smoke |
| Website nav locked | `website` not installed | Install in Odoo Apps |
| Autopilot on prod URL | Safety gate | Use local sandbox connection |
| Duplicate React key `Send`/`Print`/`Pay` | Header buttons keyed by label | Fixed: keys use stable button `id`s in FormCanvas |

---

## Related docs

- `docs/USER-GUIDE.md` — broader product tour  
- `docs/OPERATOR.md` — operator procedures  
- `docs/SAFETY.md` — confirmations & risk  
- `MEMORY.md` / `STATE.md` — current product decisions (Option A score cap, PCM additive `x_*`)

### Odoo Expert knowledge

Expert answers in-app how-tos from:
1. **Rule-based product guidance** (`apps/api/app/expert/product_guidance.py`) — always on for “how do I use View Designer / Draft Studio / …”
2. **RAG `source=project`** — ingested docs including this guide (`docs/OPERATOR-FEATURE-DEMO-GUIDE.md`, `USER-GUIDE.md`, …) via `python -m app.expert.ingest --version 19.0 --skip-odoo-docs` (or full ingest)

Expert does **not** read the live TypeScript/Python tree at ask time.

---

*Last updated: 2026-08-24 — includes Field properties panel (FP1–FP12), Option A done-bar / sandbox smoke, and View Designer model-vs-module guidance.*
