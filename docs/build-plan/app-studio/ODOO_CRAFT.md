# Odoo craft catalog: what a senior Odoo developer always builds (Pack §6.6)

Tope, 21 Oct: App Studio must build modules (or extend stock ones) as a team of senior Odoo developers would, without vertical packs as a crutch. This file is the closed list of idioms the craft stage (D) applies. **Structure** (which records exist) comes only from the owner's words (Ledger). **Craft** (how each record is built in Odoo) comes from this catalog, keyed on the shape of the ledger, never on the industry. A pack guesses what your business is; craft is how Odoo is built.

Status of every Odoo claim below: **[Inferred, to verify]**. Card AS-CRAFT-CATALOG verifies each row against stock views and models on disposable `ingenium_craft_<ver>` databases on Odoo 17, 18, 19 and 20 (RPC `get_views` on `sale.order`, `crm.lead`, `project.task`, `res.partner`), writes the per-version syntax into `apps/api/app/ai_conversation/odoo_craft/catalog_v{17,18,19,20}.py`, and marks each row Verified or Rejected here. No row ships unverified.

Lanes: **L** = live metadata (`ir.model.fields`, `ir.ui.view`, `ir.actions.*`, `base.automation` without code). **M** = generated module (sandbox → promote, Option A gate). **L!** = possible live only through an advanced action with the Odoo-style warning and the API confirmation flag (a computed field or server action evaluates Python); otherwise M only. **DEC-042 (resolved 21 Oct, Tope): module route.** Every Python-backed idiom (L! and M) is built only in the generated module, from fixed reviewed templates, never LLM-written, sandbox-tested, and promoted only by a person. The live lane builds every L row and shows the rest as "ready when you install it as a module". L! rows are not applied live.

| ID | Idiom | Applied when (ledger shape, never industry) | Lane | Version notes to verify |
|---|---|---|---|---|
| K01 | Chatter + activities (`mail.thread`, `mail.activity.mixin`) | every `record`; never on `line_of` | L, M | 17: `<div class="oe_chatter">` + 3 fields; 18+: `<chatter/>` |
| K02 | Field tracking | state, responsible person, money, key dates on K01 records | L, M | `tracking=True` |
| K03 | Reference number (`ir.sequence`, e.g. ORD/2026/0001) as the display name | record has a date and a party link, or the owner says number / ref / receipt / ticket / invoice | M, L! | live needs a code default or server action |
| K04 | Lifecycle: `state` selection + statusbar header + action buttons; kanban grouped by state | a rule or fact implies stages ("when paid", "once delivered", "approve") | L, M | existing `ai_design_compile` statusbar (L102) reused |
| K05 | Form layout: sheet, title, button box, two-column groups, notebook with an editable one2many list, chatter | every `record` | L, M | `oe_button_box name="button_box"`; 17 `<tree editable>` vs 18+ `<list editable>` |
| K06 | List view: sums on money/measures, optional columns, state badges/decorations, sensible default order | every `record` | L, M | `sum=`, `optional=`, `decoration-*`, `widget="badge"` |
| K07 | Search view: name/ref search, a filter per state, "My ___" when a responsible user exists, Archived, date filters, group-by on every selection / many2one / date | every `record` | L, M | `filter_domain`, `context="{'group_by': …}"` |
| K08 | Views chosen by data shape: calendar (a datetime + a person), pivot + graph (money or measure), kanban (stages or an image), activity view | per fact kinds | L, M | existing `ai_design_compile` L119-144 reused; 17 kanban `kanban-box` vs 18+ `card` |
| K09 | Smart buttons both ways: parent → children count, and stock host → custom records (res.partner → "Orders 3") via an inherited view anchored by `name` | every one2many / reverse many2one, including links from stock hosts | button: L; count: M, L! | xpath `//div[@name='button_box']`, never positional |
| K10 | Menus: app root, records first, Reporting submenu when pivot/graph exist, Configuration submenu for small lookup records | always | L, M | existing menu builder reused |
| K11 | Security: User + Manager groups per app; access rows; owner access rules → field/view groups; multi-company rules | always | L, M | 17-19 `ir.model.access` + `ir.rule`; 20 `ir.access` (no `ir.rule`) |
| K12 | Company and currency: `company_id` default when multi-company is on; `currency_id` for monetary fields | money facts; snapshot shows > 1 company | L, M | |
| K13 | Archive (`active`) and default order | every `record` | L, M | |
| K14 | Integrity: required links that define the record, unique reference, date-order checks the owner stated | link facts; K03; owner rules of kind `constraint` | L (required), M (SQL/Python constraints) | |
| K15 | Roll-ups: parent totals from lines (amount, quantity), counts | `line_of` with money or measure | M, L! | stored compute with `@api.depends` |
| K16 | Printable document (QWeb PDF) | owner says print / send / receipt / quote / certificate | M (L for the report action + QWeb view, to verify) | |
| K17 | Reminders and schedules as stock automations and scheduled activities, never code | rules of kind `schedule` / `automation` | L, M | `base.automation` trigger set per version |
| K18 | Extend, don't copy: stock records get fields, a notebook page and smart buttons through view inheritance anchored by `name`; stock workflows (e.g. `sale.order` states) untouched | `stock_host` / StockExtension | L, M | |
| K19 | Module hygiene: manifest (version, minimal `depends`, LGPL-3, category, `application`), data file order, security CSV, icon, `.pot`, README, and a TransactionCase test that installs, creates a record and walks its states | module lane | M | |

