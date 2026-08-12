# Vertical playbook: Library Management

Expert vertical guidance for building an Odoo **Community** library database (catalog +
circulation). Keywords: library, libraries, book, books, loan, loans, isbn, barcode,
overdue, fine, fines, reservation, member, catalog, author, branch, library management.

Vertical id: `library_management`. Domain pack: `library_management`.

## Summary

Odoo Community has **no stock Library app**. Use **Contacts** for members (`res.partner`,
link-only), **Mail** for overdue reminders, **Product** optionally for sellable fines SKUs,
and custom **`x_lib_*` models** for catalog and circulation. This app ships a **Library**
Wizard template (live metadata scaffold) and a **`library_management` domain pack** (ELITE
Draft Studio path with branches, reservations, fines, cron, QWeb receipt).

**Do not invent** parallel member models (`x_lib_member`, `x_library_member`) — members are
always **`res.partner`**.

## Stock Odoo apps — recommended install order

1. **`base`**, **`web`**, **`mail`** — platform (always present).
2. **`contacts`** — library members as `res.partner` (tag e.g. *Library Member*).
3. **`product`** — optional fines or fee products (link-only to accounting; no auto-posting).
4. Add **`account`** / **`sale`** only when you invoice fines or sell items — verify on your
   instance; Expert must not assume Enterprise billing features.

**Depends for generated modules:** `base`, `contacts`, `mail`, `product` (plus
`base_automation` when fines/overdue automations ship in the portable zip).

Do **not** require **`website`** for a staff-operated library DB unless you also need a
public OPAC or member portal.

## Custom models — use these names

| Model | Purpose | Key links |
|-------|---------|-----------|
| `x_lib_category` | Book categories | — |
| `x_lib_author` | Authors | create from Book form or Authors menu |
| `x_lib_book` | Catalog (ISBN, barcode, status, copies, fine rate) | `x_lib_category`, `x_lib_author`, O2M `x_lib_loan` |
| `x_lib_loan` | Circulation | `x_lib_book`, **`res.partner`** (`x_member_id`), dates, `x_returned` |
| `x_lib_branch` | Multi-branch libraries (ELITE pack) | optional `res.users` manager |
| `x_lib_reservation` | Holds / reservations (ELITE pack) | book + member partner |
| `x_lib_fine` | Overdue fines (ELITE pack) | loan + member partner |

Wizard **Library** template scaffolds the core four (`category`, `author`, `book`, `loan`).
Draft Studio **library_management** pack adds branch, reservation, fine, smart buttons, and
ELITE artifacts (mail templates, daily cron, QWeb **Loan Receipt** PDF).

## Path A — App Wizard (live metadata, fastest)

1. **Connect** your Odoo instance.
2. Open **App Wizard** at `/connections/{connection_id}/wizard`.
3. Pick the **Library** template; confirm phrase `I understand the risks`.
4. Optional: enable **Multi-company aware** for `x_company_id` + record rules.
5. Open **Builder** / **Designer** per model to refine fields and views.
6. Connection dashboard shows **Library stats** when `x_lib_book` exists
   (`GET /api/connections/{id}/library/stats`).

## Path B — Portable zip / sandbox → promote

1. Export from Wizard (**Export library zip**) or API
   `POST /api/apps/templates/library/export`.
2. Run sandbox gate: `./docker/run-sandbox-library-gate.sh` (preloads `contacts`, `mail`).
3. **Promote** only after sandbox validation + confirm phrase.
4. Remote targets: metadata/data install only unless Option A Python module path is used for
   cron/fines code.

## Workflows

### Members

Create or import **Contacts**; link loans via `x_lib_loan.x_member_id` → `res.partner`.
Never duplicate member identity in a custom `x_*` model.

### Circulation

Loan records track `x_loan_date`, `x_due_date`, `x_returned`. **Active Loans** menu uses domain
`[('x_returned','=',False)]`. Kanban + list decorations highlight open/overdue loans.

### Overdue & fines

- **Safe path:** computed `x_days_overdue`, `x_fine_amount` stubs + mail templates +
  scheduled action (daily cron) in exported module.
- **Option A Python:** sandbox-test before production; protected tier-1 accounting remains
  link-only (no auto `account.move` posting from Expert answers).

### Barcode / ISBN

Books expose barcode widget on `x_lib_book`; window action **Books by barcode** in the
portable module.

## Community vs Enterprise honesty

There is no Odoo Enterprise **Library** shortcut on Community. Public OPAC / member self-service
needs **Website** + portal access rules — add deliberately in Phase 3, not by default.

Protected: do not mutate **`account.move`**, **`payment.transaction`**, or payroll from Expert
generated automations without sandbox validation and operator confirmation.

## Phase rollout

**Phase 1 — Foundation:** `contacts`, scaffold `x_lib_category` / `x_lib_author` /
`x_lib_book` / `x_lib_loan`, member partners, basic menus (Books, Authors, Loans, Categories).

**Phase 2 — Operations:** Active Loans action, mail templates (overdue + due-soon), daily cron,
loan receipt QWeb report, barcode action, access groups for circulation staff.

**Phase 3 — Scale:** Branches, reservations, fines model, multi-company rules, bulk import of
books/members, module export for repeat deployments.

## Related tools in Odoo Custom

- **App Wizard** — Library template (fastest live scaffold).
- **Draft Studio** — `library_management` domain pack for ELITE module spec.
- **Designer / Builder** — refine views, automations, access.
- **Snapshots** — before bulk field or view changes.

## Example Expert questions

- "What do I need to setup a library management Odoo DB?"
- "Which stock modules and custom models for books and loans?"
- "How should I model library members — custom model or Contacts?"
- "Scaffold library catalog and circulation with overdue reminders."
