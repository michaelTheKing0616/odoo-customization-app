# Studio parity by Odoo major (M4)

> Clean-room only — public docs + our capability registry. Never Studio Enterprise source.
> Status: **M4** companion to `MULTI_VERSION_ODOO_PLAN.md`. Support floor = **16**.
> GA majors: **17 + 18 + 19**. Experimental: **16** (no `update_path`).

## How to read this matrix

| Symbol | Meaning |
|--------|---------|
| ✅ | Supported on this major (capability enabled + smoke-proven or adapter-ready) |
| ⚠️ | Supported with caveats (see notes) |
| ❌ | Not claimed — UI greys out / API `capabilities.require` refuses |
| — | Not applicable / out of product scope |

Enterprise editions: **warn-only**. Same public-ORM capabilities as Community for that major;
Studio-only features stay ❌. See MEMORY lock *Enterprise warn-only*.

## Product features × major

| Feature | Cap id | 16 | 17 | 18 | 19 | Notes |
|---------|--------|----|----|----|----|-------|
| New `x_` model + default form/list/search | — | ✅ | ✅ | ✅ | ✅ | ≤17 store list as `tree` |
| New field (`ir.model.fields`) | — | ✅ | ✅ | ✅ | ✅ | 16: no `currency_field` column |
| Place field on view (inherit inject) | `view_inject_inherit` | ✅ | ✅ | ✅ | ✅ | Designer Create+inject |
| View inject mutate (overwrite) | `view_inject_mutate` | ✅ | ✅ | ✅ | ✅ | Confirm + snapshot |
| Smart buttons (`button_box` inherit) | `smart_button_inherit_box` | ✅ | ✅ | ✅ | ✅ | Designer gated |
| Header button → object_write | `object_write_update_path` | ❌ | ✅ | ✅ | ✅ | 16: no `update_path` claim |
| Related write (dotted path) | `related_write_dotted_path` | ❌ | ✅ | ✅ | ✅ | Automations gated |
| Create record (object_create) | `object_create_crud_model` | ✅ | ✅ | ✅ | ✅ | |
| Safe automation triggers | `base_automation_safe_triggers` | ✅ | ✅ | ✅ | ✅ | |
| List as `type=list` | `list_as_list_type` | ❌ | ❌ | ✅ | ✅ | ≤17: tree-first |
| List↔tree fallbacks | `list_tree_fallback` | ✅ | ✅ | ✅ | ✅ | |
| Menus / QWeb reports | — | ✅ | ✅ | ✅ | ✅ | Smoke-proven 16–19 (`test_integration_odoo1{6,7,8,9}`) |
| Module zip export | — | ✅ | ✅ | ✅ | ✅ | **One zip / connection major** (`{n}.0.1.0.0`) |
| Sandbox validate | — | ✅ | ✅ | ✅ | ✅ | Ephemeral `odoo:{n}` on `:18069` |
| Power Ops (generic archive/unlink) | tag:`generic` | ✅ | ✅ | ✅ | ✅ | Live dry-run smoke 16–19 |
| Power Ops accounting | tag:`accounting` | ⚠️ | ⚠️ | ✅ | ✅ | Needs `account`; 16/17 live dry-run when installed (still ⚠️ — not full 18/19 recipe matrix) |
| Live Python `state=code` | — | — | — | — | — | Option A only (module→sandbox→promote) |
| Studio OWL / `web_studio` | — | ❌ | ❌ | ❌ | ❌ | Never |

## Studio-parity checklist (product, not per-major)

See `skills/studio-parity.md` v1 checklist. Gaps that remain **product-wide** (all majors):

| Gap | Status |
|-----|--------|
| Property fields | Out of scope v1 |
| Full kanban card designer polish | ✅ Card preview + ordered fields + group-by chip + ↑↓ reorder; parse→UI→save inherit round-trip. Label show/hide (`nolabel`) not in kanban arch helpers — skipped. |
| In-Odoo OWL editor feel | External app + Open-in-Odoo |
| Enterprise Studio UI clone | Explicitly never |

## Power Ops recipe tags

Recipes expose `tags` + `min_major` + `requires_modules` via `/power-ops/recipes`.

| Tag | Meaning |
|-----|---------|
| `accounting` | Needs `account` (and usually `account.move`) |
| `mail` | Needs `mail` |
| `generic` | Any model with domain |
| `users` | `res.users` — high blast radius |
| `destructive` | Permanent or hard-to-reverse |
| `archive` | Soft hide / restore |
| `purge` | Multi-step delete after draft reset |

Install `account` for accounting Power Ops gates:

| Major | Port / project | Script |
|-------|----------------|--------|
| 18 (GA) | `:8070` / `odoo18` | `./docker/ensure-account-18.sh` |
| 17 (GA) | `:8071` / `odoo17` | `./docker/ensure-account-17.sh` |
| 16 (experimental) | `:8072` / `odoo16` | `./docker/ensure-account-16.sh` |

**Honest 16/17 accounting status:** generic archive/unlink dry-runs are smoke-proven.
Accounting recipes (`purge_journal_entries`, etc.) are RPC-available once `account` is
installed (same public ORM as 18/19) but stay **⚠️** — local gates only dry-run one
accounting recipe after `ensure-account-1{6,7}.sh`; they are not claimed as a full
multi-recipe Power Ops matrix green like 18/19. Do not treat 16 as GA.

## Decision locks (M4)

1. **Enterprise:** warn-only — connect allowed; message + UI banner; same capability set as Community for that major; never claim Studio features.
2. **Support floor:** 16 (unchanged).
3. **Module export:** one zip per connection major (not multi-manifest). See MEMORY.
4. **Online SaaS / Enterprise packaging:** Enterprise = **warn-only** (connect allowed; probe message + Designer banners; same public-ORM caps as Community for that major; never Studio). Online SaaS: effective major **follows the host** — capability set unchanged (public ORM only); “follow-host” marketing/UI wording is **packaging copy only**, not a separate tier. **Power Ops** stays **RPC-first** on Online and Enterprise (UI limits ≠ API limits). Operator narrative: `docs/USER-GUIDE.md` § Odoo Online / Enterprise.

---

*Updated 2026-07-28 — Power Ops live dry-run notes for 16/17 + ensure-account scripts; 16 remains experimental.*
