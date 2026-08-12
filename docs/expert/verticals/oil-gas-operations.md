# Vertical playbook: Oil & Gas / Energy Operations

Expert vertical guidance for Odoo **Community** internal operations (assets, maintenance,
projects, procurement, HSE tracking). Keywords: oil and gas, oil & gas, petroleum, upstream,
midstream, downstream, energy, field operations, well, rig, pipeline, refinery, HSE, CMMS,
work order, asset integrity.

Vertical id: `oil_gas_operations`. **Not** real estate, hospitality, or generic CRM/website
stacks unless you explicitly add a public portal later.

## Summary

Oil & gas operators use Odoo Community for **internal** workflows: asset register, preventive
maintenance, field work orders, spare parts inventory, project/engineering jobs, vendor
procurement, and HR-linked crews. There is **no stock “Oil & Gas ERP” app** on Community —
compose **`maintenance`**, **`stock`**, **`purchase`**, **`project`**, **`fleet`**, **`hr`**, and
**`account`** with custom **`x_og_*`** models for wells, facilities, and operational tickets.

**Do not** default to `website`, `crm`, or `sale` for internal-only operations unless you also
run commercial customer-facing workflows.

## Stock Odoo apps — recommended install order

1. **`base`**, **`web`**, **`mail`** — platform.
2. **`contacts`** — operators, contractors, joint-venture partners as `res.partner` (link-only).
3. **`hr`** — field crews, shift rosters, department structure (optional **`hr_timesheet`** with project).
4. **`maintenance`** — equipment registry + preventive/breakdown maintenance requests (CMMS core).
5. **`stock`** + **`product`** — spare parts, consumables, min/max on field warehouses.
6. **`purchase`** — MRO procurement, vendor RFQ → PO linked to maintenance/project needs.
7. **`project`** — shutdowns, turnarounds, engineering jobs, capex projects with tasks/milestones.
8. **`fleet`** — field vehicles if you track them separately from fixed assets (optional).
9. **`account`** — vendor bills, cost centers, analytic accounting on projects/assets (link-only
   posting discipline; no ad-hoc `account.move` mutations from Expert automations).
10. **`mrp`** — only if you operate small-scale fabrication/assembly shops (usually skip at v1).

Add **`documents`-class features only via attachments/chatter** on Community — no Enterprise
Documents app.

## Typical custom models (`x_og_*`)

| Model | Purpose | Key links |
|-------|---------|-----------|
| `x_og_facility` | Site/plant/terminal/pipeline segment | `res.partner` operator, geo/region fields |
| `x_og_asset` | Wellhead, compressor, pipeline section, processing unit | `maintenance.equipment` or parallel register |
| `x_og_work_order` | Field job / intervention ticket | facility, asset, crew partner, dates, status |
| `x_og_permit` | PTW / safe-work permit stub | linked work order, validity dates |
| `x_og_hse_incident` | Near-miss / incident log | facility, severity, corrective actions |

Prefer **`maintenance.request`** + **`maintenance.equipment`** for CMMS when they fit; use
`x_og_*` when you need oilfield-specific fields (API well number, choke size, pipeline km, etc.).

## Path A — App Wizard / Builder (live metadata)

1. **Connect** your Odoo instance.
2. Scaffold **`x_og_facility`** and **`x_og_asset`** via **Models & Fields** (or Draft Studio
   prompt: “oil & gas field assets and maintenance tickets”).
3. Link **`maintenance`** equipment to assets; use **Project** for turnaround tasks.
4. **Sandbox-test** before production; snapshot before bulk field/view changes.

## Path B — Module export

Export an installable module with depends:
`base`, `contacts`, `mail`, `maintenance`, `stock`, `purchase`, `project`, `account`
(+ `fleet`, `hr` as needed). Run `./docker/run-sandbox-library-gate.sh` pattern on your own
sandbox script before promote.

## Workflows

### Asset integrity & CMMS

Register critical equipment in **`maintenance.equipment`**. Preventive schedules for
inspections; **`maintenance.request`** for breakdowns. Custom `x_og_work_order` when you need
joint-venture partners or permit linkage.

### MRO inventory

**`stock`** locations per site; reorder rules on high-turn spare parts. **`purchase`** RFQ from
maintenance/project demand — do not auto-post vendor bills without operator confirmation.

### Projects & turnarounds

**`project.project`** for shutdown/TA; tasks for discipline crews; optional timesheets. Analytic
accounts for cost tracking (verify on your chart).

### HSE

Lightweight **`x_og_hse_incident`** + mail activity follow-ups at v1; avoid claiming full EHS
suite parity with specialized HSE SaaS.

## Community vs Enterprise honesty

No Odoo Enterprise **industry oil & gas** shortcut on Community. IoT/SCADA integrations are
outside public ORM metadata — plan external historians + CSV/API import, not fabricated modules.

Protected: **`account.move`**, **`payment.transaction`**, payroll — link-only from custom models.

## Phase rollout

**Phase 1 — Foundation:** contacts for contractors, maintenance equipment + requests, one
facility model, basic menus.

**Phase 2 — Operations:** stock/purchase for MRO, project for jobs, mail templates for overdue
PM, access groups for field vs office.

**Phase 3 — Scale:** HSE incidents, fleet, analytic reporting, module export for other sites.

## Example Expert questions

- "What do I need to setup an oil and gas company's internal management Odoo DB?"
- "Which stock modules for upstream maintenance and spare parts?"
- "How should I model wells and facilities vs maintenance equipment?"
