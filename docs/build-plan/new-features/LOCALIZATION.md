# Localization: Nigeria pack, Statutory compliance check

Baseline `00_BASELINE.md` applies. Decomposition of BOLD-B8 (compliance packs: Nigeria). It extends 5B-05 (`l10n_ng` adopt by xmlid), the CBN gold module (`currency_rate_cbn`, stock `res.currency.rate`), the WHT markup class (`ai_markup_wht_class.py`), `invoicing_l10n.py`, IMP-OPENING and the AGENTS rule "statutory compute-only connector recipes".

**Facts policy (INV-08):**
- Tax rates, bands and authority names change by law. None are hard-coded. They live in `app/l10n_ng/rules/ng_rules.yaml`. Each entry has `value`, `effective_from`, `source` (law/circular + URL) and `reviewed_by`.
- Until Tope supplies an adviser-reviewed table (DEC-061), checks verify only *presence and structure*, and any rate shown is labelled "Example".
- [Inferred, verify before use: VAT is 7.5% (Finance Act 2019). The Nigeria Tax Act 2025 and Nigeria Revenue Service Act 2025 may rename FIRS to NRS and change WHT and PAYE rules from 2026. Odoo Community 17–20 has no payroll app (`hr_payroll` is Enterprise).]

<a id="ng"></a>
## NG: Nigeria pack (VAT, WHT, e-invoicing readiness, PAYE/pension compute, local bank statements)
1. **User / job:**
   - A Nigerian SME or the agency serving it: "Set Odoo up correctly for Nigerian tax, get ready for e-invoicing, and stop re-typing bank statements."
   - Value: home-market wedge, and compliance is a must-buy.
   - Metric:
     - On a fresh DB with country NG, the pack yields: taxes and fiscal positions per the rules table (compared by xmlid when the stock `l10n_ng` exists, otherwise by name and amount); WHT configured as stock withholding where the version supports it, otherwise as a negative-tax group [Inferred, verify per version]; and company TIN present.
     - Bank conversion: 100% of rows of each supplied sample statement convert and pass `try_loading` (dry run) on 17–20.
2. **UX (admin, consultant):** Setup → Country pack → Nigeria. Steps:
   - (1) Detect: country, `l10n_ng` installed or available, current taxes.
   - (2) Proposed plan: install or adopt `l10n_ng` by `try_loading` (5B-05); taxes, fiscal positions, WHT; TIN fields; CBN rate source (gold).
   - (3) Check → Approve → Run (drafts only; posted items never touched).
   - E-invoicing readiness: a checklist of data prerequisites (TIN on company and customers, address, VAT on lines, invoice sequence, currency) plus an export of a sample invoice payload in the mapping DEC-062 chooses. There is no transmission.
   - PAYE/pension: "Compute payroll deductions" takes an employee list (from `hr.employee` if installed, or an uploaded sheet), computes PAYE and pension per the rules table, and exports CSV/PDF. No journal entries are made (DEC-064).
   - Bank statements: upload a statement (CSV/XLSX/PDF text), bank detected or picked, preview the normalised lines, validate with Odoo `base_import` `try_loading` (dry run), then download the Odoo-ready CSV or open Odoo's import. Ingenium does not create statement lines (DEC-063).
   - ⌘K: "Nigeria pack", "Convert bank statement".
3. **UI:** area 06 onboarding (Stripe) as the stepper. Area 09 for previews. Money uses tabular figures and `NGN`, formatted from workspace locale.
4. **Security:**
   - Taxes, fiscal positions and accounts are accounting configuration. They are created as new records only, under the money guard. Existing taxes used on posted documents are never modified; a new version is created instead and the old one archived only if unused [Inferred: verify the archive guard].
   - Bank files and payroll sheets are PII: processed in memory, not stored beyond the job (default 24 h, then purged), and never sent to AI.
   - Rule text sent to AI (explanations only) is fenced. Rates come only from YAML.
5. **Robustness:**
   - Bank parsers are pure functions with golden tests from anonymised samples (DEC-063).
   - Unknown columns → STOP with a mapping screen, never a guess.
   - The plan is idempotent by xmlid or name+amount.
   - Versions: 17–20 tax field differences go through compat.
6. **Data / API:**
   - `GET /api/connections/{id}/l10n-ng/detect` → `NgDetect`.
   - `POST …/l10n-ng/plan` → `NgPlanResponse`. This POST has no request body.
   - Models. A contract test compares these field names and no others. Pinned 2026-10-22.
     - `NgDetect {country, l10n_ng_installed, l10n_ng_available, taxes}`. `country` is the company country code. `l10n_ng_installed` and `l10n_ng_available` are booleans. `taxes` is `[NgTax]`.
     - `NgTax {id, name, amount, type_tax_use}`. These are the current taxes from setup step 1.
     - `NgPlanResponse {plan_id}`.
   - `GET …/l10n-ng/einvoice-readiness` → `{items[Finding], sample_payload}`.
   - `POST …/l10n-ng/payroll-compute {upload_id|from_hr: bool, period}` → `{rows[{employee_ref, gross, paye, pension_employee, pension_employer}], rules_version}`.
   - `POST …/l10n-ng/bank/convert {upload_id, bank?}` → `{bank, rows[], csv_id, try_loading:{ok, messages[]}}`.
   - Tables `ng_rule_versions` and `bank_jobs` (TTL).
7. **Risks / DEC:**
   - DEC-061 (rules source), DEC-062 (e-invoicing transmission), DEC-063 (bank samples), DEC-064 (payroll compute only).
   - Legal exposure: every screen carries "Check with your tax adviser" and the `reviewed_by` of the rules.

<a id="stat"></a>
## STAT: Statutory compliance check
1. **User / job:**
   - An owner or auditor: "Are we compliant today?"
   - Value: recurring, cheap, and it feeds Go-live.
   - Metric: each check maps to one rule id in `ng_rules.yaml` with its source. Results match direct `search_count`s on the live DB.
2. **UX:**
   - Safety → Statutory (country NG). Read-only checks:
     - company TIN set;
     - customers with a TIN on B2B invoices in the last 90 days (count missing);
     - invoices without VAT on taxable lines;
     - WHT configured;
     - vendor bills from WHT-liable vendor categories without WHT;
     - CBN rate fresh (≤ 1 business day);
     - fiscal year and lock dates set;
     - e-invoice readiness items.
   - Each finding links to "See records" in Odoo. The fix is a plan only for configuration, never for posted documents.
   - Monthly schedule optional.
   - ⌘K: "Statutory check".
3. **UI:** area 14 Safety, with an icon and text per status.
4. **Security:** read-only. It reads `account.move` headers and taxes in aggregate (`read_group`) and never line values into the App DB. Counts only.
5. **Robustness:** `read_group` on `account.move` by state and tax presence, over a 90-day window by default.
6. **Data / API:** scan id `statutory_ng`. `GET /api/connections/{id}/statutory/latest` → `{rules_version, findings[Finding{evidence.rule_id, evidence.source}]}`.
7. **Risks:** rule drift with new law. The rules file has `effective_from`, and the UI shows "Rules as of <date>, reviewed by <name>".
