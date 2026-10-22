# Upgrade: Upgrade rehearsal, Version diff explainer, Studio-to-code converter

Baseline `00_BASELINE.md` applies.

**Hard constraint from AGENTS:** "Do not clone a customer production database." The brief asks for "clone → upgrade". The honest design rehearses the customisations on fresh target-version sandboxes, and also on an upgraded copy the owner supplies. It never makes a clone itself (DEC-054).

<a id="vdiff"></a>
## VDIFF: Version diff explainer
Extends FA-A16 (version chips with why), CR-ITEM-04 (Code Runner version view, card CR-CLICK) and the compat registry `app/compat/odoo_versions.py`.
1. **User / job:**
   - A consultant asked "what changes for us if we move from 17 to 19?"
   - Value: a plain answer tied to *their* customisations, not generic release notes.
   - Metric: for each custom object, the explainer gives one of `unchanged | adapted automatically | needs a person` with a reason. 100% of reasons cite a compat-registry fact or a reference-catalog diff line, with no free AI claims.
2. **UX:**
   - Safety → Upgrade → "What changes between versions".
   - Pick from-version and to-version (any of 17/18/19/20 later than the current one).
   - List of the owner's custom objects, each with status, reason, and the exact difference in `DiffView` (for example `<tree>` → `<list>`, `attrs` → inline, `ir.rule` → `ir.access` on 20, field renamed or removed).
   - ⌘K: "Explain upgrade to 19".
3. **UI:** area 14 Safety (Stripe). A two-column `DiffView` collapses to stacked at 390.
4. **Security:**
   - Read-only. Reference catalogs come from Ingenium's own disposable stock sandboxes (`ingenium_ref_v17..v20`), never from a client.
   - AI is optional, only to rephrase a reason, fenced, and validated: the output must keep every cited token.
5. **Robustness:**
   - Reference catalogs are versioned JSON, rebuilt by a T0 script when the Odoo image digest changes.
   - The diff is pure: same inputs, same output.
6. **Data / API:**
   - Reference catalogs are files: `apps/api/app/upgrade/ref_catalogs/v{17,18,19,20}.json.gz`, with models, fields (type, relation, required), and view type names.
   - `GET /api/connections/{id}/upgrade/diff?to=19` → `{from, to, items[{kind, tech_name, status, reasons[{fact_id|catalog_ref, text}], before, after}]}`.
7. **Risks:** catalog size (approximately 5–15 MB per version [Inferred]), so gzip it and load lazily. Third-party modules are not in the reference catalogs; they are labelled "not checked: third-party module".

<a id="upg"></a>
## UPG: Upgrade rehearsal
Decomposition of BOLD-B1 (Odoo upgrade co-pilot). It extends SUITE-36 (rehearsal on a throwaway copy), O20-16 (spec replay) and `migration_assist.py` / `version_watch.py`.
1. **User / job:**
   - An agency planning a version move: "Prove our customisations survive 17 → 18 → 19 → 20 and tell us exactly what breaks."
   - Value: upgrades are the most expensive Odoo job, and breakage found early is cheap.
   - Metric:
     - On the reference rehearsal set (3 seeded customised DBs), every breakage that a person finds on the target sandbox is also reported (recall 100% on the set).
     - Auto-fixes pass Check on the target version.
     - Report p95 ≤ 20 min per hop on size class S.
2. **UX:**
   - Safety → Upgrade → "Rehearse".
   - Step 1: choose the target path, for example 17→18→19.
   - Step 2: choose the source:
     - (a) default: "My customisations on a fresh <version> sandbox", which replays the customisation spec Ingenium exports (O20-16).
     - (b) "An upgraded copy I already have". The owner connects a second, non-production connection marked Test copy (L2-PROVE-TESTCOPY).
   - Step 3: run, with progress per hop.
   - Report per hop: installed OK / adapted automatically (with diff) / broken (error text from Odoo, object, plain cause, suggested fix), plus a step-by-step upgrade plan with a time estimate.
   - Auto-fixes are offered as a plan for the *sandbox* only. Applying them to production is a separate promote after the real upgrade (human).
   - ⌘K: "Rehearse upgrade". History records each rehearsal.
