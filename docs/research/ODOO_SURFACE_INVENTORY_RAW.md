# Odoo surface inventory (RAW) — Research R0

**Date:** 2026-07-28  
**Primary probe:** local Community `odoo:19` @ `http://127.0.0.1:8069` DB `odoo_dev`  
**Companion JSON:** [`odoo19_surface_probe.json`](odoo19_surface_probe.json)  
**Spot majors:** 18 @8070, 17 @8071, 16 @8072 — all responded to `common.version()`.

**Method:** XML-RPC `ir.model` + `ir.module.module` (installed) + `ir.ui.view` type counts + `fields_get` samples. Official Studio/editions docs consulted for outcome lists (not Studio source).

**Instance note:** Fresh CE smoke DB — mostly `base`+`web`+`mail` (+ automation/import). Many domain apps (`website`, `account`, `crm`, …) and all EE apps are **absent** until installed. Inventory still lists them as surfaces the master app must support *when present*.

---

## Sources processed

| Source | Used for |
|--------|----------|
| Studio 19 docs (models/features, fields, views, automations, export) | Taxonomy A1–A7 |
| odoo.com/page/editions | CE vs EE app matrix (G) |
| Online / Odoo.sh public docs | Hosting honesty (H) |
| External RPC + `ir.model` docs | Writability notes |
| Live Docker 19 probe | Presence on CE smoke |
| Live 18/17/16 version spot-check | Major availability |
| App routers (`apps/api/app/main.py`) | Diff vs our coverage |

---

## Probe summary (Odoo 19 CE smoke)

| Metric | Value |
|--------|-------|
| `server_version` | `19.0-20260723` |
| Total `ir.model` rows | 273 |
| Interesting prefixed models | 182 |
| Installed modules | 35 |
| Applications flagged | `mail` only |
| View types present | form 247, list 168, search 135, qweb 136, kanban 31, calendar 3, activity 1 |

**Missing on this DB (expected):** `website.*`, `uom.uom`, `account.*`, `crm.*`, `project.*`, `sign.*`, `documents.*`, `ir.property` (may be unloaded without company-dependent property usage / module).

---

## A. Studio-documented outcomes → public ORM mapping

### A1. Fourteen suggested features

| Feature | Public ORM recipe | On smoke 19 | Our app today |
|---------|-------------------|-------------|---------------|
| Contact details | m2o→`res.partner` + related phone/email; enable map view | partner exists | partial (fields/wizard; Map weak) |
| User assignment | m2o user + avatar widget + domain | users exist | partial |
| Date & Calendar | date field + calendar view | calendar views exist (3) | calendar designer thin/missing |
| Date range & Gantt | start/stop + gantt | gantt 0 views (needs web_gantt/EE or app) | module-gated |
| Pipeline stages | kanban + stages + priority/kanban_state | kanban OK | mostly done |
| Picture | binary/image field | OK | fields OK |
| Lines | one2many tab | OK | partial |
| Notes | html field | OK | OK |
| Monetary value | monetary + currency + graph/pivot | currency OK; graph/pivot 0 on smoke | monetary OK; graph/pivot designer missing |
| Company | m2o `res.company` | OK | settings OK |
| Custom Sorting | integer handle widget on list | OK | partial |
| Chatter | mail mixins on model create / module | mail installed | Option A / create flags |
| Archiving | `active` field + archive action | OK | partial |

### A2. Fields

| Item | Notes | Our app |
|------|-------|---------|
| Manual `ir.model.fields` types | RPC-creatable `state=manual` | OK |
| Widgets in arch | ~21 Studio combos | subset |
| Existing field → view | inject inherit | OK |
| Properties (required, domain, related, `currency_field`) | major-aware | mostly; currency live gap |
| Computed via RPC | Not via `ir.model.fields` — Option A | document honesty |
| AI fields | EE/host | honesty row |

### A3. Views (Studio categories)

| Type | On smoke | Our designer |
|------|----------|--------------|
| Form | yes | OK |
| Activity | yes (1) | missing |
| Search | yes | partial |
| Kanban | yes | OK |
| List | yes (`list` on 19) | OK (+ tree≤17) |
| Map | no | missing |
| Calendar | yes | missing/thin |
| Cohort | no | missing |
| Gantt | no | module-gated |
| Pivot | no | missing |
| Graph | no | missing |
| Inherit-only | policy | MEMORY OK |

