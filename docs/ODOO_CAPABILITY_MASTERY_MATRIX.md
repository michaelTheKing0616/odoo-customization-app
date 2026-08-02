# Odoo capability mastery matrix

**Canonical tier × capability map.** Derived from [`research/ODOO_SURFACE_INVENTORY_RAW.md`](research/ODOO_SURFACE_INVENTORY_RAW.md) + live CE probe 2026-07-28.  
**Refreshed:** 2026-07-28 after MEMORY unlock — finish all prior deferred M2/M4/M5 gaps.  
**Product target:** customization + day-2 admin via public ORM/RPC + Option A (never Studio source).

**Legend**

| Symbol | Meaning |
|--------|---------|
| ✅ | Supported in our app (production path) |
| ⚠️ | Partial / honesty gap / module-gated UI incomplete |
| ❌ | Not in app yet (backlog) |
| OA | Option A only (module → sandbox → promote) |
| n/a | Hosting tier cannot do this |

**Columns:** CE self-host · EE self-host · Odoo.sh · Odoo Online · Our app

---

## A1. Studio model features

| Capability | CE | EE | sh | Online | App | Backlog |
|------------|----|----|----|--------|-----|---------|
| Contact details fields | ✅ | ✅ | ✅ | ✅ | ✅ | recipes + Map |
| User assignment | ✅ | ✅ | ✅ | ✅ | ✅ | recipes honesty |
| Date & Calendar view | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Date range & Gantt | ⚠️ apps | ✅ often | ✅ | ✅ plan | ✅ | module-gated Designer |
| Pipeline / Kanban | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Picture | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Lines (O2M) | ✅ | ✅ | ✅ | ✅ | ⚠️ | deep line editor polish |
| Notes (HTML) | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Monetary + Graph/Pivot | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Company field | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Custom Sorting handle | ✅ | ✅ | ✅ | ✅ | ✅ | list handle + default_order |
| Chatter | ✅ | ✅ | ✅ | ✅ | ✅/OA | — |
| Archiving (`active`) | ✅ | ✅ | ✅ | ✅ | ✅ | recipes + on_archive |

## A2. Fields

| Capability | CE | EE | sh | Online | App | Backlog |
|------------|----|----|----|--------|-----|---------|
| Manual field create | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Widget variants | ✅ | ✅ | ✅ | ✅ | ⚠️ | catalog open |
| Inject existing → view | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| related / currency_field | ✅ | ✅ | ✅ | ✅ | ✅ | live inject proven |
| Computed fields | OA | OA | OA | n/a Python | OA | honesty |
| AI fields | ❌ | ⚠️ | ⚠️ | ⚠️ | ❌ | honesty |

## A3. Views

| Type | CE | EE | sh | Online | App | Backlog |
|------|----|----|----|--------|-----|---------|
| Form | ✅ | ✅ | ✅ | ✅ | ✅ | Can Create/Edit/Delete/Duplicate |
| Activity | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Search | ✅ | ✅ | ✅ | ✅ | ✅ | group_by_filters |
| Kanban | ✅ | ✅ | ✅ | ✅ | ✅ | create/quick_create |
| List / tree | ✅ | ✅ | ✅ | ✅ | ✅ | multi_edit/default_order |
| Map | ⚠️ | ✅ | ✅ | ✅ | ✅ | res_partner gated |
| Calendar | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Cohort | ⚠️ | ✅ | ✅ | ✅ | ✅ | module-gated honesty |
| Gantt | ⚠️ | ✅ | ✅ | ✅ | ✅ | module-gated honesty |
| Pivot | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Graph | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Inherit-only | ✅ | ✅ | ✅ | ✅ | ✅ | — |

## A4. Automations

| Capability | CE | EE | sh | Online | App | Backlog |
|------------|----|----|----|--------|-----|---------|
| Values Updated | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Email Events | ✅ | ✅ | ✅ | ✅ | ✅ | on_message_* |
| Timing Conditions | ✅ | ✅ | ✅ | ✅ | ✅ | on_time* |
| Custom / External | ✅ | ✅ | ✅ | ⚠️ code | ✅ | on_webhook + confirm |
| Domains before/after | ✅ | ✅ | ✅ | ✅ | ✅ | filter + filter_pre |
| Update record / related | ✅ | ✅ | ✅ | ✅ | ✅† | — |
| Activity / email / SMS | ✅ | ✅ | ✅ | ✅ | ✅ | SMS confirm |
| Execute code | OA | OA | OA | n/a | OA | — |
| Webhook | ✅ | ✅ | ✅ | ⚠️ | ✅ | confirm phrase |
| Followers add/remove | ✅ | ✅ | ✅ | ✅ | ✅ | confirm |

