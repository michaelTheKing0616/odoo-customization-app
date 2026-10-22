# Delivery: Fit-gap, BRD/SOW → costed plan → applied config, Auto manuals, UAT, Go-live readiness

Baseline `00_BASELINE.md` applies. These epics form one chain: requirements → fit-gap → costed plan (SOW) → applied config (Job Autopilot, sandbox) → UAT → go-live.

Shared parser: `app/delivery/requirements.py` reuses `ingest/` uploads (BRD/SOW in PDF, DOCX or text), fenced. Each requirement keeps its source quote (the AS-CONTRACT-QUOTES rule: quotes only from the original words).

<a id="fitgap"></a>
## FITGAP: Fit-gap analysis
New. It reuses the stock catalog (`ai_stock_catalog`), the live schema packet (GND) and Job Autopilot classification. It overlaps FA 13+.5/6 (discovery questionnaire, scope guard), which are covered by the FA-S13 itemise.
1. **User / job:**
   - A presales consultant with a client BRD: "For each requirement, is it standard Odoo, configuration, custom work, or not possible in Community, and how much effort?"
   - Value: fit-gap takes 2–5 days by hand.
   - Metric:
     - On a labelled set of 120 requirement lines (written by Tope or the team, never holdout_fresh), class agreement is ≥ 85% and the "impossible" class has 0 false "standard".
     - Every "standard" cites an installed or installable stock module, model or field from the catalog.
2. **UX:**
   - Delivery → Fit-gap → upload BRD or paste text.
   - Parsed requirement table: quote, class chip, evidence (module / model / field / setting, or "not in Community: <reason>"), effort range and confidence. The consultant can override any class with a reason, and overrides are kept.
   - Export: XLSX/CSV and PDF.
   - "Send to costed plan" opens SOW.
   - States per B1, with a huge-BRD case: more than 400 lines are processed in pages, with progress.
   - ⌘K: "New fit-gap".
3. **UI:** area 09 Records tables (Airtable) with inline override using `Select`, and the evidence `Sheet`.
4. **Security:**
   - The BRD is untrusted: fenced, and never executed.
   - Classes are chosen by the model but *validated* by code. "standard" or "config" needs catalog evidence, otherwise it is downgraded to "custom (unverified)". "impossible" needs a compat or Enterprise-only fact id from `app/delivery/community_limits.yaml`, which is written by people with sources.
   - No record data is read.
5. **Robustness:**
   - Chunked AI calls (20 lines per call) through `ai_client` with the cache (CACHE-SEM). A chunk failure → those lines are marked "not classified" and retryable.
   - It is idempotent on `(doc_sha256, catalog_version)`.
6. **Data / API:**
   - Tables `fitgap_docs` and `fitgap_lines` (class, evidence JSON, effort_low/high hours, override, override_reason, quote).
   - `POST /api/connections/{id}/fitgap {upload_id|text}` → job.
   - `GET …/fitgap/{doc_id}` → `{lines[{id, quote, cls: standard|config|custom|impossible, evidence[], effort_h:[lo,hi], confidence, override?}]}`.
   - `PATCH …/fitgap/{doc_id}/lines/{lid} {cls, reason}`.
7. **Risks:** the effort table needs real consultant data. Until then, effort is labelled "Example" (DEC-056).

<a id="sow"></a>
## SOW: BRD/SOW → costed plan → applied config
Extends CP-BUILDER (BRD/SOW → demo plan), Job Autopilot (FA-S13) and SUITE-26 (run time estimate).
1. **User / job:**
   - A consultant turning a fit-gap into a priced proposal and then into a configured sandbox.
   - Value: quote, plan and build stay in sync.
   - Metric:
     - Cost total equals the sum of line estimates times the rate card, exactly (unit test).
     - The applied sandbox passes the Job Autopilot RPC process smoke for every "standard" or "config" line that has a smoke recipe.
