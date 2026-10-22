# Understand: scan foundation, Database X-ray, Usage heatmap, Tech-debt score, Data health

Baseline: `00_BASELINE.md` (B1–B5) applies to every epic below. Each epic lists only what differs.

<a id="scan"></a>
## SCAN: Scan foundation (enabler, no owner-facing feature of its own)
1. **User / job:** every Understand, Operate and Localization epic needs the same thing: a read-only, budgeted, resumable scan that produces findings. That includes Data health, Usage, Tech-debt, SoD, Performance, Drift, Go-live and Statutory. Today each suite tool reads Odoo its own way (`suite_insights.py`, `health_check.py`, `production_readiness.py`). Value: one tested reader, one findings store and one UI list instead of eight. Metric: every NF scan uses `app/scans/reader.py`, enforced by a static test, and no scan bypasses the RPC budget.
2. **UX:** no screen of its own. It supplies `FindingsList` (grouped by severity, filter, export CSV) and `ScanStatus` (state machine B1) to every epic screen. ⌘K: "Run <scan>" is registered by each epic.
3. **UI:** area 01 lists (Linear, Stripe Dashboard). Built from `DataTable`, `StatusPill`, `Callout`, `Sheet` for the finding detail. Severity uses status tokens only, with text plus an icon and never colour alone.
4. **Security:** read-only. Samples are ids only. An exported finding CSV masks partner names and emails by default. The new routes go into `idor_registry`.
5. **Robustness:** this card set implements B4 (idempotency key, retries, timeouts, cancel, token bucket, sampling, partial).
6. **Data / API:**
   - Tables `scan_runs` and `scan_findings` (Alembic; DEC-052 retention).
   - `POST /api/connections/{id}/scans {scan_id, params}` → `ScanRun` (202, or 200 if the idempotent run exists).
   - `GET …/scans/{run_id}` → `ScanRun`.
   - `GET …/scans/{run_id}/findings?severity=&area=&cursor=` → `{items: [Finding], next_cursor}`.
   - `POST …/scans/{run_id}/cancel`.
   - `POST …/findings/{fid}/plan` → change-plan draft id (no write).
   - Registry: `app/scans/registry.py` maps `scan_id` → area functions.
7. **Risks / DEC:** a second job runner beside `jobs.py`. Mitigation: reuse `jobs.py` queueing. DEC-052 covers retention and stored values.

<a id="xray"></a>
## XRAY: Database X-ray
Extends SUITE-11 (handover pack PDF), SUITE-TOOL-3 ("What this database can do") and BOLD-B5 (knowledge capture). It does not duplicate the role x-ray (REG-SUITE-LOOK) and links to it instead.
1. **User / job:**
   - An agency consultant who has just been handed an unknown Odoo: "Tell me in 10 minutes what this database is, what was customised and what is risky."
   - An in-house admin who inherits a system.
   - Value: replaces a 1–3 day manual discovery. The free X-ray is also a sales opener (CP).
   - Metric: median time from connect to the first X-ray report is ≤ 10 min on size class M. At least 90% of custom objects (`x_` fields, custom views, automations, server actions, custom modules) are listed and match a live count.
2. **UX (consultant, admin; client sees the shared PDF only):**
   - Open the connection → Explore → X-ray tab → "Run X-ray (read-only)".
   - The report shows: apps installed (stock vs custom vs third-party by author/website metadata); models with record counts; customisations (fields, views, automations, server actions, reports, menus) grouped by app with created/last-changed dates; companies, currencies and localisation; users by role; integrations seen (`ir.config_parameter` keys masked, `fetchmail`/`ir.mail_server` presence); and a top-10 risks list linking to Tech-debt and Data health.
   - Export: PDF via SUITE-11 and Markdown.
   - States per B1. Huge data: counts only.
   - ⌘K: "Run X-ray", "Export X-ray".
   - History: runs are listed. No writes.
3. **UI:**
   - Area 09 Records tables (Attio, Notion) for the inventory, plus area 16 Charts for the composition bar.
   - Layout: summary strip of 4 numbers from the DB, then tabs Apps / Customisations / People / Integrations / Risks.
   - 390 px: tabs become a `Select`.
4. **Security:**
   - Odoo groups: Settings read (`base.group_system` is not needed; `base.group_erp_manager` read on `ir.module.module`, `ir.model`, `ir.model.fields`, `ir.ui.view`, `base.automation`, `ir.actions.server`, `ir.cron`, `res.users`) [Inferred: verify the minimum set on 17–20 in XRAY-LIVE].
   - `ir.config_parameter` values are never stored: key names only, masked.
   - The PDF has no record values.
5. **Robustness:** 9 areas, each with its own budget. Area failure → partial. p95 per B4.
6. **Data / API:** scan id `xray`. `GET /api/connections/{id}/xray/latest` → `XrayReport {run, apps[], models[{model, count, custom: bool}], customisations[{kind, tech_name, app, created, changed, by_ingenium: bool}], people{by_group}, integrations[], risks[Finding]}`. `GET …/xray/{run_id}/export?format=md|pdf`.
7. **Risks / open:**
   - Third-party module classification relies on `author`/`website` manifest metadata, which can be wrong. Label it "as declared by the module".
   - DEC-050 (scope) and DEC-052.

<a id="usage"></a>
## USAGE: Usage heatmap
Extends FA-S01 (fill rate), FA-S02 (hide unused menus) and SUITE-19/33 (unused apps, hot-spot heatmap; look-only today in REG-SUITE-LOOK).
1. **User / job:**
   - A consultant planning a clean-up or a licence review: "What do people actually use?"
   - Value: stop configuring apps nobody uses; find users who never log in.
   - Metric: the heatmap shows activity per app × week for 12 weeks, with record counts that match `read_group` on 17–20. At least 1 "hide unused menu" plan is generated per DB with unused apps.