† Fail-closed on Odoo 16 (`update_path`).

## A5–A7 Security / reports / export

| Capability | CE | EE | sh | Online | App | Backlog |
|------------|----|----|----|--------|-----|---------|
| Access rights | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Record rules | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| QWeb reports | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Paperformat | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Module export ZIP | ✅ | ✅ | ✅ | data-only | ✅ | — |
| Online Python install | n/a | n/a | ✅ | ❌ | refuse | M1 contract |

## B–E Admin surfaces

| Capability | CE | EE | sh | Online | App | Backlog |
|------------|----|----|----|--------|-----|---------|
| Menus / window actions | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Sequences | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `ir.config_parameter` | ✅ | ✅ | ✅ | ✅ | ✅ | snapshots |
| `ir.default` / `ir.property` | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `ir.cron` | ✅ | ✅ | ✅ | ⚠️ | ✅ | confirm |
| Mail templates / activities | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Website pages/menus | ✅ | ✅ | ✅ | ✅ | ✅ | available:false |
| Company / currency / lang | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| UoM / fiscal (if account) | ✅ | ✅ | ✅ | ✅ | ✅ | available:false |

## F–G Module / EE playbooks

| Capability | CE | EE | sh | Online | App | Backlog |
|------------|----|----|----|--------|-----|---------|
| Detect installed modules | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| CRM/Project/Sale playbooks | ✅ | ✅ | ✅ | ✅ | ✅ | domain-playbooks |
| Sign / Documents RPC | ❌ | ✅ | ✅ | ✅ | ✅ | grey-out |
| Spreadsheet / VoIP / IoT / Payroll detect | ❌ | ✅ | ✅ | ✅ | ✅ | grey-out |
| Studio presence warn | n/a | ✅ | ✅ | ✅ | ✅ | warn_only |
| Never Studio source | — | — | — | — | ✅ | — |
| EE **live** image RPC | — | ✅ | ✅ | ✅ | ❌ | needs EE Docker |

## H. Hosting / ops

| Capability | CE | EE | sh | Online | App | Backlog |
|------------|----|----|----|--------|-----|---------|
| Hosting probe hint | — | — | — | — | ✅ | — |
| Matching-major sandbox | ✅ | ✅ | ✅ | n/a | ✅ | — |
| Power Ops recipes | ✅ | ✅ | ✅ | ✅ RPC | ✅ | requires_modules |
| Snapshots / rollback honesty | ✅ | ✅ | ✅ | ✅ | ✅ | broad mutate coverage |
| Pipelines sandbox→prod | ✅ | ✅ | ✅ | data | ✅ | — |
| App API key auth | — | — | — | — | ✅ off default | DEPLOY.md |

## Forever ❌

Studio OWL clone · `web_studio` source · default live `state=code` · full column rollback fiction · majors ≤15/20+ without MEMORY · multi-manifest zips · “full Odoo replacement”.

---

## Coverage map (tests)

| Area | Tests |
|------|-------|
| Caps / edition / hosting | `capabilities.test.ts`, `test_capabilities_m1.py`, `test_hosting_m1.py` |
| Encoders multi-major | `test_automation_encoders_multimajor.py` |
| View adapters + reporting | `test_views_adapters_multimajor.py`, `test_view_arch_reporting.py` |
| Feature recipes | `test_studio_feature_recipes_m2.py` |
| Config M3 | `test_config_ops_m3.py` |
| Domain playbooks | `test_domain_playbooks_m3.py` |
| Pipeline / packs | `test_pipeline_major_m4.py`, `test_power_ops_packs_m4.py` |
| Snapshots M4 | `test_snapshots_m4_remainders.py` |
| EE playbooks | `test_ee_playbooks_m5.py` |
| Battery how-to | [`TEST_BATTERY_UPGRADE_MAP.md`](TEST_BATTERY_UPGRADE_MAP.md) |
