# Odoo 20 — production operator checklist

Use this list before you point Ingenium at a **customer** Odoo 20 Community database or promote customizations into production. Checking a box here means **you** performed or verified the step on that environment — not that this app has already done it for you.

---

## Connection and API access

- [ ] **Dedicated bot user** — Create a service user for Ingenium (not a human admin’s personal login). Grant only the groups needed for the planned customization scope.
- [ ] **RPC-scoped API key with expiry** — Issue an API key on that user with RPC scope and a defined expiration date. Rotate before expiry; revoke on offboarding.
- [ ] **`ODOO_PROTOCOL=auto` on Odoo 20** — With `auto`, the platform uses **JSON-2** against Odoo 20. If you must use password login over classic XML-RPC, set **`rpc_protocol=xmlrpc`** explicitly on the connection (do not assume `auto` will pick XML-RPC for password auth).

---

## Version table — read `(verify)` before trusting field names

Before you treat a version-table row as a guaranteed field or model name on a given major, read its **verify** note in the profile / version table output.

These rows still carry **verify** (as of this checklist): confirm on your target database before wiring automations, views, or reports to them:

| Row | Topic | Majors called out |
|-----|--------|-------------------|
| V06 | Tax included | 18–19 |
| V24 | `account.payment.state` | 17 and 19 |
| V26 | Partner mobile / title | 19 |
| V28 | BOM consumption | 19 |
| V29 | Return wizard | 19 |
| V30 | Tracking values model | 19 |

Do not copy field names from docs or tables into production metadata until the verify note is cleared for **your** major and apps installed.

---

## Odoo 20 model and security deltas

- [ ] **`company_type` removed on 20** — Do not reference `company_type` in new metadata or migrated specs; use the 20-era partner/company fields and translators instead.
- [ ] **`company_registry` → additional identifiers** — Map legacy registry usage through the version translators; do not assume the old field semantics on 20.
- [ ] **Pricelist percentage → discount** — Percentage-based pricelist rules are expressed as discount on 20; replay or translate old specs before apply.
- [ ] **Access model on 20 is `ir.access`** — Not `ir.model.access` plus `ir.rule` as on older majors. Plan access as **`ir.access`** records.
- [ ] **Group record rules → access rights with domain** — Rewrite former group/record-rule patterns as access rights that include a domain where needed. Have a **security owner** review domains and groups before production apply.

---

## Flow tests, sandbox vs production

- [ ] **Re-run flow tests on a duplicate** — Never use the live production database as the first pass for quote-to-cash, procure-to-pay, or manufacturing smoke flows.
- [ ] **Local sandbox scores are not a customer pass** — A green run on the local Community 20 sandbox (e.g. quote-to-cash 7/7, procure-to-pay 6/6, manufacture 2/2) validates the **script and stack**, not your customer’s chart of accounts, fiscal localization, or installed apps.
- [ ] **Printed invoice layout** — Open or print a customer invoice (PDF or print preview) separately; layout and QWeb inherit issues do not always show up in RPC flow checks.

---

## AI, MCP, and Enterprise

- [ ] **Community 20 has no native MCP** — Do not present MCP as available on a Community-only connection.
- [ ] **Do not agree AI/MCP key ownership** until an **Enterprise** database is actually connected and you know who holds keys, rotation, and audit responsibility.

---

## Backups and metadata snapshots

- [ ] **Database dumps are operator-owned on 20** — This app does **not** take full database dumps on Odoo 20, Odoo.sh, or Odoo Online. The operator takes backups on the host per host runbooks.
- [ ] **Metadata snapshots still apply** — Before a **destructive production apply**, ensure a fresh metadata snapshot exists within the **10-minute freshness window** (or take a new snapshot per product rules).

---

## Module promotion

- [ ] **Sandbox first** — Do not install unvalidated generated or custom modules into production. Zip → sandbox install and smoke → human promote only when satisfied.
- [ ] **Promote stays human** — Automated jobs must not push modules or live metadata to production without an explicit operator decision.

---

## Related automation (names tests where they exist)

| Checklist item | Where to look |
|----------------|---------------|
| List arch root `list` on 20 | `packages/odoo-client/tests/test_view_arch.py` — `test_render_list_arch_major20_root_is_list_never_tree` |
| Local 20 flow smoke (sandbox only) | `apps/api/scripts/run_odoo20_flow_checks.py` (XML-RPC admin path; not a substitute for duplicate-DB customer validation) |
| Version-table verify rows | Profile / version table output; drift cards under T8-OD-DRIFT |

---

*Operator guidance only — not evidence that every item has been executed on any specific customer database.*
