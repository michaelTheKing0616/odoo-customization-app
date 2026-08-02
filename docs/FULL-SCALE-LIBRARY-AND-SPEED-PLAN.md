# Plan: Full-Scale Library Product + Faster Customization

> **Status:** Implementation boxes closed (2026-07-27) — production paths verified; optional polish only  
> **Created:** 2026-07-27  
> **Owner:** Temitope / Cursor agents  
> **North star:** A user can scaffold, refine, sandbox-validate, and promote a **production-grade Library Management** app from this platform — and every other custom app benefits from the same speed layer.

---

## 0. How to use this document

1. Treat checkboxes as the source of truth for remaining work.
2. After each session: tick completed items, move blockers into §14, update `STATE.md` with a one-line pointer here.
3. Do **not** fork Enterprise Studio or MNametissa ports. Stay on public ORM/RPC + clean-room patterns.
4. Prefer **free/OSS**: existing FastAPI/Next/Jinja/Docker stack; optional **Ollama** (local); light in-process jobs (no Celery day one); no paid LLM hard dependency.

**Related docs:** `skills/module-interop.md`, `skills/studio-parity.md`, `skills/advanced-actions.md`, `DEPLOY.md`, `MEMORY.md`, `STATE.md`.

---

## 1. Goal definition

### 1.1 “Full-scale library product” (acceptance)

A Library app is **full-scale** for v1 when an operator can, without hand-writing an Odoo addon from scratch:

| Capability | Acceptance criteria |
|------------|---------------------|
| **Catalog** | Books, categories, authors (partner or dedicated), copies/availability, status |
| **Circulation** | Loans (member, book, dates, returned); overdue visibility |
| **Barcode** | Scan/enter barcode (ISBN or copy barcode) to find/loan a book in Odoo UI |
| **Fines** | Configurable fine rules + Python (Option A) that computes amount on return/overdue |
| **Email reminders** | Polished automation: due-soon / overdue emails to member (mail templates + scheduled action or automation) |
| **Kanban** | Loan or book pipeline board (designer or template arch) |
| **Chatter** | `mail.thread` / activities on Book and/or Loan |
| **Reporting** | At least: loans by period, overdue list, popular books (list/pivot or QWeb report export) |
| **Multi-company** | Record rules / company fields so branches see only their stock/loans when multi-company is on |
| **Portability** | Export → sandbox → promote as installable module with menus, ACL, depends |

### 1.2 “Much faster customization” (acceptance)

| Lever | Acceptance criteria |
|-------|---------------------|
| App wizard | One click: Library / CRM lite / Inventory lite → models+fields+views+menus+ACL |
| NL → ModuleSpec | Optional Ollama: sentence → draft ModuleSpec → confirm → apply/sandbox |
| Live preview | Designer shows real Odoo form/list for the model being edited |
| Draft/apply | Edit project offline; Apply runs batched RPC with diff + snapshots |
| Async jobs UI | Sandbox/promote return `job_id`; UI polls until done |
| Smarter defaults | Required M2O `on_delete`; depends inference; menus/ACL auto (extend) |
| Domain/selection builders | Visual editors; no raw domain string required for common cases |
| One2many from parent | “Add loans on Book” creates inverse O2M in one gesture |
| Gates | Playwright confirm + sandbox smoke/extension stay green in CI |

### 1.3 Explicit non-goals (this program)

These stay **out of scope** (intentional — not unfinished work):

- [x] **Out of scope:** Enterprise Studio clone / OEEL source
- [x] **Out of scope:** Celery as default queue (in-process jobs + optional light queue later)
- [x] **Out of scope:** Paid cloud LLM required for core flows

**Odoo versions (platform vs this program):** Platform multi-version is **live** (Community **16–19**; GA **17+18+19**; **16** experimental) — see `docs/MULTI_VERSION_ODOO_PLAN.md` and `docs/HANDOVER_UNFINISHED_WORK.md`. This Library reference vertical stays **19-primary**: full-scale Library smoke, UAT, and CI gates remain **19-centric**; other majors use the shared compat layer and their own gates.

---

## 2. Current baseline (already proven)

Tick = done as of 2026-07-27 Library smoke.

### 2.1 Platform
- [x] Connections + encrypted secrets + introspection
- [x] Model/field create (`x_*`), inject views (**inherit** default), designer form/list/search
- [x] Automations (safe update/activity/create_record + Option A code path)
- [x] Access rights + record rules (create/update/delete + confirm)
- [x] Export zip (`_name` + `_inherit` extensions), depends inference, module picker
- [x] Sandbox → promote → uninstall; async job API; sale/account preload option
- [x] Auth / rate limit / audit; Playwright confirm harness; CI unit + e2e
- [x] Library live proof: Category/Book/Loan + sample data
- [x] Library zip sandbox install (`library_mgmt_demo`)
- [x] Required M2O → `on_delete=restrict`
- [x] menus.xml attribute spacing fix