2. **UX:**
   - Delivery → Plan.
   - Lines from fit-gap are grouped into phases. Rate card from Settings (DEC-056). Contingency %. Totals with a range.
   - "Export SOW" produces a PDF/DOCX with scope, exclusions (impossible and out-of-scope lines) and assumptions.
   - "Build in sandbox" hands config lines to Job Autopilot (sandbox only).
   - The status per line comes back: built / needs a person / failed.
   - Production promote stays human.
   - ⌘K: "Export SOW".
3. **UI:** area 15 Settings and Billing (Linear, Stripe) for the money layout. Numbers use tabular figures. Currency comes from the workspace setting.
4. **Security:**
   - Costs are workspace-private.
   - Sandbox only. `write_mode=production` is refused (AGENTS).
   - The SOW export contains no client record data.
5. **Robustness:**
   - Decimal arithmetic, half-up rounding to the currency's minor unit.
   - Building hands off to the existing Job Autopilot (its retries and smoke).
6. **Data / API:**
   - Tables `rate_cards` and `sow_plans` (lines, phase, rate, hours range, contingency, status).
   - `POST /api/connections/{id}/sow {fitgap_doc_id}` → plan.
   - `GET …/sow/{id}` → `{phases[{name, lines[{fitgap_line_id, hours:[lo,hi], rate, cost:[lo,hi], build_status}]}], totals}`.
   - `POST …/sow/{id}/export?format=pdf|docx`.
   - `POST …/sow/{id}/build` → Job Autopilot job id.
7. **Risks:** DOCX output needs a FOSS library (python-docx, MIT). Its dependency is added only with the build card and a licence check.

<a id="manual"></a>
## MANUAL: Auto user manuals and videos per role
Decomposition of BOLD-B7 (training mode). It extends FA-A9 (guided tours) and touch 81.
1. **User / job:**
   - A consultant handing over to client staff: "A manual per role (sales rep, warehouse clerk, accountant) built from *their* screens."
   - Value: training docs are rarely written.
   - Metric:
     - Every menu visible to a role (from the role x-ray) appears in that role's manual with its form fields.
     - The page count for a role equals its visible top-level menus (test).
     - Screenshots come only from a sandbox with Example data (DEC-057).
2. **UX:**
   - Delivery → Manuals.
   - Choose roles from the DB's groups, then generate.
   - Preview: chapter per app, page per action (what it is for, steps, fields in plain words, required fields, buttons).
   - Edit text inline. Export PDF and Markdown.
   - Videos come later (DEC-057) and are hidden until then: there is no dead button.
   - ⌘K: "Generate manual".
3. **UI:** area 19 Docs (Stripe docs) with a left contents tree and a reading column at 65ch.
4. **Security:**
   - Role → menus comes from group access only.
   - Field labels come from the schema, never record values.
   - Screenshots come only from `ingenium_*` sandboxes seeded with Example data and labelled "Example".
   - AI writes the explanations from schema plus view arch (fenced), and a validator removes any field not in the view.
5. **Robustness:** per-role generation is a job. Each page is cached by `(view_arch_hash, lang)`.
6. **Data / API:**
   - Table `manuals` (role, version, pages JSON, edits).
   - `POST /api/connections/{id}/manuals {group_ids[]}` → job.
   - `GET …/manuals/{mid}` → `{role, chapters[{app, pages[{action, title, purpose, steps[], fields[{label, required, help}]}]}]}`.
   - `GET …/manuals/{mid}/export?format=pdf|md`.
7. **Risks:** a video needs a recorder and an encoder: Playwright (Apache-2.0) and an LGPL ffmpeg build only (DEC-057).

<a id="uat"></a>
## UAT: UAT scripts, run against the DB, sign-off pack
Extends SUITE-40 (client sign-off, PlanLedger), FA 13+.7 (acceptance checklist) and the Job Autopilot RPC process smoke (quote → confirm → invoice wizard).
1. **User / job:**
   - A consultant and the client's key users proving that the configured system does what the SOW promised.
   - Value: replaces spreadsheets of test steps, and the signed pack ends scope arguments.
   - Metric:
     - Each SOW line in scope has ≥ 1 script.
     - Automated scripts run on the test copy or sandbox and record pass/fail with evidence ids.
     - The sign-off pack hash is recorded in the audit chain.