### Rows K20-K44: beyond smart buttons (added 21 Oct, Tope: "don't limit it to smart buttons")
Same rules: triggered by ledger shape, technical, `craft:Kxx` lineage, verified per major by AS-CRAFT-CATALOG before use.

**Fields that behave like a senior developer set them up** (card AS-CRAFT-FIELDS)
| ID | Idiom | Applied when | Lane |
|---|---|---|---|
| K20 | Smart defaults: date = today, responsible = current user, company = current company, currency = company currency, first state | date / person / money / lifecycle facts | M, L! (dynamic defaults); L for static `ir.default` |
| K21 | Delete policy: lines `cascade` with their parent; links to master data `restrict`; optional links `set null` | every many2one | L, M |
| K22 | `copy=False` on references, states and dates when a record is duplicated | K03, K04, date facts | L, M |
| K23 | Indexes on many2one and on dates/selections used in filters and group-bys | K07 filters | L, M |
| K24 | Link domains: active records only, same company, and the right kind (a "customer" link offers customers) | link facts; multi-company | L, M |
| K25 | The right widget per fact: monetary, image, email/phone/URL, many2many tags, `handle` for ordered lines, badge for state, progress bar for percentages, priority star only if the owner said priority | fact kinds | L, M |
| K26 | Help text and placeholders in the owner's own words, from the quote that created the field | every owner field | L, M |
| K27 | Search by reference + party name (`_rec_names_search`) and a display name that shows the reference with the party | K03 + party link | M |

**Forms and lists that guide the user** (card AS-CRAFT-UX)
| ID | Idiom | Applied when | Lane |
|---|---|---|---|
| K28 | State-aware forms: fields read-only after the done state, header buttons visible only in the right state, required only when it matters (17+ `invisible=`/`readonly=` expressions, never `attrs`) | K04 | L, M |
| K29 | Ribbons for terminal states ("Paid", "Cancelled", "Archived") | K04 terminal states; K13 | L, M |
| K30 | Confirm text on irreversible buttons ("Cancel this order?") | buttons leading to terminal states | L, M |
| K31 | Rich kanban card: reference, party avatar, amount, date, activity widget, state progress bar at the column top; all columns shown even when empty | K08 kanban | L (cards), M (`group_expand`) |
| K32 | Empty state help on every action ("Record your first order. Each order keeps its items, deposit and pickup date.") written from the owner's quotes | every window action | L, M |
| K33 | Default filter and grouping on the main menu (e.g. open orders, grouped by pickup date) | K04 / K07 | L, M |
| K34 | Smart-button actions open with context defaults, so a new line created from a customer is already linked to that customer | K09 | L, M |
| K35 | Lines edited inline at the bottom, with a handle to reorder when order matters | `line_of` | L, M |

**Work that happens around the record** (card AS-CRAFT-COMMS)
| ID | Idiom | Applied when | Lane |
|---|---|---|---|
| K36 | App-specific activity types ("Call customer", "Check deposit"), scheduled by the owner's reminder rules | rules of kind `schedule` / `automation` | L, M |
| K37 | Overdue and "due this week" filters, plus a red decoration on late records | date + lifecycle | L, M |
| K38 | Email template + "Send by email" button for documents, only when the owner says send / email / share | owner wording, cited | L, M |
| K39 | Print button + report filename with the reference ("Order ORD-2026-0007.pdf"), extends K16 | K16 | M |

