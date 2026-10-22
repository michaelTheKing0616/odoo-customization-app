# Integrate: Connector builder, Data migration studio

Baseline `00_BASELINE.md` applies.

<a id="cxb"></a>
## CXB: Connector builder (Paystack, Flutterwave, WMS, banks)
Mostly covered by Bridge:
- BR-ITEM-01: the gallery includes Paystack and Flutterwave.
- BR-AISPEC-DRAFT, -VALIDATE and -EVAL: API docs → connector descriptor, validated against the document.
- BR-DRIFT, `bridge/connector.py`, `bridge/spec_import.py`, `bridge/live_probe.py`.

FACTS: Paystack has no stock Odoo module, so Paystack flows go through Bridge. This epic adds only the deltas:
- a connector test kit (contract and replay tests every connector must pass);
- certified Paystack and Flutterwave flows into stock Odoo models;
- a generic WMS REST template;
- a bank-feed template behind DEC-065.

1. **User / job:**
   - A consultant wiring a Nigerian client's payments and warehouse into Odoo without code.
   - Value: payments reconciliation is the top integration request for African SMEs [Inferred from the BR gallery order and handover §9.2].
   - Metric:
     - Each certified connector passes the test kit: auth, pagination, idempotent webhook replay, signature check and rate-limit backoff.
     - Paystack and Flutterwave test-mode events create the expected stock records on a live sandbox: draft `account.payment` is *not* created (money guard). Instead an `x_` staging record or a Bridge inbox item for human reconciliation, per DEC-065.
2. **UX:**
   - Bridge → Gallery → Paystack → "Connect (test mode first)" → paste a test key (stored encrypted) → map events to Odoo targets (the default map is shown) → test with a replayed sample webhook → go live per workspace.
   - Builder for others: paste an OpenAPI spec or docs (the existing BR-AISPEC flow) → the test kit runs → certify.
   - ⌘K: "Add connector".
3. **UI:** area 10 Bridge flow canvas (n8n, Make). Existing BR-CANVAS components; nothing new.
4. **Security:**
   - Partner keys are stored with the Bridge secrets store and never written to Odoo (AGENTS: do not write partner API keys).
   - Webhook signature verification is mandatory (HMAC per provider docs).
   - Inbound payloads are untrusted, so they are validated against the descriptor schema and fenced if they reach AI.
   - No payment or posted-entry writes.
   - SSRF guard on outbound calls (SEC-SSRF).
5. **Robustness:**
   - Webhook replay is idempotent on the provider event id.
   - Dead letter uses `MAX_ATTEMPTS 6` (`bridge/delivery.py`).
   - It honours provider 429s with backoff.
6. **Data / API:**
   - Reuses Bridge tables.
   - New: `connector_certifications` (connector_id, kit_version, results JSON, certified_at).
   - `POST /api/bridge/connectors/{cid}/certify` → results.
   - `GET /api/bridge/connectors/{cid}/certification`.
7. **Risks / DEC:**
   - DEC-065: targets and the payment landing model.
   - Provider docs must be read from official sites at build time, and the descriptor cites them (INV-08).

<a id="mig"></a>
## MIG: Data migration studio (QuickBooks, Sage, Excel, other ERP; dry run and reconciliation)
Extends FA 8.4 (migration mode; FA-S08 itemise), IMP-* (IMP-MATCH, IMP-BIG, IMP-CLEAN, IMP-TPL, IMP-OPENING), EL-IMP-RECONCILE (counts and sums reconciliation), `data_import.py`, `suite_import.py`, and the money guard rule "opening balances via try_loading only".
1. **User / job:**
   - A consultant moving an SME off QuickBooks, Sage or spreadsheets: "Bring customers, vendors, products, open invoices and opening balances in, prove it matches, and let me re-run until it does."
   - Value: migration is part of every new Odoo project.
   - Metric:
     - For each supported source sample, a dry run reports 0 unmapped required columns.
     - Reconciliation shows count and sum equality per entity (partners, products, open AR/AP totals, trial-balance opening totals) between file and Odoo after import on 17–20 test DBs.
     - Re-running is idempotent: no duplicates, by Ingenium external ids.
2. **UX:**
   - Import → Migration studio.
   - Pick the source (QuickBooks Online export, Sage 50 CSV, Excel workbook, Other ERP CSV) → upload files → auto-mapping per entity (source profile) with manual override → dependency order (partners → products → open documents → opening balances) → dry run (`try_loading`) per entity with row-level errors → fix in place or re-upload → import to the *test copy* → reconciliation report → repeat → when green, the same package goes to production through IMP-OPENING rules (drafts only, money guard) and a human confirm.
   - ⌘K: "New migration".
3. **UI:** area 09 Records tables (Airtable) for mapping and errors, area 16 for the reconciliation bars.
4. **Security:**
   - Files are client data, so they are kept for the job TTL (7 days by default, DEC-066), encrypted at rest and never sent to AI.
   - AI may suggest column mappings from *headers only*, fenced and validated against the live schema.
   - Open invoices import as drafts. Opening balances use the existing IMP-OPENING path only. There are no posted writes.
5. **Robustness:**
   - Batches of 500 with resume (IMP-BIG).
   - External ids `ingenium_mig_<job>_<entity>_<source_key>` make re-runs idempotent.
   - Partial failure keeps imported batches and lists failed rows. Rollback archives the batch's records where allowed.
6. **Data / API:**
   - Tables `migration_jobs` and `migration_profiles` (source, entity, column map, transforms).
   - `POST /api/connections/{id}/migrations {source}`.
   - `POST …/migrations/{mid}/files`.
   - `GET …/migrations/{mid}/mapping`.
   - `PUT …/migrations/{mid}/mapping`.
   - `POST …/migrations/{mid}/dry-run` → `{entities[{entity, rows, errors[{row, column, message}]}]}`.
   - `POST …/migrations/{mid}/import {target_connection_id}` (409 if Live without confirm).
   - `GET …/migrations/{mid}/reconcile`.
7. **Risks:** source export formats vary by version and region, so profiles need real samples (DEC-066). There is no direct QuickBooks or Sage API in v1: files only.
