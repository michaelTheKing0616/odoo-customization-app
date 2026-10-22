# Odoo configuration catalog, versions 17 to 20 (Community and Enterprise)

Written 2026-10-15 for Tope (Ingenium Configuration Suite, Bulk Setup). Input for CONFIG_SUITE_SPEC.md section 20.

## 0. How this was built, and how far to trust it
- **Source scan (verified):** a read-only Python AST scan of every addon in the official Docker images, with no database: `odoo:17` (17.0-20260723), `odoo:18` (18.0-20260723), `odoo:19` (19.0-20260723) and the running `odoo20` container (20.0-20260926) on Tope's Mac. Path in each: `/usr/lib/python3/dist-packages/odoo/addons`. Scanner: `/tmp/cfgscan.py` (box). Raw output: `/workspace/cfgscan/cfg_{17,18,19,20}.json`.
- **Spot checks (verified):** greps of named files in the same images. The file paths are cited inline.
- **Enterprise (docs only):** the images are Community. Enterprise apps (Accounting full, Studio, Helpdesk, Payroll, Planning/Field Service, Documents, Sign, Knowledge, Quality, Barcode, PLM, MPS, Subscriptions, Rental, AI) are described from odoo.com documentation, **not** from source. They are tagged **EE**.
- **Never invented:** where the scan can't say where a setting moved, the catalog says "removed from the Settings page", not where it went.

### 0.1 Scan totals
| | 17 | 18 | 19 | 20 |
|---|---|---|---|---|
| Addon modules (Community image) | 638 | 683 | 684 | 693 |
| `res.config.settings` fields (all modules) | 632 | 704 | 712 | 796 |
| of which install-an-app toggles (`module_*`) | 123 | 136 | 127 | 118 |
| of which feature switches (`group_*` / implied_group) | 54 | 51 | 42 | 41 |
| of which system parameters (`config_parameter`) | 77 | 85 | 80 | 93 |
| of which company fields (`related='company_id.*'`) | 172 | 211 | 233 | 270 |
| Wizards (TransientModel, excluding settings) | 197 | 227 | 223 | 238 |
| Onboarding step files (`onboarding.onboarding.step`) | 5 (account, account_payment, calendar, sale, payment) | 4 | 2 (account) | account only: company data, document layout, fiscal year, chart of accounts, sales tax (+2 dashboards) |

The trend: from 17 to 20, settings move from feature switches and app toggles toward company fields and system parameters. A bulk engine has to write company fields per company, not once.

### 0.2 Structural model changes that break naive bulk scripts (verified by scan + grep)
| Change | 17 | 18 | 19 | 20 | Evidence |
|---|---|---|---|---|---|
| `uom.category` (unit categories) | yes | yes | **gone** | gone | uom/models/uom_uom.py in 20 has `relative_factor`, `relative_uom_id` |
| `product.packaging` | yes | yes | **gone** | gone | packaging lives in `product/models/product_uom.py` (`product.uom`) |
| `hr.contract` (contracts) | yes | yes | **gone** | gone | `hr.version` from 19; 20 wizard `hr.employee.create.version.wizard` |
| `account.group` (account groups) | yes | yes | yes | **gone** | 20 `account.account.parent_id`, `code_store` company-dependent (account/models/account_account.py:47,133) |
| `ir.rule` + `ir.model.access` | yes | yes | yes | **gone** | 20 `ir.access` (base/models/ir_access.py:66) |
| `res.bank` | yes | yes | yes | **gone** | 20 `res.partner.bank.bank_name`, `bank_bic` (base/models/res_partner_bank.py:59,67) |
| `hr.leave.type` (time off types) | yes | yes | yes | **gone** | 20 hr_holidays inherits `hr.work.entry.type` (hr_holidays/models/hr_work_entry_type.py:31) |
| `res.groups.privilege` | no | no | **new** | yes | base/models/res_groups_privilege.py |
| `account.code.mapping` (per-company codes) | no | **new** | yes | yes | account/models/account_code_mapping.py |
| `account.lock_exception` | no | **new** | yes | yes | scan |
| `product.combo` | no | **new** | yes | yes | scan |
| `pos.preset` | no | no | **new** | yes | point_of_sale/models/pos_preset.py |
| `ir.actions.server.history` + `server.action.history.wizard` | no | no | **new** | yes | base/models/ir_actions.py |
| `res.config.installer` | yes | **gone** | gone | gone | scan |
| `stock_picking_batch` wizards folded into `stock` | separate | separate | separate | **in stock** | scan (`stock.picking.to.batch` in stock, 20) |
| `purchase_requisition` alternatives -> `purchase_alternative` | 17-19 | | | **20** | scan |