3. **UI:** area 14 Safety plus the area 01 list. Hops show as a horizontal stepper (vertical at 390). The broken list uses `DataTable` with `Sheet` detail and `DiffView`.
4. **Security:**
   - Production is never written; the target is always an Ingenium sandbox or a connection marked Test copy.
   - It is refused on a connection marked Live.
   - Online: only source (b) is allowed, because the sandbox replay works for any host but the Online upgrade is Odoo's own service.
   - No customer data goes into Ingenium sandboxes; the replay is metadata plus Example records.
5. **Robustness:**
   - Each hop is independent. A failed hop stops later hops and keeps its report.
   - Sandboxes are created and dropped per run (`ingenium_upg_<run>`, INV-03), with a 2-hour cap.
   - It is idempotent on `(spec_hash, path)`.
6. **Data / API:**
   - Table `upgrade_rehearsals` (run, path, source, status, per-hop report JSON).
   - `POST /api/connections/{id}/upgrade/rehearsals {path:[18,19], source:"replay"|"copy", copy_connection_id?}` → run.
   - `GET …/rehearsals/{rid}` → `{hops[{to, status, items[{object, outcome: ok|adapted|broken, odoo_error?, cause, fix_plan?}]}], plan_steps[], estimate_h}`.
7. **Risks / DEC:**
   - DEC-054: no clone; OpenUpgrade (AGPL-3.0, outside the INV-09 allow-list) is not bundled or run by Ingenium.
   - Data migration is out of scope; that is said on screen.
   - Sandbox capacity: max 1 rehearsal per workspace at a time.

<a id="s2c"></a>
## S2C: Studio-to-code converter
Extends FA-S14 item 5 (export as an installable module) and the module export (`export_service.py`, `module_inspect.py`). Clean-room: it reads only the client DB's *metadata records* through the public ORM, such as `ir.model.fields` with `state='manual'`, `ir.ui.view` with an inherit, and `ir.model.data` with module `studio_customization` [Inferred: verify the module name live]. It never reads Studio's source.
1. **User / job:**
   - A client leaving Enterprise for Community, or putting Studio changes under version control: "Turn our Studio changes into a normal module."
   - Value: the Enterprise→Community downgrade market, and a reviewable module.
   - Metric: on a seeded DB with N manual fields, M inherited views and K automations, the generated module installs on a fresh sandbox of the same version and reproduces every object. The object-by-object diff shows zero missing objects.
2. **UX:**
   - Projects → "Turn Studio changes into a module".
   - Inventory of detected manual customisations, each with a checkbox.
   - Generate → module preview (file tree, manifest, `CodeBlock` per file) → "Test in sandbox" (Option A gate) → report → Download zip.
   - Install to production stays a human promote, and the screen explains the field takeover risk (DEC-055).
   - ⌘K: "Convert Studio changes".
3. **UI:** area 11 Code Runner (Zed, Cursor) for the file preview, and area 01 for the inventory.
4. **Security:**
   - The generated module contains metadata only: fields, views, menus, actions and automations in XML. It contains no Python unless the source has `state=code` server actions, which are included only as Option A authored code with the authoring gate.
   - Reading `studio_customization` records is metadata. It is not Enterprise source.
5. **Robustness:**
   - Deterministic generation from the inventory JSON.
   - Field takeover: the module declares the same `x_studio_*` names. The sandbox test installs over a copy *of the metadata* with Example data, so data loss on a real DB cannot be fully proven. The confirm dialog says so.
6. **Data / API:**
   - `GET /api/connections/{id}/studio-convert/inventory` → `{fields[], views[], menus[], actions[], automations[], unsupported[{record, reason}]}`.
   - `POST …/studio-convert/module {selection}` → `{module_id, files[], zip_sha256}`. Sandbox and promote reuse `promote.py` / `export_sandbox`.
7. **Risks:**
   - Views that Studio built with positional xpath break name-anchor rules (INV repo trap). The converter rewrites them to name anchors where it can, and lists the rest under `unsupported`.
   - DEC-055.