2. **UX:**
   - Delivery → UAT. Scripts are generated from SOW lines (steps, expected result, data needed). There are two kinds:
     - "automated" runs RPC steps through the smoke recipes;
     - "manual" is a checklist for a person.
   - Run all automated scripts on the chosen *test* connection or sandbox, with live progress.
   - Manual results are entered by key users in Client mode.
   - The sign-off pack is a PDF with results, failures with notes, and signer names and time. The client signs via SUITE-40.
   - ⌘K: "Run UAT".
3. **UI:** area 05 Approvals (Linear Inbox) for the run and sign queue, and area 09 for the scripts.
4. **Security:**
   - Automated runs create records, so they are refused on a connection marked Live (DEC-058). On a Live connection only read-only checks run.
   - Signers authenticate with Ingenium accounts, with a second approver if the workspace requires it (SEC-2APPROVER).
5. **Robustness:**
   - Each script runs in its own sandbox transaction scope where possible, otherwise it creates records tagged `ingenium_uat_<run>` that are archived after the run.
   - A failed step stops that script, not the run.
6. **Data / API:**
   - Tables `uat_scripts` (sow_line_id, kind, steps JSON, expected) and `uat_runs` (connection, results JSON, pack_sha256, signed_by).
   - `POST /api/connections/{id}/uat/generate {sow_id}`.
   - `POST …/uat/runs {script_ids[], target_connection_id}` → run (409 `HOSTING_NOT_SUPPORTED` / `CONFLICT` if the target is Live).
   - `GET …/uat/runs/{rid}`.
   - `POST …/uat/runs/{rid}/pack` → PDF + sha.
7. **Risks:** a smoke recipe does not exist for every line, so those lines become manual and are labelled.

<a id="golive"></a>
## GOLIVE: Go-live readiness check
Extends EL-JOB-GOLIVE (checklist + sign-off), O20-13 (production checklist), `production_readiness.py`, SUITE-48 (import health after go-live) and FA 13+.8 (post-go-live watch).
1. **User / job:**
   - A consultant and the client owner deciding "can we switch on Monday?"
   - Value: one honest gate across data, access, statutory, backups and UAT.
   - Metric:
     - The readiness verdict is reproducible.
     - Every red item links to the check that produced it.
     - The post-go-live watch runs daily for 14 days and stops itself.
2. **UX:**
   - Delivery → Go-live. Checklist groups:
     - Data health (DHEALTH)
     - Access and SoD (SOD)
     - Statutory (STAT, if Nigeria)
     - UAT pass rate (UAT)
     - Mail and outgoing server
     - Sequences and numbering (`suite_insights.numbering_check`)
     - Backups and snapshot drill (`production_readiness`)
     - Users invited and logged in
   - Verdict: Ready / Ready with risks (listed and accepted with a name) / Not ready.
   - "Start the 14-day watch" runs a daily scan subset and notifies (A10 notification centre when it exists, otherwise Home "Needs you").
   - ⌘K: "Go-live check".
3. **UI:** area 04 Home (Stripe, Vercel) for the verdict card, and area 05 for the accept-risk flow.
4. **Security:**
   - Read-only. Accepting a risk is an audit-chain entry with name and reason.
   - The watch uses the same budgeted scans.
5. **Robustness:** the verdict is computed from the latest successful runs no older than 24 hours. Stale inputs show "re-run".
6. **Data / API:**
   - Table `golive_reviews` (inputs run ids, verdict, accepted risks).
   - `GET /api/connections/{id}/golive` → `{verdict, groups[{id, status, findings[], source_run_id, stale: bool}]}`.
   - `POST …/golive/accept {finding_id, reason}`.
   - `POST …/golive/watch {days:14}`.
7. **Risks:** the dependency fan-in is large. GOLIVE reads whatever scans exist and shows "not checked" for missing ones, never green.