### 2.2 Gaps vs full-scale library (from product review)
- [x] Barcode field + Books-by-barcode action (full scan-to-loan UX still manual)
- [x] Fine calculation (Option A in library zip)
- [x] Email reminders (overdue + due-soon templates + cron)
- [x] Kanban board designer + Loan kanban in template
- [x] Chatter / `mail.thread` (+ activities) checkbox on models
- [x] Reporting: Active Loans + pivot/graph + web stats strip + QWeb loan receipt
- [x] Multi-company library policies (`multi_company` flag)

### 2.3 Gaps vs speed layer
- [x] App wizard / templates (API + wizard UI + multi-company checkbox)
- [x] NL → ModuleSpec (Ollama optional draft)
- [x] Live Odoo preview in Designer (Open-in-Odoo v1; iframe when same-origin allows)
- [x] Draft projects + apply/diff (v1)
- [x] Async jobs **UI** (`pollJob` on sandbox)
- [x] Domain / selection builders
- [x] One2many-from-parent gesture
- [x] Smarter defaults: required M2O on_delete + builder on_delete picker

---

## 3. Workstreams overview

```
WS-A  Full-scale Library domain capabilities
WS-B  Speed layer (wizard, preview, draft, AI, builders)
WS-C  Platform hardening that both streams need
WS-D  Verification (tests, sandbox gates, docs)
```

**Dependency rule:** WS-B wizard/templates should land **before** polishing Library-only Python, so Library ships as a **template** that exercises A+B together.

**Recommended build order (ROI):**
1. WS-B1 App wizard + Library template  
2. WS-B3 Live preview  
3. WS-A chatter/mail + kanban (template + designer)  
4. WS-B4 Draft/apply  
5. WS-B2 NL → ModuleSpec  
6. WS-A fines + email + barcode + reports + multi-company  
7. Remaining builders (domain/selection/O2M) interleaved  

---

## 4. WS-A — Full-scale Library capabilities

### A1. Library domain template (scaffold)
**Outcome:** `templates/library` (or ModuleSpec factory) creates the canonical schema.

- [x] Spec: Category, Book (copies, ISBN/barcode, status, author, category), Loan (member, dates, returned, fine fields stub), optional Copy/Item model if barcode-per-copy
- [x] Default form/list/search + menus + ACL
- [x] Wire into App wizard (B1)
- [x] Document operator flow in `skills/library-app.md`

**Files (expected):** `packages/module-generator/.../templates_apps/`, `apps/api/app/app_templates.py`, `apps/web/.../wizard/`

### A2. Chatter / mail.thread / activities
**Outcome:** Checkbox on model create: “Log chatter & activities”.

- [x] Client: support mixins on custom models (`mail.thread`, `mail.activity.mixin`) via `_inherit` list in generator + live create path (verify Odoo 19 RPC/`ir.model` constraints)
- [x] Builder UI checkbox
- [x] Export: `depends` includes `mail`
- [x] Library template enables chatter on Book + Loan
- [x] Integration smoke on Odoo 19 (`./docker/run-library-functional-uat.sh`)

**Risk:** Live `ir.model` may not attach mixins the same way as Python `_inherit` — prefer **python install_mode** for mixin models; document data-mode limits.

### A3. Kanban designer / template
**Outcome:** User can ship a kanban for Loan status or Book status.

- [x] `view_arch.py`: render kanban arch (card: title + status + member)
- [x] Designer: view type `kanban` + stage field picker (selection or many2one)
- [x] Library template includes Loan kanban by `x_status` or dedicated stage
- [x] Unit tests for kanban render; integration create view

### A4. Barcode
**Outcome:** Find/loan by barcode without custom JS modules if possible.

- [x] Field type/widget: barcode on Book (`x_barcode` / ISBN) — Odoo widget `barcode` or char + action
- [x] Server action / automation: on scan context open loan wizard (document limitations of Community widgets)
- [x] **N/A — stock `barcode` widget sufficient**; no custom OWL/JS snippet required for v1
- [x] Library template includes barcode field + list search

### A5. Fine calculation (Option A Python)
**Outcome:** Overdue return computes fine; sandbox-tested.