## 1. Legend
- **Mechanism:** the stock Odoo path Ingenium must use. `S:` = a `res.config.settings` field (module.field). `W:` = wizard. `M:` = model records (create/write). `F:` = model method or button. `I:` = `base_import.import` (`execute_import(..., dryrun=True)` exists in 17-20, base_import/models/base_import.py:1534 in 20). `D:` = data file / module install. `OB:` = onboarding step.
- **Bulk:** **Y** = many records or many companies in one run. **P** = partly (per company, or one-time but scriptable). **N** = single decision, done once.
- **Risk:** **L** low (reversible, no money or stock effect). **M** medium (changes future documents, mail or access). **H** high (stock valuation, security, irreversible, or affects existing documents). **G** guarded (accounting core: only through the stock localization mechanism or Odoo's own screens, under the Money guard, spec 7.4).
- **Ed.:** CE = Community, EE = Enterprise only (docs), CE+ = Community with extra EE options.
- **Versions:** "17-20" = same mechanism in all four (scan). Otherwise the difference is stated.

## 2. Catalog

### 2.1 Apps and modules (always first)
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 1 | Install apps | F: `ir.module.module.button_immediate_install` (base/models/ir_module.py); S: `module_*` toggles | P | M | 17-20; toggles 123 -> 118 | CE+ |
| 2 | Uninstall apps (look first) | W: `base.module.uninstall` shows what goes | N | H | 17-20 | CE |
| 3 | Update app list / upgrade | W: `base.module.update`, `base.module.upgrade` | N | M | 17-20 | CE |
| 4 | Load demo data (never on client DBs) | W: `ir.demo` | N | H | 17-20 | CE |
| 5 | Country package (localization) | D: `l10n_xx` modules, auto-picked from company country | P | G | 17-20; many l10n modules added and renamed (e.g. 20: `l10n_us_account`, `l10n_pk_edi`, `l10n_in_ewaybill` replaces `l10n_in_edi_ewaybill` from 19) | CE+ |

### 2.2 Company and multi-company
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 6 | Company details (name, address, VAT, logo, currency) | M: `res.company`; OB: `onboarding_onboarding_step_company_data` (account) | P | M | 17-20 | CE |
| 7 | Create more companies / branches | M: `res.company` (parent_id for branches) | Y | M | 17-20; branches 17+ | CE |
| 8 | Company currency | M: `res.company.currency_id` (locked once entries exist; S: `account.has_accounting_entries`) | N | G | 17-20 | CE |
| 9 | Fiscal country, tax ID, company registry | M: `res.company` (`account_fiscal_country_id`, `vat`) | P | G | 17-20 | CE |
| 10 | Inter-company rules | S: `base_setup.module_account_inter_company_rules` | N | H | 17-20 | EE |
| 11 | Inter-company payments | S in `account_payment_interco` | N | H | 19-20 | CE |
| 12 | Default company per user, allowed companies | M: `res.users.company_id`, `company_ids` | Y | M | 17-20 | CE |
| 13 | Time zone per company | S: `hr.company_tz` | P | L | 20 setting (hr); earlier on users/calendar | CE |
| 14 | Country groups | M: `res.country.group` | Y | L | 17-20 | CE |

### 2.3 Users, groups and access
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 15 | Create users / invite | M: `res.users`; I: users import | Y | M | 17-20 | CE |
| 16 | Assign roles per app | M: `res.users.groups_id` (17-18), privileges + groups (19-20: `res.groups.privilege`) | Y | H | screen layout and field names differ 19+ | CE |
| 17 | Default rights for new users | S: `base_setup.user_default_rights` (17); gone from Settings by 20 | N | M | 17 only on Settings page | CE |
| 18 | Model access lines | M: `ir.model.access` (17-19); `ir.access` (20) | Y | H | **changed in 20** | CE |
| 19 | Record rules (row filters) | M: `ir.rule` (17-19); domains on `ir.access` (20) | Y | H | **changed in 20** | CE |
| 20 | Portal access for contacts | W: `portal.wizard` | Y | M | 17-20 | CE |
| 21 | Password reset / sign-up policy | S: `auth_signup.auth_signup_reset_password`, `auth_signup_uninvited`, `auth_signup_template_user_id` | N | M | 17-20 | CE |
| 22 | Two-factor enforcement | S in `auth_totp_mail_enforce` (17-18), `auth_totp_mail` (19-20) | N | M | module renamed 19 | CE |
| 23 | Passkeys | W: `auth.passkey.key.create` | N | L | 18-20 | CE |
| 24 | OAuth / LDAP login | S: `base_setup.module_auth_oauth`, `module_auth_ldap` | N | H | 17-20 | CE |
| 25 | API keys | W: `res.users.apikeys.description` | N | H | 17-20 (MCP-scoped keys in 20, EE AI) | CE |
| 26 | Departing user (archive, reassign) | M: `res.users.active`; HR W: `hr.departure.wizard` (17-19) | Y | M | departure wizard gone in 20 scan | CE |

### 2.4 Accounting core (all G: Money guard)
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 27 | Load chart of accounts | F: `account.chart.template.try_loading(template_code, company)` -> `_load` (account/models/chart_template.py:151,184 in 20; admin only); S: `account.chart_template`; OB: chart of accounts | P (per company) | G | 17-20 (template-as-Python since 17) | CE |
| 28 | Accounts: add / rename / deprecate | M: `account.account` | Y | G | 18+: per-company codes (`account.code.mapping`); 20: codes optional, `parent_id` hierarchy | CE |
| 29 | Account groups / hierarchy | M: `account.group` (17-19); `account.account.parent_id` (20) | Y | G | **changed in 20** | CE |
| 30 | Account tags | M: `account.account.tag` | Y | G | 17-20 | CE |
| 31 | Taxes | M: `account.tax` (from template); OB: sales tax | Y | G | 18+: `price_include_override` on taxes (scan: withholding, POS) | CE |
| 32 | Default sale / purchase tax | S: `account.sale_tax_id`, `purchase_tax_id` | N | G | 17-20 | CE |
| 33 | Prices tax-included or excluded (company switch) | S: `account.account_price_include` | N | G | **20 only** | CE |
| 34 | No-VAT company | S: `account.vat_disabled` | N | G | 20 only | CE |
| 35 | Tax rounding (per line / global) | S: `account.tax_calculation_rounding_method` | N | G | 17-20 | CE |
| 36 | Tax groups | M: `account.tax.group` | Y | G | 17-20 | CE |
| 37 | Fiscal positions (tax and account mapping) | M: `account.fiscal.position` | Y | G | 17-20 | CE |
| 38 | Journals (sales, purchase, bank, cash, misc) | M: `account.journal` | Y | G | 17-20 | CE |
| 39 | Bank accounts | W: `account.setup.bank.manual.config`; M: `res.partner.bank` | Y | G | 20: bank name/BIC on `res.partner.bank`, `res.bank` gone | CE |
| 40 | Payment terms | M: `account.payment.term` | Y | M | 17-20 | CE |
| 41 | Payment methods per journal | M: `account.payment.method.line` | Y | G | 17-20 | CE |
| 42 | Cash rounding | S: `account.group_cash_rounding`; M: `account.cash.rounding` | P | G | 20 adds rounding profit/loss account settings | CE |
| 43 | Exchange difference accounts and journal | S: `account.currency_exchange_journal_id`, income/expense exchange accounts | N | G | 17-20 | CE |
| 44 | Suspense / transfer accounts | S: `account.account_journal_suspense_account_id`, `transfer_account_id` | N | G | 17-20 | CE |
| 45 | Default income / expense accounts | S: `account.income_account_id`, `expense_account_id` | N | G | new by 20 | CE |
| 46 | Fiscal year and lock dates | W: `account.financial.year.op`; OB: fiscal year; M: `account.lock_exception` (18+) | N | G | 18+ lock exceptions | CE+ |
| 47 | Incoterms | S: `account.incoterm_id`; M: `account.incoterms` | P | L | 17-20 | CE |
| 48 | Reconciliation models | M: `account.reconcile.model` | Y | G | 17-20 | CE |
| 49 | Analytic plans and accounts | M: `account.analytic.plan`, `account.analytic.account` | Y | M | 17-20 | CE |
| 50 | Document numbering (invoice sequences) | W: `account.resequence.wizard`; S: `account.document_sequence_editable` (20) | N | G | resequence 17-20 | CE |
| 51 | Autopost bills | S: `account.autopost_bills`; W: `account.autopost.bills.wizard` | N | G | 18-20 | CE |
| 52 | Secure entries (hash) | W: `account.secure.entries.wizard` | N | G | 18-20 | CE |
| 53 | Audit trail | S in `account_audit_trail` (17); `account.force_restrictive_audit_trail` (20) | N | G | moved into account | CE |
| 54 | Merge duplicate accounts | W: `account.merge.wizard` | N | G | 18-20 | CE |
| 55 | Bank feeds, statement import, reports, budgets, assets | S: `module_account_accountant`, `module_account_budget`; statement import toggles dropped from Settings by 20 | N | G | 17-20 | EE |
| 56 | E-invoicing (Peppol, country EDI) | W: `peppol.registration` (18+); S: per-country EDI modules | N | G | many country changes, see 0.2 and scan | CE+ |
| 57 | Check printing, batch payments, SEPA | S: `module_account_check_printing`, `module_account_batch_payment`, `module_account_sepa_direct_debit`, `module_account_iso20022` | N | G | 17: `module_account_sepa`; 20: `module_account_iso20022` | CE+/EE |
| 58 | Opening balances | Odoo's own opening balance screen / import of journal entries | P | G | 17-20 | CE |
| 59 | Tax return / periodic reports | `account.return` not present in Community images | N | G | EE (docs) | EE |

### 2.5 Currencies
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 60 | Turn on multi-currency | S: `base_setup.group_multi_currency` | N | M | 17-20 | CE |
| 61 | Activate currencies | M: `res.currency.active` | Y | M | 17-20 | CE |
| 62 | Exchange rates (manual / import) | M: `res.currency.rate`; I: rates import | Y | G | 17-20 | CE |
| 63 | Live rates | S: `account.module_currency_rate_live` | N | G | 17-20 | EE |

### 2.6 Products, units and prices
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 64 | Units of measure on | S: `product.group_uom` | N | M | 17-20 | CE |
| 65 | Unit categories and units | M: `uom.category` + `uom.uom` (17-18); `uom.uom` with `relative_uom_id` / `relative_factor` (19-20) | Y | H (once used) | **changed in 19** | CE |
| 66 | Price per unit display | S: `product.group_show_uom_price` | N | L | moved from website_sale to product by 20 | CE |
| 67 | Product categories (incl. costing method and accounts) | M: `product.category` | Y | G for costing/accounts, else L | 17-20 | CE |
| 68 | Products and services | M: `product.template`; I: products import | Y | M | 17-20 | CE |
| 69 | Variants and attributes | S: `product.group_product_variant`; M: `product.attribute`; W: `update.product.attribute.value` (18+) | Y | M | 17-20 | CE |
| 70 | Packagings | S: `product.group_stock_packaging` (17); `product.uom` (19-20) | Y | M | **changed in 19** | CE |
| 71 | Combos | M: `product.combo` | Y | L | 18-20 | CE |
| 72 | Pricelists on | S: `product.group_product_pricelist` (20); `group_sale_pricelist` / `product_pricelist_setting` (17) | N | M | renamed | CE |
| 73 | Pricelists and rules | M: `product.pricelist` (+ items); I: import | Y | M | 17-20 | CE |
| 74 | Discounts on lines | S: `sale.group_discount_per_so_line` (20); in `product` (17) | N | L | moved | CE |
| 75 | Loyalty, coupons, gift cards | S: `product.module_loyalty`; M: `loyalty.program` | Y | M | 17-20 | CE |
| 76 | Barcode lookup | S: `product.module_product_barcodelookup` | N | L | new by 20 | CE |
| 77 | Weight / volume units | S: `product.product_weight_in_lbs`, `product_volume_volume_in_cubic_feet` | N | L | 17-20 | CE |
| 78 | Product labels layout | W: `product.label.layout` | N | L | 17-20 | CE |

### 2.7 Inventory
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 79 | Warehouses (auto-created per company) | M: `stock.warehouse`; F: `res.company._create_per_company_*` (stock/models/res_company.py) | Y | M | 17-20 | CE |
| 80 | Reception / delivery steps | M: `stock.warehouse.reception_steps`, `delivery_steps`; F: `_create_or_update_route` (stock/models/stock_warehouse.py:449 in 20) | P | H | 17-20 | CE |
| 81 | Storage locations | S: `stock.group_stock_multi_locations`; M: `stock.location`; I: import | Y | M | 17-20 | CE |
| 82 | Routes and rules | S: `stock.group_stock_adv_location`; M: `stock.route`, `stock.rule` | Y | H | 17-20 | CE |
| 83 | Operation types | M: `stock.picking.type`; F: `_create_or_update_sequences_and_picking_types` (stock_warehouse.py:327) | Y | M | 17-20 | CE |
| 84 | Putaway rules | M: `stock.putaway.rule` | Y | L | 17-20 | CE |
| 85 | Storage categories | S: `stock.group_stock_storage_categories` (17); M: `stock.storage.category` | Y | L | Settings switch gone by 20 | CE |
| 86 | Lots and serial numbers | S: `stock.group_stock_production_lot`, `group_lot_on_delivery_slip`, `group_stock_lot_print_gs1` | N | H (once used) | 17-20 | CE |
| 87 | Expiry dates | S: `stock.module_product_expiry` | N | M | 17-20 | CE |
| 88 | Packages | S: `stock.group_stock_tracking_lot`; M: `stock.package.type` | P | L | 17-20 | CE |
| 89 | Consignment | S: `stock.group_stock_tracking_owner` | N | M | 17-20 | CE |
| 90 | Batch and wave transfers | S: `stock.group_stock_picking_batch` (20); `module_stock_picking_batch`, `group_stock_picking_wave` (17) | N | L | **merged into stock in 20** | CE |
| 91 | Reorder rules | M: `stock.warehouse.orderpoint`; W: `stock.orderpoint.suggest` (20) | Y | M | 17-20 | CE |
| 92 | Replenish on order, horizon days | S: `stock.replenish_on_order`, `horizon_days` | N | M | new by 20 | CE |
| 93 | Shipping policy | S: `stock.picking_policy` | N | L | new by 20 | CE |
| 94 | Annual inventory date | S: `stock.annual_inventory_month`, `annual_inventory_day` | N | L | 17-20 | CE |
| 95 | Initial stock quantities | M: `stock.quant` (inventory mode); I: import | Y | G (valuation) | 17-20 | CE |
| 96 | Costing method and valuation (per category) | M: `product.category` (`property_cost_method`, `property_valuation`) | Y | G | 20: valuation without Inventory (release notes) | CE |
| 97 | Landed costs | S: `stock_account.module_stock_landed_costs` | N | G | 17-20 | EE |
| 98 | Delivery methods / carriers | S: `stock.module_delivery`; M: `delivery.carrier` | Y | M | carrier toggles removed from Settings by 20 | CE+ |
| 99 | Barcode app, quality | S: `stock.module_stock_barcode`, `module_quality_control` | N | M | 17-20 | EE |
| 100 | Dropshipping | S: `stock.module_stock_dropshipping` | N | M | 17-20 | CE |
| 101 | Signature on delivery, email/SMS on validation | S: `stock.group_stock_sign_delivery`, `stock_move_email_validation`, `module_stock_sms` | N | L | 17-20 | CE |
| 102 | Location, package, operation labels | W: `stock.location.label.layout`, `stock.package.label.layout`, `stock.picking.type.label.layout` | N | L | 20 only | CE |

### 2.8 Sales and CRM
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 103 | Invoicing policy (ordered / delivered) | S: `sale.sale_invoice_policy` (20); `default_invoice_policy` (17) | N | M | renamed | CE |
| 104 | Automatic invoice after online payment | S: `sale.sale_automatic_invoice` (20); `automatic_invoice` (17) | N | M | renamed | CE |
| 105 | Down payments | S: `sale.downpayment_account_id` (20); `deposit_default_product_id` (17) | N | G | changed | CE |
| 106 | Quotation validity, online sign / pay, prepayment | S: `sale.quotation_validity_days`, `portal_confirmation_sign`, `portal_confirmation_pay`, `prepayment_percent` | N | L | 17-20 | CE |
| 107 | Quotation templates | M: `sale.order.template` | Y | L | 17-20 (`sale_management` settings fields gone by 20) | CE |
| 108 | Pro-forma, warnings, lock confirmed orders | S: `sale.group_proforma_sales`, `group_warning_sale`, `group_auto_done_setting` | N | L | 17-20 | CE |
| 109 | Sales teams | M: `crm.team` | Y | L | 17-20 | CE |
| 110 | Leads on / off, recurring revenue | S: `crm.group_use_lead`, `group_use_recurring_revenues` | N | L | 17-20 | CE |
| 111 | Pipeline stages, lost reasons | M: `crm.stage`, `crm.lost.reason` | Y | L | 17-20 | CE |
| 112 | Lead assignment rules | S: `crm.crm_use_auto_assignment` and interval fields | N | M | 17-20 | CE |
| 113 | Predictive lead scoring | S: `crm.predictive_lead_scoring_*`; W: `crm.lead.pls.update` | N | L | 17-20 | CE |
| 114 | Lead enrichment / mining | S: `crm.module_crm_iap_enrich`, `module_crm_iap_mine` | N | M (IAP credits) | 17-20 | CE (IAP) |
| 115 | Partnerships / memberships | S: `crm.module_partnership` | N | L | 19-20 | CE |
| 116 | Commissions, product matrix, Amazon / Shopee | S: `sale.module_sale_commission`, `module_sale_product_matrix`, `module_sale_amazon`, `module_sale_shopee` | N | M | added over 18-20 | EE |

### 2.9 Purchase
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 117 | Order approval (two-step, amount) | S: `purchase.po_order_approval`, `po_double_validation`, `po_double_validation_amount` | N | M | 17-20 | CE |
| 118 | Lock confirmed orders | S: `purchase.lock_confirmed_po` / `po_lock` | N | L | 17-20 | CE |
| 119 | Bill control (ordered / received) | S: `purchase.default_purchase_method` (17); gone from Settings by 20 | N | M | changed | CE |
| 120 | Vendor lead times / security days | S: `purchase.po_lead`, `use_po_lead` (17); gone from Settings by 20 | N | L | changed | CE |
| 121 | Purchase agreements / alternatives | S: `purchase.module_purchase_requisition`; `module_purchase_alternative` (20) | N | L | split in 20 | CE |
| 122 | Vendor pricelists | M: `product.supplierinfo`; I: import | Y | M | 17-20 | CE |
| 123 | 3-way match | S: `purchase.module_account_3way_match` | N | G | 17-20 | EE |
| 124 | Receipt reminders | S: `purchase.group_send_reminder` | N | L | 17-20 | CE |

### 2.10 Manufacturing, repair, maintenance
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 125 | Work orders on | S: `mrp.group_mrp_routings` | N | M | 17-20 | CE |
| 126 | By-products, unlock by default | S: `mrp.group_mrp_byproducts`, `group_unlocked_by_default` | N | L | 17-20 | CE |
| 127 | Work centres | M: `mrp.workcenter` | Y | M | 17-20 | CE |
| 128 | Bills of materials and operations | M: `mrp.bom`, `mrp.routing.workcenter`; I: import | Y | M | 17-20 | CE |
| 129 | Manufacturing lead time | S: `mrp.manufacturing_lead`, `use_manufacturing_lead` (17); gone from Settings by 20 | N | L | changed | CE |
| 130 | Subcontracting | S: `mrp.module_mrp_subcontracting` | N | M | 17-20 | CE |
| 131 | MPS, PLM, quality | S: `mrp.module_mrp_mps`, `module_mrp_plm`, `module_quality_control` | N | M | 17-20 | EE |
| 132 | WIP accounting | W: `mrp.account.wip.accounting` | N | G | 18-20 | CE |
| 133 | Maintenance equipment and teams | M: `maintenance.equipment` | Y | L | 17-20 | CE |
| 134 | Repair settings | M: repair operation type (stock) | P | L | 17-20 | CE |

### 2.11 Point of Sale
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 135 | Shops / registers | M: `pos.config`; S: `point_of_sale.pos_config_id` + `pos_*` related fields (73 -> 97 settings fields) | Y | M | heavy churn every version | CE |
| 136 | Payment methods | M: `pos.payment.method`; S: terminal toggles (`module_pos_adyen`, `module_pos_stripe`, ...; 20 adds `module_pos_viva_com`, `module_pos_razorpay`, `module_pos_qfpay`, `module_pos_dpopay`, `module_pos_pine_labs`, `module_pos_mercado_pago`) | Y | G | changed | CE+ |
| 137 | Restaurant, preparation display | S: `point_of_sale.pos_module_pos_restaurant`; `module_pos_preparation_display` (17) | N | L | changed | CE+ |
| 138 | Presets (dine-in / takeaway) | M: `pos.preset`; S: `pos_use_presets` | Y | L | 19-20 | CE |
| 139 | Receipt header, logo, contact details | S: `pos_custom_logo`, `pos_custom_phone`, `pos_custom_receipt_address`, ... | P | L | 20 fields; 17 used `pos_is_header_or_footer` | CE |
| 140 | Session closing (daily hour) | S: `pos_session_closing_mode`, `pos_session_closing_daily_hour` | N | M | 20 | CE |
| 141 | Kiosk mode | S: `use_kiosk_mode` (20); `is_kiosk_mode` (17) | N | L | renamed | CE |
| 142 | Prices tax-included in POS | W: `pos.price.inclusion.wizard` | N | G | 20 only | CE |
| 143 | Printers | S: `pos_receipt_printer_ids`, `pos_preparation_printer_ids` | P | L | 20 | CE |

### 2.12 Website and eCommerce
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 144 | Create website (configurator) | F: `website.create_and_redirect_configurator` (website/models/website.py:559 in 20) | N | L | 17-20 | CE |
| 145 | Domain, name, homepage, logo, favicon | S: `website.website_domain`, `website_name`, `website_homepage_url`, `website_logo`, `favicon` | P | M | 17-20 | CE |
| 146 | Languages on site | S: `website.language_ids`, `website_default_lang_id` | N | L | 17-20 | CE |
| 147 | Cookie bar, cookie policy, block third-party domains | S: `website.website_cookies_bar`, `cookie_policy_id`, `website_block_third_party_domains` | N | M | policy and blocking 18+/20 | CE |
| 148 | Analytics, Search Console, Plausible | S: `google_analytics_key`, `google_search_console`, `plausible_*` | N | L | 17-20 | CE |
| 149 | CDN | S: `cdn_activated`, `cdn_url`, `cdn_filters` | N | M | 17-20 | CE |
| 150 | robots.txt, llms.txt | W: `website.robots`; `website.llms` (20) | N | L | llms 20 only | CE |
| 151 | Menus and pages | M: `website.menu`, `website.page`; W: `website.page.properties` (18+) | Y | L | 17-20 | CE |
| 152 | Checkout: guest or account, extra step | S: `website_sale.account_on_checkout`, `ecommerce_access` (20); `enabled_extra_checkout_step` (17) | N | M | changed | CE |
| 153 | Abandoned cart emails | S: `website_sale.send_abandoned_cart_followup`, `cart_abandoned_delay`, `cart_recovery_mail_template` | N | L | renamed by 20 | CE |
| 154 | Stock availability and out-of-stock rules | S: `default_allow_out_of_stock_order`, `default_available_threshold`, `default_show_availability`, `group_unpublish_out_of_stock` | N | L | 20 | CE |
| 155 | Product feeds (Google Merchant) | S: `website_sale.group_gmc_feed` | N | L | 20 | CE |
| 156 | Click and collect | S: `website_sale.module_website_sale_collect` | N | M | 20 (17: `website_sale_picking`) | CE |
| 157 | Payment providers | M: `payment.provider`; W: `payment.provider.onboarding.wizard` (17-18) | P | G | onboarding wizard gone 19 | CE |
| 158 | Live chat | S: `website.module_website_livechat`; M: `im_livechat.channel` | P | L | 17-20 (20: AI agent as operator, EE) | CE+ |

### 2.13 Project, timesheets, HR, payroll, field service, helpdesk
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 159 | Project stages, task stages | S: `project.group_project_stages`; M: `project.task.type` | Y | L | 17-20 | CE |
| 160 | Milestones, dependencies, recurring tasks, ratings | S: `project.group_project_milestone` etc. (17-18); removed from Settings in 19 | N | L | **changed in 19** | CE |
| 161 | Project templates | W: `project.template.create.wizard` | Y | L | 19-20 | CE |
| 162 | Timesheets | S: `project.module_hr_timesheet` | N | L | 17-20 | CE |
| 163 | Departments, job positions | M: `hr.department`, `hr.job`; I: import | Y | L | 17-20 | CE |
| 164 | Employees | M: `hr.employee`; I: import | Y | M | 17-20 | CE |
| 165 | Working schedules | S: `hr.resource_calendar_id`; M: `resource.calendar` | Y | M | 17-20 | CE |
| 166 | Contracts / versions | M: `hr.contract` (17-18); `hr.version` (19-20) | Y | H | **changed in 19** | CE |
| 167 | Presence control | S: `hr.hr_presence_control_*` | N | L | 17-20 | CE |
| 168 | Contract / work permit expiry notices | S: `hr.contract_expiration_notice_period`, `work_permit_expiration_notice_period` | N | L | in hr by 20 | CE |
| 169 | Time off types | M: `hr.leave.type` (17-19); `hr.work.entry.type` (20) | Y | M | **changed in 20** | CE |
| 170 | Public holidays | W: `load.public.holiday.wizard` (20); manual resource leaves before | Y | L | 20 only | CE |
| 171 | Allocations in bulk | W: `hr.leave.allocation.generate.multi.wizard` | Y | M | 18-20 | CE |
| 172 | Expenses: categories, journal, email alias | S: `hr_expense.expense_journal_id`, `hr_expense_alias_prefix`, `hr_expense_use_mailgateway` | P | G (journal) | 17-20 | CE |
| 173 | Recruitment: website, surveys | S: `hr_recruitment.module_website_hr_recruitment`, `module_hr_recruitment_survey` | N | L | 17-20 | CE |
| 174 | Work entry export | W: `hr.export.work.entries` | N | M | 20 | CE |
| 175 | Payroll structures, rules | Payroll app | Y | G | Payroll is EE (docs) | EE |
| 176 | Field service | Field Service app; **merged into Planning in 20** (release notes) | P | L | changed 20 | EE |
| 177 | Helpdesk teams, SLAs, stages | Helpdesk app | Y | L | 17-20 | EE |
| 178 | Fleet vehicles | M: `fleet.vehicle` | Y | L | 17-20 | CE |

### 2.14 Email and communication
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 179 | Outgoing mail servers | M: `ir.mail_server`; S: `mail.external_email_server_default` | P | M | 17-20 | CE |
| 180 | Incoming mail servers | M: `fetchmail.server` | P | M | 17-20 | CE |
| 181 | Alias domain | M: `mail.alias.domain`; S: `mail.alias_domain_id` | P | M | 17-20 | CE |
| 182 | Aliases per app / team | M: `mail.alias` | Y | M | 17-20 | CE |
| 183 | Gmail / Outlook login | S: `mail.module_google_gmail`, `module_microsoft_outlook` | N | M | 17-20 | CE |
| 184 | Email templates | M: `mail.template`; W: `mail.template.preview`, `mail.template.reset` | Y | M | 17-20 | CE |
| 185 | Restrict template editing | S: `mail.restrict_template_rendering` | N | M | 17-20 | CE |
| 186 | Email brand colours | S: `mail.email_primary_color`, `email_secondary_color` | N | L | 17-20 | CE |
| 187 | Activity types and plans | M: `mail.activity.type`, `mail.activity.plan` | Y | L | 17-20 (20: assign to roles, release notes) | CE |
| 188 | Digest emails | S: `digest.digest_emails`, `digest_id` | N | L | 17-20 | CE |
| 189 | SMS sender | W: `sms.account.sender`, `sms.account.phone` | N | M | 18-20 | CE (IAP) |
| 190 | Calls / video (Twilio, SFU) | S: `mail.use_twilio_rtc_servers`, `use_sfu_server`, ... | N | L | 17-20 | CE |

### 2.15 Automation and scheduled actions
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 191 | Automation rules | M: `base.automation` | Y | H | 17-20 ("Update with AI" EE, saas-18.3+) | CE+ |
| 192 | Server actions | M: `ir.actions.server`; history: `ir.actions.server.history` + `server.action.history.wizard` (19+) | Y | H | 19+ keep history | CE |
| 193 | Scheduled actions | M: `ir.cron` (active, interval, next call) | Y | H | 17-20 | CE |
| 194 | AI tools (server actions "Use in AI") | AI app | P | H | **20 only, EE** | EE |

### 2.16 Reports, layouts, sequences, defaults
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 195 | Document layout (logo, colours, font, footer) | W: `base.document.layout` (web); S: `base_setup.external_report_layout_id`, `report_footer`; OB: document layout | P (per company) | L | 17-20; DIN 5008 settings 19+ | CE |
| 196 | Paper formats | M: `report.paperformat` | Y | L | 17-20 | CE |
| 197 | Report actions (which PDF, file name) | M: `ir.actions.report` | Y | M | 17-20 | CE |
| 198 | Sequences (non-accounting) | M: `ir.sequence` | Y | M | 17-20 | CE |
| 199 | Default values | M: `ir.default` | Y | M | 17-20 | CE |
| 200 | System parameters | M: `ir.config_parameter`; S: `config_parameter` fields (77 -> 93) | Y | H | 17-20 | CE |
| 201 | Partner tags, industries, titles | M: `res.partner.category`, `res.partner.industry` | Y | L | 17-20 | CE |
| 202 | Contact merge | W: `base.partner.merge.automatic.wizard` | Y | H | 17-20 | CE |

### 2.17 Languages and translations
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 203 | Install languages | W: `base.language.install`; F: `res.lang._activate_lang` | Y | L | 17-20 | CE |
| 204 | Language per user / partner | M: `res.users.lang`, `res.partner.lang` | Y | L | 17-20 | CE |
| 205 | Import / export translations | W: `base.language.import`, `base.language.export` | Y | L | 17-20; 20 adds multi-language import via Excel/CSV (release notes) | CE |
| 206 | Translate field values | M: translated fields (JSONB since 16) | Y | L | 17-20 | CE |

### 2.18 Data import
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 207 | Import any model from CSV / Excel | I: `base_import.import.parse_preview`, `execute_import(dryrun=True)` then real run (base_import.py:1081,1534 in 20) | Y | M (G for accounting models) | 17-20 | CE |
| 208 | External IDs for re-import / update | I: `id` column (xml ids) | Y | M | 17-20 | CE |
| 209 | Import aftercare / undo | none in Odoo; Ingenium external ids `__ingenium_import__.*` find created records (spec 20.13) | Y | M | n/a | Ingenium |

### 2.19 Customization (Studio-like)
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 210 | Custom fields | M: `ir.model.fields` (x_ fields) | Y | H | 17-20 | CE |
| 211 | View changes | M: `ir.ui.view` (inherit); W: `reset.view.arch.wizard` | Y | H | 17-20 (`tree` -> `list` from 18) | CE |
| 212 | Menus | M: `ir.ui.menu`; W: `wizard.ir.model.menu.create` | Y | L | 17-20 | CE |
| 213 | Studio (apps, reports, approvals) | Studio app | Y | H | 17-20 | EE |
| 214 | Spreadsheet dashboards | spreadsheet modules | P | L | 17-20 (CE core, EE editing) | CE+ |

### 2.20 Other apps (settings exist; set once)
| # | Task | Mechanism | Bulk | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|
| 215 | Events, surveys, eLearning, mass mailing lists | M: `event.event`, `survey.survey`, mailing lists | Y | L | 17-20 | CE |
| 216 | Calendar sync (Google / Microsoft) | S: `base_setup.module_google_calendar`, `module_microsoft_calendar` | N | M | 17-20 | CE |
| 217 | Geolocation, address autocomplete, reCAPTCHA, Turnstile | S: `base_setup.module_base_geolocalize`, `module_google_address_autocomplete`, `module_google_recaptcha`, `module_website_cf_turnstile` | N | L | autocomplete 19+ | CE |
| 218 | Cloud storage for attachments (Azure / Google) | S in `cloud_storage*` | N | H | 18-20 | CE |
| 219 | VoIP | S: `base_setup.module_voip` | N | L | 17-20 | EE |
| 220 | Documents, Sign, Knowledge, Subscriptions, Rental, Appointments | app settings | P | L-M | 17-20 | EE |

### 2.21 Documents a person can upload (any document, any database)
Rule: **code picks the target from this catalog and the live database** (installed models, the person's access, the version's mechanism). The AI only proposes how to read the document and which live fields its columns match. Anything unknown or ambiguous becomes a plain question, never a guess. The rows below are **examples of the registry, not a closed list**. Any catalog task with mechanism `M:` or `I:` on a model present in the live database is a valid target. Model names were checked in the 17 and 20 images unless marked EE.

Formats:
- **Already read today** (repo `apps/api/app/ingest/extract*.py`, `data_import.parse_tabular`): CSV, XLSX, text PDF, and scanned PDF or photos through local vision (off by default; `INGEST_VISION`).
- **New:** DOCX (tables and text), emails (.eml/.msg body and attachments), multi-sheet workbooks (one table per sheet), several documents in one email or zip.

| # | Document (examples) | Target in live DB (code decides) | Must exist first | Apply mechanism | Undo | Risk | Versions | Ed. |
|---|---|---|---|---|---|---|---|---|
| 221 | Customer / vendor list | `res.partner` (+ `res.partner.category`, `res.partner.bank`) | countries, tags, payment terms, fiscal positions | I: base_import (Ingenium external ids) | Remove / Revert | M | 20: bank name and BIC on `res.partner.bank` | CE |
| 222 | Product catalogue, POS products | `product.template`/`product.product`, `pos.category`, `available_in_pos` | units, categories, taxes, attributes | I: base_import | Remove / Revert | M | 19+: units without categories; packagings on `product.uom` | CE |
| 223 | Price list with quantity breaks and dates | `product.pricelist` + items | products, currencies | I: base_import | Remove / Revert | M | 17-20 | CE |
| 224 | Vendor price list | `product.supplierinfo` | vendors, products, currencies | I: base_import | Remove / Revert | M | 17-20 | CE |
| 225 | Unit list | `uom.uom` (+ `uom.category` 17-18) | none | I: base_import | Remove | H once used | **19 change** | CE |
| 226 | Product categories (with costing) | `product.category` | accounts (if set) | I: base_import; costing and accounts G | Remove / Revert | G for costing | 17-20 | CE |
| 227 | Bill of materials (flat or nested) | `mrp.bom` + lines | products, units, operations | I: base_import (parent and lines; sub-assemblies first) | Remove | M | 17-20 | CE |
| 228 | Routings / work centres | `mrp.workcenter`, `mrp.routing.workcenter` | BoMs (for operations) | I: base_import | Remove / Revert | M | 17-20 | CE |
| 229 | Warehouses and locations | `stock.warehouse`, `stock.location` | company | M: create (warehouse builds its own routes and operation types) | Remove (archive) | M | 17-20 | CE |
| 230 | Lots / serial numbers | `stock.lot` | products with tracking on, company | I: base_import | Remove while unused | M | 17-20 | CE |
| 231 | Stock count | `stock.quant` `inventory_quantity` + `action_apply_inventory` (existing `ingest/inventory.py`) | products, locations, lots | F: inventory adjustment | Compensating count back to the old quantity (G, approval) | G (valuation) | 17-20 | CE |
| 232 | Chart of accounts (client's own list) | align to the loaded country package (existing `ingest/coa_align.py`); create only missing accounts after confirm | country package loaded | M: `account.account` | Remove while unused | G | 18+ per-company codes; 20 parent accounts, optional codes | CE |
| 233 | Tax table | **match** to package taxes; never create rates from a document | country package | M: select / activate | Revert | G | 17-20 | CE |
| 234 | Payment terms | `account.payment.term` (+ lines) | none | I: base_import | Remove / Revert | M | 17-20 | CE |
| 235 | Opening balances / trial balance | draft entry on the Opening journal (existing `ingest/opening_balance.py`); never posted by Ingenium | accounts, partners, journals | M: draft `account.move` | Remove draft | G | 17-20 | CE |
| 236 | Open invoices and bills at go-live | draft `account.move` via existing `batch_os/document_batch.py` | partners, products, taxes, accounts | M: drafts only | Remove draft | G | 17-20 | CE |
| 237 | Assets register | asset model only if present in the live DB | accounts, journals | M (drafts) | Remove draft | G | not in CE images | EE |
| 238 | Budgets | budget model only if present in the live DB | analytic plans and accounts | I: base_import | Remove | G | not in CE images | EE |
| 239 | Analytic plans and accounts | `account.analytic.plan`, `account.analytic.account`, `account.analytic.distribution.model` | company | I: base_import | Remove / Revert | M | 17-20 | CE |
| 240 | Employees (organisation fields only) | `hr.employee`, `hr.department`, `hr.job` (existing org-field allowlist; pay columns dropped) | company, working schedules | I: base_import | Remove (archive) | M | 17-20 | CE |
| 241 | Employment contracts | `hr.contract` (17-18) or `hr.version` (19-20); org and dates only, pay fields never | employees | M | Remove / Revert | H | **19 change** | CE |
| 242 | Skills | `hr.skill` (+ types) | employees | I: base_import | Remove | L | 17-20 | CE |
| 243 | Users and roles | `res.users` via existing `config_packet` users path | groups / privileges | M | Remove (archive) | H | 19+ privileges; 20 `ir.access` | CE |
| 244 | Leads / opportunities | `crm.lead` | teams, stages, salespeople, tags | I: base_import | Remove | L | 17-20 | CE |
| 245 | Projects and tasks | `project.project`, `project.task` | users, stages, partners | I: base_import (projects, then tasks, then subtasks) | Remove | L | 17-20 | CE |
| 246 | Timesheets | `account.analytic.line` (timesheet) | employees, projects, tasks | I: base_import | Remove | M (billing) | 17-20 | CE |
| 247 | Fleet | `fleet.vehicle` (+ models, brands) | drivers (partners/employees) | I: base_import | Remove | L | 17-20 | CE |
| 248 | Equipment | `maintenance.equipment` | teams, employees | I: base_import | Remove | L | 17-20 | CE |
| 249 | Website pages / content | `website.page` | website | M: page with content in the website builder's blocks; never raw code | Remove (unpublish) | M | 17-20 | CE |
| 250 | Email templates | `mail.template` (body checked by the existing qweb safety gate) | the model it applies to | M | Remove / Revert | M | 17-20 | CE |
| 251 | Sequences (non-accounting) | `ir.sequence`; accounting numbering stays G | none | M | Revert | M (G for accounting) | 17-20 | CE |
| 252 | Loyalty / coupon programmes | `loyalty.program` (+ rules, rewards) | products | M | Remove | M | 17-20 | CE |
| 253 | Company details, bank letter, tax certificate | Bulk Setup settings / company steps (2.2, 2.4 #39) | none | S: / M: `res.company` | Revert | M (G for fiscal) | 17-20 | CE |
| 254 | Anything else | any model in the live DB that the person can create and the catalog doesn't mark protected | from the live link graph | I: base_import | Remove / Revert | from field and model risk | from live DB | CE/EE |

**Order for documents** (code, from two sources):
1. **Live link graph:** each target's required links (`ir.model.fields` many2one with `required`) are hard edges. Optional links are soft edges.
2. **Catalog hard edges:** units → categories → products → vendor prices / price lists / BoMs; work centres → BoM operations; warehouses → locations → lots → stock counts; country package → accounts → taxes → products' taxes → opening balances; analytic plans → analytic accounts → budgets; departments → jobs → employees → contracts → timesheets; projects → tasks → timesheets; partners → leads / open invoices.

Self-links (parent company, manager, parent task) run in two passes: create, then link. A cycle that can't be split becomes a question.

## 3. Coverage
- **254 rows in 21 areas: 220 configuration tasks plus 34 document kinds (2.21, an open registry, not a closed list).** Every area in Tope's brief is covered: company/multi-company (2.2), users/access (2.3), localization/fiscal (2.1, 2.4), chart/taxes/journals/fiscal positions/payment terms (2.4), products/categories/UoM/pricelists (2.6), warehouses/locations/routes/operation types (2.7), sales/purchase/CRM/project/HR/payroll/manufacturing/POS/website/eCommerce/helpdesk/field service (2.8-2.13), sequences (2.16, 2.4 #50), email servers/aliases/templates (2.14), automations and scheduled actions (2.15), reports/layouts (2.16), languages/translations (2.17), currencies/rates (2.5), data imports (2.18), Studio-like customizations (2.19).
- **Bulk-able:** 89 Y, 26 P, 105 N (counted from the tables). **Guarded (G or partly G):** 47 tasks.
- **Source-verified:** the settings fields, wizards and key models named in CE rows come from the scan or a cited grep. A few common models outside the scan list (e.g. `product.supplierinfo`, `stock.quant`) are named from Odoo's standard data model and should be re-checked in Stage 1. **EE-only rows (16), plus EE options inside CE+ rows:** from docs only.
- **Not covered in depth:** per-country EDI settings (about 60 l10n modules have their own settings; they are listed in the scan JSON and handled by the localization card); every one of the 97 POS fields (grouped above).

## 4. Dependency order (used by Bulk Setup)
1. Apps (2.1), then company and branches (2.2).
2. Country package and chart of accounts (2.4 #27); then currencies (2.5).
3. Users and access (2.3); then languages (2.17).
4. Taxes, fiscal positions, journals, payment terms, bank accounts (2.4), all from the loaded package.
5. Units, categories with costing, products and prices (2.6).
6. Warehouses, steps, locations, routes, operation types (2.7).
7. App settings (2.8-2.13), mail (2.14), layouts and sequences (2.16).
8. Automations and scheduled actions (2.15), last. They react to the data loaded before them.
9. Imports of master data (2.18), then opening balances and initial stock (G, last).
