# Skill: Studio Parity Targets (clean-room only)

## When to use
Any UI/product session for fields, views, models, automations, export, or security —
before inventing UX from scratch. Read this so our external builder matches (and exceeds)
what users expect from Odoo Studio **capability**, without copying Studio source.

## Hard rule
- **Allowed:** public Odoo docs (`documentation/*/applications/studio*`), marketing feature
  lists, and clean-room OSS (`mahmoudegpro/odoo-studio-community`, `bf_studio_light`).
- **Forbidden:** Odoo Enterprise `web_studio` / Studio source, and any "Studio port"
  that retains Odoo copyright / OEEL lineage (e.g. `MNametissa/odoo_studio_community`).

## What Studio users expect (from public Odoo 19 docs)

### Entry & mental model
- Enter customization from the **context of an app/model** (not a blank admin screen).
- Clear exit ("Close") back to normal use.
- Separate **building a new app** vs **customizing an existing one**.

### Fields
- Add **new** fields (persisted `ir.model.fields` columns) and **existing** fields onto a view.
- ~15 technical types; Studio surfaces ~21 picker entries via widget variants.
- Core types we must support first: char, text, integer, float, monetary, boolean, date,
  datetime, html, selection, many2one, one2many, many2many, binary, related (read-only link).
- Properties tab: label, required, readonly, invisible (domain/conditional), help, default,
  widget, placeholder, and type-specific options (selection values, relation target, currency).
- Removing a field from a view ≠ deleting the column — make that distinction explicit in UI.
- Property fields (pseudo-fields scoped by parent) are a later phase; document as out-of-scope
  for v0.1 unless requested.

## Views (Designer production bar)
- Form: drag fields; groups; notebook/pages; **functional buttons** bound to
  `ir.actions.server` / `ir.actions.act_window` via `type="action"` + action id.
- Header buttons + smart button box (`oe_button_box` / `oe_stat_button`) for related
  window actions (`domain` with `active_id`); optional **computed count** badge
  (`widget=statinfo`) with advanced confirm.
- Statusbar field in header (`widget=statusbar` + optional `statusbar_visible`).
- Safe button actions: `object_write`, `next_activity`, `mail_post`, related windows.
  Python `type="object"` / `state=code` stay on Option A.
- List/tree: columns + decoration-danger/info/muted UI.
- Kanban: card fields + group-by.
- Search: fields + filters (DomainBuilder).
- Field invisible: DomainBuilder (domain string).
- XPath inherit power editor (preview + validate + save inherit arch).
- Load: round-trip parse (groups/notebooks/header/button_box/statusbar); flat fallback.
- Save: **inherit by default**; overwrite gated by confirm + snapshot.
- Preview: Open-in-Odoo (authoritative) + same-origin proxy iframe (banner + no-store + refresh).
- Create field from Designer palette (confirm phrase + inherit inject).
- Cross-link Designer ↔ Automations (shared model query).

### Models / apps
- New models use `x_` technical names.
- Default form + list (and often search) created with the model.
- Optional mail.thread / activities mixins as checkboxes (seen in clean-room OSS too).

### Automations
- Model + trigger + domain ("apply on") + action — DomainBuilder on filter.
- Triggers: on create, on update, on delete/archive, timed, value-change on field.
- Safe no-code: update fields, create record, **mail_post**, schedule activity.
- Form-bound twin of the same server actions lives in **Designer** (cross-linked).
- Advanced: live code (confirm); Option A Python module → sandbox → promote.
- **Never** expose unrestricted Python in the default no-code path (AGENTS.md).

### Security
- Record rules and access rights as first-class builders (Studio docs list this explicitly).

### Export
- Export customizations as an installable module zip (models/views/data/security).
- Import/export is parity with Studio; **sandbox-test-before-install** is our edge.

## Lessons from clean-room OSS (not source to copy)

### mahmoudegpro `studio_community` (Odoo 18, immature but structured)
- Wrapper models (`studio.model`, `studio.field`, `studio.view`) that provision real
  `ir.*` records — good pattern for **our metadata store** (projects → intended state → apply).
- Draft → active lifecycle before mutating live metadata.
- `x_[a-z0-9_]+` validation on model names.
- Export wizard: module / json / xml formats — we should ship module zip first.
- In-Odoo OWL editor proves native feel wins for in-instance tools; our external app must
  compensate with **live preview** (iframe to Odoo or faithful preview) and fast apply feedback.

### bf_studio_light
- Narrow excellence: add field → inject into form/list/search → survive `-u all`.
- Survival/integrity hooks matter — our apply pipeline should verify fields/views still exist
  after upgrade-like operations (sandbox gate).
- Locked models list concept: refuse destructive edits on sensitive core models.

## Our differentiators (must stay visible in product)
1. Works on **Community** (and any reachable instance) without Enterprise Custom tier.
2. **Multi-instance** dashboard — Studio is single-instance only.
3. **Sandbox validate → then apply/install** — Studio is live-immediate.
4. Versioned project history / one-click rollback of metadata snapshots.

## Premium UX bar (external app)
- Context-first: connect → pick instance → pick model/app → customize.
- Instant feedback: optimistic UI + clear apply/error states from RPC.
- Destructive actions: confirm + snapshot + show blast radius (records/views using field).
- Visual density: one job per screen; view designer is the only heavy canvas.
- Vision-verify every designer milestone (`skills/vision-verify-ui.md`).

## v1 parity checklist (gate for "Studio-class")
- [x] New model (`x_`) + default form/list
- [x] New field on existing + custom models (core types above)
- [x] Place field on form + list; set required/readonly/invisible
- [x] Basic form layout: groups + notebook pages
- [x] Form buttons bound to real actions (update / activity / mail / related / smart)
- [x] Statusbar + smart button counts (computed field, confirmed)
- [x] List decorations + DomainBuilder + xpath inherit editor
- [x] Automation: create/write trigger → update field, activity, record, mail_post (no Python)
- [x] Access rights CSV-equivalent + simple record rule
- [x] Export installable module zip
- [x] Sandbox install of that zip before optional prod apply
- [x] Multi-connection switcher

## Sources
- https://www.odoo.com/documentation/19.0/applications/studio.html
- https://www.odoo.com/documentation/saas-19.2/applications/studio/fields.html
- Public automation docs under Studio / Productivity
- Clean-room repos listed in MEMORY.md (reference only)
- Per-major support matrix: `docs/STUDIO_PARITY_BY_MAJOR.md` (M4)