### A4. Automations (`base.automation` + `ir.actions.server`)

Models present: `base.automation`, `ir.actions.server`.  
Triggers/actions from Studio docs must map to encoders; `update_path` fail-closed on 16.  
Our app: safe subset OK; webhook/code = confirm + Option A.

### A5–A7

| Surface | Present | Our app |
|---------|---------|---------|
| `ir.model.access` / `ir.rule` | yes | OK |
| `ir.actions.report` + QWeb | yes | OK |
| `report.paperformat` | yes | incomplete UI |
| Module zip export | n/a | OK |
| Online data-only install | policy | promote path / harden messages |

---

## B. Core metadata / UI

| Model | Smoke | Our coverage |
|-------|-------|--------------|
| `ir.model`, `ir.model.fields`, selection | yes | OK |
| `ir.model.constraint`, `ir.model.data` | yes | partial |
| `ir.default` | yes | thin |
| `ir.property` | absent this DB | when present |
| `ir.ui.view`, `ir.ui.menu` | yes | OK |
| `ir.actions.*` | yes | window/server/report; client/url thin |
| `ir.filters` | yes | thin |
| `ir.sequence` | yes | config OK |
| `ir.cron` | yes | thin |
| `ir.config_parameter` | yes | config_ops partial |
| `ir.attachment` | yes | thin |
| `ir.translation` | yes | CSV only (MEMORY: full UI deferred) |
| `ir.module.module` | yes | install/promote OK |
| `base_import*` | installed | data_import OK |

---

## C. Mail / Discuss

Present: `mail.template`, `mail.activity.type`, subtypes, `ir.mail_server`, digest, sms module installed.  
Our: templates/activities in Settings OK; cron/aliases thin; discuss channels = operational.

---

## D. Website / CMS

**Not installed** on smoke (`website.page` / `website.menu` missing).  
Still a mastery surface when `website` module installed — P1 backlog.

---

## E. Settings / master data

| Model | Smoke | Our app |
|-------|-------|---------|
| `res.company` | yes | OK |
| `res.currency` | yes | thin |
| `res.lang` | yes | CSV OK |
| UoM | no | playbook when `uom` installed |
| Fiscal/tax/journal | no (`account` uninstalled) | Power Ops needs account |
| `res.config.settings` | transient | config_ops partial |
| Payment / POS | no | module-gated |

---

## F. Domain app playbooks (module-gated)

All absent on smoke: CRM/Project/Sale/Stock/MRP/HR/Events/Mailing/Knowledge.  
Pattern: detect `ir.module.module` state=installed → enable playbook → grey-out else.

---

## G. Enterprise-installed only

Absent on CE: Studio/`web_studio`, Sign, Documents, Spreadsheet, VoIP, IoT, deep Payroll/OCR.  
Policy: warn on `+e`; consume public models if installed; never clone Studio.

---

## H. Hosting / ops

| Concern | Honesty |
|---------|---------|
| Online | Metadata + data XML OK; no custom Python modules |
| Odoo.sh | Git/filesystem Option A; staging branches |
| Self-host | Sandbox `:18069` → promote |
| API keys | App AUTH_MODE + Odoo API keys |
| Snapshots | Partial honesty (views/automations yes; columns no) |
| Power Ops | Recipes + min_major |
| Pipelines | matching-major sandbox |

---

## Diff vs our API routers (today)

Routers: auth, audit, jobs, connections, apps, ai, module_spec, introspection, builder, projects, reminders, views, actions, preview_proxy, automations, access, snapshots, export_sandbox, data_import, power_ops, config_ops, menus_builder, reports, environments.

**Gaps vs taxonomy:** calendar/graph/pivot/map/gantt/cohort designer; website builders; ir.property/default UI; paperformat UI; hosting_hint on probe; EE playbook grey-out; production Automations e2e; deeper live 18 CI.

---

## Evidence files

- Live probe JSON: `docs/research/odoo19_surface_probe.json`
- Studio docs URLs (public): applications/studio/* (19.0)
- Editions: https://www.odoo.com/page/editions