2. **UX:**
   - Explore → Usage.
   - Heatmap: rows are apps/models, columns are weeks, cells are records created and changed.
   - People table: last login and records touched per user.
   - Fill rate per custom field.
   - Every row action: "Hide this menu for everyone" (plan via FA-S02) or "Hide this field on forms" (a view change plan; data kept; Odoo fields cannot be archived).
   - Honest label: "Odoo Community does not record page views. This shows records created and changed, and log-ins."
   - ⌘K: "Open usage". Undo per B1.
3. **UI:** area 16 Charts (Linear Insights, Vercel). The heatmap uses the UI-CHARTS-* build with a token ramp and a text value on focus. Each cell has an aria-label "Sales, week 41: 230 changes".
4. **Security:** reads `create_date`/`write_date` aggregates, `res.users` `login_date` and `res.users.log` counts. Per-user activity counts are personal data: they are visible to workspace admins only and never exported unmasked.
5. **Robustness:** `read_group` by `create_date:week` per model (top 40 models by count). The window defaults to 12 weeks.
6. **Data / API:** scan id `usage`. `GET …/usage/latest` → `{weeks[], cells[{model, week, created, changed}], users[{id, login_days, touched}], fields[{model, field, fill_rate}]}`.
7. **Risks / DEC:** DEC-053 (activity-based usage only; no click tracking addon).

<a id="debt"></a>
## DEBT: Tech-debt score and one-click cleanup
This is the decomposition of BOLD-B3 (Database doctor). It extends FA 1+.17 (model health), suite idea 10 (attachment housekeeping, `suite_upkeep.file_scan`) and the automation catalogue.
1. **User / job:**
   - A consultant or admin who wants to cut what makes upgrades and support expensive.
   - Value: a single 0–100 score with the reasons, and fixes that are safe by construction.
   - Metric: the score is reproducible (same DB, same score). Every finding with a fix produces a plan that passes Check on 17–20.
2. **UX:**
   - Housekeeping → Tech-debt.
   - Score card: number, trend and "what moves it".
   - Ranked findings, for example:
     - custom fields with 0% fill for 180 days;
     - views inheriting a missing anchor;
     - automations and crons that are inactive or have errored recently;
     - duplicate views on the same model and priority;
     - server actions with `state=code` (flag only; Option A);
     - orphan `ir.model.data`;
     - attachments with no res_id.
   - Multi-select → "Clean up selected" → one plan: Check (dry run) → Approve → Run → History with Undo.
   - Non-undoable steps (deleting fields) are excluded by default. They are offered as "archive" or "hide" instead (DEC-059 style).
3. **UI:** area 14 Safety (Stripe, Mercury) for the score card and confirm, area 09 for the table. The `ConfirmDialogV2` names the target and the count.
4. **Security:**
   - Writes only via plan.
   - Cleanup never touches stock (non-`x_`) fields or records owned by stock modules (`ir.model.data` module not in the custom set).
   - Money guard applies (no accounting objects in cleanup).
5. **Robustness:**
   - The score is a deterministic weighted sum. Weights are in `app/scans/debt_weights.yaml`, versioned and shown in the UI.
   - The plan is chunked at ≤ 50 objects (blast-radius check).
6. **Data / API:** scan id `debt`. `GET …/debt/latest` → `{score, weights_version, findings[Finding]}`. `POST …/debt/plan {finding_ids[]}` → `{plan_id, excluded[{id, reason}]}`.
7. **Risks:**
   - A false "unused" signal on fields that a report reads. Mitigation: "used by" from FA-S01, checking views, reports and automations before suggesting.
   - DEC-059 (undo scope).

<a id="dhealth"></a>
## DHEALTH: Data health
Extends SUITE-05 (data quality board, `suite_insights.data_quality`) and suite tool 6 (merge duplicates).
1. **User / job:**
   - Before go-live, migration or an audit: "Is the data clean enough?"
   - Value: catches the four classic failures: duplicate partners/products, orphans, wrong UoM categories, products without taxes or income/expense accounts.
   - Metric: each check reports the same count as a direct `search_count` on 17–20 (live test). The go-live gate consumes the result.
2. **UX:**
   - Explore → Data health. Checks run grouped by area:
     - Contacts: duplicates by normalised email, phone or VAT; missing country.
     - Products: missing taxes, missing income/expense account on product or category; UoM category mismatch between purchase and sale UoM.
     - Orphans: lines whose parent is archived, partners with no company on multi-company.
     - Accounting: missing default accounts on journals (read-only).
   - Each finding offers "See records" (opens Odoo filtered) or "Fix with a plan" where the fix is not an accounting write. Examples: merge duplicates via tool 6; set a tax on products as a plan, with drafts only, and never on products already used in posted invoices unless Tope's DEC says so. The default is to flag only.
3. **UI:** area 09 Records tables. The finding detail is in a `Sheet` with sample ids and a link to Odoo.
4. **Security:**
   - Product account and tax fields are tier-1 accounting fields. The plan path is refused by the money guard unless the field is outside tier 1.
   - The default is report plus a link, no write (DEC-061 does not apply here; see the risks).
5. **Robustness:** duplicate detection runs server-side per page of 500 with normalisation (lowercase, strip, E.164-like digits only). Fuzzy matching is capped at 20k records, otherwise exact-only, with a label.
6. **Data / API:** scan id `data_health`. `GET …/data-health/latest` → `{areas[{area, findings[Finding]}]}`. Merge plans reuse the suite tool 6 endpoints.
7. **Risks:** writing taxes or accounts on products is sensitive. Open question folded into DEC-050: keep it report-only in v1 (recommended).