- [x] Spec fields: `x_fine_rate`, `x_fine_amount`, `x_days_overdue`
- [x] Python automation or model method in generated module (daily cron or on write of returned)
- [x] UI: “Add fine logic” → opens code template → sandbox → promote
- [x] Confirm phrase + snapshot discipline
- [x] Extension sandbox gate covers module with `mail` (`SANDBOX_EXTRA_MODULES=contacts,mail`)

### A6. Email reminders (polished)
**Outcome:** Due-soon / overdue emails with templates.

- [x] Ensure `mail` installed; mail template records in export XML
- [x] Scheduled action (ir.cron) + overdue mail template in library zip
- [x] Library template: “Overdue” template
- [x] Library template: “Due in 2 days” template
- [x] Builder UX: Reminder wizard (model, date field, template, interval) — `/connections/{id}/reminders`

### A7. Reporting / dashboards
**Outcome:** Usable ops reports without BI suite.

- [x] Export: `ir.actions.act_window` with `view_mode` including `pivot`/`graph` on Loans
- [x] Predefined filters: Active Loans menu (`x_returned=False`); search Active/Returned filters
- [x] Optional QWeb PDF report for loan receipt (generator `ReportSpec` + `reports.xml.j2`)
- [x] Connection UI: Library stats strip (`GET .../library/stats`) when `x_lib_book` exists
- [x] Stretch: simple dashboard strip in web app reading RPC aggregates

### A8. Multi-company policies
**Outcome:** Branch libraries isolated when `res.company` multi-company is used.

- [x] Optional `company_id` many2one on Book/Loan/Category (zip); live scaffold uses `x_company_id`
- [x] Record rules: `['|', ('company_id','=',False), ('company_id','in',company_ids)]`
- [x] Template toggle: “Multi-company aware” (wizard + scaffold/export API)
- [x] Docs: requires companies configured in Odoo; sandbox may be single-company (`skills/library-app.md`)

---

## 5. WS-B — Speed layer (free stack)

### B1. App wizard / templates ⭐ highest ROI
**Outcome:** `/apps/new` or connection “Create app” → pick template → name → apply.

- [x] Templates registry: `library`, `crm_lite`, `inventory_lite` (minimal viable each)
- [x] API: `POST /connections/{id}/apps/scaffold` → creates live metadata **or** draft project (prefer draft if B4 ready; else live with confirm)
- [x] UI: template cards + technical name (`template-card-*`) + display name + optional `technical_prefix`
- [x] Progress checklist after scaffold (models, menus, open designer, run sandbox)
- [x] Playwright: scaffold library → sees models listed (`e2e/wizard-scaffold.spec.ts`)

### B2. NL → ModuleSpec (optional Ollama)
**Outcome:** “Books, authors, 14-day loans” → editable draft → confirm.

- [x] Settings: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, feature flag `AI_ASSIST=off|ollama`
- [x] Prompt → JSON ModuleSpec schema (pydantic validate)
- [x] UI: prompt box + JSON preview + template fallback (draft does not apply)
- [x] Fallback: no Ollama → show template picker only
- [x] Never auto-apply without confirm
- [x] Unit tests with golden JSON fixtures (no live LLM required in CI)

### B3. Live preview panel ⭐
**Outcome:** Designer right pane = Odoo iframe or deep link.

- [x] Build URL helper: `{odoo}/web#model=…&view_type=form` + **Open in Odoo** (no password in URL)
- [x] Prefer: embedded iframe when allowed; else popup + note that X-Frame-Options may block
- [x] After save view: auto-refresh preview (`previewKey` remount)
- [x] Security: only for saved connections; no password in iframe URL

### B4. Draft projects + apply/diff
**Outcome:** Offline ModuleSpec/project in app DB; Apply batches mutations.

- [x] Tables: `customization_projects` (revisions deferred)
- [x] API: CRUD project, `POST .../apply` (models+fields v1)
- [x] Apply: ordered create models → fields (views/ACL/menus deferred)
- [x] UI: project list + create from library template + Apply with confirm
- [x] Conflict detection: live field/model already exists (`GET .../projects/{id}/diff`)
- [x] Diff against live introspection (pre-apply report + projects UI)

### B5. Async jobs UI
**Outcome:** Sandbox/promote never freeze the page.

- [x] Web: poll `GET /api/jobs/{id}`; progress states (`pollJob`)
- [x] Connection page: `async_job: true` by default (API default **true**)
- [x] Toast/banner: succeeded / failed + collapsible log tail
- [x] Cancel: `POST /api/jobs/{id}/cancel` (queued/running → cancelled)

### B6. Smarter defaults
- [x] Required M2O → `on_delete=restrict`
- [x] Depends inference (stock map) + module picker
- [x] Default menus/ACL for new models
- [x] Builder: on_delete picker (restrict/cascade/set null)
- [x] Auto-suggest depends from M2O targets in UI before export (`GET .../suggest-depends`)
- [x] Wizard: always application-style root menu + per-model actions on live scaffold (`ensure_app_menus`)

