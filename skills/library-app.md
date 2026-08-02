# Library app — operator guide

> Reference vertical for the No-Code Odoo Customization Platform (Community **19**).
> Stay on public ORM/RPC + portable module zip. Never Enterprise Studio source.

## What you get

Scaffold / zip creates four custom models:

| Model | Role |
|-------|------|
| `x_lib_category` | Categories |
| `x_lib_author` | Authors (create from Book form or Authors menu) |
| `x_lib_book` | Catalog (ISBN, barcode widget, status, author, fine rate, O2M loans) |
| `x_lib_loan` | Circulation (member, dates, returned, fine stubs, kanban) |

Portable zip (`library_module_spec`) also ships:

- Root menu **Library** → **Books**, **Authors**, **Loans**, **Active Loans**, **Categories**
- Labeled form groups (Identity / Catalog / Circulation on Books)
- Active Loans act_window domain `[('x_returned','=',False)]` (simpler than `context_today` overdue)
- Loans action `list,form,kanban,pivot,graph`; list `decoration-danger` for open loans
- Chatter mixins on Book + Loan; **overdue + due-soon** mail templates + daily cron; Option A fine automation
- QWeb **Loan Receipt** PDF report (Print menu)
- Books-by-barcode window action
- Depends: `base`, `contacts`, `mail` (+ `base_automation` when fines automation included)
- Optional **multi-company**: `company_id` + company record rules

## Path A — Wizard (live metadata)

1. Open connection → **Wizard** (`/connections/{id}/wizard`).
2. Set display name; optionally check **Multi-company aware** (Library only).
3. Pick **Library** → confirm phrase `I understand the risks`.
4. Result lists models → open **Builder** / **Designer** per model.
5. Connection page shows a **Library** stats strip (books / loans / active / overdue) when `x_lib_book` exists.
6. Optional: **Export library zip** (fines + reminders + multi-company flags) without writing to Odoo.

Live multi-company uses `x_company_id` (RPC custom-field naming) + matching `ir.rule` domains. Portable zip uses standard `company_id`.

## Path B — Designer refine

1. **Builder**: add/adjust fields. For many2one, set **On delete** (`restrict` / `cascade` / `set null`). Required M2O cannot use `set null` on Odoo 19.
2. **Designer**: form/list/search/kanban arches; prefer inherit injects.
3. **Access**: tighten ACL / record rules if non-admin users need the app.
4. **Automations**: safe update/activity only unless Option A Python module path.

## Path C — Sandbox → promote

1. Export portable zip from wizard, or:

   ```bash
   PYTHONPATH=packages/module-generator/src python3 -c "
   from pathlib import Path
   from module_generator import build_module_zip, library_module_spec
   Path('library_mgmt.zip').write_bytes(
       build_module_zip(library_module_spec(multi_company=False))
   )
   "
   ```

2. Sandbox gate (contacts + mail preloaded):

   ```bash
   ./docker/run-sandbox-library-gate.sh
   # SANDBOX_EXTRA_MODULES defaults to contacts,mail
   ```

3. Promote only after sandbox validation (`validation_id` / matching zip sha) + confirm phrase.
4. Local Docker: filesystem install into `/mnt/extra-addons`. Remote: `install_mode=data` only (no Python / cron / fines code).

## UAT checklist script

```bash
./docker/run-library-uat.sh
# Optional: LIBRARY_MULTI_COMPANY=1 ./docker/run-library-uat.sh

# Full functional UAT on sandbox (install → RPC checks → tear down)
./docker/run-library-functional-uat.sh

# Install-only gate
./docker/run-sandbox-library-gate.sh
```

Prints PASS/FAIL for models, fields, menus in zip; functional script proves chatter, fines, barcode, mail templates/cron, QWeb report.

CI: `.github/workflows/odoo-sandbox.yml` → workflow_dispatch gate **`library`** runs UAT then sandbox install.

## Stats API

`GET /api/connections/{id}/library/stats` — `search_count` for books, loans, active (`x_returned=False`), overdue (active + `x_due_date` before today). Returns `available: false` if `x_lib_book` missing.

## Full-scale UAT (§8 plan)

**Automated exit criterion met 2026-07-27** — see `docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md` §8.

**Operator local checklist:** [docs/LOCAL-UAT.md](../docs/LOCAL-UAT.md) (stack up → wizard → Designer → sandbox scripts → promote).

Optional human confidence pass on a clean connection:

- [ ] Wizard scaffold &lt; 2 minutes in the web UI
- [ ] Click kanban / Print → Loan Receipt in Odoo
- [ ] Promote to a non-sandbox target and uninstall residuals

## Related skills

- `skills/module-interop.md` — depends / export / promote
- `skills/advanced-actions.md` — confirm phrases, Option A Python
- `skills/odoo-rpc-gate.md` — verify claims on `odoo:19`
- `skills/studio-parity.md` — clean-room parity only
