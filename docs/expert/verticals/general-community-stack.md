# Vertical playbook: General Odoo Community stack

Baseline apps almost every vertical builds on. Keywords: foundation, core apps, getting started,
new database, which modules, install order, Community stack.

## Universal foundation

Every Odoo Community database includes **`base`**, **`web`**, and usually **`mail`** (Discuss).
Before adding vertical-specific apps, configure:

- **Settings → Users & Companies** — company, currency, timezone.
- **Contacts** — people and organizations (`res.partner`).
- **Security** — groups and record rules before go-live (use this app's **Access** builder).

## Core apps by business need

| Need | Module | Notes |
|------|--------|-------|
| People & companies | `contacts` | Customers, vendors, students, patients as partners |
| Public website | `website` | Pages, forms, blog; gateway to portal |
| Customer portal | `portal` | Often installed with website/sale |
| Sales quotes | `sale` | Quotations and sales orders |
| Invoicing | `account` | Customer invoices, chart of accounts |
| Products | `product` | Required for sale/inventory |
| Inventory | `stock` | Warehouses, receipts, deliveries |
| Purchasing | `purchase` | Vendor bills and POs |
| CRM pipeline | `crm` | Leads and opportunities |
| Projects & tasks | `project` | Internal or client projects |
| Timesheets | `hr_timesheet` | Often with project |
| Employees | `hr` | HR master data |
| Events | `event` | Registrations and tickets |
| Calendar | `calendar` | Meetings and scheduling |
| eLearning | `website_slides` | Courses and slides |
| Point of Sale | `point_of_sale` | Retail shops |
| Online shop | `website_sale` | eCommerce on website |
| Manufacturing | `mrp` | BoMs and manufacturing orders |
| Fleet | `fleet` | Vehicles |
| Surveys | `survey` | Forms and quizzes |

## Install discipline

Install the **minimum** set for go-live week one. Each app adds menus, default data, and
upgrade surface. Add apps when a workflow is blocked — not "just in case."

Use **Apps → Update Apps List** after enabling new code from generated modules.

## Customization path in this app

1. **Connect** the Odoo instance (observer mode first).
2. **Models & Fields** — add `x_` models/columns.
3. **View Designer** — forms, lists, menus.
4. **Automations** — `base.automation` without raw Python on the safe path.
5. **Export module** — portable zip; **sandbox-test** before production install.

## Expert usage

Ask with a **connection selected** so Expert knows installed modules and Odoo version.
For vertical-specific module lists (school, clinic, hotel, etc.), see other playbooks in
this folder or ask "vertical playbook for …".

## Honest limits

Community does not include Odoo Studio, some Sign/Documents/Enterprise HR flows, or hosted-only
features. Expert answers should cite these playbooks or official docs — not invent modules.