### B7. Domain & selection builders
- [x] Selection editor: list of value/label rows → Odoo selection string
- [x] Domain builder: field / operator / value chips → domain string
- [x] Use in automations, record rules, field invisible
- [x] Vitest for serializer helpers

### B8. One2many from parent
- [x] UI: “Link one2many” → creates O2M on parent + M2O on child
- [x] API helper: `POST .../fields/relational_pair`
- [x] Inject O2M into parent form (inherit)

### B9. Playwright + sandbox gates
- [x] ConfirmDialog e2e harness
- [x] Smoke + extension sandbox scripts / workflow_dispatch
- [x] E2E: wizard scaffold (mock API) — `e2e/wizard-scaffold.spec.ts`
- [x] Nightly extension gate (`schedule:` Sundays on `odoo-sandbox.yml`)
- [x] Library template sandbox gate script (`run-sandbox-library-gate.sh` + `run-library-uat.sh` + workflow `library`)

---

## 6. WS-C — Shared platform work

- [x] `mail` / `barcodes` (if used) in `MODEL_TO_MODULE` / depends map
- [x] Generator: mixin-aware `model.py.j2` (`_inherit = ['mail.thread', ...]`)
- [x] Export live automations/mail templates/crons into zip (code automations + mail.template + ir.cron; safe non-code autos skipped with warning)
- [x] Health: report Ollama reachability when AI enabled (`/health` + `/api/ai/status`)
- [x] SETTINGS / `.env.example`: `OLLAMA_*`, `AI_ASSIST`, preview proxy notes
- [x] `skills/library-app.md` (module-interop / studio-parity updates still optional)

---

## 7. WS-D — Verification matrix

| Gate | Command / action | Required for |
|------|------------------|--------------|
| Unit | `uv run ... pytest` + `pnpm test` | every PR |
| Confirm e2e | `pnpm test:e2e` | every PR |
| Odoo integration | `pytest -m integration` | before merge of RPC features |
| Sandbox smoke | `./docker/run-sandbox-gate.sh` | before release |
| Sandbox library | `./docker/run-sandbox-library-gate.sh` | Library template |
| Extension | `./docker/run-sandbox-extension-gate.sh` | depends on sale/account |
| Manual UAT | Checklist §8 | “full-scale” declaration |

---

## 8. UAT checklist — “We can build a full-scale library product”

Verified **2026-07-27** via sandbox install + RPC (`./docker/run-sandbox-library-gate.sh`, `./docker/run-library-functional-uat.sh`, multi-company isolation probe). Human UI click-through remains optional confidence.

- [x] Scaffold Library from wizard / portable zip in &lt; 2 minutes (sandbox install path proven)
- [x] Create category, book with barcode/ISBN, member (contact), loan
- [x] See chatter on book or loan (`message_ids` + `message_post`)
- [x] See kanban of loans (`x_lib_loan.kanban` installed; group by `x_returned`)
- [x] Trigger or schedule overdue email (templates + cron + `send_mail` / `cron_send_overdue_reminders`)
- [x] Return overdue loan → fine amount populated (`fine=10.0` for 4d × 2.5)
- [x] Open overdue report / pivot or filtered list (Active Loans + Loan Receipt QWeb)
- [x] With 2 companies: company A context does not see company B stock (`allowed_company_ids`)
- [x] Export → sandbox green → Library menu works on target
- [x] Uninstall/residual messaging understood (documented; sandbox tears down with `-v`)

**Exit criterion:** All boxes checked on Community 19 Docker; documented in STATE retro. ✅

---

## 9. Phased delivery plan

### Phase P0 — Tracking & fixes (this document)
- [x] Plan document created
- [x] STATE.md points here
- [x] MEMORY decision: full-scale library program approved scope

### Phase P1 — Wizard + Library template + preview (speed + skeleton)
**Delivers:** fastest path to a usable library shell + Studio-like feedback.

- [x] B1 App wizard (API + templates + UI)
- [x] A1 Library template (live scaffold + portable ModuleSpec)
- [x] B3 Live preview (or Open-in-Odoo v1)
- [x] B5 Async jobs UI
- [x] B6 on_delete picker
- [x] D: library sandbox gate (`docker/run-sandbox-library-gate.sh`)

### Phase P2 — Draft/apply + mixins + kanban
- [x] B4 Draft projects (CRUD + apply models/fields v1)
- [x] A2 mail.thread checkbox
- [x] A3 Kanban
- [x] B8 One2many from parent
- [x] B7 Selection builder (minimum)