**Data that makes it ready on day one** (card AS-CRAFT-DATA)
| ID | Idiom | Applied when | Lane |
|---|---|---|---|
| K40 | Selection values the owner listed, kept in their order, with colours for states | dimension / lifecycle facts | L, M |
| K41 | Small lookup records the owner listed (e.g. "three branches: Ikeja, Lekki, Ajah") created as data, `noupdate` | dimension promoted to a record with listed values | L, M |
| K42 | Import template per record (columns in the form's order), so the owner can bring a spreadsheet straight in (pairs with Universal Ingest) | every `record` | L, M |
| K43 | Upgrade-safe module data: stable XML ids, `noupdate` on owner-editable data, no uninstall hook that deletes data | module lane | M |
| K44 | Performance hygiene: store a compute only when it is searched or grouped; no per-record queries in computes; batch writes in templates | K15 / K27 | M |

## Suggested upgrades (opt-in, never built without the owner's click)
A senior developer also says "you'll probably want…". These are **not** built: they appear as suggestion chips with one plain sentence each, and the owner clicks to add them (Promote, Pack §6.5). They never count as invented, because nothing exists until the owner asks. Card AS-UPGRADES. **Every** upgrade whose trigger matches is offered; none is dropped by a count limit (DEC-044). They are ranked by fit to the ledger shape: the top 3 show inline, the rest sit one click away under "More suggestions (n)", and each one can be added on its own or all together with "Add all". The inline count keeps the screen calm; it never decides what the owner can have. An upgrade that touches an excluded or future topic is never offered.
| ID | Upgrade | Offered when |
|---|---|---|
| U01 | Customer portal: customers see and sign their own records (`portal`) | records with a customer link |
| U02 | Online payment link on documents with an amount (`payment`, if installed or installable) | money + customer link |
| U03 | Invoice from this record (`account.move` from lines) | money lines + customer link; never if the owner excluded invoicing |
| U04 | Dashboard menu: pivot + graph + kanban on one board; spreadsheet dashboard if `spreadsheet_dashboard` exists in Community on that major (to verify) | ≥ 2 records with money or measures |
| U05 | Approval step (draft → to approve → approved) with a manager group | money above a threshold the owner mentioned, or "approve" in a rule |
| U06 | Calendar sync for appointment-like records (`calendar.event` link) | datetime + person + customer |
| U07 | Products and units of measure instead of free-text items (`product`, `uom`) | `line_of` with an item link and a quantity |
| U08 | Mobile-friendly kanban as the default view for field staff | owner mentions phones / on the road / drivers |
| U09 | Website form that creates records (`website` lead-style) | owner mentions enquiries / bookings from customers |
| U10 | Barcode on records (`barcode` field + scanning) | items / stock-like records |
| U11 | Multi-currency on money fields | snapshot has > 1 active currency |
| U12 | Audit view for owners: who changed what (tracking report filter) | access rules present |

## Quality systems around the build (not idioms; they check and explain the result)
| ID | System | What it does | Card |
|---|---|---|---|
| Q1 | Stock-parity score | For each view type, compare the generated app's features with the stock exemplar read by AS-CRAFT-CATALOG (e.g. our order form vs `sale.order`'s form). Report gaps per row. Bar: no gap that a stock app of the same shape has | AS-CRAFT-PARITY |
| Q2 | Senior Odoo reviewer (bounded LLM) | One optional call reviews the built design and may only propose rows from this catalog or upgrades from the U list, each with a reason; code validates and applies only catalog rows. Experiment X7: does it raise Tope's rating with craft score unchanged? Kept only if it does | AS-CRAFT-REVIEW |
| Q3 | Try it with your data | After sandbox install, load 5-20 rows from the owner's own spreadsheet (Universal Ingest) or clearly labelled Example rows, run a guided walkthrough (create → move state → print → smart button) and show it in the preview | AS-TRYIT |
| Q4 | Explain every idiom | Each craft item shows one plain sentence in the review screen ("Added a reference number so you can find orders by number") and can be switched off by the owner (`owner_override`) | AS-CRAFT-EXPLAIN |
| Q5 | Craft score live | K rows checked by RPC on 17-20 (already AS-CRAFT-SCORE) | AS-CRAFT-SCORE |

Never from craft: a business record, or a business field the owner did not state (priority, tags, ratings, extra parties). Craft fields are technical (`x_name`/reference, `state` only per K04, `active`, `company_id`, `currency_id`, counts, totals). Each carries lineage `craft:Kxx` and the scorer checks it against this table, so craft can never hide invention.