### Phase P3 — Circulation intelligence
- [x] A4 Barcode
- [x] A5 Fines (Option A)
- [x] A6 Email reminders (overdue + due-soon)
- [x] B7 Domain builder
- [x] B2 NL → ModuleSpec (optional Ollama)

### Phase P4 — Ops & scale
- [x] A7 Reporting (Active Loans + pivot/graph + stats strip + QWeb PDF)
- [x] A8 Multi-company
- [x] UAT §8 complete (automated functional + multi-company isolation; see §8)
- [x] Polish docs + UAT scripts (`skills/library-app.md`, `run-library-uat.sh`, `run-library-functional-uat.sh`)

---

## 10. File / component map (expected touch list)

| Area | Paths |
|------|--------|
| Wizard UI | `apps/web/src/app/apps/new/`, `connections/[id]/wizard/` |
| Preview | `apps/web/.../designer/`, `apps/web/src/components/OdooPreview.tsx` |
| Draft DB | `apps/api/app/db_models.py`, `routers/projects.py`, `project_apply.py` |
| Templates | `packages/module-generator/src/module_generator/app_templates/`, `templates/` |
| Mixins/kanban | `odoo_client/client.py`, `view_arch.py`, `model.py.j2` |
| AI | `apps/api/app/ai_ollama.py`, `routers/ai.py` |
| Jobs UI | `apps/web/src/lib/jobs.ts`, connection page |
| Gates | `docker/run-sandbox-library-gate.sh`, `docker/run-library-uat.sh`, `.github/workflows/` |
| Skills | `skills/library-app.md`, this plan |

---

## 11. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Mixins impossible via pure `ir.model` RPC | Force python module path for chatter models; sandbox before promote |
| Iframe X-Frame-Options blocks preview | “Open in Odoo” + refresh; optional reverse-proxy same origin later |
| Ollama quality / drift | Schema-validate ModuleSpec; templates remain primary path |
| Fine/email logic wrong on edge dates | Golden tests + sandbox gate with demo data |
| Scope creep into full ILS | Keep Library as **reference vertical**; generalize via templates |
| Multi-company subtle bugs | Feature-flag template toggle; test with 2 companies in Docker |

---

## 12. Effort sketch (rough, solo)

| Phase | Calendar (solo, part-focused) |
|-------|-------------------------------|
| P1 | ~1–2 weeks |
| P2 | ~1–2 weeks |
| P3 | ~2 weeks |
| P4 | ~1–2 weeks |
| **Total** | **~5–8 weeks** to UAT “full-scale library” |

Re-estimate after P1.

---

## 13. Decision log (plan-level)

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Library is the **reference vertical**, not a separate product codebase | Forces platform features to stay general |
| D2 | Wizard before NL AI | Deterministic scaffold &gt; probabilistic first |
| D3 | Fines/reminders via Option A + templates | Correctness + sandbox gate |
| D4 | Ollama optional | Free, local, no paid lock-in |
| D5 | Draft/apply after wizard | Wizard value first; draft reduces fear next |
| D6 | No Celery | Keep `background_jobs` thread pool until scale demands |

---

## 14. Open questions → decisions (2026-07-27)

- [x] **Barcode:** char + Community `barcode` widget + search/action. Do **not** hard-depend on `barcodes` module for v1.
- [x] **Email UAT:** rely on Odoo mail queue + `send_mail(force_send=False)` in functional UAT; Mailhog/Mailpit optional later (not blocking).
- [x] **Preview:** **Open in Odoo first** + best-effort iframe; same-origin proxy deferred.
- [x] **Inventory model:** keep **copies integer** on Book for v1; per-copy rows are a future template option.
- [x] **Scaffold default:** live scaffold with confirm remains default; draft projects are opt-in via `/projects` (wizard stays fast path).

---

## 15. Session protocol

At start of each implementation session:
1. Read this plan §9 current phase.
2. Pick **one** epic (e.g. B1); avoid cross-phase thrash.
3. End session: tick boxes; update §14 if blocked; `STATE.md` last-run → link here.

**STATE one-liner (copy):**  
`Plan: docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md — all implementation boxes closed`

---

## 16. Progress summary

| Stream | Progress |
|--------|----------|
| Baseline platform | ~98% |
| Full-scale library (A2–A8) | **100%** (automated UAT §8 + reminder wizard) |
| Speed layer (B1–B9) | **~98%** (iframe may still be X-Frame blocked — Open-in-Odoo is the production path) |
| **Program overall** | **~98%** — remaining is optional polish (Mailpit, preview proxy, per-copy inventory) |
