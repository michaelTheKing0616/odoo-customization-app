<!-- Recovered verbatim from project chat transcript on 2026-08-03. Source of truth for the 8-document master reference. -->
<!-- Recovery note: the original paste contained Document 8 twice; the first copy was a truncated exact prefix of the second, so only the complete copy is kept. No content was lost. -->

# Project Northstar / Odoo No-Code Customization App — Master Reference Document

Combined, fully current compendium of every planning/reference document produced for this project. All eight source documents are reproduced here in full — nothing summarized or condensed. Section numbering within each document is preserved from its source for cross-reference.

## Table of Contents

**Document 1 — Production Plan: No-Code Odoo Customization Platform**
Feasibility summary · Architecture · 8-phase build plan · Tech stack · Cursor session breakdown · Key risks

**Document 2 — AI Module Generation & Code-to-UI Design**
1. Model serving (Qwen3) · 2. Canonical schema · 3. Staged generation pipeline · 4. Domain template library (full car-rental example) · 5. Validation/rules engine · 6. Self-critique pass · 7. Code→Graphical UI reverse import · 8. End-to-end flow example · 9. Cursor session addendum

**Document 3 — The Odoo UI/UX & Functionality Compendium (v16–v19)**
1. Architecture fundamentals · 2. Module structure & manifest · 3. View types · 4. Fields & widgets · 5. View inheritance & XPath · 6. Security model · 7. Automation rules (⚠ corrected — Studio/plan-tier dependency) · 8. QWeb reports · 9. Actions & menus · 10. Chatter/activities/sequences · 11. OWL framework · 12. UI/UX evolution by version · 13. What Studio does that is worth matching · 14. Images & media pipeline · 15. Niche/specialty widgets · 16. Barcode (core vs. third-party) · 17. Approval rules · 18. Property fields · 19. Financial operations — integrate, never reinvent · 20. Visual identity & UI component conventions · 21. Open items for follow-up research

**Document 4 — Prompt Engineering & Model Selection Guide (Qwen3)**
0. Model selection (Qwen3, thinking mode, size ladder) · 1–10. Prompt engineering techniques (decomposition, schema design, few-shot, chain-of-thought, temperature, self-consistency, negative examples, structured decoding, model mixing, distillation) · Summary checklist

**Document 5 — Protected Core Modules: Guardrail Design & Source Retrieval**
1. Why a hardcoded list is wrong · 2. Protected categories (verified against real Odoo 18.0 source) · 3. Source retrieval script (tested, working) · 4. Hard guardrail prompt

**Document 6 — Odoo Online Support: Compatibility Matrix & Gap-Filling Strategy**
1. What Odoo Online actually restricts · 2. Full compatibility matrix · 3. Gap-by-gap strategy · 4. Summary of what to build differently

**Document 7 — Workflow Optimization Opportunities: Bulk & Batch Operations**
1. Bulk state-transition tool · 2. Universal mass-field-edit tool · 3. Generic duplicate detection/merge · 4. Scheduled-action management · 5. Attachment/document housekeeping · 6. Bulk activity/reminder scheduling · 7. Bulk security/access provisioning · 8. Cross-reference to earlier optimization ground · 9. Discovery mechanism · 10. Design guardrails · 12. Stored computed field recompute · 13. Bulk Send & Print (documented bug) · 14. Bulk portal access provisioning · 15. Apps Store/OCA-as-gap-map research technique · 16. Why this is the strongest Online-compatible differentiator

**Document 8 — The Odoo Expert: A General-Purpose RAG Assistant**
1. How this differs from the module generator · 2. Architecture overview · 3. Knowledge base construction (Odoo's own documentation source, your own Documents 1–7, curated community Q&A) · 4. Live-instance grounding — the actual differentiator · 5. Generation layer (Qwen3, reusing Document 4's discipline) · 6. Anti-hallucination guardrails (ground-or-decline, protected-category caution) · 7. Honest refusal as a feature · 8. Shared infrastructure with Document 2 · 9. Evaluation/regression testing · 10. UX surfaces · 11. Why this is transformative, not just nice-to-have

---

# ═══════════════════════════════════════
# DOCUMENT 1: PRODUCTION PLAN
# ═══════════════════════════════════════

# No-Code Odoo Customization Platform — Production Plan

## 1. Feasibility summary

Odoo's entire customization surface is data, not code:

| What Odoo Studio does no-code | Underlying Odoo mechanism | Externally accessible? |
|---|---|---|
| New model | `ir.model` (creates a real `x_*` table at runtime) | Yes, via ORM `create` |
| New field | `ir.model.fields` | Yes |
| New form/list/kanban view | `ir.ui.view` (arch is just XML) | Yes |
| New menu/action | `ir.ui.menu`, `ir.actions.act_window` | Yes |
| Automation ("when X happens, do Y") | `base.automation` (built into Community since v14) | Yes |
| Access rules | `ir.model.access`, `ir.rule` | Yes |
| Reports | `ir.actions.report` + QWeb templates (`ir.ui.view` type=qweb) | Yes |

All of this is reachable through Odoo's standard external API (XML-RPC or JSON-RPC over HTTPS), available on **Community edition** — no Enterprise license needed. You are not reverse-engineering Studio's proprietary code; you're using the same public ORM mechanisms it uses, which is legitimate.

The one thing you can't get from Community for free is Studio's *polished drag-and-drop UI* — that's the product you're building.

**Two tiers of "no-code" to design for:**
1. **Metadata-level customization** (fields, views, menus, simple automations, access rules) — fully live, no restart needed, no code generated.
2. **Real module generation** — for anything needing custom business logic beyond declarative automation (computed fields with Python, integrations, complex workflows), generate an actual installable Odoo module (`__manifest__.py`, models, views, security CSV) that the user can review, version in git, and install like any addon. This is your "no-code to code" escape hatch — critical for production trust, since pure metadata hacking has limits and enterprises will want real modules eventually.

## 2. Architecture

```
┌─────────────────────────────────────────┐
│  Frontend (Next.js/React)                │
│  - Model/field builder (form-based)      │
│  - Visual view designer (drag-drop)      │
│  - Automation rule builder (trigger→cond→action) │
│  - Module export/download UI             │
└──────────────────┬────────────────────────┘
                    │ REST/tRPC
┌──────────────────▼────────────────────────┐
│  Backend (Python/FastAPI)                 │
│  - Odoo connection manager (multi-tenant) │
│  - Metadata service (wraps ORM calls)     │
│  - Module generator (jinja2 templates →   │
│    real Odoo addon file tree)             │
│  - Sandbox test runner (Docker + Odoo     │
│    test instance, installs generated      │
│    module before it touches prod)         │
│  - Job queue (Celery/RQ) for long tasks   │
└──────────────────┬────────────────────────┘
                    │ XML-RPC / JSON-RPC
┌──────────────────▼────────────────────────┐
│  Target Odoo instance(s)                  │
│  Community or Enterprise, self-hosted or  │
│  Odoo.sh — your app is instance-agnostic  │
└────────────────────────────────────────────┘
```

**Why Python/FastAPI over Node for the backend:** the Odoo ecosystem's RPC libraries (`odoorpc`, `python-odoo-client`) and module-generation tooling are Python-native, and you'll eventually want to run Odoo's own test framework (`pytest-odoo`) against generated modules before install — much simpler in Python.

**Metadata store (your own Postgres, separate from any customer's Odoo DB):**
- `connections` (encrypted Odoo credentials/API keys per tenant)
- `projects` (a customization project = a bundle of model/field/view/automation definitions)
- `generated_modules` (versioned exports, so users can roll back)
- `users`, `roles` (access to the builder itself)

## 3. Phased build plan

### Phase 0 — Foundation (1–2 weeks)
- Spin up a throwaway Odoo Community instance locally (Docker: `odoo:17` + `postgres:15`) as your dev/test target.
- Get comfortable with `odoorpc` or raw XML-RPC: connect, read `ir.model`, `ir.model.fields`, create a test `x_` model and field manually via API to confirm the mechanism end-to-end.
- Set up repo structure: `/apps/web` (Next.js), `/apps/api` (FastAPI), `/packages/odoo-client` (shared RPC wrapper).

### Phase 1 — Connection & introspection (2–3 weeks)
- Build the "Connect your Odoo" flow: URL + DB name + API key (Odoo supports API keys since v14, safer than storing passwords).
- Encrypt credentials at rest (e.g. `cryptography` Fernet, key from env/secrets manager).
- Build a metadata browser: list installed modules, models, fields, views — read-only first. This alone is useful and de-risks the RPC layer before you write anything.

### Phase 2 — No-code field & model builder (3–4 weeks)
- UI: "New Field" form (name, label, type, required, default, relation target if many2one/one2many).
- Backend translates this into an `ir.model.fields.create()` call. Handle the field-type mapping carefully (char, text, integer, float, boolean, date, datetime, selection, many2one, one2many, many2many, binary).
- "New Model" flow: creates `ir.model` with `x_` prefix (Odoo convention for custom models), auto-creates default views.
- Validation layer: block reserved names, check for conflicts, warn on destructive changes (deleting a field with data).

### Phase 3 — Visual view designer (4–5 weeks)
- This is the hardest UI piece. Build a drag-drop canvas that outputs Odoo view XML (`ir.ui.view.arch`) for form/list/kanban.
- Start narrow: support the ~20% of XML tags that cover 80% of real customization (`<field>`, `<group>`, `<notebook>`/`<page>`, `<button>`, basic `<tree>` columns) rather than trying to support every Odoo view directive.
- Live preview: render an iframe pointed at the actual Odoo instance's view via `web` client URL, or build a lightweight preview renderer client-side.

### Phase 4 — Automation & business rules (2–3 weeks)
- Map a visual "When [trigger] and [condition], do [action]" builder onto `base.automation` records (trigger on create/write/time-based, domain-based conditions, actions: update field, send email, create activity, execute server action).
- For anything requiring actual Python logic, don't try to expose raw code eval in the no-code UI (security risk) — route it to Phase 5's module generator instead, where a *developer* (or you) reviews the generated Python before install.

### Phase 5 — Module generator / "no-code to code" export (3–4 weeks)
- Jinja2 templates for a full Odoo addon skeleton: `__manifest__.py`, `models/*.py`, `views/*.xml`, `security/ir.model.access.csv`, `security/security.xml`.
- Given a project's field/view/automation definitions, generate the equivalent *declarative* module (models via ORM class definitions with `_inherit`/`_name`, views as XML, access rules) — this is what lets a customer graduate from "quick metadata hack" to "real versionable module they can put in their own git repo."
- Output as a downloadable `.zip`; optionally, direct-install into a **sandbox** Odoo container first (Phase 6) to catch errors before the customer's production instance ever sees it.

### Phase 6 — Sandbox test pipeline (2 weeks)
- Docker-based ephemeral Odoo instance spun up per test: install the generated module, run Odoo's own module load (which validates XML/manifest), run any generated unit tests, tear down.
- This is your production-readiness gate — never let unvalidated metadata/modules touch a real customer instance without passing this.

### Phase 7 — Multi-tenancy, auth, and hardening (2–3 weeks)
- Auth for your own app (NextAuth/Clerk-style or roll your own with JWT).
- Per-project audit log (who changed what field/view/rule, when) — critical for an ERP-adjacent tool since customers will ask "who broke this."
- Rate limiting and connection pooling per Odoo tenant.
- Rollback: keep versioned snapshots of every `ir.ui.view`/`ir.model.fields` change so a bad customization can be reverted in one click.

### Phase 8 — Polish & launch (ongoing)
- Onboarding flow, template library (starter customization packs: CRM extension, custom invoicing fields, etc.).
- Docs + a "generated module" README so customers understand what was created and can hand it to their own devs later.

## 4. Tech stack (budget-conscious, matches your Cursor/solo workflow)

- **Frontend:** Next.js + TypeScript + Tailwind (matches your no-paid-subscription constraint — all open source)
- **Backend:** Python 3.12 + FastAPI
- **Odoo RPC:** `odoorpc` (simpler API than raw XML-RPC) or raw `xmlrpc.client` (stdlib, zero dependency) if you want minimal footprint
- **Metadata DB:** Postgres (Supabase free tier works for early dev, or self-hosted Docker Postgres — no vendor lock-in)
- **Queue:** Celery + Redis, or lighter-weight `arq`/RQ if you want fewer moving parts solo
- **Sandbox:** Docker + `docker-compose` running throwaway Odoo Community containers
- **Module templating:** Jinja2
- **Hosting (later):** Fly.io or Railway have generous free/cheap tiers for early-stage single-founder projects; avoid committing to anything with recurring cost until you have paying users

Everything above avoids paid SaaS dependencies given your no-subscription-budget constraint — the only real "cost" is compute for testing, which Docker locally handles for free during development.

## 5. Building it in Cursor — session breakdown

Cursor works best when each session has a tight, testable scope. Suggested cadence:

1. **Session: Odoo RPC wrapper.** Prompt: "Build a Python client wrapping odoorpc that exposes connect(), list_models(), create_field(), create_model(), create_view() with typed request/response models (pydantic)." Test against your local Docker Odoo before moving on.
2. **Session: FastAPI CRUD around that wrapper**, with the Postgres metadata store for connections/projects.
3. **Session: Next.js scaffold + auth**, connect to the FastAPI backend.
4. **Session: Field builder UI + API wiring.** Ship this as a usable v0.1 before touching the view designer — it's independently valuable.
5. **Session: View designer** — this is the one to give Cursor the most explicit spec for (exact XML output examples), since generative UI-building tools tend to hallucinate on Odoo's more obscure view syntax.
6. **Session: Automation builder.**
7. **Session: Module generator + Jinja2 templates.**
8. **Session: Sandbox Docker pipeline.**

At each session boundary, commit and write a short test script that actually installs/exercises the change against your local Odoo container — this catches Cursor's occasional confident-but-wrong Odoo API usage immediately rather than after several sessions of drift.

## 6. Key risks to watch

- **Odoo version drift.** `base.automation` and view syntax differ meaningfully between v14–v18. Pick one target version first (recommend the latest stable Community LTS at the time you start) and explicitly scope out cross-version support until v1 is solid.
- **Destructive metadata changes.** Deleting/renaming a field/model via API can silently drop data. Always snapshot before mutating.
- **Security of generated automations/modules.** Never let the no-code UI generate raw Python `eval` server actions without a review step — that's a direct code-injection surface into the customer's ERP.
- **Studio IP boundary.** Don't look at or copy Odoo Enterprise Studio's source — it's proprietary. Building against the public ORM/RPC API is fine; reverse-engineering the closed module is not.

# ═══════════════════════════════════════
# DOCUMENT 2: AI MODULE GENERATION & CODE-TO-UI DESIGN
# ═══════════════════════════════════════

# AI Module Generation & Code-to-UI — Design

## 1. Model serving

**Run qwen3:8b locally via Ollama** — free, no API cost, works fine on Apple Silicon. (Superseded qwen2.5:7b as the recommended default — see the companion Prompt Engineering & Model Selection Guide for the full rationale, including Qwen3's native thinking-mode toggle and the size-ladder strategy for reasoning-heavy steps.)

```bash
ollama pull qwen3:8b   # default tier — bulk, high-volume, narrow extraction steps
ollama pull qwen3:14b  # reasoning-heavy tier — domain matching, automation proposals, self-critique
```

- On a MacBook Air (M2/M3, 16GB unified memory), the Q4 quant runs comfortably via Metal. Q4_K_M is the sweet spot — Q8/fp16 will be noticeably slower and the quality gain doesn't matter much for structured extraction tasks.
- For production, don't assume every customer runs Ollama locally — offer three backend modes in your API layer: `ollama` (local/self-hosted, free), `openai-compatible` (so power users can point at vLLM/LM Studio/any endpoint), and later a hosted option if you want a paid tier. Abstract this behind one interface (`LLMProvider.generate(prompt, schema)`) so swapping models later doesn't touch the pipeline.
- Use Ollama's `format: "json"` parameter (grammar-constrained decoding) for every structured call — this alone eliminates most malformed-JSON failures from a 7B model, which is the single biggest reliability problem you'll hit otherwise.

## 2. The canonical schema — the one idea that makes everything else work

Define one internal JSON representation that is the *single source of truth* for a module, and make every other piece of the system a translator to/from it:

```
ModuleSpec
├── models: [ ModelDef ]
│   ├── name, label, description
│   ├── fields: [ FieldDef (name, type, label, relation, required, selection_options, default) ]
│   ├── inherits: [ "mail.thread", "mail.activity.mixin" ]  # chatter/activity support
│   └── state_field: StatusWorkflow (states, transitions)   # if it's a workflow model
├── relationships: [ (model_a, model_b, type: m2o|o2m|m2m, field_name) ]
├── views: [ ViewDef (model, type: form|list|kanban, layout) ]
├── menus: [ MenuDef (name, parent, action, sequence) ]
├── automations: [ AutomationDef (model, trigger, condition, action) ]
├── security: [ AccessRuleDef (model, group, permissions) ]
└── smart_buttons: [ SmartButtonDef (source_model, target_model, relation_field, icon) ]
```

This schema is what:
- the LLM generation pipeline outputs (Section 3)
- your visual builder (from the earlier plan) reads and writes
- the Jinja2 module-code-generator consumes to emit real `.py`/`.xml`
- the **Code → Graphical UI** feature parses real Odoo code *into* (Section 6)

Because everything routes through one representation, "generate from prompt," "edit visually," and "import existing module" are three different producers of the *same* object — you build the rendering/export logic once.

## 3. Staged generation pipeline (don't ask for everything at once)

A 7B model degrades fast on single giant JSON generations — it loses track of consistency (field names not matching relations, forgetting half the models). Decompose into small, sequential, checkable steps instead:

**Step 0 — Domain retrieval (RAG, not generation).**
Before calling the LLM at all, embed the user's prompt (`sentence-transformers/all-MiniLM-L6-v2` runs fine locally, no API needed) and do a similarity search against a **domain template library** you curate (Section 4). If "car rental" matches a stored template at high similarity, pull it in as a scaffold. If it's a novel domain, fall back to the closest partial matches (e.g. "equipment rental," "fleet management") as weaker priors. This step is what actually solves your comprehensiveness problem — the model isn't inventing the field list, it's adapting one.

**Step 1 — Entity extraction.**
```
Given: user prompt + retrieved scaffold (if any)
Task: "List the core business entities (models) this app needs.
For each: name, purpose, whether it's a workflow entity (has a status
lifecycle) or a reference entity."
Output: JSON list of {name, purpose, is_workflow}
```
Small, scoped, checkable — a 7B model handles this reliably.

**Step 2 — Fields per model (one call per entity, not all at once).**
```
Given: entity name + purpose + scaffold fields for this entity type (if matched)
Task: "List all fields this model needs for a production-grade app,
including operational fields a beginner might forget (audit fields,
reference codes, status, dates)."
Output: JSON list of FieldDef
```
Looping per-model keeps each call small and focused — this is the single biggest reliability lever with a small model. It also means you can run these calls in parallel.

**Step 3 — Relationships pass.**
Given the full entity + field list so far, ask specifically: "which fields should be many2one/one2many/many2many links between these models, and what's missing to connect them properly?" This catches things like `rental_id` on Contract needing to link both Vehicle and Customer.

**Step 4 — Workflow pass.**
For every entity flagged `is_workflow` in Step 1: "define the status field's states and valid transitions" (e.g. Contract: draft → confirmed → picked_up → returned → closed; Vehicle: available → rented → maintenance → retired).

**Step 5 — Automation pass.**
```
Given: entities, workflow states, relationships
Task: "Propose automation rules of the form trigger → condition → action
that a real operator of this app would need."
```
This is where "overdue return" and "mark vehicle available on return" get generated — but *only* if Steps 0's scaffold primed the model with rental-domain patterns. Don't skip Step 0 and expect Step 5 to invent this from a generic prompt.

**Step 6 — Views/menus/smart-buttons pass.**
Deterministic, not LLM: once you have models + relationships + workflow states, you can generate sensible default list/form/kanban views and smart buttons (e.g. "Rentals" smart button on Vehicle form) with a rules engine (Section 5), no model call needed. Save LLM calls for judgment, not boilerplate.

## 4. Domain template library — your actual moat

This is more valuable long-term than the LLM pipeline itself, because it's what separates "generic AI slop" from "comprehensive, expert-grade module." Seed it manually, 15–20 minutes each, for common verticals:

- Car/equipment rental (your example — see full spec below)
- Clinic/appointment booking
- Restaurant/POS
- Real estate/property management
- Field service / job dispatch
- Hotel/PMS
- Subscription/membership billing
- Simple project/task tracking

Store each as a partial `ModuleSpec` plus metadata tags for embedding search. Every real customer project that gets built through your tool is a candidate to (with permission) generalize and fold back into the library — this compounds over time and is genuinely hard for a competitor to replicate quickly.

**Example — car rental scaffold**, matching your list:

```yaml
models:
  - name: fleet.vehicle
    fields: [make, model, year, plate_number, vin, status(selection:
      available/rented/maintenance/retired), branch_id(m2o res.branch),
      odometer, category(selection: economy/compact/suv/luxury/van),
      daily_rate, weekly_rate]
    inherits: [mail.thread]
  - name: rental.contract
    is_workflow: true
    fields: [customer_id(m2o res.partner), vehicle_id(m2o fleet.vehicle),
      driver_license_number, license_expiry, pickup_datetime,
      pickup_location_id, return_datetime_planned, return_datetime_actual,
      return_location_id, mileage_limit, deposit_amount, insurance_option,
      state(selection: draft/confirmed/active/overdue/closed/cancelled)]
    inherits: [mail.thread, mail.activity.mixin]
  - name: rental.damage.report
    fields: [contract_id(m2o), vehicle_id(m2o), description, photos,
      repair_cost, reported_date]
automations:
  - trigger: cron (daily)
    condition: return_datetime_actual is null AND
      return_datetime_planned < now
    action: set contract.state = overdue, notify branch manager
  - trigger: on write, contract.state = closed
    condition: always
    action: set vehicle.status = available
  - trigger: on write, contract.state = active
    condition: always
    action: set vehicle.status = rented
smart_buttons:
  - on fleet.vehicle → count of rental.contract where vehicle_id = self
  - on res.partner → count of rental.contract where customer_id = self
```

This is exactly the kind of thing a 7B model won't reliably produce cold, but will correctly *adapt* when it's given as a starting point ("the user wants a lighter/heavier version of this — adjust").

## 5. Validation & rules-engine layer (deterministic, catches what the LLM misses)

After the LLM pipeline produces a `ModuleSpec`, run it through non-LLM checks before showing it to the user:

- **Schema validation** (pydantic) — reject/repair malformed output.
- **Referential integrity** — every relation field must point at a defined model; flag orphans.
- **Pattern-based enrichment rules** — deterministic heuristics that don't need an LLM call:
  - any model with a `state`/`status` selection field → auto-add statusbar widget + confirm/cancel buttons
  - any model referencing `res.partner` → auto-add smart button back-reference
  - any workflow model → auto-suggest `ir.sequence` reference code field (e.g. `RNT/00001`) — you already have exactly this pattern in your Inventory ID Generator project, worth reusing the logic
  - detect "rental," "booking," "reservation" type domains → auto-suggest overdue/expiry automations even if Step 5 didn't propose one, as a safety net

This rules layer is what makes the system trustworthy — the LLM proposes, deterministic code disposes.

## 6. Self-critique / completeness pass

Before finalizing, run one more LLM call — not generation, but *evaluation*, which small models do more reliably than open-ended generation:

```
Given: the full ModuleSpec generated so far
Task: "Check this against a production-readiness checklist. For each
item, answer yes/no: audit trail (mail.thread)? sequence/reference
numbers on workflow models? security groups defined per model?
search/filter views? kanban view for workflow models? Missing items —
list them."
```
Checking a list against criteria is a much easier task for a 7B model than generating comprehensively from nothing — use this pattern anywhere you want quality assurance from a small model.

## 7. "Turn code into Graphical UI" — reverse import

Given the canonical schema from Section 2, this feature is the **inverse translator**: parse real Odoo module code back into a `ModuleSpec`, then render it in the same visual builder used for building from scratch.

**Parsing strategy — split by source, not one universal parser:**

- **Modules generated by your own tool**: trivial. Since you control the Jinja2 templates, you can embed a `.meta.json` sidecar file (or structured comments) alongside the generated code that *is* the ModuleSpec — no parsing needed, just read it back. Always do this for your own output.
- **Arbitrary existing Odoo modules** (the harder, more valuable case — customers importing modules they already have): 
  - XML views: parse with `lxml` — Odoo's `ir.ui.view` arch is regular XML, straightforward to walk into your `ViewDef` structure.
  - Python models: don't write a general Python interpreter. Use `ast` to walk model class definitions — Odoo model files follow strong conventions (`_name`, `_inherit`, `fields.Char(...)` etc. as class attributes), so an AST visitor that recognizes these specific patterns covers the large majority of real-world modules without needing to actually execute code.
  - Security CSV/XML: trivial, structured formats.
  - Anything the parser can't confidently map (custom Python business logic, compute methods, unusual patterns) — don't silently drop it. Flag it in the UI as "custom logic — view as code, not editable visually" and preserve it verbatim on re-export. This partial-fidelity approach is what makes it safe to use on real-world modules instead of only your own output.

**Then it's just Section 2's schema rendered by your Phase 3 visual designer** — same drag-drop canvas, same field/view editors, now populated from parsed code instead of an LLM. This is also your safety mechanism for the AI-generation feature: after the LLM pipeline produces a module, render it through this same code→UI path so the user reviews and tweaks the *visual* representation before anything touches their Odoo instance, rather than reviewing raw generated Python/XML.

## 8. End-to-end flow for your example prompt

```
User: "I want to create a car rental service management app"
  → embed prompt, similarity search → matches "vehicle/equipment rental" scaffold (0.86 similarity)
  → Step 1 (entities): confirms fleet.vehicle, rental.contract, customer link,
    adds rental.damage.report (from scaffold, model may not have said this alone)
  → Step 2 (fields, parallel per entity): fills in fields per model,
    scaffold provides the baseline, model adapts naming/extras
  → Step 3 (relationships): links contract → vehicle, contract → partner
  → Step 4 (workflow): defines contract states, vehicle status states
  → Step 5 (automations): overdue-return, status-sync — primed by scaffold
  → Step 6 (views/menus/smart buttons): deterministic generation
  → Validation + rules engine: adds sequence numbers, statusbar widgets,
    security groups
  → Completeness check: flags "no insurance-option field detected" if
    missed → loop back to Step 2 for that model
  → Render in visual builder (Code→UI path) for human review
  → On approval: Jinja2 → real Odoo module → sandbox test → export/install
```

## 9. Cursor session addendum

Add these to the earlier session breakdown:
1. **Ollama client wrapper** — `LLMProvider` interface, JSON-mode calls, retry/repair loop on schema validation failure.
2. **Embedding + template library** — local embedding model, vector similarity search (even just numpy cosine similarity over a few dozen templates doesn't need a vector DB yet).
3. **Staged pipeline orchestrator** — the Step 0–6 sequence, with per-step pydantic validation gates.
4. **Rules engine** — the deterministic enrichment/pattern layer (Section 5), pure Python, no LLM, so make this its own well-tested module since it's your reliability backbone.
5. **AST/XML parser for code→schema** — start narrow (support only your own generated output first), expand to third-party modules as a v2.
6. **Visual builder renderer** — bind to `ModuleSpec` as the single data contract feeding it, whether the source was LLM, human editing, or parsed code.

# ═══════════════════════════════════════
# DOCUMENT 3: ODOO UI/UX & FUNCTIONALITY COMPENDIUM
# ═══════════════════════════════════════

# The Odoo UI/UX & Customization Compendium (v16 → v19)

**Purpose:** A working technical reference for building a no-code Odoo customization tool that matches Odoo Studio's output fidelity. Compiled from Odoo's official developer/user documentation across versions 16.0–19.0, cross-checked against community technical sources.

**How to use this document:** Treat it as a living spec. Every mechanism here maps to something your `ModuleSpec` schema (from the earlier design doc) needs to represent. Sections are ordered roughly in the sequence your builder needs to implement them.

---

## 1. Architecture fundamentals

Odoo is a three-layer system, and every customization tool has to respect the boundary between the layers:

1. **ORM/Model layer** (Python) — business objects (`models.Model` classes), fields, computed logic, constraints.
2. **View layer** (XML, stored as `ir.ui.view` records) — declarative descriptions of how a model's data is presented. Views don't contain logic; they reference fields and widgets.
3. **Web client** (JavaScript, OWL framework since v14+) — renders views into interactive UI, talks to the backend over JSON-RPC.

Everything Studio (and your tool) manipulates is layer 2 (views, as data) plus a subset of layer 1 (dynamically-created models/fields via `ir.model`/`ir.model.fields`, which create real database tables/columns at runtime — this is the mechanism that makes true no-code model creation possible without writing Python).

**Key insight for your builder:** almost nothing you need to expose in a no-code UI requires writing Python at all. Model creation, field creation, view layout, menus, actions, security, and automation rules are *all* data records. Only genuinely custom business logic (complex computed fields, integrations, non-declarative workflows) requires actual code — which is exactly the boundary your "module export" feature should sit at.

## 2. Module structure & manifest

Every Odoo addon is a directory with this canonical shape (stable across v15–v19):

```
my_module/
├── __init__.py                 # imports models/, controllers/, etc.
├── __manifest__.py             # the module descriptor (see below)
├── models/
│   ├── __init__.py
│   └── my_model.py
├── views/
│   └── my_model_views.xml      # ir.ui.view records
├── security/
│   ├── ir.model.access.csv     # ACLs (bulk, tabular)
│   └── security.xml            # groups + record rules (ir.rule)
├── data/
│   └── my_data.xml             # sequences, cron jobs, default data
├── demo/
│   └── demo.xml                # demo data (only loaded in demo mode)
├── report/
│   └── my_report_templates.xml # QWeb report templates + ir.actions.report
├── static/
│   └── src/                    # JS/CSS/OWL components, only if custom frontend logic needed
└── controllers/
    └── main.py                 # HTTP routes, only if you need custom web endpoints
```

**`__manifest__.py`** is a single Python dict:
```python
{
    'name': "Rental Management",
    'version': '1.0',
    'category': 'Operations',
    'summary': "Short one-line description",
    'description': "Longer description, can be multi-line",
    'author': "Your Name/Company",
    'depends': ['base', 'mail', 'contacts'],   # module dependencies — critical to get right
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',   # security files should load early
        'data/sequences.xml',
        'views/rental_views.xml',
        'views/rental_menus.xml',          # menus often split into their own file, loaded last
        'report/rental_reports.xml',
    ],
    'demo': ['demo/demo_data.xml'],
    'installable': True,
    'application': True,     # True = shows as a top-level "app" in the main menu, not just a technical module
    'auto_install': False,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': ['my_module/static/src/js/my_widget.js'],
    },
}
```

**Critical ordering rule:** `data` files load sequentially, and records reference each other by XML ID — a model must be defined (and its access rights granted) before a view references its fields, and a view must exist before a menu action can reference it. Your module generator must topologically sort by dependency, not just dump files in arbitrary order — this is one of the most common hand-written-module bugs and your generator should get it right by construction.

**Reserved prefixes/conventions worth encoding into your generator:**
- Custom/dynamically-created models and fields created outside a "real" module (i.e. via Studio-style runtime creation) get an `x_` prefix (`x_studio_field_name`, `x_my_model`) — this is Odoo's own convention for distinguishing "this was created through the UI, not by a developer module," and Studio's own generated modules follow it.
- If your tool generates *real* modules (not just `x_`-prefixed runtime objects), you're free to use clean names without the `x_` prefix, since you're producing an installable addon like any other.

## 3. View types — the full catalog

Odoo views fall into three families: **general views** (single-record), **multi-record views**, and **reporting/analysis views**. Availability varies by edition (Community vs Enterprise) — flag this in your builder so users on Community don't try to configure Enterprise-only views.

| View | Purpose | Edition | Notes for your builder |
|---|---|---|---|
| **Form** | Single-record detail/edit view | Community | The foundational view; almost every model needs one |
| **List** (formerly "tree") | Tabular multi-record overview | Community | Supports inline editing; can embed a mini form view for x2many lines |
| **Kanban** | Card-based board, often grouped by a status field | Community | Default view on mobile if present; supports quick-create, drag between columns |
| **Search** | Defines available filters/group-by/facets | Community | Not visually rendered alone — attaches to list/kanban/etc. as the search bar |
| **Activity** | Grid of records × activity types | Community | Used for follow-up/task-tracking views |
| **Calendar** | Day/week/month/year event view | Community | Needs date/datetime start (and optionally end) fields |
| **Graph** | Bar/line/pie aggregation charts | Community | Read-only, analytical |
| **Pivot** | Cross-tab aggregation table | Community | Drill-down by dimension; pairs naturally with Graph |
| **Map** | Records plotted geographically with routes | Enterprise | Needs an address/geolocation field |
| **Cohort** | Data change over time (retention-style analysis) | Enterprise | Niche — subscriptions/attrition analysis |
| **Gantt** | Timeline/scheduling chart | Enterprise | As of recent 18/19 releases, supports zoom in/out, horizontal scroll, drag to schedule/unschedule via a side panel |
| **Grid** | Numerical cell entry (e.g. timesheets) | Enterprise | Rebuilt on OWL as of v17, enabling sample-data display |
| **Diagram** | Node/transition graph (e.g. workflow visualization) | Community (rare) | Used sparingly in core (e.g. accounting sequences) |
| **QWeb** | Generic HTML templating — powers reports, website, some dashboards | Community | Not a "view type" in the Studio sense but the templating layer under several of the above |

**Practical implication for your builder:** your MVP view designer (from the earlier build plan) should prioritize Form → List → Kanban → Search → Calendar → Graph/Pivot, in that order — that covers the large majority of real customization requests, is fully achievable against Community, and defers the Enterprise-only views (Map, Cohort, Gantt, Grid) to a later phase since they both require Enterprise underneath and are lower-frequency asks.

### View-level configuration options worth exposing in your UI
- **List view:** can-create / can-edit / can-delete toggles, default "add record" behavior (inline row vs. popup form vs. full form view), default group-by.
- **Kanban view:** can-create toggle, quick-create (minimal inline creation), default group-by (usually the status field), whether it's used as the mobile fallback.
- **Sample data:** several view types (kanban, list, gantt, graph, pivot, cohort) support a `sample="1"` attribute that populates the view with realistic fake data when the model has no real records yet — genuinely useful for your tool's live-preview feature so a freshly-generated module doesn't show an empty screen.

## 4. Fields and widgets — the full catalog

This is the part your field-builder UI directly surfaces. Odoo Studio exposes a curated ~20 "field types" in its picker, which map onto Odoo's underlying field classes plus a default widget — but the underlying widget system is more flexible than what Studio's simplified picker shows, and your tool can expose more of it.

### Core field types (ORM level)
`Char`, `Text` (multi-line), `Html` (rich text), `Integer`, `Float`, `Monetary` (float + companion currency field), `Boolean`, `Date`, `Datetime`, `Selection` (fixed dropdown), `Many2one`, `One2many`, `Many2many`, `Binary` (file storage), `Reference` (polymorphic link to any model).

### Widget catalog by underlying field type

**Char/Text:**
- default (plain text input)
- `email`, `phone`, `url` — add semantic click-actions (mailto/tel/link)
- `html` — WYSIWYG rich text editor in edit mode

**Numeric (Integer/Float):**
- `handle` — drag-to-reorder handle, used specifically on sequence fields in list views
- `float_time` — displays a float as HH:MM
- `monetary` — currency-formatted, requires a companion `currency_id`-type field (configurable via `options`)
- `progressbar` — float as a completion-percentage bar
- `percentage`, `percentpie` — percentage display variants

**Selection/relational:**
- `many2many_tags` — pill/tag display for M2M
- `radio` — selection as radio buttons instead of dropdown
- `priority` — star-rating style selection widget (used for lead/task priority in core)
- `statusbar` — the horizontal status/stage pipeline widget (requires a Selection field, typically the workflow `state` field) — this is the single most important widget for any workflow-heavy app (your rental contract's draft→confirmed→active→overdue→closed states, for example)
- `checkboxes` — M2M rendered as a checkbox list
- `many2one_avatar` — relational field rendered as a person/record avatar

**File/binary:**
- `image` — displays and allows upload of an image, with size options (small/medium/large)
- `pdf_viewer` — inline PDF browsing
- `signature` — electronic signature capture pad

**Relational/related:**
- Standard `many2one` dropdown with search
- **Related fields** — not a separate relational link, but a read-through field that fetches a value across an existing relation (e.g., showing `partner_id.email` directly on a Sales Order without creating a new relationship) — very useful in a no-code builder because it lets users surface "linked" information without needing to understand joins.

### Field-level configuration to expose
- Label, help/tooltip text, placeholder, default value
- Required / read-only / invisible, each optionally as a **conditional expression** (domain-like, e.g. "required if Status = Confirmed") — this conditional-visibility mechanic is core to good UX and something your builder needs a visual expression-builder for, not just static booleans
- `groups` attribute — restrict field visibility to specific security groups (field-level security, distinct from model-level ACLs — see Section 6)

## 5. View inheritance & XPath — how customizations layer on top of existing views

This is the mechanism that makes Odoo's modularity work, and it's what your tool must generate correctly for any customization that extends an existing (non-custom) model's view rather than building a model from scratch.

Instead of editing a view in place, you create a **new** `ir.ui.view` record with an `inherit_id` pointing at the parent view, and an `arch` containing one or more `<xpath>` (or shorthand element) instructions describing where and how to modify the parent's structure:

```xml
<record id="my_module.view_form_inherit" model="ir.ui.view">
    <field name="name">model.name.form.inherit</field>
    <field name="model">model.name</field>
    <field name="inherit_id" ref="base_module.view_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='description']" position="after">
            <field name="my_new_field"/>
        </xpath>
    </field>
</record>
```

**Position values** (apply to both `<xpath>` and the field-name shorthand):
- `inside` (default) — content appended inside the matched element
- `replace` — content replaces the matched element entirely (a lone `$0` text node inside the replacement re-inserts a copy of the original node, letting you "wrap" rather than fully discard it)
- `after` / `before` — content inserted as a sibling after/before the matched element
- `move` — relocates an existing node to a new position (used less often, but essential for reordering fields already present in a parent view)

**Matching rules:** an `<xpath expr="...">` uses a real XPath expression against the parent arch; a bare `<field name="x">` element matches the first field with that name; any other tag matches the first element with the same tag and identical attributes (ignoring `position`).

**Resolution order:** if a view has a parent, the parent is fully resolved first, then the current view's specs are applied; a view's own children (other views that inherit from it) are then applied depth-first — child first, then its children, then siblings.

**Why this matters for your tool:** when a user customizes a *stock* Odoo model (e.g. adding fields to `sale.order` rather than building `rental.contract` from scratch), your generator must emit an inheriting view record, not attempt to overwrite the original — overwriting core views breaks on every Odoo upgrade and is exactly the kind of mistake that makes hand-rolled customizations fragile. Studio does this correctly under the hood; your generator needs to as well.

## 6. Security model — access rights, record rules, field-level security

Three independent layers, all of which your generator must produce together or a "working" customization will still be a security hole:

### Layer 1 — Access rights (`ir.model.access`, via CSV)
Controls model-level CRUD (can this group read/write/create/delete records of this model *at all*). Defined in `security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_rental_contract_user,rental.contract.user,model_rental_contract,base.group_user,1,1,1,0
```
Access rights are **additive** — a user's permissions are the union of every group they belong to. No access-right entry for a model means *no* access for anyone outside superuser, regardless of record rules — this is the most common "why can't anyone see this new model" bug, and your generator should always emit at least one baseline ACL per new model.

### Layer 2 — Record rules (`ir.rule`, via XML)
Filters *which records* within a model a user can act on, expressed as a domain:
```xml
<record id="rule_rental_contract_branch" model="ir.rule">
    <field name="name">Rental Contract: only own branch</field>
    <field name="model_id" ref="model_rental_contract"/>
    <field name="domain_force">[('branch_id', 'in', user.branch_ids.ids)]</field>
    <field name="groups" eval="[(4, ref('group_rental_agent'))]"/>
</record>
```
Record rules are **default-allow**: if a model has access rights granting a permission and no rule targets that operation for the user, access is granted. Rules combine per operation (`perm_read`/`perm_write`/`perm_create`/`perm_unlink` on the rule itself indicate which CRUD operations the rule's domain applies to). A common real bug: creating multiple *global* (no-group) rules that don't overlap correctly can silently deny all access — your generator should default to group-scoped rules and warn if a global rule is being created.

### Layer 3 — Field-level security
Any field can carry a `groups` attribute restricting visibility/writability to specific security groups — restricted fields are automatically stripped from views and `fields_get()` responses for users outside the listed groups, and direct read/write attempts via RPC raise an access error. This is the mechanism to expose for "hide the cost/margin field from front-line staff" type requests.

### Groups (`res.groups`)
Organize users by role; groups can imply/inherit from other groups (e.g., "Sales Manager" implies "Sales User" implies "Internal User"), forming a hierarchy. Your builder's security UI should let users define this hierarchy visually rather than editing raw CSV — this is one of Studio's genuine UX wins worth matching.

## 7. Automation rules — the no-code business-logic engine

**Tier/edition dependency — read this before the rest of the section:** the `base_automation` module that powers this feature is bundled with Studio, not with Community/base Odoo generally — in practice, it installs automatically when Studio is installed, and typically isn't present (or exposed in the UI) on installations that don't have Studio. Concretely: **this is not usable on an Odoo Online subscription unless that subscription is on Odoo's Custom plan tier (the one that includes Studio)** — Standard-tier Online customers, and any Community installation, won't have this model available at all. This is a hard, subscription-level gate your builder must detect (via live-instance module introspection — Document 5's Path B, checking for `base_automation`/`web_studio` in the installed-modules list) before offering the automation-rule builder UI, not a "works everywhere" mechanism the way Sections 2–6's field/view/menu/security mechanisms are.

This is Studio's **Automations** feature (backed by the `base.automation` model) — the mechanism for "when X happens, do Y" without writing Python, and the single most important piece to replicate well since it's most of what separates a "form builder" from a genuine no-code app platform, **on the instances where it's actually available.**

### Structure
Every automation rule has:
1. **Model** — which model the rule watches
2. **Trigger** — the event category (see below)
3. **Before Update Domain / Apply on domain** (conditions) — a domain filter checked before/after the triggering change; this is how you express "only when field X was previously unset AND is now set" style conditions, which is common for "first time this happens" logic
4. **Actions** — one or more actions, executed in the order defined (so a later action sees the effects of an earlier one within the same rule)

### Trigger categories (current, v17–v19; broadly consistent since v14 with additions)
- **On creation** — record created and saved
- **On update** — a previously-saved record is edited and saved; can be scoped to specific "trigger fields" so it only fires when those particular fields change
- **On creation & update** — combination of the above two
- **On deletion**
- **Based on form modification** ("on UI change") — fires on unsaved, in-progress edits in the form, before the record is saved; restricted to "Execute Code" actions and only fires on manual edits (not when another automation changes the field)
- **Based on date** (time-based) — fires a defined delay before/after a date field's value is reached (e.g., "3 days before the return date" or "7 days after last update") — this is exactly the mechanism your car-rental "overdue return" automation needs
- **On webhook** — fires from an external HTTP(S) request hitting a generated, secret-bearing URL; a "Target Record" code snippet determines which record(s) the payload maps to

### Action types
- **Execute Python code** — raw code block (has access to helper variables like `record`, `env`); this is the escape hatch for logic too complex to express declaratively, and the one action type your no-code UI should gate behind a "review as code" step rather than free-form user input, per the earlier design doc's security note
- **Create a new record** — on the same or a different target model, optionally linking back via a designated field, with a "Data to Write" tab for setting field values (either literal values or references to other records)
- **Update the triggering record**
- **Send an email** (via a mail template)
- **Add followers** (chatter subscription)
- **Create a next activity** (call, meeting, reminder — ties into the Activity view/mixin)
- **Execute several actions** — chains/calls other server actions

### Practical notes for your generator
- Automations that only need "if condition then update field / send email / create activity" map cleanly to a declarative `base.automation` record — no code generation needed, this is squarely in your Phase 4 no-code territory.
- Anything needing actual computation beyond a domain filter (e.g., dynamic pricing math, external API calls) should route to your Phase 5 module-export path as a real Python method, with the automation rule calling it via "Execute Python code" or a proper compute method — don't try to force complex logic through the declarative UI; it degrades UX and invites the security issues noted above.

## 8. Reports — QWeb PDF reports

Distinct from the "reporting views" (Graph/Pivot) — this is the printable-document layer (invoices, contracts, delivery notes).

**Mechanism:** a report is declared via an `ir.actions.report` record pointing at a **QWeb template** (an `ir.ui.view` of type `qweb`, or a `<template>` element in a data file). The template is regular HTML with QWeb directives (`t-foreach`, `t-if`, `t-field`, etc.) — rendering context automatically exposes the records being printed (`docs`), and PDF rendering itself happens via `wkhtmltopdf`.

```xml
<template id="report_rental_contract_document">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="o">
            <t t-call="web.external_layout">
                <div class="page">
                    <h2>Rental Agreement #<span t-field="o.name"/></h2>
                    <p>Customer: <span t-field="o.customer_id.name"/></p>
                </div>
            </t>
        </t>
    </t>
</template>
```

- `web.external_layout` provides the standard header/footer (company logo, address).
- Reports inherit and extend the same way views do (xpath-based), so a customization can add a line to an *existing* report (e.g., a standard invoice) rather than needing a full rewrite.
- Reports can be viewed in-browser as HTML (not just downloaded as PDF) and carry the same access-right checks as any other Odoo data.
- Translation support requires defining a matching translatable template variant and invoking it with `t-lang`.

**For your builder:** a report designer is a natural v2 feature once the view designer (Section 3) exists, since the underlying mechanics (QWeb + xpath inheritance) are the same skill — reuse the same drag-drop canvas concept, targeting a print layout instead of a screen view.

## 9. Actions & menus — wiring views into the navigation

- **`ir.actions.act_window`** — the "window action" connecting a menu click to a model + a set of views (form, list, kanban, etc.) + default filters/context.
- **`ir.ui.menu`** — the actual clickable menu entry, with a `parent_id` for nesting and a `sequence` for ordering. Top-level menus (with no parent) become "apps" in the main app switcher if the module's manifest sets `application: True`.
- **Smart buttons** — the small stat-buttons in a form view's top-right ("5 Rentals", "3 Damage Reports") that link to related records via a `button` element with `type="object"` calling a method that returns an `act_window` action filtered to the related records. This is one of the highest-value "feels professional" details Studio nails and generic AI-generated modules often skip — worth hard-coding into your rules engine (Section 5 of the earlier design doc) as an automatic addition whenever a one2many/many2one relationship is detected between two workflow models.

## 10. Chatter, activities, and sequences (supporting infrastructure)

- **`mail.thread`** (inherit mixin) — adds the chatter (message log, followers, logged changes) to any model. Almost every "serious" business model should inherit this — it's what gives an app the audit-trail feel of a real ERP module rather than a toy CRUD app.
- **`mail.activity.mixin`** — adds the "schedule an activity" (call, meeting, to-do) feature, and pairs with the Activity view type.
- **`ir.sequence`** — generates the "REF/0001"-style reference codes ERP records need (invoice numbers, contract numbers). Defined once per sequence, then referenced from a model's `_get_default` for its reference field. Your Inventory ID Generator project already implements this exact pattern (`PREFIX/INITIALS/NUMBER`) — the logic transfers directly to Odoo's `ir.sequence` mechanism, just swapping your AppleScript-based generator for Odoo's native one.

## 11. OWL — the JavaScript framework layer

Odoo's frontend (from v14 onward, and the sole framework by v17+) runs on **OWL (Odoo Web Library)** — a component-based, reactive framework Odoo built in-house rather than adopting React/Vue, specifically so third-party modules can override/extend other modules' frontend components without patching core files (a constraint tied to Odoo's addon/upgrade model). Components pair a JS class (state, lifecycle hooks like `onMounted`/`onWillStart`, methods) with an XML template using QWeb syntax for structure and data binding.

**Relevance to your tool:** you generally don't need to touch OWL directly — your generator produces declarative XML (views, actions) that the existing OWL-based web client already knows how to render. You'd only drop into OWL/JS territory for genuinely custom interactive widgets (a bespoke field widget, a custom dashboard component) that no combination of existing widgets can express — treat this as an advanced/manual-code escape hatch, not something your prompt-to-module pipeline should attempt to generate, since JS generation quality from a 7B model is far less reliable than structured XML/JSON generation.

## 12. UI/UX evolution by version — what to target and what to ignore

| Version | Notable UI/UX-relevant changes |
|---|---|
| **16.0** | Baseline for this compendium's oldest supported target; mature OWL adoption for most core views. |
| **17.0** | Significant visual redesign focused on usability/aesthetics: reworked dropdown "View all" behavior, more efficient default advanced-search filters (search on records rather than raw text), avatar-click info cards, left-aligned map sidebar (consistency with other views), chatter message/note translation. Grid view rebuilt on OWL (enabling sample-data display). Progressive Web App installability. |
| **18.0** | Further Gantt view redesign (zoom in/out, horizontal scroll, one-task-per-line). Various app-specific UI reworks (POS session UI revamp, manufacturing UI revamp). Studio gained the ability to define whether records can be duplicated, and to be opened from any view regardless of how it was reached. |
| **19.0** | Contact form/model reworked for clarity (linked records visible at a glance). Streamlined activity creation (quick "today/tomorrow/next week" scheduling). Mobile improvements including offline search execution and a redesigned mobile login flow. Broader AI integration across modules (lead assignment, business-card scanning-to-lead). Gantt view gained an explicit "Scheduling" option in Studio enabling drag-and-drop schedule/unschedule via a side panel. |

**Practical targeting advice:** the *view/widget/security/automation mechanisms* in Sections 3–7 above are stable across all four versions — this is your safe common core to build against first. Version-specific UI polish (the redesign details in the table) mostly affects Odoo's *own* built-in screens, not the views your generated modules produce, so you don't need to chase every point release's cosmetic change. Where it does matter: automation-rule trigger options have grown incrementally (webhook trigger and "on UI change" are more recent additions) — if you're targeting v16 specifically, verify a given trigger type exists before offering it in your builder's UI for that version.

## 13. What Studio can do that's worth explicitly matching (recap from the version-comparison discussion)

- Full field/model/view/menu/security/automation editing, live, inside the running instance.
- Export customizations as an installable, version-controllable module.
- Report (PDF) layout editing.
- Approval workflows (a Studio feature not covered in depth above — worth a dedicated research pass when you get to that phase, since it's a distinct mechanism from automation rules: it gates a button/action behind one or more required approvers rather than reacting to a data change).

## 14. Images and media — the full pipeline

This is directly what powers product photos, contact avatars, employee pictures, and any "attach a picture to this record" need — and it's a distinct field type from generic file storage, with its own conventions your generator should follow exactly to match Studio/core quality.

### `Binary` vs `Image` field
- **`Binary`** stores *any* file type (PDF, zip, spreadsheet) with no format validation or processing.
- **`Image`** (a specialized field type, not just a widget) is specifically for image files. It validates that the upload is actually an image, and — critically — **resizes automatically on save** while preserving aspect ratio, so users never have to pre-resize anything themselves.

### The multi-resolution convention (`_1920`/`_1024`/`_512`/`_256`/`_128`)
Odoo's own product/contact/employee models don't store one image field — they store one **base field** at max resolution plus several **computed, related sub-size fields**, following a naming convention your generator should replicate for any model that needs an image shown in more than one context:
- `image_1920` — the actual stored field (max 1920px, the source of truth)
- `image_1024`, `image_512`, `image_256`, `image_128` — computed/related fields that resize down from the 1920 source on the fly

**Why this matters practically:** a kanban view showing 50 cards should render `image_128`, not `image_1920` — fetching a small thumbnail per card is far faster than loading the full-resolution image 50 times. Your rules engine (from the earlier design doc's Section 5) should auto-generate this sub-field set whenever a user adds an Image field and flags it for use in a list/kanban view, rather than making them think about performance themselves — this is exactly the kind of "invisible expert default" that separates a professional-grade generator from a naive one.

### Display conventions
- `widget="image"` is the field widget; the `oe_avatar` CSS class is the standard convention for square, contact/profile-style avatar rendering (used throughout core for users, contacts, employees).
- Size can be overridden per-view via `options="{'size': [300, 300]}"` on the field, letting the same underlying field render differently in different views (e.g., large on the form, tiny in a list).
- Images are stored as base64-encoded attachments; for anything beyond ordinary user-driven upload (e.g., bulk-importing hundreds of product photos programmatically), the practical path is writing base64 image data directly via the RPC API rather than driving the UI — worth exposing as a "bulk image import" utility in your tool for the fleet-photo, product-catalog-photo type use case.

### For your generator
Any model resembling a "thing with a photo" (vehicles, products, staff, patients, properties) should default to: one `Image` field named clearly (`image` or a descriptive `x_photo`), auto-generated `_128`/`_256` computed variants if the model is used in kanban/list views, `widget="image"` with the `oe_avatar` class if it's a profile-style single subject, and plain `widget="image"` without that class for general content photos (e.g., a damage-report photo, which isn't an "avatar" concept).

## 15. Niche and specialty widgets worth knowing

Beyond the widget catalog in Section 4, Odoo's internal widget registry includes many narrower-purpose widgets. Not all are meant for general reuse (some are tightly coupled to specific core apps), but the patterns are worth recognizing so your builder doesn't reinvent them badly:

- **`priority`** — the star-rating selection widget (used for lead/task priority in core CRM/Project). Backed by a plain Selection field; any workflow needing a lightweight urgency indicator can reuse this pattern instead of inventing a new UI.
- **`kanban_state`** (a specific selection widget, distinct from the general `statusbar`) — the small colored dot/indicator on a kanban card signaling "on track / blocked / ready," independent of the main stage/status field. Genuinely useful in your rental example for flagging "vehicle needs attention" without overloading the main workflow state.
- **`color` / color picker** — stores an integer mapped to a fixed palette, used for kanban card color-coding (e.g., color-code vehicles by category). Distinct from the `Use colors` option on Tags fields (Section 4), which colors individual tag pills rather than the whole card.
- **`boolean_favorite`** / **`boolean_toggle`** — star/toggle-style rendering for boolean fields instead of a plain checkbox — small UX detail, but exactly the kind of polish that makes a generated app feel native rather than generic.
- **`many2many_tags_avatar`** / **`many2one_avatar_user`** — relational widgets that render the linked record's avatar image alongside its name (e.g., assignee avatars on a kanban card) — combines directly with Section 14's image conventions.
- **`activity_exception`** — a small icon indicating an overdue/exception activity exists on a record, shown inline in list/kanban views.
- **`state_selection`** — a specialized statusbar-adjacent widget used for stage pipelines with a fixed small set of "kanban state" style values, distinct from a full custom Selection-based statusbar.
- **`domain`** — a visual, filterable-condition-builder widget for editing a `domain` value (used, for example, when a user needs to define which records an automation rule or record rule applies to). This is directly relevant to your builder: rather than asking users to hand-write Odoo domain syntax (`[('field', '=', 'value')]`), reuse this widget's UX pattern in your own condition/automation builder UI.

**Practical implication:** most of these are narrow-purpose and app-specific in core Odoo, so don't try to expose the entire internal widget registry in your builder's UI — that would overwhelm non-technical users. Instead, curate a "recommended widget" shortlist per field type (the way Studio does) and treat the wider catalog as an "advanced/technical" toggle for power users.

## 16. Barcode — what's core vs. third-party

Worth being precise here since it's easy to overpromise: Odoo's **core Barcode/Inventory functionality** (assigning barcodes to products, scanning to drive stock-movement workflows) is a full built-in application, present in both Community and Enterprise, designed around dedicated hardware scanners or the mobile app's camera within that specific app's screens.

A **generic "scan into any field on any custom form" widget**, however, is *not* a stock Odoo feature — the field-level barcode/QR scanner widgets that do this (scanning via webcam/phone camera into an arbitrary Char field) are third-party marketplace modules (several proprietary, a few OCA/community-licensed), not part of core. If your no-code builder wants to offer "add barcode scanning to any field," that's a genuine value-add feature to build yourself (a generic OWL field-widget wrapping a JS barcode-scanning library), not something you get for free from the platform — worth flagging honestly to prospective users rather than implying it's a native Studio-equivalent capability, since it isn't.

## 17. Approval rules — Studio's action-gating workflow (distinct from Automation rules)

This is a different mechanism from Section 7's automation rules — automations *react* to data changes; approval rules *gate* a button/action behind required sign-off before it can be performed at all. Worth its own place in your builder since the UX and data model are both distinct.

**Structure (consistent core concept v16–v19, though the setup flow's exact steps evolved):**
- Attached to a specific **button** on a specific view (e.g., the "Confirm" button on a purchase order).
- One or more **approval steps**, each specifying who can approve — by individual **Approver** users and/or an **Approver Group** (a security group scoped to approval duty).
- Steps can be **exclusive** (a user who approved one step cannot also approve another step on the same record — prevents self-approval chains) and can carry **approval order** (sequential gating).
- Steps can be made **conditional** — a filter determines whether a given step even applies to a particular record (e.g., only require finance approval above a certain contract value).
- If an unauthorized user clicks the gated button, they're blocked with an error and an activity is auto-created for the designated approvers, rather than the action silently failing.
- All approve/reject/revoke actions are logged in the record's chatter, and a dedicated technical log (**Studio Approval Entries**, under developer mode) tracks every approval event for audit purposes.

**Distinct from the standalone "Approvals" app:** Odoo also ships a separate **Approvals** application (a general-purpose request/approve workflow app for things like purchase requests or time off) with its own sequential-approval-chain configuration (multiple approval levels, minimum-approvals-required thresholds, role-based approvers). That's a different, heavier-weight tool for standalone approval *processes*; Studio's approval rules are lighter-weight and attach directly to an existing button/action on an existing model. Your builder should offer Studio-style button-gating as the default (it's what most customization requests actually need — "require a manager to approve before this rental contract can go active") and treat the full standalone Approvals-app pattern as a more advanced feature for later.

## 18. Property fields — the schema-less field type (v17+)

A distinct mechanism from both regular custom fields and Studio's `x_studio_*` fields, introduced in the v17 generation and worth understanding because it solves a specific problem regular custom fields don't: **per-parent-record-type flexible fields without a schema migration.**

**How it differs from a regular field:** a Property field is *not* a database column — it's stored as structured data attached to records, scoped to a **parent record** (for example, properties defined for tasks are actually configured per-*project*, so different projects can have different task properties; properties on a product line up with the product's category). This means:
- Adding/removing a property doesn't require a schema migration the way adding/removing a real `ir.model.fields` entry does.
- Records linked to different parents (different projects, different product categories) can have genuinely different property sets, which a single shared custom field cannot express without a Selection/conditional-visibility workaround.
- The available property types cover the common cases (text, checkbox, integer, decimal, date, selection, tags, many2one, many2many) — not the full custom-field type catalog, but enough for most "lightweight, contextual extra data" needs.

**When to offer this vs. a regular custom field in your builder's UI:** if a user wants "the same field on every record of this model regardless of context," that's a regular field. If they want "different extra fields depending on which project/category/parent this belongs to" — the classic symptom being a request like "I want different custom fields for hardware tasks vs. software tasks within the same Project app" — properties are the right mechanism, and building this distinction into your builder's UI (rather than only offering regular custom fields) is a genuine differentiator, since generic AI-generated modules built from a flat schema mindset tend to over-rely on Selection-gated conditional fields where a property field would be both simpler and more correct.

## 19. Financial operations — integrate, never reinvent

This section exists because Accounting is architecturally different from everything else in this document, and your builder needs a distinct guardrail for it, not just a widget/view mapping.

### Why it's different
- **Legal exposure, not just UX risk.** A chart of accounts, tax computation, and a posted journal entry are artifacts a tax authority can audit. A bug here isn't cosmetic.
- **Jurisdiction-specific by design, not by oversight.** Odoo Accounting isn't one system — it's a shared engine plus a **fiscal localization package** (`l10n_XX` module) per country, installed automatically based on the company's registered country, providing that country's chart of accounts, tax groups, and fiscal positions. Each company in a multi-company setup can run a different package, and a company can only switch packages before it has posted its first entry.
- **Fiscal positions handle tax/account mapping automatically** — they map which tax and which income/expense account applies based on the customer's country or country group, can auto-detect based on conditions, and can carry legally-required notes that must print on the resulting documents. This is a rules engine in its own right, already built and already correct for each supported country — not something to approximate.

### What Studio itself does and doesn't allow here (the actual boundary to match)
Studio **does** let you drop new fields (Monetary, Selection, Many2One, Related, etc.) directly onto invoice/accounting form views and add columns to printed PDF layouts — this is presentation-layer and safe, and your builder should offer the same. Studio's ceiling is reached once you need to coordinate multiple inherited reports, share CSS across several documents, or override methods on `account.move` itself — at that point even Odoo's own documentation points to writing a real, developer-authored module. That's the exact line your tool should also draw.

### The rule for your builder
**Financial models (`account.*`, `l10n_*`, and by extension anything feeding posted entries) are link-only targets for your no-code/AI pipeline — never logic-generation targets.**

- Your field/view/menu builder (Sections 3–4) can freely add fields to, or read from, accounting models — this is presentation, same as Studio.
- Your automation-rule builder (Section 7) and AI module-generation pipeline should **hard-reject** any generated automation or business logic that writes to `account.move`, `account.move.line`, `account.tax`, or similar — route these to a deterministic, human-reviewed "Connect to Invoicing" flow instead of open generation.
- Your module generator should never attempt to create or select a chart of accounts or tax configuration. That's what fiscal localization packages exist for; your generator's job is to *detect* that a generated module needs invoicing and prompt the user to confirm the right `l10n_XX` package is installed for their company's country — not configure taxes itself.

### The safe integration pattern (what "Connect to Invoicing" should generate)
For any custom model that needs to bill someone (your rental contract, a service job, a subscription):
1. Add an `invoice_ids` (One2many to `account.move`) relation — the same pattern `sale.order` uses.
2. Add a "Create Invoice" button that calls Odoo's existing, standard invoice-creation method rather than hand-assembling journal entries — the generated module becomes a thin wrapper around logic the Accounting team already built and maintains for tax correctness, exactly the way `sale.order`'s own advance-payment/invoice-creation methods work and are meant to be extended (via `_inherit`, calling `super()`), not replaced.
3. Add the `account` (and typically `sale`) module as a manifest dependency, not a re-implementation.
4. Leave tax computation, account determination, and posting entirely to the standard flow — your custom model supplies the business context (what's being billed, to whom, for how much), Accounting's engine handles the legally-sensitive part.

This is the same principle as the read-only vs. link-only distinction your builder already needs elsewhere, just with materially higher stakes given the regulatory surface.

## 20. Odoo's visual identity & UI component conventions

This section is about matching the *feel* of Odoo's interface — colors, typography, navigation chrome, and iconography — so your app reads as familiar to someone who already uses Odoo daily, rather than needing to reverse-engineer pixel-perfect values from screenshots.

### Brand colors
Odoo's primary brand purple has shifted over major versions — worth knowing the history since screenshots/tutorials from different eras show different values:
- Original Enterprise purple: `#875A7B`, paired with a teal secondary accent `#00A09D`.
- Since the v15-era rebrand, the primary purple darkened to `#714B67` (Odoo's own release commentary describes this explicitly as a deliberate shift to "a slightly darker purple").
- Odoo's public brand guidelines also specify a gradient variant (roughly 150° from `#875A7B` to `#62495B`) for marketing use, plus a small neutral gray scale for text/backgrounds (dark charcoal tones in the RGB(33,39,43)–RGB(107,109,112) range).

These are **SCSS variables** (`$o-brand-primary`, `$o-enterprise-color`, `$o-enterprise-primary-color`), not hardcoded CSS — Odoo's theming system compiles them into the actual runtime stylesheet via `primary_variables.scss`/`bootstrap_overridden.scss` overrides layered on top of Bootstrap (Bootstrap is included by default; Odoo's asset bundles like `web._assets_primary_variables` and `web._assets_backend_helpers` control which variables are available where).

**Practical recommendation, and the one that matters most:** don't hardcode the hex values above into your app and call it done — compiled brand values can drift by point release, and hand-copied hex from old tutorials (like the `#875A7B` still floating around plenty of guides) is already stale. The more robust approach, consistent with this whole document's "integrate with the real mechanism" philosophy: **extract the actual compiled CSS custom properties/variables directly from a live target Odoo instance's asset bundle** when your app first connects to a customer's instance, and derive your own theme from those live values rather than a value you assumed in advance. This also means your look-and-feel automatically stays current as Odoo's branding evolves, without you needing to track every release's palette tweak.

### Typography
This is a common misconception worth correcting directly: Odoo's **backend web client does not ship a custom brand webfont**. Its actual font stack (confirmed directly from Odoo's own Bootstrap variable overrides) is the standard modern **system font stack** — `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", "Liberation Sans", Arial, sans-serif`. In practice this renders as San Francisco on macOS, Segoe UI on Windows, and Roboto on Android/Linux — Odoo deliberately uses each OS's native font rather than forcing a webfont, which is both a performance choice (no font download) and a "feels native" choice.
- Odoo's separate **marketing/brand guidelines** (logo, website, brand collateral) do specify custom fonts — Montserrat for headings, Open Sans for body copy — but that's for Odoo's own marketing materials, not what the actual application UI renders with. Don't import Montserrat/Open Sans into your builder's generated apps expecting it to "match Odoo" — it won't, because the real backend doesn't use them either.
- **Practical recommendation:** default your own app to the same system font stack. It's simultaneously the most accurate match, the best-performing choice, and requires zero font-loading work.

### The fixed 11-color palette (tags, kanban cards)
Odoo's tag/kanban color picker has long used a fixed palette of 11 named colors (plus "no color" at index 0), consistent across recent versions: **Red, Orange, Yellow, Light blue, Dark purple, Salmon pink, Medium blue, Dark blue, Fuchsia, Green, Purple** (indices 1–11 in that order). This is the palette your color-picker widget (Section 15) should offer by default for any Many2many-tags or kanban-card-color field, both because it's what users already recognize and because generated data (a color index integer) round-trips correctly with real Odoo instances. As with the brand colors above, the exact hex behind each named color has shifted slightly across versions — sample it from the live instance's CSS rather than assuming a fixed hex table, and treat the *names/positions* as the stable contract, not the exact color values.

### Navigation chrome — the structural conventions
- **`.o_main_navbar`** — the top navigation bar (app switcher grid on the left, current app's menu structure across the top, systray on the right). Its background uses the brand-primary variable, which is why the top bar is the most visually "Odoo-branded" strip of the whole interface.
- **App switcher** — a grid of app icons, each a colored square/rounded-square tile with an icon and label; this is the entry point equivalent to your builder's own "which app am I in" concept.
- **Systray** (top-right icon tray) — houses global, cross-app elements: notifications/activities bell, the Discuss messaging icon, the user avatar/menu, and (in developer mode) technical/debug tools. If your app has any persistent global controls (notifications, account menu), this is the conventional location users will expect them.
- **Breadcrumb** — sits directly under the navbar, shows the drill-down path for the current record (e.g., "Rentals / Contract #0042"), and is a first-class navigable element (click any earlier crumb to go back up), not just a passive label. Your view designer's generated forms should default to breadcrumb navigation for any drill-down (parent list → record detail) rather than inventing a different back-navigation pattern.
- **Control panel** — the area just below the breadcrumb holding action buttons (New, and record-specific buttons like Confirm/Cancel) on the left and view-switcher/search/filters on the right. This consistent left-actions/right-search split is one of the most recognizable Odoo layout conventions and worth replicating exactly in your generated form/list views.
- **Button conventions** — a solid, brand-colored button (Bootstrap's `btn-primary`, tinted with the brand purple) marks the primary/recommended action on a screen (Save, Confirm, Create); secondary actions (Discard, Cancel, Back) use an outlined/neutral `btn-secondary` style. Your generated views should follow this exact one-primary-button-per-screen convention rather than presenting several equally-weighted buttons, which is a subtle but important part of why Odoo's UI feels decisive rather than cluttered.

### Icons — two registries, not one
Odoo's UI draws from **two separate icon systems**, and knowing the boundary matters for your builder's icon picker:
- **FontAwesome** (`fa-` prefixed classes) — the default for the large majority of common icons (actions, objects, status).
- **Odoo's own custom icon font** (`oi` base class plus a specific icon class, e.g. `oi-apps`) — built specifically to cover functionality FontAwesome doesn't have iconography for. These are Odoo-specific concepts (the app switcher icon, certain Odoo-specific UI affordances) rather than generic symbols. Directional icons in this set have automatic RTL adaptations (flipped 180° for right-to-left languages) — worth replicating if you expect any Arabic/Hebrew-reading customers.
- There's also a **separate SVG-based icon set specifically for the Spreadsheet feature**, rendered via QWeb rather than an icon font — narrow-purpose, low priority for your builder.

**Practical recommendation for your icon picker:** default to FontAwesome for anything generic (a trash can, a checkmark, an arrow) since it's the larger, better-documented, more broadly-known set — and only reach for Odoo's `oi-` icons when you're specifically trying to represent an Odoo-native concept (e.g., an "app" tile) that FontAwesome genuinely has no equivalent for. Trying to use `oi-` icons throughout would both limit your options unnecessarily and tie your rendering to Odoo's specific (and less-documented) icon-font asset, which is more fragile to depend on than FontAwesome's stable, widely-used class names.

### A caution worth naming directly (not a refusal, a business/legal consideration)
Matching Odoo's *layout conventions and general feel* (navbar structure, breadcrumb behavior, button hierarchy, system fonts) is good, sensible product design — it reduces the learning curve for anyone switching between your tool and Odoo itself. Reproducing Odoo's *exact* brand purple plus logo-adjacent styling in a way that could read as an official Odoo product, however, edges into trademark/brand-confusion territory — Odoo's own brand guidelines are explicit that the purple is meant to be identified specifically with Odoo. I'm not a lawyer and this isn't legal advice, but the practically safer path is: match the *structural* conventions closely (this section's navbar/breadcrumb/button/icon guidance), while giving your own app a distinct accent color rather than Odoo's exact purple — familiar shape, your own visual identity. This protects you from any brand-confusion concern and, longer-term, gives your product its own recognizable look rather than reading as a purple-tinted copy.

## 21. Open items worth a dedicated follow-up research pass

Now narrowed after this pass — still worth dedicated research when you reach these build phases:
- Full **Gantt/Grid/Map/Cohort** configuration options (Enterprise-only, lower priority per Section 3).
- Multi-company/multi-currency-specific view and security patterns (record rules that filter by `company_id`, multi-company field visibility rules).
- Translation/i18n mechanics in more depth (relevant given your Lagos base and any eventual multi-language customer base).
- The standalone **Approvals** application's full configuration model (sequential chains, minimum-approvals thresholds), as distinct from Studio's lighter button-level approval rules covered in Section 17.
- **Documents app** integration patterns (centralized attachment/file management across models) — relevant if your generated modules need more than basic per-record file/image fields.

# ═══════════════════════════════════════
# DOCUMENT 4: PROMPT ENGINEERING & MODEL SELECTION GUIDE
# ═══════════════════════════════════════

# Closing the Gap: Prompt Engineering & Model Selection for the Module-Generation Pipeline

## The honest starting point

A small local model and a frontier model differ in ways prompting alone can't erase: fewer parameters means less capacity to hold multiple constraints in mind simultaneously, weaker implicit world-knowledge depth, and much less reliable multi-step reasoning in a single pass. Claude (or any frontier model) can take an underspecified one-line prompt and correctly infer ten unstated requirements at once. A small model will drop several of them, invent inconsistent ones, or produce plausible-looking-but-wrong output — not because the prompt was bad, but because the model has less capacity to juggle everything at once.

**What this means practically:** your gains come from *doing the reasoning the model can't do reliably itself, outside the model* — in your pipeline's structure, your prompt scaffolding, your model choice, and (eventually) your training data — not from finding magic wording. The techniques below are roughly ordered from "immediate, cheap, do this first" to "bigger lever, more effort, do this once the pipeline is working."

## 0. Model selection — use Qwen3, not qwen2.5

Before any prompt engineering, the model you pick sets your ceiling. As of mid-2026, **Qwen3 has superseded qwen2.5 as the default recommended local model family** across independent model-comparison sources — it improved on qwen2.5 in reasoning, coding, and instruction-following at comparable speed and hardware cost, under the same Apache 2.0 license (no restrictions on commercial use or redistribution).

### The default: `qwen3:8b`
Swap this in directly where qwen2.5:7b was planned. Same rough hardware footprint, same Ollama workflow (`ollama pull qwen3:8b`), better baseline quality.

### The feature that actually matters most for your pipeline: native thinking mode
This is the single most consequential difference for a staged-generation pipeline like yours: **Qwen3 has a built-in, toggleable "thinking" mode** — the model can switch between doing explicit step-by-step reasoning before answering, and answering directly, without you having to hand-write a chain-of-thought scaffold in the prompt (see Section 4 below, which qwen2.5 required and Qwen3 makes largely unnecessary).

This maps directly onto the per-step reasoning-depth guidance in this document:
- **Thinking mode ON** for the reasoning-heavy steps — domain-scaffold matching, automation proposals, the completeness self-critique pass. The model was actually trained to reason well in this mode, which should be more reliable than a bolted-on CoT instruction.
- **Thinking mode OFF** for the high-volume extraction steps — per-model field listing, relationship mapping. You want speed and low variance here, not deliberation, and skipping the thinking step cuts latency meaningfully across the many parallel calls your pipeline makes per generation.

In Ollama, this is controlled per-call (check the current Qwen3 model card/Ollama docs for the exact parameter name and syntax at the time you implement this, since tooling details shift) — architect your `LLMProvider` wrapper (from the earlier module-generation design) to accept a `reasoning: bool` flag per call, and route it to whichever mechanism Qwen3/Ollama expects at build time.

### The size ladder — map pipeline steps to model sizes
Qwen3 ships a clean ladder: 1.7B → 4B → 8B → 14B → 30B (a Mixture-of-Experts variant, `30b-a3b`, with only ~3B active parameters per token despite 30B total weights). This lets you implement the mixed-model-size strategy (Section 9) within one consistent model family rather than mixing unrelated architectures:

| Tier | Model | Use for | Notes |
|---|---|---|---|
| Default/bulk | `qwen3:8b` | Per-model field listing, relationship mapping — the many-calls-per-generation steps | Thinking mode off |
| Reasoning-heavy | `qwen3:14b` | Domain-scaffold matching, automation proposals, completeness self-critique | Thinking mode on; test that ~9GB Q4 footprint runs acceptably alongside everything else on your MacBook Air before committing |
| Stretch/experimental | `qwen3:30b-a3b` | Same reasoning-heavy steps, if 14B proves insufficient | MoE architecture means faster inference than its 30B size suggests, but full weights still need to fit in memory — treat as an experiment, not a launch commitment, until confirmed tolerable on your actual hardware |

### Worth knowing about, not necessarily switching to
- **`gpt-oss-20b`** (OpenAI's Apache 2.0 open-weight release) — 128K context, genuine reasoning model. Worth a look for your single highest-stakes call (e.g., a final validation pass touching the financial-integration guardrails from the compendium's Section 19), but 20B is a heavier hardware ask than the Qwen3 ladder for comparable benefit on your actual pipeline steps.
- **DeepSeek-R1 distillations** — strong reasoning, but these are "think through everything, every time" models by design, which adds latency you don't need on narrow extraction steps. Better suited to one hard, standalone reasoning call than to a pipeline running dozens of small calls per generation.
- **Recommendation:** don't adopt either of these as your default. Keep them in mind as options for one specific future call if Qwen3's reasoning tier proves insufficient for a particular step.

## 1. Decomposition (you've already got this — it's the single biggest lever)

Your staged pipeline (entity extraction → per-model fields → relationships → workflow → automations → views) is doing the most important thing already: converting one task a small model does unreliably into many tasks it does reliably. Nothing below matters as much as this. If you only do one thing, do this.

## 2. Explicit schema-in-prompt, not schema-in-description

Frontier models can work from a schema *described* in prose ("output a JSON object with a models array..."). Small models are dramatically more reliable when the schema is *shown*, not described — a concrete example output, not an abstract spec.

**Weak (works fine for Claude, unreliable for a small local model):**
```
Output a JSON list of fields, each with a name, type, and label.
```

**Strong (show, don't tell):**
```
Output JSON in exactly this shape:
{
  "fields": [
    {"name": "pickup_datetime", "type": "datetime", "label": "Pickup Date & Time", "required": true},
    {"name": "customer_id", "type": "many2one", "relation": "res.partner", "label": "Customer", "required": true}
  ]
}
Only use these type values: char, text, integer, float, boolean, date, datetime,
selection, many2one, one2many, many2many, binary, monetary.
```
The second version gives the model a concrete pattern to imitate plus a closed vocabulary to constrain against — both measurably improve small-model JSON reliability.

## 3. Few-shot exemplars pulled from your domain template library

This is where your domain template library (from the earlier generation-pipeline design) does double duty — it's not just a source of scaffolding to *adapt*, it's also your source of **in-context examples** to show the model what "good" looks like for this task shape.

**Prompt structure for the per-model field-listing step:**
```
SYSTEM:
You are an ERP data modeler. You output only valid JSON, nothing else —
no explanation, no markdown fences, no commentary.

USER:
Example — for a "hotel room booking" entity, good field output looks like:
{"fields": [
  {"name": "room_id", "type": "many2one", "relation": "hotel.room", "label": "Room", "required": true},
  {"name": "checkin_date", "type": "date", "label": "Check-in Date", "required": true},
  {"name": "checkout_date", "type": "date", "label": "Check-out Date", "required": true},
  {"name": "guest_id", "type": "many2one", "relation": "res.partner", "label": "Guest", "required": true},
  {"name": "num_guests", "type": "integer", "label": "Number of Guests"},
  {"name": "state", "type": "selection", "label": "Status",
   "selection_options": ["draft", "confirmed", "checked_in", "checked_out", "cancelled"]}
]}

Now do the same for this entity:
Model: rental.contract
Purpose: tracks a single vehicle rental from pickup to return
Domain context: car rental service (fleet management, deposits, mileage limits, insurance)

Output ONLY the JSON, matching the exact shape above.
```
Notice the exemplar is *thematically adjacent but not identical* (hotel booking, not car rental) — this teaches the model the *pattern* (a workflow model needs a state field with a sensible lifecycle, relational fields point at real models, dates come in logical pairs) without it just copying the example's specific fields. Pull the closest 1–2 templates from your library's similarity search (Section 0 of the earlier pipeline design) as these exemplars dynamically, rather than hardcoding one fixed example for every call.

## 4. Reasoning before the final answer — prefer native thinking mode over manual chain-of-thought

Small models reason better when they're allowed to "think out loud" before committing to a final structured answer — but you only want the final JSON, not the reasoning, going into your pipeline's next step.

**With Qwen3 (preferred path):** use the model's native thinking-mode toggle (Section 0) instead of hand-rolling this. Turn thinking on for the reasoning-heavy steps and parse only the final structured answer from the response, discarding the reasoning trace. This should be more reliable than a manually bolted-on instruction, since the model was actually trained to reason well in this mode.

**Manual fallback (if you're testing against a model without native thinking mode, or as a debugging aid even with Qwen3):**
```
USER:
Think through what this model needs step by step, then give your final answer.

Step 1: what real-world objects/facts does this entity need to track?
Step 2: which of those are simple values vs. links to other models?
Step 3: does this entity have a lifecycle/status? If so, what are the stages?

After your reasoning, output a line containing only ---JSON--- followed by
the final JSON object on the next line, and nothing after it.
```
Parse everything after the `---JSON---` marker; discard the reasoning. This roughly doubles token cost per call. **Skip this (or thinking mode) for the easy steps** (e.g., "does this look like a workflow entity, yes/no") where deliberation adds latency without adding accuracy — reserve it for steps 3 (relationships) and 5 (automations) from your pipeline design, which need more implicit reasoning.

## 5. Temperature per step type — don't use one setting for everything

- **Extraction/structured steps** (field listing, relationship mapping, schema validation-adjacent tasks): temperature **0.1–0.2**. You want consistency and low variance, not creativity — a field list should be nearly deterministic given the same input.
- **Brainstorm/proposal steps** (Step 1 entity discovery, Step 5 automation proposals): temperature **0.5–0.7**. Some creative latitude helps here since you're eliciting possibilities, and your validation/rules-engine layer (Section 5 of the earlier design) catches anything that goes too far afield.
- **Self-critique/completeness-check step**: temperature **0.1–0.2** — this is evaluation against a checklist, which benefits from consistency, not creativity.

## 6. Self-consistency for the steps most likely to matter and most likely to vary

For any step where a wrong answer would be expensive to catch later (the domain-matching/scaffold-selection step, and the workflow-state-definition step), run the same prompt **2–3 times** at moderate temperature and either (a) take a majority vote on discrete choices, or (b) merge the outputs and let a human/your rules engine reconcile differences. This costs 2–3x the calls on a handful of pipeline steps but meaningfully reduces the "the model had an off run" failure mode that's more common with smaller models than frontier ones.

## 7. Negative examples and explicit anti-patterns

Small models benefit disproportionately from being told what *not* to do, because they're more likely to default to a generic/wrong pattern without that steer:

```
Do NOT invent a field type outside the allowed list.
Do NOT create a relation to a model that wasn't listed in the entity list above.
Do NOT add explanatory text before or after the JSON.
Do NOT use "id" as a field name — Odoo reserves this.
```
This reads as over-explicit for a frontier model (which infers most of this from context) — that's fine; the redundancy costs a few tokens and materially helps a small model.

## 8. Structured output enforcement at the decoding level, not just the prompt level

Prompting for JSON gets you most of the way; grammar-constrained decoding gets you the rest, and is worth using for every structured call regardless of how good your prompt is:
- Ollama's `format: "json"` parameter (basic JSON-mode constraint) should be the floor for every call in your pipeline.
- For tighter guarantees (enforcing the *exact* schema, not just "valid JSON"), look at libraries like `outlines` or `guidance` that constrain decoding to match a JSON schema or grammar directly — this eliminates an entire category of "almost right" failures (wrong field names, missing required keys) that no amount of prompting fully prevents with a small model, since the constraint is enforced by the decoder, not requested of the model.

## 9. Model-size mixing — use a bigger local model for the steps that need it most

You don't have to use the same model size for every pipeline step. This is now formalized as the Qwen3 size ladder in Section 0 — `qwen3:8b` for the high-volume, narrow, low-ambiguity steps that run many times per generation, and `qwen3:14b` (or the `30b-a3b` MoE variant, if your hardware tolerates it) for the few steps per generation that need more reasoning depth: domain scaffold selection, the automation-proposal step, and the completeness self-critique.

This mixed-size approach often closes more of the quality gap per dollar/compute-second than uniformly using the biggest model everywhere, because you're spending your compute budget where reasoning depth actually matters instead of spreading it evenly across steps that didn't need it.

## 10. The biggest lever, for later: distillation / fine-tuning on your own pipeline's output

Everything above is prompt-time (and now model-selection-time) engineering — real, effective, but with diminishing returns once you've applied it well. The technique that most directly closes the gap is **using a frontier model during development to generate a training set, then fine-tuning your chosen Qwen3 model on it**:

1. Run your staged pipeline's *prompts* through a frontier model (Claude, GPT-4-class) instead of Qwen3 for a batch of maybe 200–500 diverse example domains (rental, clinic, restaurant, real estate, etc. — your domain template library is a natural seed list to expand from).
2. Collect the frontier model's high-quality outputs at each pipeline step as `(prompt, ideal_output)` pairs.
3. LoRA fine-tune `qwen3:8b` (or whichever size you've settled on as your default) on this distilled dataset — a few hundred to low-thousands of examples is often enough for LoRA to meaningfully shift a small model's behavior on a narrow task distribution, and this runs on consumer hardware with libraries like `peft`/`unsloth`.
4. The fine-tuned model now has the *specific* task pattern baked into its weights, rather than relying on your prompt to re-teach it every single call — this is what actually gets a small local model closest to matching frontier-model *behavior on this specific task*, even though it'll never match frontier-model *general* capability.

This is worth doing once your pipeline and domain template library have stabilized (don't fine-tune against a schema/prompt structure that's still changing weekly) — treat it as a v2 investment once the prompt-engineered version is working end-to-end and you have real usage data (or your own frontier-model-generated synthetic data) to train on.

## Summary — what to actually implement, in order

1. **Model selection: `qwen3:8b` as default, `qwen3:14b` for reasoning-heavy steps** (Section 0) — do this first, it's a strict upgrade over qwen2.5 at the same integration cost.
2. Decomposition (already designed).
3. Show-don't-tell schemas + closed type vocabularies in every structured prompt.
4. Dynamic few-shot exemplars pulled from your domain template library.
5. Native thinking mode on for the reasoning-heavy steps (relationships, automations, self-critique), off for the bulk extraction steps.
6. Per-step temperature tuning (low for extraction, moderate for brainstorming).
7. Self-consistency (2–3 samples, vote/merge) on the highest-stakes steps.
8. Explicit negative-example anti-patterns in every prompt.
9. Grammar-constrained decoding (`format: json` minimum, schema-constrained decoding as a stretch goal) on every call.
10. Distillation/fine-tuning once the pipeline and template library have stabilized — the highest-effort, highest-payoff step, intentionally last.

# ═══════════════════════════════════════
# DOCUMENT 5: PROTECTED CORE MODULES — GUARDRAIL & RETRIEVAL
# ═══════════════════════════════════════

# Protected Core Modules: Guardrail Design & Source Retrieval

**Why this exists:** your AI generation pipeline and no-code builder should never propose redesigning, overriding, or reimplementing the business logic of Odoo's own sensitive core modules — only extend/link/inherit them (per Section 19 of the compendium, extended here to the full set of categories that deserve the same treatment). This document gives you (1) the real, source-verified list of what falls in that category, (2) a ready-to-use hard guardrail prompt, and (3) a script that retrieves the authoritative, version-correct list at build/connect time instead of relying on a hardcoded list that goes stale.

## 1. Why a hardcoded list is the wrong approach (and what to do instead)

Odoo Community alone ships **625 addon modules** in the 18.0 branch (verified directly from source while building this — see Section 3 for the method). That number shifts every version, and it doesn't include OCA modules, third-party marketplace apps, or whatever a specific customer's Enterprise subscription or custom installs add on top. A static list I hand you today is already an approximation and will be measurably wrong within a version or two.

**The right design: classify by pattern and origin, retrieve the actual list from source at build/connect time.** This section gives you the *categories and reasoning* (durable — these don't change even as module names get added/removed); Section 3 gives you the *script* that turns those categories into an accurate, current, per-target-instance list.

## 2. Protected categories — verified against real Odoo 18.0 source

Pulled directly from the live `odoo/odoo` GitHub repository's `addons/` and `odoo/addons/` directories (18.0 branch), not from memory or assumption. Each category below is a **pattern rule**, not a fixed list — apply the pattern, don't just copy today's matches.

### Tier 1 — Never generate logic against; link/extend only (highest stakes)

| Category | Pattern | Real examples confirmed in source | Why |
|---|---|---|---|
| **Accounting & Invoicing core** | `account`, `account_*` | `account`, `account_edi`, `account_edi_ubl_cii`, `account_payment`, `account_check_printing`, `account_debit_note`, `account_tax_python`, `account_peppol*` | Posted entries, tax computation, e-invoicing standards compliance (Section 19 of the compendium) |
| **Fiscal localization** | `l10n_*` | 232 modules confirmed in source — `l10n_us`, `l10n_uk`, `l10n_ng` (Nigeria — directly relevant to your Lagos base), `l10n_de`, etc. | Jurisdiction-specific chart of accounts, tax law compliance — see Section 19 |
| **Stock valuation** | `stock_account`, `stock_landed_costs`, `mrp_account`, `mrp_landed_costs` | Confirmed in source | Feeds directly into accounting entries (inventory valuation hits the books) |
| **Payment processing** | `payment`, `payment_*` | `payment_stripe`, `payment_paypal`, `payment_adyen`, `payment_mollie`, `payment_razorpay`, `payment_flutterwave` (again, relevant to your market), etc. | Real money movement, PCI-adjacent handling, external processor integrations with legal/compliance surface |
| **POS financial/tax logic** | `pos_account_tax_python`, `pos_*_stripe`, `pos_*_adyen`, `pos_*_razorpay`, `pos_online_payment*` | Confirmed in source | Same reasoning as payment processing, applied at point-of-sale |
| **Payroll** | `hr_payroll*`, `hr_payroll_account` | **Not in Community source — Enterprise-only.** Confirmed absent from the public repo. | Wage/tax withholding calculations are exactly the kind of jurisdiction-sensitive, legally-binding logic Section 19's reasoning applies to hardest |
| **E-signature (legal)** | `sign*` | **Not in Community source — Enterprise-only.** | Legally-binding signature/document integrity — same class of risk as accounting, different domain |
| **Subscriptions/recurring billing** | `sale_subscription*` | **Not in Community source — Enterprise-only.** | Automated recurring charges — direct financial exposure if generated logic miscalculates a billing cycle |
| **IAP (In-App Purchase billing)** | `iap`, `iap_*` | `iap`, `iap_crm`, `iap_mail` | Odoo's own metered-billing mechanism for services like SMS/lead enrichment — real money, external metering |

### Tier 2 — Core infrastructure; extend via documented inheritance only, never patch directly

| Category | Pattern | Real examples | Why |
|---|---|---|---|
| **Framework core** | `base`, `web` | Confirmed living under `odoo/addons/` (shipped inside the core package itself, not the general `addons/` tree) | Everything else depends on these; breaking them breaks the whole instance |
| **Authentication/security** | `auth_*` | `auth_oauth`, `auth_ldap`, `auth_totp`, `auth_password_policy*`, `auth_passkey`, `auth_signup` | Security-critical by definition — this is the technical enforcement of everything in Section 6 (security model) of the compendium |
| **Messaging/audit infrastructure** | `mail` | Confirmed core | Underpins the chatter/audit-trail mechanism (Section 10) that gives generated apps their audit-trail credibility — don't let generated automations bypass or corrupt it |

### Tier 3 — Extend freely, but still prefer inheritance over full rewrite (lower stakes, standard Odoo best practice)
Everything else — CRM, Sales, Inventory operations (non-valuation), Project, standard HR (non-payroll), Manufacturing (non-costing), Website, general POS features. Normal Section 5 (XPath inheritance) practices apply; no special hard guardrail needed beyond your general "extend, don't overwrite core views" discipline.

## 3. Retrieval script — for the Cursor agent to run at build time and at each new instance connection

Two complementary retrieval paths, since Community and Enterprise require different methods:

**Path A — Community module list, from Odoo's public source (version-correct, no auth needed).** Use a sparse git checkout (fast — only fetches the addon directory names, not blob content) rather than the GitHub REST API, which is aggressively rate-limited for unauthenticated requests and will fail under real usage.

**Path B — Live instance introspection via `ir.model.module`, covers Enterprise + OCA + custom modules actually installed on a specific customer's database**, which Path A can never see since Enterprise source isn't public and custom/OCA modules aren't in Odoo's own repo at all.

Combine both into one manifest your generation pipeline loads before every module-generation run.

```python
"""
protected_modules.py — retrieves and classifies protected Odoo modules
from source (Community) and live instance introspection (Enterprise/OCA/custom).

Usage:
    python protected_modules.py --version 18.0 --output protected_modules.json
    python protected_modules.py --version 18.0 --odoo-url https://customer.odoo.com \
        --db customer_db --api-key XXXX --output protected_modules.json
"""

import argparse
import json
import re
import subprocess
import tempfile
import xmlrpc.client
from pathlib import Path

# --- Category patterns: durable across versions, unlike the module list itself ---
PROTECTED_PATTERNS = {
    "accounting_core": re.compile(r"^account($|_)"),
    "fiscal_localization": re.compile(r"^l10n_"),
    "stock_valuation": re.compile(r"^(stock_account|stock_landed_costs|mrp_account|mrp_landed_costs|mrp_subcontracting_account|mrp_subcontracting_landed_costs)$"),
    "payment_processing": re.compile(r"^payment($|_)"),
    "pos_financial": re.compile(r"^pos_(account_tax_python|.*_(stripe|adyen|razorpay|paytm|pine_labs|six)|online_payment.*)"),
    "payroll": re.compile(r"^hr_payroll"),
    "esign": re.compile(r"^sign"),
    "subscriptions": re.compile(r"^sale_subscription"),
    "iap_billing": re.compile(r"^iap($|_)"),
    # Tier 2 — infra, extend-only
    "framework_core": re.compile(r"^(base|web)$"),
    "auth_security": re.compile(r"^auth_"),
    "messaging_audit": re.compile(r"^mail$"),
}

TIER_1_KEYS = {"accounting_core", "fiscal_localization", "stock_valuation", "payment_processing",
               "pos_financial", "payroll", "esign", "subscriptions", "iap_billing"}
TIER_2_KEYS = {"framework_core", "auth_security", "messaging_audit"}

def classify(module_name: str) -> str | None:
    for category, pattern in PROTECTED_PATTERNS.items():
        if pattern.match(module_name):
            return category
    return None

def fetch_community_modules_from_source(version: str) -> list[str]:
    """Path A: sparse git checkout of the addons directory tree — no blob
    content downloaded, just directory names. Fast and avoids GitHub API
    rate limits entirely."""
    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = Path(tmp) / "odoo-src"
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1",
             "-b", version, "https://github.com/odoo/odoo.git", str(repo_dir)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "sparse-checkout", "init", "--cone"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "sparse-checkout", "set", "addons", "odoo/addons"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "checkout"],
            check=True, capture_output=True,
        )
        names = set()
        for base in ["addons", "odoo/addons"]:
            p = repo_dir / base
            if p.exists():
                names.update(d.name for d in p.iterdir() if d.is_dir())
        return sorted(names)

def fetch_live_instance_modules(url: str, db: str, username: str, api_key: str) -> list[str]:
    """Path B: query ir.module.module on the actual target instance via
    XML-RPC. This is the ONLY way to see Enterprise modules (not in public
    source) plus any OCA/custom/third-party modules that customer has
    installed — the source-only path (A) is blind to all of these."""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, api_key, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    modules = models.execute_kw(
        db, uid, api_key,
        "ir.module.module", "search_read",
        [[["state", "=", "installed"]]],
        {"fields": ["name"]},
    )
    return sorted(m["name"] for m in modules)

def build_manifest(module_names: list[str], source_label: str) -> dict:
    manifest = {"source": source_label, "tier_1_never_generate_logic": {},
                "tier_2_extend_only": {}, "unclassified_count": 0}
    for name in module_names:
        category = classify(name)
        if category in TIER_1_KEYS:
            manifest["tier_1_never_generate_logic"].setdefault(category, []).append(name)
        elif category in TIER_2_KEYS:
            manifest["tier_2_extend_only"].setdefault(category, []).append(name)
        else:
            manifest["unclassified_count"] += 1
    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="18.0", help="Odoo branch/version to check out")
    parser.add_argument("--odoo-url", help="Live instance URL for Path B (optional)")
    parser.add_argument("--db", help="Database name (required if --odoo-url given)")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--api-key", help="API key/password (required if --odoo-url given)")
    parser.add_argument("--output", default="protected_modules.json")
    args = parser.parse_args()

    print(f"Fetching Community module list for {args.version} from source...")
    community_modules = fetch_community_modules_from_source(args.version)
    manifest = build_manifest(community_modules, f"odoo/odoo@{args.version} (source)")
    print(f"  {len(community_modules)} Community modules found, "
          f"{sum(len(v) for v in manifest['tier_1_never_generate_logic'].values())} Tier-1 matches, "
          f"{sum(len(v) for v in manifest['tier_2_extend_only'].values())} Tier-2 matches")

    if args.odoo_url:
        print(f"Fetching live installed-module list from {args.odoo_url}...")
        live_modules = fetch_live_instance_modules(args.odoo_url, args.db, args.username, args.api_key)
        live_manifest = build_manifest(live_modules, f"{args.odoo_url} (live instance, db={args.db})")
        print(f"  {len(live_modules)} installed modules found on live instance, "
              f"{sum(len(v) for v in live_manifest['tier_1_never_generate_logic'].values())} Tier-1 matches "
              f"(includes Enterprise/OCA/custom modules invisible to source-only check)")
        manifest = {"community_source": manifest, "live_instance": live_manifest}

    Path(args.output).write_text(json.dumps(manifest, indent=2))
    print(f"Manifest written to {args.output}")

if __name__ == "__main__":
    main()
```

**How to wire this into your pipeline:**
1. Run Path A once per Odoo version you support (16.0/17.0/18.0/19.0) at build time — cache the result, it only needs refreshing when you add support for a new version.
2. Run Path B automatically the moment your app connects to a new customer instance (Section 1 of the Production Plan's connection flow) — this is what catches Enterprise modules, OCA add-ons, and prior custom work specific to that customer, which no static or source-only list could ever know about.
3. Merge both into the manifest your generation pipeline's rules-engine validator (Section 5 of the AI Module Generation design) loads before every run, and hard-reject any generated automation/logic targeting a Tier-1 model.

## 4. The hard guardrail prompt

Inject this as a fixed system-level prompt segment on every call in your generation pipeline that could plausibly touch business logic (Steps 3–6 of the staged pipeline) — not just the automation-proposal step, since relationship-mapping and field-generation steps can also inadvertently point logic at protected models.

```
PROTECTED MODULE GUARDRAIL — NON-NEGOTIABLE

You are generating specifications for a no-code Odoo customization tool.
The following list of Odoo modules is PROTECTED. You must NEVER propose:
- new business logic, computed fields, or automation actions that write to
  any model belonging to these modules
- overriding, replacing, or reimplementing any behavior these modules
  already provide
- automations with a "trigger" or "action" targeting these modules' models

PROTECTED_MODULES = {{PROTECTED_MODULE_MANIFEST_JSON}}

You MAY:
- add a relational field (many2one/one2many) from a NEW custom model TO a
  model in a protected module (e.g., linking a custom "rental.contract" to
  "account.move" via an invoice_ids field)
- read/display fields from protected models in views
- propose that the user connect to a protected module's EXISTING, STANDARD
  workflow (e.g., "use the standard invoice creation flow") rather than
  generating new logic

If a user's request would require generating logic against a protected
module, respond with a structured refusal object instead of generating
the logic:
{
  "protected_module_conflict": true,
  "requested_capability": "<what the user asked for>",
  "protected_module": "<which module/category this touches>",
  "safe_alternative": "<the link-only pattern to offer instead>"
}

Do not attempt to satisfy the request by using a different field name,
wrapping the logic in a different automation type, or any other
rephrasing that achieves the same effect on a protected model. The
restriction is on the EFFECT (writing to / altering behavior of a
protected model), not the specific mechanism used to attempt it.
```

Note the last paragraph — it's there deliberately. A model (especially a smaller one under pressure to satisfy a request) can find a technically-different path to the same restricted effect (e.g., "the rule says don't touch `account.move` directly, so I'll trigger a webhook that calls an external service that touches it instead"). The guardrail needs to name the *effect* it's blocking, not just one *mechanism*, or it's trivial to route around by accident.

Substitute `{{PROTECTED_MODULE_MANIFEST_JSON}}` with the actual Tier-1 category list (names, not full module lists — keep the prompt token-efficient) generated by the script in Section 3, refreshed per Odoo version/instance rather than hardcoded once.

# ═══════════════════════════════════════
# DOCUMENT 6: ODOO ONLINE SUPPORT — COMPATIBILITY & GAP-FILLING
# ═══════════════════════════════════════

# Odoo Online Support: Compatibility Matrix & Gap-Filling Strategy

**Why this document exists:** Odoo Online is your largest realistic customer base (it's the default hosting choice for most SMEs, and the tier priced out of Enterprise Custom that this whole product targets), but it's also the most restrictive environment your app has to work inside — external API only, no server-side code deployment, no filesystem/SSH access, and — as clarified in this document — several Studio-dependent features gated behind a specific subscription plan, not just "Enterprise vs. Community." This document maps every capability discussed across the earlier documents against what's actually achievable on Odoo Online specifically, and gives a concrete strategy for each gap.

## 1. What Odoo Online actually restricts — precisely, not loosely

Recapping and sharpening the earlier tier discussion: Odoo Online is Odoo's own fully-managed SaaS. You get:
- Full external API access (XML-RPC/JSON-RPC) — same as any tier.
- No SSH, no filesystem access, no ability to deploy custom server-side Python modules yourself, regardless of what your subscription plan includes.
- The customer's own admin CAN self-install any module published on the official Odoo Apps Store through their instance's own Apps menu — this is a *customer-initiated, Odoo-store-mediated* action, not something your external tool can trigger or bypass.
- Certain apps (Studio among them) are **paywalled at the subscription-plan level** (Odoo's Custom plan), not blocked by the hosting infrastructure itself. This is a licensing gate enforced by Odoo's own backend, distinct in kind from the "no SSH" infrastructure restriction — worth keeping these two categories separate in your own thinking, because they need different handling.

## 2. Compatibility matrix — every mechanism from the earlier documents, checked against Odoo Online

| Mechanism (source section) | Works on Odoo Online via RPC? | Gate, if any |
|---|---|---|
| Custom models (`ir.model`) — Document 3 §2 | **Yes, always** | None — base ORM capability, not Studio-gated |
| Custom fields (`ir.model.fields`) — Document 3 §4 | **Yes, always** | None |
| Views — form/list/kanban/calendar/graph/pivot (`ir.ui.view`) — Document 3 §3 | **Yes, always** | None (Enterprise-only view types — Map, Cohort, Gantt, Grid — still need Enterprise edition, but that's an edition question, not an Online-hosting-specific one) |
| Menus & actions (`ir.ui.menu`, `ir.actions.act_window`) — Document 3 §9 | **Yes, always** | None |
| Security — ACLs, record rules, groups — Document 3 §6 | **Yes, always** | None |
| QWeb PDF reports (`ir.actions.report`) — Document 3 §8 | **Yes, always** | None — report templates are `ir.ui.view` records like any other, `wkhtmltopdf` is already present server-side on Online |
| View inheritance/XPath — Document 3 §5 | **Yes, always** | None |
| Images/media (`Image` field, resized variants) — Document 3 §14 | **Yes, always** | None |
| **Automation rules** (`base.automation`) — Document 3 §7 | **Only on Custom-plan Online subscriptions** | Requires Studio to be installed (the corrected finding above) — a real, meaningful gap for the likely-large share of your Online customers on the Standard plan |
| **Approval rules** (`studio.approval.*`) — Document 3 §17 | **Only on Custom-plan Online subscriptions** | Same Studio dependency |
| Property fields — Document 3 §18 | **Needs live verification, don't assume** | Introduced alongside recent Enterprise app work; verify per-instance via Document 5's introspection script rather than assuming availability |
| Financial integration (link-only pattern) — Document 3 §19 | **Yes, always** | Adding relational fields/buttons pointing at `account.move` is base RPC capability regardless of tier |
| Real installable custom modules (Document 2 §5 "module export") | **No** | Cannot be deployed by your tool at all on Online — see Section 3 below |
| Sandbox-test-before-install (Document 2 §6/Document 1 Phase 6) | **Partially** | Can't clone the customer's actual Online database for testing — see Section 3 below |
| Direct PostgreSQL/reporting queries | **No** | Never available on Online regardless of plan — use `read_group`/RPC aggregation instead |

The headline finding: **your core no-code builder (models, fields, views, menus, security, reports) is fully Online-compatible with no gaps at all.** The gaps cluster specifically around automation, approvals, real module deployment, and true sandbox parity — four things worth a deliberate strategy each, not a blanket "Online is limited" assumption.

## 3. Gap-by-gap strategy

### Gap 1 — Automation/Approval rules unavailable without Studio (Custom plan)
**Detect first, always:** run Document 5's Path B (`ir.module.module` introspection) the moment your app connects to any Online instance, checking specifically for `base_automation`/`web_studio`. Don't assume — verify per-instance, since plan tiers and installed apps vary customer to customer.

**If present:** proceed with the automation/approval builder UI as designed in Documents 2 and 3, no changes needed.

**If absent, three honest options — present all three to the user, don't silently pick one:**
1. **Upsell path**: surface a clear message that this feature requires Odoo's Custom plan (which includes Studio) and let the customer decide whether to upgrade their Odoo subscription — this is Odoo's monetization choice, not something to route around, and your tool shouldn't try to.
2. **Scheduled-action fallback, for customers who also have Odoo.sh or on-premise available**: if the customer's actual deployment target is Odoo.sh/on-prem (not pure Online), your Phase 5 module-export path can generate a real module using `ir.cron` (scheduled actions — a base, non-Studio-gated mechanism) plus a real Python method, achieving equivalent automation behavior without needing `base_automation` at all. This doesn't help pure-Online customers (see Gap 2), but is the right answer for Odoo.sh/on-prem customers who simply don't want to pay for Studio specifically.
3. **Do nothing and clearly scope it out**: for a pure-Online, Standard-plan customer who won't upgrade and isn't on Odoo.sh, be upfront that automation/approval features aren't available to them through your tool — better to say so plainly than to build something confusing or partially working.

### Gap 2 — Real custom module deployment isn't possible on Online at all
This is the sharpest limitation, and there's no clever workaround — it's a deliberate platform boundary, not an oversight. Three legitimate paths, worth building explicit product flows around rather than treating as a dead end:

1. **Reframe the module-export feature's value proposition for Online customers specifically**: the exported module is still valuable as *portable, customer-owned code* — even if your tool can't install it on their current Online instance, it's ready the moment they migrate to Odoo.sh or self-hosting, and it's a real artifact they own regardless of what happens to your relationship with them. Market this honestly as "your customization, yours to take with you" rather than implying it installs anywhere automatically.
2. **Apps Store submission packaging** — build a feature that prepares a generated module for submission to Odoo's own Apps Store (correct manifest metadata, icon, description formatting, compliance with Odoo's listing requirements) as a genuine assist, while being clear that the review/approval itself is entirely Odoo's process, on Odoo's timeline, and outside your tool's control.
3. **Migration-assist feature**: since Odoo.sh removes this entire limitation, consider a "you've hit Online's ceiling — here's what moving to Odoo.sh would unlock" flow that helps customers actually migrate when they've outgrown what pure metadata-level customization can do. This turns your product's honest limitation into a guided upsell/next-step rather than a dead end, and keeps the customer inside your tool's value chain rather than losing them to "figure it out themselves."

### Gap 3 — No true sandbox parity for testing before install
Your sandbox pipeline (Document 1 Phase 6) assumed a throwaway Docker Odoo instance for validation — but that's a generic Community sandbox, not a clone of the customer's actual Online database with their actual data/customizations/installed apps. This matters because a metadata change that's safe in a vanilla sandbox could still conflict with something specific to their real instance.

**Strategy**: be explicit in your UI that sandbox validation on Online is an *approximation*, not a true staging test — set that expectation rather than implying false confidence. Where possible, layer in:
- A **dry-run mode** that uses Odoo's own validation without committing (e.g., testing view XML well-formedness and field-reference validity against the live instance's actual schema via read-only introspection calls, before writing anything) — this catches the most common failure class (broken XPath references, invalid field names) without needing a full clone.
- For customers who do have Odoo.sh available (even if their production is Online — some customers maintain a separate Odoo.sh instance specifically for staging), offer to run full validation there instead, and treat that as the "real" sandbox path when available.

### Gap 4 — Post-upgrade regression risk (Online-specific, easy to miss)
Worth naming even though it wasn't in the original compatibility matrix: **Odoo controls Online's upgrade schedule, and you get no advance operational control over exactly when a customer's instance gets upgraded to a new Odoo version.** A metadata customization that worked fine can, in principle, be affected by an upgrade you didn't see coming (a renamed field, a changed view structure in a module you'd extended). Odoo.sh and on-prem customers, by contrast, control their own upgrade timing.

**Strategy**: build a lightweight, low-cost **post-upgrade health check** — a lightweight RPC call sequence run periodically (or triggered when your tool detects the instance's Odoo version has changed since last connection) that re-validates your generated customizations still resolve correctly (views still parse, referenced fields still exist), and flags anything that broke for the customer to review. This is a genuinely valuable feature specific to the Online tier's lack of upgrade-timing control, and worth building as a real differentiator rather than an afterthought.

## 4. Summary — what to actually build differently for Online support

1. **Nothing changes for your core builder** (models/fields/views/menus/security/reports) — it already works fully on Online. Don't over-engineer a "special Online mode" for functionality that has no gap.
2. **Gate the automation/approval builder UI behind a live introspection check** (Document 5 Path B) — show it only when `base_automation`/`web_studio` is actually present, with a clear upsell/explanation path when it isn't.
3. **Reframe module-export's value proposition for pure-Online customers** as portable ownership rather than auto-installation, and build the Apps Store submission-packaging and Odoo.sh-migration-assist features as genuine product surfaces, not afterthoughts.
4. **Set honest expectations in the UI about sandbox validation being approximate on Online**, and build the lighter-weight dry-run/schema-validation check as the practical middle ground.
5. **Build the post-upgrade health-check feature** — genuinely novel, directly addresses something specific to not controlling your own upgrade timing, and nothing in the earlier documents covered it.

# ═══════════════════════════════════════
# DOCUMENT 7: WORKFLOW OPTIMIZATION OPPORTUNITIES — BULK & BATCH OPERATIONS
# ═══════════════════════════════════════

# Workflow Optimization Opportunities: Bulk & Batch Operations Odoo Permits But Doesn't Expose

**The core principle, stated precisely, because it matters for how this document differs from Document 5's guardrails:** every operation catalogued here is something Odoo's own business logic already permits for a given user — the underlying method (`write()`, `unlink()`, `button_draft()`, `action_confirm()`, etc.) enforces exactly the same permission checks, state validations, and compliance locks (hash-locked entries, locked periods, reconciled lines) whether it's called once or five hundred times in one RPC call. **Batching a permitted operation isn't bypassing anything — Odoo's safety checks fire on every individual record inside the batch, automatically, for free.** This is categorically different from Document 5's protected-modules guardrail (which blocks generating *new* logic against sensitive models) — this document is about doing *existing, already-permitted* operations efficiently, at scale, where Odoo's own web client simply never got around to building a convenient bulk UI for them.

## 1. Verified gap: no universal bulk state-transition tool

**What's confirmed:** there is no native "bulk Reset to Draft" button in Odoo's own Journal Entries list view — getting one requires manually building a custom Server Action (Settings → Technical → Actions → Server Actions, writing `for move in records: move.button_draft()`, then attaching it as a contextual action) — a developer-mode, code-writing task most Accounting users can't do themselves. This gap is well-known enough that **multiple competing paid apps exist on the Odoo Store solely to fill it** (reset/cancel/post journal entries in bulk) — and at least one explicitly states it cannot be used on Odoo Online at all, since installing any of them requires server-side module deployment.

**The generalization — this is the real opportunity, not just journal entries:** this exact pattern (a workflow model has `button_X()`/`action_X()` methods for its state transitions, but the UI never wraps them in a bulk action) repeats across most of Odoo's workflow-driven models: Sales Orders (confirm/cancel), Purchase Orders (confirm/cancel), Stock Pickings (validate/cancel), Manufacturing Orders (mark done/cancel), Invoices (post/cancel/reset), Timesheets (validate), and any custom workflow model your own tool generates. Odoo's own web client happens to expose a bulk action for *some* of these (varies by model and version) and not others, with no consistent rule — it's simply whichever specific screen a core-Odoo developer happened to add the button to.

**What to build:** a generic **Bulk State Transition** feature that works on *any* model, not a hardcoded list of specific ones (see Section 5 for the discovery mechanism). One RPC call passing the full set of selected record IDs to the target method is usually sufficient — Odoo's action methods are typically written as `for record in self:` loops already, so a single `execute_kw` call against a multi-ID recordset achieves true batch execution, not N separate round-trips.

## 2. Verified gap: no universal mass-field-edit tool

**What's confirmed:** Odoo has had a native multi-record inline-edit capability since v13 (the `multi_edit="1"` attribute on list views) — select several rows, edit one field's value, get prompted "apply to all selected records?" But it's **opt-in per view** — only works where the specific view's XML author enabled the flag, on the fields that view exposes as columns, and behaves inconsistently across widget/field types. This gap is significant enough that **an entire ecosystem of paid and free (OCA) "Mass Editing" modules exists** specifically to provide generic, any-model, any-field bulk update — strong, direct market validation of exactly this pain point.

**What to build:** since `write()` natively accepts a list of record IDs plus a values dict as a single call, a generic mass-edit feature needs no module installed on the target at all — `models.execute_kw(db, uid, pwd, model, 'write', [record_ids, {field: value}])` is one RPC call regardless of whether the source view happened to enable `multi_edit`. This is strictly better than even the native Odoo 19 capability (works on every model/field combination, not just ones a view author remembered to flag) and works identically on every tier including plain Odoo Online.

## 3. Verified gap: duplicate detection & merge is hardcoded to Contacts only

**What's confirmed:** Odoo's "Deduplicate Contacts" / merge tool is a real, well-built feature — but its actual implementation (`base_partner_merge_automatic` wizard) is specific to `res.partner`. There's no equivalent generic tool for finding and merging duplicates of, say, products, leads-beyond-CRM's-own-narrow-merge, or any custom model your own tool generates (a duplicate vehicle record, a duplicate customer-adjacent model in your rental app, etc.).

**What to build:** a generalized duplicate-detection-and-merge engine — search for records matching a field-similarity criterion (exact or fuzzy match on user-chosen fields), present candidates, and on confirm: relink every foreign key across the database that points at the "losing" record(s) to the "winning" one (discoverable generically via `ir.model.fields` introspection for all `many2one`/`many2many` fields referencing the target model — the same introspection technique already established for Document 5), then archive/delete the losing records. This is pure RPC — `search_read` to find candidates, `write` to relink references, `unlink` to remove duplicates — no module install needed, and it works on any model, not just Contacts.

## 4. Verified gap: scheduled-action (cron) management requires developer mode, has no bulk trigger

**What's confirmed:** Scheduled Actions (`ir.cron`) are only visible/manageable through Settings → Technical → Scheduled Actions, which requires Developer Mode to even access — not something a typical operations/configuration person would enable or feel comfortable in. There's a "Run Manually" option per individual cron job, but no bulk "run these five now" and no non-technical presentation of what each scheduled job actually does.

**What to build:** since triggering "what a cron does" is just calling the same model method the cron would call, your tool doesn't need Odoo's cron infrastructure at all to offer "run this maintenance task now" — read the `ir.cron` record's target model/method via RPC, present it in plain language (not "ir.cron #47," but "Send overdue payment reminders"), and let the user trigger one or several with a normal button, no developer mode required. This turns a hidden, technical feature into an accessible one purely through better UI on top of existing, fully-permitted RPC access.

## 5. Gap worth building even though it's not consumer-visible: attachment/document housekeeping

Not something end users typically know to ask for, but a genuine maintenance pain point: `ir.attachment` records accumulate over years of use — duplicate uploads, attachments whose parent record was deleted (orphaned), oversized old files nobody needs. Odoo provides no native UI at all for surfacing or cleaning this up (it's the kind of thing that historically pushed people toward direct SQL access, which — per Document 6 — isn't available on Online anyway).

**What to build:** a housekeeping utility that (a) finds attachments whose `res_id`/`res_model` no longer points to an existing record (orphaned — safe to flag for cleanup), and (b) finds likely duplicates by checksum (`ir.attachment` already stores a checksum field). Entirely RPC-based (`search_read` + `unlink`), no module needed, and it's a genuinely differentiated maintenance feature almost no one else is offering because it's invisible until someone specifically goes looking for database bloat.

## 6. Gap: bulk activity/reminder scheduling across many records at once

Scheduling a follow-up activity (call, meeting, to-do) on one record is a normal, well-supported Odoo action (`mail.activity.mixin`, Section 10 of the compendium). Doing it across 200 selected records at once has no native bulk UI outside of Studio's automation-rule "Create Activity" action (which, per Document 3 Section 7's correction, requires the Studio/Custom-plan gate). Since creating an activity is just a `create()` call on `mail.activity`, your tool can offer "schedule a follow-up for all N selected records" as a plain bulk RPC operation with zero Studio dependency — filling exactly the gap Studio's gated feature leaves for non-Custom-plan Online customers.

## 7. Gap: bulk security/access provisioning for onboarding and offboarding

Adding a new employee to five security groups, or removing a departing employee's access across a dozen groups/record rules, is currently a one-user-at-a-time process in Odoo's own Settings → Users screen. Since `res.users`/`res.groups` membership is just a many2many field, bulk add/remove across a selected set of users is a straightforward `write()` call — a genuinely valuable operational feature for any company with real onboarding/offboarding cadence, again requiring nothing installed on the target.

## 8. Cross-reference: don't rebuild what's already covered

Some of the general "batch RPC vs. naive single-record calls" efficiency ground was already covered in the earlier tier-optimization conversation (batched `create()`/`write()`, `tracking_disable`/`mail_notrack` context flags during bulk import, field-limited `search_read`, using `load()` for bulk import) — that's the *performance* layer underneath everything in this document. This document is about *exposing operations the UI hides*, a distinct but complementary category — both belong in your "why we're faster than doing this by hand, or even by hand-in-Odoo's-own-UI" pitch.

## 9. The discovery mechanism — "even more elite," consistent with Document 5's philosophy

Don't hardcode which models have which bulk-eligible buttons/methods — the same lesson from Document 5's protected-module retrieval applies here in reverse: **discover bulk-eligible operations dynamically per target instance**, so your tool automatically supports new/custom models (including ones your own AI-generation pipeline creates) without you hand-coding a table that goes stale.

**Mechanism:**
1. For a given model, call `get_views` (or the older `fields_view_get`) to retrieve its form view's XML arch.
2. Parse the arch for `<button>` elements with `type="object"` — these are exactly the action-triggering methods Odoo's own UI exposes (`action_confirm`, `button_draft`, `action_done`, etc.), the same convention documented in Section 9 of the compendium.
3. Cross-reference discovered button names against the model's introspected fields (`fields_get`) to distinguish state-transition buttons (near a Selection field named `state`) from other button types, giving your tool a reasonable automatic guess at which buttons represent "bulk-safe workflow transitions" worth surfacing prominently versus other action buttons that might not make sense in bulk (e.g., opening a wizard that needs per-record input).
4. Cache this per model/version — refresh whenever the target instance's Odoo version changes (tying naturally into the post-upgrade health-check feature from Document 6).

This is the same "retrieve from source instead of hardcoding" discipline that made Document 5's module list durable across versions — applied here to bulk-operation discoverability instead of module classification.

## 10. Design guardrails specific to this feature category

Because bulk operations are inherently higher blast-radius than single-record ones, even when every individual call is fully permitted:
- **Never escalate privilege.** Every batched call runs as the authenticated user with their actual Odoo permissions — your tool is a faster way to do what they could already do one record at a time, never a way to do what they couldn't.
- **Surface partial failures clearly.** A batch of 500 reset-to-draft calls might succeed on 480 and fail on 20 (locked period, hash-secured entries, reconciled lines) — Odoo's own checks will reject those individually; your UI needs to report success/failure per record, not just an aggregate pass/fail, so the user knows exactly what happened and why.
- **Log every bulk operation** (what operation, which records, who ran it, when, success/failure count) — this is good practice generally and specifically important for anything touching workflow-state or financial-adjacent models, even when fully within permitted bounds, since "someone bulk-reset 200 invoices" is exactly the kind of action a business wants an audit trail for regardless of whether it was legitimate.

## 12. Additional verified gap: stored computed field recompute has no UI at all

**What's confirmed:** when a stored computed field's cached value goes stale (a known, well-documented Odoo behavior — see the GitHub issues on compute/dependency edge cases), fixing it requires actual Python console access: `env.add_to_compute(model._fields['field_name'], model.search([]))` followed by `model.recompute()`, or the newer `_recompute_recordset()` API. **There is no UI button for this anywhere in stock Odoo, technical settings included** — it's Python-shell-only, meaning self-hosted/Odoo.sh customers with shell access can do it and pure-Online customers structurally cannot, at all, through any interface Odoo itself provides.

**Important honesty note, not a clean win:** `recompute()` itself isn't an externally RPC-callable method — it's internal ORM API, not exposed for XML-RPC/JSON-RPC calls the way `write()`/`search_read()` are. The practical workaround available to an external tool is the **"touch" technique**: writing a dependency field's existing value back to itself (`write({'the_depended_on_field': current_value})`) triggers the same recompute machinery as a side effect, since Odoo's dependency graph doesn't distinguish "value changed" from "write occurred" for triggering purposes. This is a real, usable technique, but built on a side-effect rather than a clean dedicated API — worth building carefully (verify it actually triggers recompute for the specific field/version combination before relying on it) rather than assuming it always works identically. Where it doesn't work reliably, be honest with the user that this specific fix genuinely requires shell access unavailable on Online, rather than claiming a workaround that might not hold.

## 13. Additional verified gap: bulk "Send & Print" has a real, documented bug — not just a missing feature

**What's confirmed:** selecting multiple records (e.g., vendor bills) and using Odoo's native "Send & Print" wizard is documented (via an open Odoo GitHub issue) to silently break email threading — because the multi-record path switches to a "mass mail" composition mode internally, the resulting emails don't get the `references` header set correctly, so a vendor's reply doesn't thread back to the original record in Odoo's Discuss/chatter, and instead bounces. This is a genuine **correctness bug in bulk usage of a feature that works fine for single records**, not just a missing convenience — a stronger case for building your own version than a pure UX gap would be.

**What to build:** rather than driving Odoo's own buggy mass-mail wizard, send properly-threaded individual messages per record via `message_post()` (the same method used by Section 10's chatter mechanism) in a loop — one RPC call per record rather than one batched wizard call, but each message correctly threaded to its own record. Slower than a true single-call batch, but correct — worth the trade-off given the alternative is documented to break reply-tracking.

**A related, narrower gap**: combining *multiple different report types* into one merged document (e.g., an invoice plus its packing slip as one PDF) has no native mechanism at all — printing multiple records of the *same* report type natively produces one merged PDF (this part of Odoo's UI already works fine, worth not overclaiming a gap that isn't real), but cross-report-type combination is genuinely unsupported natively, evidenced by dedicated OCA modules built solely for this. A real, if narrower, opportunity for logistics-heavy customers (the food-wholesaler delivery-batch use case the OCA module documentation describes directly).

## 14. Additional verified gap: portal access provisioning is one-contact-at-a-time

Granting a contact portal login access (`portal.wizard`) is a per-record action in stock Odoo — no bulk "grant portal access to these 50 contacts" exists natively. Same underlying pattern as Section 7 (bulk security provisioning) but worth calling out separately since it's a distinct wizard/mechanism (`portal.wizard`, not `res.groups` membership) and a common real need — B2B companies onboarding a batch of client contacts, or an educational/membership-based business (relevant to a rental/subscription-style app) granting many customers self-service portal access at once.

## 15. What this second pass demonstrates about the research approach going forward

The pattern holding across all fourteen gaps now catalogued: **every one of them is a real, already-permitted Odoo operation with a documented UI or API limitation** — verified via official Odoo forums, GitHub issues, or the existence of dedicated third-party modules (free or paid) built specifically to fill that one gap. That last signal — a module existing whose entire purpose is one narrow bulk/convenience operation — is a reliable way to keep finding more of these: **the Odoo Apps Store and OCA repository are themselves a map of every UI convenience gap the ecosystem has already identified and monetized**, one module at a time. Worth treating "what narrow-purpose modules exist for this pain point" as a standing research technique whenever evaluating a new feature idea, not just a one-time pass — it's a faster way to validate a gap is real than guessing from first principles.

## 16. Why this is your strongest Online-compatible differentiator

Every feature in Sections 1–7 and 12–14 requires **zero module installation on the target Odoo instance** — it's 100% external RPC (with the one honestly-flagged exception of Section 12's recompute technique, which is a best-effort workaround, not a guaranteed clean path, on pure Online). Compare that to the gaps identified in Document 6 (automation rules, approval rules, real module deployment) which are genuinely tier-gated — this entire category has no such gate. If you're looking for where to invest first for maximum reach across your whole addressable market regardless of what plan a customer is on, this is it.

# ═══════════════════════════════════════
# DOCUMENT 8: THE ODOO EXPERT — GENERAL-PURPOSE RAG ASSISTANT
# ═══════════════════════════════════════

# The Odoo Expert: A General-Purpose RAG Assistant for Odoo Operators

## 1. What this is, and why it's a different feature from the module generator

Document 2 (AI Module Generation) builds things: given a prompt, it produces a `ModuleSpec` — fields, views, automations — meant to become production configuration. Its risk profile is "did we generate something correct enough to install," and it's guarded accordingly (Document 5's protected-module rejection, Document 4's structured-output discipline).

**The Odoo Expert is different in kind, not just in scope.** It doesn't produce artifacts — it answers questions, explains concepts, walks someone through a manual configuration step, diagnoses an error message, or advises on which of two approaches fits their situation. Its risk profile is "did we tell this person something true that they can act on with confidence" — closer to a knowledgeable colleague than a code generator. That difference drives almost every design decision below, especially around anti-hallucination discipline (Section 6) and honest refusal (Section 7).

**The positioning that matters:** a generic "ask GPT/Claude about Odoo" already exists and is free — that's not a reason to skip this feature, but it does mean the value has to come from somewhere a generic chatbot structurally can't reach. That somewhere is **live-instance grounding**: this assistant sees the customer's actual installed modules, actual custom fields your builder created, actual current screen in your app — none of which a standalone chatbot can access. That's Section 4, and it's the difference between "a chatbot that knows about Odoo in general" and "an expert who knows about *your* Odoo."

## 2. Architecture overview

```
┌─────────────────────────────────────────────┐
│  In-app chat surface (contextual, persistent) │
└───────────────────┬───────────────────────────┘
                     │
┌────────────────────▼───────────────────────────┐
│  Retrieval layer                                │
│  ├─ Static knowledge base (versioned, re-embedded periodically) │
│  │   ├─ Odoo's own documentation source (RST, per-version)     │
│  │   ├─ Documents 1–7 of this project (your own curated expertise) │
│  │   └─ Curated, quality-filtered community Q&A                │
│  ├─ Live-instance context (fetched fresh per query)             │
│  │   ├─ Installed modules (Document 5's Path B)                 │
│  │   ├─ Current model/field/view schema of whatever the user    │
│  │   │   is looking at in your builder                          │
│  │   └─ Odoo version (feeds version-filtered retrieval)         │
│  └─ In-app workflow context (what screen, what they're building)│
└────────────────────┬───────────────────────────┘
                     │
┌────────────────────▼───────────────────────────┐
│  Generation (Qwen3 — same model family as       │
│  Document 4, thinking mode on for multi-step     │
│  explanations, cited retrieval context injected) │
└────────────────────┬───────────────────────────┘
                     │
┌────────────────────▼───────────────────────────┐
│  Response with inline source citations           │
│  ("per Odoo 18 documentation...", "your          │
│  rental.contract model has...")                  │
└──────────────────────────────────────────────────┘
```

## 3. Knowledge base construction — retrieve from source, per Document 5's established discipline

**Primary source: `github.com/odoo/documentation`** — Odoo's actual documentation source, written in reStructuredText, version-branched (confirmed: branches exist for 13.0 through 19.0 and presumably continuing). This is meaningfully better than scraping the rendered HTML site: RST files are clean, structured, already organized by heading hierarchy (ideal chunking boundaries), and — using the same sparse-git-checkout technique validated in Document 5 — retrievable without hitting API rate limits.

```bash
# Same pattern as Document 5's retrieval script
git clone --filter=blob:none --no-checkout --depth 1 -b 18.0 \
    https://github.com/odoo/documentation.git odoo-docs
cd odoo-docs && git sparse-checkout init --cone && git sparse-checkout set content
git checkout
```

**Secondary source: your own Documents 1–7.** This is worth taking seriously as a first-class ingestion source, not an afterthought — you've already produced ~1,500 lines of verified, curated, cross-referenced Odoo expertise specific to customization/configuration work, including corrections (the automation-rules Studio-dependency fix) that the raw documentation doesn't state as plainly. Embedding these gives the assistant your project's *accumulated judgment*, not just Odoo's raw documentation — this is a genuine compounding asset, the same way the domain template library compounds value in Document 2.

**Tertiary source: curated community Q&A** (Odoo's own forum, `odoo.com/forum`). Community content is noisier — quality-filter aggressively (accepted-answer status, vote count thresholds) before ingesting, since a RAG system is only as trustworthy as its worst-indexed source, and an upvoted-but-wrong forum answer embedded without filtering becomes a confidently-cited wrong answer downstream.

**Chunking strategy:** semantic chunking by heading structure (RST's own section hierarchy, and your own Documents 1–7's numbered-section structure) rather than fixed-size sliding windows — technical documentation loses coherence when split mid-explanation, and heading-aligned chunks keep each retrieved unit conceptually complete.

**Version-tag every chunk.** Odoo's documentation is branched per version for good reason — behavior genuinely differs. Tag each chunk with its source version, and filter retrieval to the target instance's actual detected Odoo version (from Document 6's compatibility work) before ranking — don't let a v16 answer surface for an v19 user's question, and vice versa.

## 4. Live-instance grounding — the actual differentiator

This is what a generic chatbot cannot do, and it's not a separate build — it reuses infrastructure Documents 1, 5, and 6 already specify:

- **Installed-module awareness**: before answering, check (via Document 5's Path B introspection, likely already cached from the session) what's actually installed on the target instance. A question like "how do I set up automations" gets a different, more useful answer depending on whether `base_automation` is actually present — either a real walkthrough, or an honest "this isn't available on your current plan, here's why and what your options are" (echoing Document 6 Section 3's exact reasoning, but delivered conversationally in context rather than requiring the user to have read that document themselves).
- **In-progress-work awareness**: if the user is mid-session in your field/view builder (Document 2's canonical `ModuleSpec` being edited), the assistant can see that state and answer questions like "should this be a Many2one or Many2many" *about the actual field they're currently configuring*, not a generic explanation of the two field types.
- **Schema-aware troubleshooting**: paste an RPC error message, and the assistant can cross-reference it against the actual live schema (does the referenced field/model actually exist on this instance?) rather than guessing generically — genuinely diagnostic, not just explanatory.

This turns the assistant from "a search engine over Odoo docs" (replicable by anyone) into "something that knows what you're actually looking at right now" (not replicable without the rest of your app's infrastructure already existing) — worth stating plainly in how you market this feature, since it's the actual moat, not the RAG mechanism itself.

## 5. Generation layer — reusing Document 4's established discipline

- **Model**: Qwen3, same family as the generation pipeline — `qwen3:8b` for straightforward factual lookups, `qwen3:14b` with thinking mode **on** for multi-step "walk me through configuring X" explanations, matching Document 4's per-task model-mixing strategy exactly. No new infrastructure to stand up.
- **Prompting**: retrieved chunks injected with explicit source labels, low temperature (0.1–0.2, per Document 4 Section 5 — this is a factual-accuracy task, not a creative one), and a system prompt establishing the "Odoo Expert" persona plus the anti-hallucination rules in Section 6 below.
- **Citation requirement**: every substantive claim should trace to a specific retrieved chunk, surfaced to the user as a visible source ("per Odoo 18 documentation," "based on your rental.contract model's current fields") — this is both a trust mechanism (user can verify) and a quality forcing-function (a claim you can't attribute to a retrieved chunk is a claim you probably shouldn't make).

## 6. Anti-hallucination guardrails — the opposite risk profile from Document 2, needing its own design

Document 2's pipeline risk is bad *generated artifacts* that get validated before install (Document 2 Section 5's rules engine, Document 2 Section 6's self-critique pass). This assistant's risk is bad *advice* that a person might act on directly and immediately, with no validation layer in between — a materially different failure mode that needs its own guardrail, not a reused one.

**Core rule: ground or decline.** If retrieval returns nothing relevant or low-confidence for a question, the assistant should say so plainly ("I don't have a solid source for this specific question") rather than answering from the model's own parametric knowledge — which, for a 7–14B local model, is exactly where confident-sounding wrong answers come from. This is worth enforcing at the prompt level explicitly:

```
If the retrieved context does not contain enough information to answer
confidently, say so directly. Do not fill gaps with plausible-sounding
information not present in the retrieved context. A partial, honestly-
qualified answer is better than a complete but ungrounded one.
```

**Elevated caution for anything touching Document 5's protected-module categories.** If a user asks something like "how do I fix a mistake in a posted journal entry" or "how do I bypass the reset-to-draft requirement," the assistant should apply the same reasoning Document 5's guardrail applies to code generation — but conversationally: explain *why* the constraint exists (the audit-trail/compliance reasoning from Document 3 Section 19), point to the legitimate path (reversal entries, or Document 7's properly-guarded bulk reset-to-draft feature if applicable), and stop short of walking someone through defeating a compliance control even if they frame the request innocuously. The two AI features should share this reasoning rather than having one enforce it and the other not know it exists — see Section 8 on shared infrastructure.

**No definitive legal/tax/compliance conclusions, ever** — mirroring Document 3 Section 19's principle exactly, but for advice rather than generated code. "Should I use this fiscal position for my situation" gets a factual explanation of what the fiscal position mechanism does, not a yes/no recommendation — that's genuinely a question for the user's own accountant, and saying so is more useful than a confident-sounding wrong answer.

## 7. Honest refusal is a feature, not a failure

Worth stating as a design principle rather than an edge case: an assistant that says "I'm not confident about this, here's what I do know, and here's where I'd suggest verifying" is *more* valuable to an operations person than one that always sounds certain — because the failure mode of an advisory tool that's occasionally confidently wrong is much worse than one that's visibly, honestly uncertain sometimes. Build your evaluation set (Section 9) to specifically reward calibrated uncertainty, not just raw accuracy on the questions it does answer.

## 8. Shared infrastructure with Document 2 — build once, benefit twice

Both AI features should draw from the same underlying components rather than duplicating logic:
- **Document 5's protected-module classification** — used by Document 2 to reject bad generation, used here to shape advisory caution around the same categories.
- **Document 6's tier/compatibility detection** — used to scope what the module generator offers, used here to give accurate "here's what's available to you" answers instead of generic ones.
- **Document 7's bulk-operation discovery mechanism** — when a user asks "how do I do X to many records at once," the assistant can check whether your own bulk-operations tool already covers it and route them there directly, rather than just explaining Odoo's native (often absent) mechanism.
- **The `ModuleSpec` canonical schema** — when a user asks about their in-progress customization, this is the shared representation both features read.

This isn't just efficient engineering — it means the two AI surfaces give *consistent* advice, which matters for trust. A user who gets one answer from the chat assistant and a contradictory guardrail rejection from the generator (or vice versa) will trust neither.

## 9. Evaluation — build a regression test set early, not after launch

Given hallucination is the central risk, don't treat quality as something you'll assess informally. Build a curated set of question/verified-correct-answer pairs early — your own Documents 1–7 are a natural source (you already know the correct answers, since you researched and verified them), supplemented with real questions from your own use of the tool during development. Re-run this eval set whenever you change the embedding model, chunking strategy, retrieval parameters, or generation model — the same discipline Document 4 recommends before any eventual fine-tuning, applied here to retrieval quality specifically. This also becomes your dataset for an eventual distillation/fine-tuning pass (Document 4 Section 10's playbook), once the feature has real usage data to learn from.

## 10. UX surfaces — where this shows up in the app

- **Persistent contextual chat panel** — available throughout the app, aware of current screen/task, not a separate disconnected "help" destination.
- **Inline "explain this" affordances** — a small help affordance next to field types, widget options, automation triggers in your builder (Document 2/3's UI) that asks the assistant to explain *this specific choice, in this specific context* rather than sending the user to search documentation separately.
- **Error/troubleshooting mode** — paste an RPC exception or a confusing Odoo error message, get a grounded diagnosis, cross-referenced against the live instance's actual schema.
- **Post-generation review companion** — after Document 2's AI module-generation pipeline produces a `ModuleSpec` for review, offer the Expert as the natural next step for "why did it choose this" questions, closing the loop between generation and understanding.

## 11. Why this is genuinely transformative for the product, not just a nice-to-have

Two compounding effects worth being explicit about:
- **Retention/engagement**: a builder tool gets opened when someone has a specific customization task. An always-available expert gets opened whenever someone has *any* Odoo question — a much higher-frequency trigger, meaning this feature pulls people into the app far more often than the generator alone would, with each visit reinforcing awareness of your other features.
- **Trust compounding**: every well-grounded, honestly-caveated answer builds confidence in your product's judgment generally — which directly supports adoption of the higher-stakes AI module-generation feature, since a user who's seen the Expert be reliably honest about its limits will trust the generator's guardrails more too. The two features aren't just infrastructure-sharing; they're reputation-sharing.

THIS HERE IS THE RECORD OF MY CHAT WITH A CLAUDE AGENT OVER MULTIPLE ITERATIONS OF BUILDING OUT THIS IDEA. I HAVE ALREADY PASTED THE CULMINATION/SYNTHESIS OF ALL DOCUMENTS IT CREATED FOR YOU ABOVE. THIS IS JUST FOR INFORMATION AND SO YOU UNDERSTAND MY THINKING PROGRESSION:

Yes — this is very doable, and it's actually a well-trodden path (it's essentially what Odoo Studio does, except Studio is Enterprise-only and closed). Odoo stores almost everything — models, fields, views, menus, security rules, automations — as data records accessible through its standard external API (XML-RPC/JSON-RPC). That means you can build an external app that reads/writes those metadata records and gives users a no-code UI for creating custom fields, models, views, and automations, without ever touching Odoo's Python codebase directly — while still producing a real, installable Odoo module as an export for full ownership/portability.

I put together a full production plan below.

Created a file, created a memory, read a file
Created a file, created a memory, read a file

The core insight that makes this tractable: Odoo already exposes almost all of its customization surface (models, fields, views, automations, access rules) as regular data records through its standard external API — that's literally what Odoo Studio uses under the hood, just gated behind an Enterprise license. Building an external app against that same public API is legitimate and gives you a real product, not a hack.

The plan is phased so you get value early — the field/model builder alone (Phase 2) is a usable, shippable tool before you touch the harder visual view designer. I'd start there, validate the RPC layer thoroughly against a local Docker Odoo instance, and only invest in the drag-drop view designer once the metadata plumbing is solid.

Odoo nocode app plan
Document · MD 
Excavated Odoo's hidden bulk-operation capabilities across modules and tiers
Excavated Odoo's hidden bulk-operation capabilities across modules and tiers

Confirmed and important — my earlier draft actually understated this. There's no native "bulk reset to draft" button in stock Odoo at all; getting it requires manually building a custom Server Action (developer-mode, Python code), and there's a whole cottage industry of third-party paid apps that exist purely to fill this one gap — several of which explicitly can't even run on Odoo Online. Let me broaden the research across other areas before compiling.

Architected universal bulk operations framework leveraging Odoo's permitted RPC capabilities
Architected universal bulk operations framework leveraging Odoo's permitted RPC capabilities

Excellent research base — this connects directly to the last two conversations and confirms your instinct was right, and actually understates the opportunity. Let me compile this properly.

Workflow optimization gap-analysis document - bulk/batch operations Odoo permits but doesn't expose conveniently
Workflow optimization gap-analysis document - bulk/batch operations Odoo permits but doesn't expose conveniently

Now rebuilding the master document with this as Document 7.

Ran a command, read a file, read a memory
Ran a command, read a file, read a memory

The research validated your instinct more strongly than I expected. Three things worth sitting with:

Your journal-entry example wasn't a minor case — it's a pattern that repeats across nearly every workflow model in Odoo, and the market already proves it's a real pain point: there's a genuine cottage industry of paid third-party apps that exist solely to add bulk reset/post/cancel buttons, several of which explicitly can't run on Odoo Online at all (since they require server-side module installation). Your tool doing the same thing purely via RPC works everywhere those paid apps don't.
The most valuable design decision here is Section 9 — don't hardcode which models have which bulk-eligible buttons. Discover them the same way you're already discovering protected modules in Document 5: parse the target model's actual view XML for type="object" buttons at connection time. This means your bulk-operations tool automatically works on any model — including ones your own AI-generation pipeline creates — without you maintaining a table that goes stale every version.
This whole category needs zero module installation on the target instance, which makes it your cleanest, most universal differentiator across every tier including plain Odoo Online — no Studio dependency, no plan-tier gate, nothing Document 6 flagged as restricted. If you're deciding what to build first for the widest possible reach, this is probably it.

One thing worth your own judgment before building: Section 3's generic merge/deduplicate tool relinks foreign keys across the database automatically — genuinely useful, but also the single riskiest operation in this whole document (an incorrect merge on a model your validation didn't anticipate could silently corrupt relationships). I'd build and harden the state-transition and mass-edit tools first, and treat generic cross-model merge as a later, more carefully-tested feature rather than launching all seven simultaneously.

Odoo workflow optimization gaps
Document · MD 
Master reference document
Document · MD 

hope your research wasn't restricted only to the edge case I pointed out (the reset to draft)... I believe there's so much more that can be done

Validated comprehensive research across seven distinct operational categories beyond the initial example
Validated comprehensive research across seven distinct operational categories beyond the initial example

Fair to double check — let me be straight about it: the research (and Document 7) already went well beyond reset-to-draft into six other verified categories — mass-edit, duplicate/merge, scheduled-action management, attachment housekeeping, bulk activity scheduling, and bulk security provisioning, each with its own evidence (the mass-edit third-party app market, the Contacts-only merge limitation, etc.). But you're right that there's more out there, and I'd rather actually go find it than assure you it's covered. Let me dig into a few categories I haven't verified yet.

Excavated broader gaps beyond initial scope, synthesized findings into cohesive document
Excavated broader gaps beyond initial scope, synthesized findings into cohesive document

Good — found two more genuine, verified gaps, plus an important nuance I should be upfront about rather than oversell. Let me fold these into Document 7 properly.

Edited a file, ran a command
Edited a file, ran a command

Right, Section 11 got dropped. Let me restore it at the end as the closing section.

Restore section 11 as the closing section after the new additions
Restore section 11 as the closing section after the new additions

Now rebuilding the master document with the expanded Document 7.

Ran a command, read a file
Ran a command, read a file

To directly answer the concern: no, it wasn't restricted to reset-to-draft — Document 7 now covers 14 distinct verified gaps. Three things from this second pass worth your attention specifically:

Section 13 found something better than a gap — a real bug. Odoo's own native "Send & Print" breaks email threading when used on multiple records at once (documented on Odoo's GitHub). That's not "the UI is inconvenient," that's "the feature is broken in bulk" — a stronger justification for building your own than pure convenience would be.
Section 12 (recompute) is the one place I pulled back rather than oversold. recompute() isn't actually exposed over RPC the way write() is — the practical workaround (writing a dependency field's value back to itself to trigger the same cascade) is real but a side-effect, not a clean API, and I said so plainly rather than promising a capability I'm not fully certain holds across every version. Worth you deciding whether that caveat changes how confidently this feature gets marketed.
Section 15 is probably the more valuable takeaway than any single gap: the Odoo Apps Store and OCA repository are themselves a living map of every UI gap the ecosystem has already found and monetized — a module existing to solve one narrow pain point is the validation signal. That's a repeatable research method for you going forward, not just something I did once — worth running yourself against the Apps Store periodically as you're deciding what to build next, rather than treating this document as the final word.
Odoo workflow optimization gaps
Document · MD 
Master reference document
Document · MD 

write a separate feature plan for a second AI feature - this one a general purpose, ask-anything-related-to-Odoo AI built using our freely-available AI models that can help Odoo operators and users of the app during customizations and configurations. It can be implemented as an RAG AI. I think you mentioned something like that in the document. If you did, it'd be good to harden and expound on that as a transformative fetaure for this app. This general AI is different from the build a module AI and should effectively be an Odoo-expert that anyone can consult for all things Odoo

Validated documentation source and prepared comprehensive feature specification
Validated documentation source and prepared comprehensive feature specification

Confirmed — github.com/odoo/documentation is real, version-branched (13.0 through 19.0), and RST source rather than scraped HTML. That's the right ingestion source, and it lets this feature reuse the exact retrieval technique already proven in Document 5. Let me build this out properly.

Feature plan for the general-purpose Odoo Expert RAG assistant
Feature plan for the general-purpose Odoo Expert RAG assistant

Now let me fold this into the master document as Document 8.

Ran a command, read a file, edited a memory
Ran a command, read a file, edited a memory

Document 8 is done and folded into the master (~1,600 lines, 8 documents now). The one idea I'd want you to hold onto above the rest of the detail:

Section 4 is the whole game. A generic "ask GPT about Odoo" is already free and already exists — so the reason to build this yourself instead of just telling users to go use ChatGPT is entirely the live-instance and in-workflow grounding: it knows what's actually installed on this customer's database, what field they're staring at right now in your builder, and can cross-reference an error message against their actual schema. That's not replicable without the rest of your app already existing — which means this feature is nearly free to build once Documents 1, 5, and 6's infrastructure is in place, and close to worthless as a standalone product if built in isolation. Build it after that infrastructure exists, not in parallel with it.

The other thing worth flagging clearly: this feature's failure mode is the opposite of the generator's. The generator's danger is a bad artifact that (per Document 2's design) gets validated before anything happens. This assistant's danger is bad advice a person acts on directly with nothing in between — which is why Section 6 and 7 exist as their own real design work, not a copy-paste of Document 5's guardrail. An assistant that occasionally says "I'm not confident about this" is doing its job correctly, not failing at it — worth making sure that survives contact with whatever pressure exists later to make the product feel more impressively certain than it should be.


---

<!-- The AppleScript below was part of the same paste (it preceded the document title in the original message) and is the Inventory ID Generator referenced by the document. Reproduced verbatim. -->

# Appendix: Inventory Reference ID Generator (AppleScript, v3)

```applescript
-- =============================================================================
--  INVENTORY REFERENCE ID GENERATOR   (v3 — semantic initials, strict/dry-run,
--                                      sorting, logging)
-- =============================================================================
--  Generates codes in the form:      PREFIX/INITIALS/NUMBER
--  Example:                          RM/CY/0001
--
--  Target: the frontmost NUMBERS document, first table of the active sheet.
--
--  WHAT'S NEW IN v3
--  ----------------------------------------------------------------------
--  - Semantic initials: strips parenthesized text (units, packaging notes)
--    and a configurable list of stop words (KG, ML, PACK, DRUM, ...) before
--    extracting initials, so "SODIUM HYDROXIDE (25 KG)" -> SH, not "S2"
--    or similar noise.
--  - DRY_RUN mode: computes and reports everything a real run would do,
--    without touching the spreadsheet.
--  - STRICT_MODE: if any existing ID fails validation, stop immediately
--    (before generating anything new) instead of generating around the
--    problem and reporting it after the fact.
--  - SORT_MODE: choose whether new numbers are handed out in sheet order
--    or alphabetically by product name.
--  - ENABLE_LOGGING: appends a timestamped run report (config, matched
--    columns, every code generated) to a text file for an audit trail.
--  - ALLOW_MIXED_ALPHANUMERIC: choose whether names with tokens like
--    "12V" or "M6" (mixing letters and digits) get their letters
--    guessed at automatically, or get set aside for manual review.
--
--  Carried over from v2 (still all here):
--  - Bulk column reads/writes (a handful of Apple Events total, not one
--    per row) — this is what fixed the original hang.
--  - Duplicate-header detection: aborts with the exact column numbers
--    instead of silently guessing which "name"/"default_code" is real.
--  - Boolean-safe reads: a Checkbox-formatted cell reads back as blank,
--    not as the literal text "false".
--  - Diagnostics block in the summary: which column/header got matched,
--    and a sample of what was actually read.
--  - Iteration caps on every search loop so a data problem raises a
--    clear error instead of ever hanging again.
-- =============================================================================

-- =============================================================================
--  SECTION 1: CONFIGURATION  (edit these, nothing else, for normal changes)
-- =============================================================================
property PREFIX : "RM" -- change to "PM", "FG", etc. as needed
property NUMBER_WIDTH : 4 -- 4 -> 0001, 5 -> 00001
property REUSE_MISSING_NUMBERS : false -- true = fill gaps, false = always increment
property NAME_HEADER : "name" -- header text of the product-name column
property CODE_HEADER : "default_code" -- header text of the ID column
property HEADER_ROW_INDEX : 1 -- which row holds the column headers
property MAX_SEARCH_ITERATIONS : 999999 -- safety cap so a bug can never hang forever

-- Words to ignore when extracting initials (packaging/unit noise).
-- Matching is case-insensitive; edit this list freely.
property STOP_WORDS : {"KG", "G", "MG", "ML", "L", "LTR", "LITRE", "LITRES", ¬
	"PCS", "PC", "PACK", "PACKS", "PACKET", "PACKETS", "BOTTLE", "BOTTLES", ¬
	"BAG", "BAGS", "DRUM", "DRUMS", "BOX", "BOXES", "CARTON", "CARTONS", ¬
	"SACHET", "SACHETS", "ROLL", "ROLLS", "UNIT", "UNITS", "SET", "SETS", ¬
	"TIN", "TINS", "CAN", "CANS", "JAR", "JARS", "CTN"}

-- Operating mode switches.
property DRY_RUN : false -- true = compute + report everything, write nothing
property STRICT_MODE : false -- true = abort entirely if any existing ID is malformed
property SORT_MODE : "row" -- "row" = number in sheet order; "name" = number alphabetically by product name
property ENABLE_LOGGING : false -- true = append a run report to LOG_FILE_PATH
property LOG_FILE_PATH : "" -- blank = default to ~/Desktop/inventory_id_generator_log.txt
property ALLOW_MIXED_ALPHANUMERIC : true -- true = extract letters from tokens that mix letters+digits (e.g. "12V" -> V, "M6" -> M); false = flag those rows for manual review instead of guessing at their initials

-- Column selection. "header" (default) finds columns by header text and
-- refuses to guess if a header appears more than once. "index" bypasses
-- header lookup entirely and uses the exact column numbers below — use
-- this for sheets where the same header text legitimately repeats (e.g.
-- several product blocks pasted side by side) and you want to point the
-- script at one specific block.
property COLUMN_SELECTION_MODE : "index" -- "header" or "index" — set to "index" because "name" has a merged-header-cell artifact on this sheet (see diagnostic run)
property NAME_COLUMN_INDEX : 3 -- confirmed via diagnostic preview: column 3 held "ACETIC ACID"
property CODE_COLUMN_INDEX : 6 -- confirmed via diagnostic preview: column 6 held "RM/AC/0001"

-- =============================================================================
--  SECTION 2: MAIN
-- =============================================================================
on run
	set addedCount to 0
	set skippedHasID to 0
	set skippedBlankName to 0
	set malformedList to {}
	set usedNumbers to {}
	set existingCodes to {}
	set logLines to {}
	set flaggedMixedList to {}

	try
		-- -----------------------------------------------------------------
		-- SECTION 3: LOCATE TABLE + BULK READ
		-- Everything Numbers-related happens in this one small block —
		-- a handful of calls total, none of them per-row.
		-- -----------------------------------------------------------------
		tell application "Numbers"
			if (count of documents) is 0 then
				display alert "No Numbers document is open." message "Open the spreadsheet you want to process and run this script again." as critical
				return
			end if

			tell front document
				set targetSheet to active sheet
				tell targetSheet
					if (count of tables) is 0 then
						display alert "No table found on the active sheet." as critical
						return
					end if
					set targetTable to table 1
				end tell
			end tell

			set rowCount to row count of targetTable
			set colCount to column count of targetTable

			if rowCount < 2 then
				display alert "The table has no data rows below the header." as critical
				return
			end if

			-- ONE call for the whole header row, instead of one call per column.
			set headerValues to value of every cell of row HEADER_ROW_INDEX of targetTable

			if COLUMN_SELECTION_MODE is "index" then
				-- Manual override: skip header lookup entirely.
				if NAME_COLUMN_INDEX is 0 or CODE_COLUMN_INDEX is 0 then
					display alert "COLUMN_SELECTION_MODE is \"index\" but NAME_COLUMN_INDEX / CODE_COLUMN_INDEX aren't set." message "Set both to the actual column numbers you want to use (1 = column A, 2 = column B, ...)." as critical
					return
				end if
				if NAME_COLUMN_INDEX < 1 or NAME_COLUMN_INDEX > colCount then
					display alert "NAME_COLUMN_INDEX (" & NAME_COLUMN_INDEX & ") is out of range." message "This sheet has " & colCount & " column(s)." as critical
					return
				end if
				if CODE_COLUMN_INDEX < 1 or CODE_COLUMN_INDEX > colCount then
					display alert "CODE_COLUMN_INDEX (" & CODE_COLUMN_INDEX & ") is out of range." message "This sheet has " & colCount & " column(s)." as critical
					return
				end if
				set nameColIndex to NAME_COLUMN_INDEX
				set codeColIndex to CODE_COLUMN_INDEX
			else
				-- Find EVERY column matching each header, not just the first —
				-- a sheet built from merged/duplicated exports can easily have
				-- the same header more than once. Taking the first match is
				-- exactly how the wrong column gets picked silently.
				set nameMatches to my findAllColumnIndices(headerValues, NAME_HEADER)
				set codeMatches to my findAllColumnIndices(headerValues, CODE_HEADER)

				if (count of nameMatches) is 0 then
					display alert "Could not find a column header called \"" & NAME_HEADER & "\"." as critical
					return
				end if
				if (count of nameMatches) > 1 then
					set sampleLines to my buildColumnSampleText(nameMatches, (HEADER_ROW_INDEX + 1), targetTable)
					display alert "The header \"" & NAME_HEADER & "\" appears in more than one column." message "Found it in columns: " & my joinList(nameMatches, ", ") & "." & return & return & "First data row in each:" & return & sampleLines & return & "Make column headers unique before running, point NAME_HEADER at a more specific label, or set COLUMN_SELECTION_MODE to \"index\" and use NAME_COLUMN_INDEX to pick one directly." as critical
					return
				end if
				if (count of codeMatches) is 0 then
					display alert "Could not find a column header called \"" & CODE_HEADER & "\"." as critical
					return
				end if
				if (count of codeMatches) > 1 then
					set sampleLines to my buildColumnSampleText(codeMatches, (HEADER_ROW_INDEX + 1), targetTable)
					display alert "The header \"" & CODE_HEADER & "\" appears in more than one column." message "Found it in columns: " & my joinList(codeMatches, ", ") & "." & return & return & "First data row in each:" & return & sampleLines & return & "Make column headers unique before running, point CODE_HEADER at a more specific label, or set COLUMN_SELECTION_MODE to \"index\" and use CODE_COLUMN_INDEX to pick one directly." as critical
					return
				end if

				set nameColIndex to item 1 of nameMatches
				set codeColIndex to item 1 of codeMatches
			end if

			-- ONE call for the entire name column, ONE call for the entire
			-- code column — this replaces hundreds/thousands of per-cell
			-- reads with exactly two calls, no matter how many rows exist.
			set nameValues to value of every cell of column nameColIndex of targetTable
			set codeValues to value of every cell of column codeColIndex of targetTable
		end tell

		-- Everything below is pure AppleScript operating on the lists we
		-- already have in memory — no more talking to Numbers until the
		-- single write-back at the very end (skipped entirely in dry-run).

		-- ---------------------------------------------------------------
		-- SECTION 4: DIAGNOSTICS — capture exactly what got matched and
		-- what the first few real cells contain.
		-- ---------------------------------------------------------------
		set matchedNameHeader to my safeText(item nameColIndex of headerValues)
		set matchedCodeHeader to my safeText(item codeColIndex of headerValues)

		set sampleNames to {}
		set sampleCodes to {}
		set sampleLimit to (HEADER_ROW_INDEX + 3)
		if sampleLimit > rowCount then set sampleLimit to rowCount
		repeat with r from (HEADER_ROW_INDEX + 1) to sampleLimit
			set end of sampleNames to ("[" & my safeText(item r of nameValues) & "]")
			set end of sampleCodes to ("[" & my safeText(item r of codeValues) & "]")
		end repeat

		set logLines to logLines & {"=== Inventory ID Generator run: " & (current date as string) & " ==="}
		set logLines to logLines & {"Config: PREFIX=" & PREFIX & " NUMBER_WIDTH=" & NUMBER_WIDTH & " REUSE_MISSING_NUMBERS=" & REUSE_MISSING_NUMBERS & " SORT_MODE=" & SORT_MODE & " DRY_RUN=" & DRY_RUN & " STRICT_MODE=" & STRICT_MODE}
		set logLines to logLines & {"Name column: #" & nameColIndex & " (\"" & matchedNameHeader & "\")   Code column: #" & codeColIndex & " (\"" & matchedCodeHeader & "\")"}

		-- ---------------------------------------------------------------
		-- SECTION 5: FIRST PASS — validate existing codes, record which
		-- numbers are already taken.
		-- ---------------------------------------------------------------
		repeat with r from (HEADER_ROW_INDEX + 1) to rowCount
			set rawCode to my trimText(my safeText(item r of codeValues))
			if rawCode is not "" then
				set existingCodes to existingCodes & {rawCode}
				if my isValidCode(rawCode) then
					set usedNumbers to usedNumbers & {my extractNumber(rawCode)}
				else
					set malformedList to malformedList & {rawCode}
				end if
			end if
		end repeat

		-- STRICT_MODE: stop now, before generating anything, if the sheet
		-- already has malformed IDs that need attention.
		if STRICT_MODE and (count of malformedList) > 0 then
			set strictMsg to "STRICT_MODE is on and " & (count of malformedList) & " existing ID(s) don't match the expected " & PREFIX & "/XX/" & my padNumber(0) & " pattern. Fix these first, or turn STRICT_MODE off." & return & return
			set previewCount to 25
			if (count of malformedList) < previewCount then set previewCount to (count of malformedList)
			repeat with i from 1 to previewCount
				set strictMsg to strictMsg & "  " & (item i of malformedList) & return
			end repeat
			if (count of malformedList) > previewCount then
				set strictMsg to strictMsg & "  ...and " & ((count of malformedList) - previewCount) & " more"
			end if
			display alert "Stopped: malformed existing IDs found" message strictMsg as critical
			return
		end if

		-- ---------------------------------------------------------------
		-- SECTION 6: SECOND PASS — gather rows that need a new code
		-- (blank code, non-blank name), then optionally sort them.
		-- ---------------------------------------------------------------
		set pendingRows to {}

		repeat with r from (HEADER_ROW_INDEX + 1) to rowCount
			set rawCode to my trimText(my safeText(item r of codeValues))

			if rawCode is not "" then
				set skippedHasID to skippedHasID + 1
			else
				set rawName to my trimText(my safeText(item r of nameValues))

				if rawName is "" then
					set skippedBlankName to skippedBlankName + 1
				else if (not ALLOW_MIXED_ALPHANUMERIC) and (my containsMixedAlphanumericToken(rawName)) then
					-- A token like "12V" or "M6" mixes letters and digits.
					-- Rather than silently guessing which letters belong
					-- in the initials, set this row aside for manual review.
					set end of flaggedMixedList to {rowIndex:r, nameText:rawName}
				else
					set end of pendingRows to {rowIndex:r, nameText:rawName}
				end if
			end if
		end repeat

		if SORT_MODE is "name" then
			set pendingRows to my sortPendingRowsByName(pendingRows)
		end if

		-- ---------------------------------------------------------------
		-- SECTION 7: THIRD PASS — assign codes in memory, in whatever
		-- order SECTION 6 left pendingRows in.
		-- ---------------------------------------------------------------
		set newCodeValues to codeValues

		repeat with pendingItem in pendingRows
			set r to rowIndex of pendingItem
			set rawName to nameText of pendingItem

			set theInitials to my extractInitials(rawName)
			set theNumber to my getNextNumber(usedNumbers)
			set newCode to PREFIX & "/" & theInitials & "/" & my padNumber(theNumber)

			-- Belt-and-suspenders duplicate check, capped so a bug can
			-- never spin forever.
			set safetyCounter to 0
			repeat while existingCodes contains newCode
				set theNumber to theNumber + 1
				set newCode to PREFIX & "/" & theInitials & "/" & my padNumber(theNumber)
				set safetyCounter to safetyCounter + 1
				if safetyCounter > MAX_SEARCH_ITERATIONS then
					error "Could not find a free code for \"" & rawName & "\" — check NUMBER_WIDTH."
				end if
			end repeat

			set item r of newCodeValues to newCode
			set existingCodes to existingCodes & {newCode}
			set usedNumbers to usedNumbers & {theNumber}
			set addedCount to addedCount + 1

			if ENABLE_LOGGING then
				set logLines to logLines & {"Row " & r & ": \"" & rawName & "\" -> " & newCode & "  (initials: " & theInitials & ")"}
			end if
		end repeat

		-- ---------------------------------------------------------------
		-- SECTION 8: WRITE BACK — a single call that writes every
		-- generated code at once. Skipped entirely in DRY_RUN.
		-- ---------------------------------------------------------------
		if addedCount > 0 and not DRY_RUN then
			tell application "Numbers"
				set value of every cell of column codeColIndex of targetTable to newCodeValues
			end tell
		end if

		-- ---------------------------------------------------------------
		-- SECTION 9: SUMMARY REPORT (+ log file if enabled)
		-- ---------------------------------------------------------------
		set summaryText to ""
		if DRY_RUN then
			set summaryText to summaryText & "*** DRY RUN — nothing was written to the spreadsheet ***" & return & return
		end if

		set summaryText to summaryText & "Name column: #" & nameColIndex & " (header text: \"" & matchedNameHeader & "\")" & return
		set summaryText to summaryText & "Sample names read: " & my joinList(sampleNames, " ") & return & return
		set summaryText to summaryText & "Code column: #" & codeColIndex & " (header text: \"" & matchedCodeHeader & "\")" & return
		set summaryText to summaryText & "Sample codes read: " & my joinList(sampleCodes, " ") & return & return
		set summaryText to summaryText & "Done!" & return & return
		set summaryText to summaryText & "Added: " & addedCount & " IDs" & return
		set summaryText to summaryText & "Skipped: " & skippedHasID & " already had IDs" & return
		set summaryText to summaryText & "Skipped: " & skippedBlankName & " blank names" & return
		set summaryText to summaryText & "Flagged: " & (count of flaggedMixedList) & " names with mixed letters+numbers (ALLOW_MIXED_ALPHANUMERIC is off)" & return
		set summaryText to summaryText & "Found: " & (count of malformedList) & " malformed ID(s)"

		if (count of flaggedMixedList) > 0 then
			set summaryText to summaryText & return & return & "Flagged for manual review (mixed letters+numbers):" & return
			set previewCount to 25
			if (count of flaggedMixedList) < previewCount then set previewCount to (count of flaggedMixedList)
			repeat with i from 1 to previewCount
				set flaggedItem to item i of flaggedMixedList
				set summaryText to summaryText & "  Row " & (rowIndex of flaggedItem) & ": " & (nameText of flaggedItem) & return
			end repeat
			if (count of flaggedMixedList) > previewCount then
				set summaryText to summaryText & "  ...and " & ((count of flaggedMixedList) - previewCount) & " more" & return
			end if
		end if

		if (count of malformedList) > 0 then
			set summaryText to summaryText & return & return & "Malformed:" & return
			repeat with badCode in malformedList
				set summaryText to summaryText & "  " & badCode & return
			end repeat
		end if

		if ENABLE_LOGGING then
			set resultLine to "Result: added=" & addedCount & " skippedHasID=" & skippedHasID & " skippedBlankName=" & skippedBlankName & " flaggedMixedAlphanumeric=" & (count of flaggedMixedList) & " malformed=" & (count of malformedList)
			if DRY_RUN then set resultLine to resultLine & " [DRY RUN]"
			set logLines to logLines & {resultLine}
			set logLines to logLines & {""}
			set logPath to LOG_FILE_PATH
			if logPath is "" then
				set logPath to (POSIX path of (path to desktop folder)) & "inventory_id_generator_log.txt"
			end if
			my appendToLogFile(logPath, my joinList(logLines, return))
			set summaryText to summaryText & return & return & "Log appended to: " & logPath
		end if

		display dialog summaryText buttons {"OK"} default button "OK" with title "Inventory ID Generator"

	on error errMsg number errNum
		display alert "Something went wrong" message (errMsg & " (error " & errNum & ")") as critical
	end try
end run

-- =============================================================================
--  SECTION 10: HELPER HANDLERS  (all pure AppleScript — no Apple Events, fast)
-- =============================================================================

-- ---- COLUMN DISCOVERY -------------------------------------------------------
-- Returns every matching column index, not just the first — lets the
-- caller detect and refuse duplicate headers instead of silently guessing.
on findAllColumnIndices(headerValues, headerName)
	set matches to {}
	repeat with c from 1 to (count of headerValues)
		set cellText to my trimText(my safeText(item c of headerValues))
		if my uppercaseText(cellText) is equal to my uppercaseText(headerName) then
			set end of matches to c
		end if
	end repeat
	return matches
end findAllColumnIndices

on joinList(theList, delim)
	set oldDelims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to delim
	set joined to theList as text
	set AppleScript's text item delimiters to oldDelims
	return joined
end joinList

-- For each column index in matches, fetches the value in sampleRowIndex
-- so a "duplicate header" alert can show what's actually inside each
-- colliding column, instead of just the column numbers.
on buildColumnSampleText(matches, sampleRowIndex, targetTable)
	set sampleLines to ""
	tell application "Numbers"
		repeat with idx in matches
			set sampleVal to ""
			try
				set sampleVal to my safeText(value of cell idx of row sampleRowIndex of targetTable)
			end try
			set sampleLines to sampleLines & "  Column " & idx & ": \"" & sampleVal & "\"" & return
		end repeat
	end tell
	return sampleLines
end buildColumnSampleText

-- ---- ID VALIDATION -----------------------------------------------------------
-- Valid shape: PREFIX & "/" & <2 letters> & "/" & <NUMBER_WIDTH digits>
on isValidCode(codeText)
	set AppleScript's text item delimiters to "/"
	set parts to text items of codeText
	set AppleScript's text item delimiters to ""

	if (count of parts) is not 3 then return false

	set p1 to item 1 of parts as text
	set p2 to item 2 of parts as text
	set p3 to item 3 of parts as text

	if p1 is not PREFIX then return false
	if (length of p2) is not 2 then return false
	if not (my isAllLetters(p2)) then return false
	if (length of p3) is not NUMBER_WIDTH then return false
	if not (my isAllDigits(p3)) then return false

	return true
end isValidCode

on extractNumber(codeText)
	set AppleScript's text item delimiters to "/"
	set parts to text items of codeText
	set AppleScript's text item delimiters to ""
	try
		return (item 3 of parts) as integer
	on error
		return -1
	end try
end extractNumber

-- ---- SEMANTIC INITIAL EXTRACTION -----------------------------------------------
-- Pipeline: strip parenthesized text -> strip digits/punctuation ->
-- tokenize -> drop stop words -> take initials from what's left.
--   2+ tokens -> first letter of token 1 + first letter of token 2
--   1 token    -> first two letters of that token (padded with "X" if
--                 the token is a single letter)
--   0 tokens   -> "XX" fallback
on extractInitials(productName)
	set noParens to my removeParentheses(productName)
	set cleaned to my cleanToLettersAndSpaces(noParens)
	set rawTokens to my getTokens(cleaned)

	set filteredTokens to {}
	repeat with tok in rawTokens
		if not (my isStopWord(tok as text)) then
			set end of filteredTokens to (tok as text)
		end if
	end repeat

	-- If stop-word filtering removed every token (e.g. a name that was
	-- just a unit, like "125 ML"), fall back to the unfiltered tokens
	-- rather than defaulting straight to "XX".
	if (count of filteredTokens) is 0 then
		set tokens to rawTokens
	else
		set tokens to filteredTokens
	end if

	set tokenCount to count of tokens

	if tokenCount is 0 then
		return "XX"
	else if tokenCount is 1 then
		set tok to item 1 of tokens
		if (length of tok) ≥ 2 then
			return my uppercaseText(text 1 thru 2 of tok)
		else
			return (my uppercaseText(tok)) & "X"
		end if
	else
		set tok1 to item 1 of tokens
		set tok2 to item 2 of tokens
		return (my uppercaseText(character 1 of tok1)) & (my uppercaseText(character 1 of tok2))
	end if
end extractInitials

-- Removes parenthesized spans, including nested ones, e.g.
-- "SODIUM HYDROXIDE (25 KG)" -> "SODIUM HYDROXIDE "
on removeParentheses(t)
	set result to ""
	set depth to 0
	repeat with i from 1 to length of t
		set ch to character i of t
		if ch is "(" then
			set depth to depth + 1
		else if ch is ")" then
			if depth > 0 then set depth to depth - 1
		else if depth is 0 then
			set result to result & ch
		end if
	end repeat
	return result
end removeParentheses

on isStopWord(tok)
	set upperTok to my uppercaseText(tok)
	repeat with sw in STOP_WORDS
		if (my uppercaseText(sw as text)) is equal to upperTok then return true
	end repeat
	return false
end isStopWord

-- Checks the ORIGINAL name (after paren-stripping, before letter-only
-- cleaning) for any whitespace-separated token that mixes letters and
-- digits, e.g. "12V", "M6", "500ML". Used to decide whether a name is
-- ambiguous enough to flag rather than guess at when
-- ALLOW_MIXED_ALPHANUMERIC is false.
on containsMixedAlphanumericToken(t)
	set noParens to my removeParentheses(t)
	set oldDelims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to " "
	set rawTokens to text items of noParens
	set AppleScript's text item delimiters to oldDelims

	set letters to "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
	set digits to "0123456789"

	repeat with tok in rawTokens
		set tokText to tok as text
		if tokText is not "" then
			set hasLetter to false
			set hasDigit to false
			repeat with i from 1 to length of tokText
				set ch to character i of tokText
				if letters contains ch then set hasLetter to true
				if digits contains ch then set hasDigit to true
			end repeat
			if hasLetter and hasDigit then return true
		end if
	end repeat
	return false
end containsMixedAlphanumericToken

on cleanToLettersAndSpaces(theText)
	set letters to "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
	set cleaned to ""
	repeat with i from 1 to length of theText
		set ch to character i of theText
		if letters contains ch then
			set cleaned to cleaned & ch
		else
			set cleaned to cleaned & " "
		end if
	end repeat
	return cleaned
end cleanToLettersAndSpaces

on getTokens(theText)
	set AppleScript's text item delimiters to " "
	set rawItems to text items of theText
	set AppleScript's text item delimiters to ""
	set tokens to {}
	repeat with itm in rawItems
		if (itm as text) is not "" then set end of tokens to (itm as text)
	end repeat
	return tokens
end getTokens

-- ---- SORTING -------------------------------------------------------------------
-- Simple insertion sort by product name (case-insensitive). Fine
-- performance-wise even for thousands of rows since this never touches
-- Numbers — it's pure in-memory list manipulation.
on sortPendingRowsByName(pendingRows)
	set n to count of pendingRows
	repeat with i from 2 to n
		set currentItem to item i of pendingRows
		set currentKey to my uppercaseText(nameText of currentItem)
		set j to i - 1
		repeat while j ≥ 1 and (my uppercaseText(nameText of (item j of pendingRows))) > currentKey
			set item (j + 1) of pendingRows to item j of pendingRows
			set j to j - 1
		end repeat
		set item (j + 1) of pendingRows to currentItem
	end repeat
	return pendingRows
end sortPendingRowsByName

-- ---- DUPLICATE CHECKING / NUMBER GENERATOR -------------------------------------
-- Both branches are capped by MAX_SEARCH_ITERATIONS so a data problem
-- raises a clear error instead of hanging.
on getNextNumber(usedNumbers)
	if REUSE_MISSING_NUMBERS then
		set n to 1
		repeat MAX_SEARCH_ITERATIONS times
			if usedNumbers does not contain n then return n
			set n to n + 1
		end repeat
		error "Could not find an available number after " & MAX_SEARCH_ITERATIONS & " attempts."
	else
		if (count of usedNumbers) is 0 then return 1
		set maxN to 0
		repeat with n in usedNumbers
			if (n as integer) > maxN then set maxN to (n as integer)
		end repeat
		return maxN + 1
	end if
end getNextNumber

on padNumber(n)
	set numStr to (n as integer) as text
	repeat while (length of numStr) < NUMBER_WIDTH
		set numStr to "0" & numStr
	end repeat
	return numStr
end padNumber

-- ---- LOGGING ---------------------------------------------------------------------
-- Appends (never overwrites) so ENABLE_LOGGING builds a running audit
-- trail across runs.
on appendToLogFile(logPath, content)
	try
		set fileRef to open for access (POSIX file logPath) with write permission
		write (content & return) to fileRef starting at eof
		close access fileRef
		return true
	on error
		try
			close access (POSIX file logPath)
		end try
		return false
	end try
end appendToLogFile

-- ---- GENERIC TEXT UTILITIES ----------------------------------------------------
on safeText(v)
	try
		if v is missing value then return ""
		-- A boolean here means the cell is Checkbox-formatted (Numbers
		-- data format), not that it contains real text. Converting it
		-- with "as text" would turn an empty checkbox into the literal
		-- string "false", which then looks like a real (if malformed)
		-- existing code and blocks generation for that row. Treat it
		-- as blank instead. NOTE: this only stops the false-positive
		-- reads — if a column is Checkbox-formatted, writing real text
		-- codes into it may still fail or get coerced back to a
		-- boolean. Fix the column's Data Format to "Text" in Numbers
		-- (select the column -> Format sidebar -> Cell -> Data Format)
		-- before running this script.
		if class of v is boolean then return ""
		return v as text
	on error
		return ""
	end try
end safeText

-- Computes start/end indices first and slices once, instead of
-- repeatedly reslicing — avoids an invalid reversed range ("text 2
-- thru 1") that a naive version throws on any 1-character or
-- whitespace-only string.
on trimText(t)
	set t to t as text
	set L to length of t
	if L is 0 then return t

	set startIdx to 1
	set endIdx to L
	repeat while (startIdx ≤ endIdx) and (character startIdx of t is " ")
		set startIdx to startIdx + 1
	end repeat
	repeat while (endIdx ≥ startIdx) and (character endIdx of t is " ")
		set endIdx to endIdx - 1
	end repeat

	if startIdx > endIdx then return ""
	return text startIdx thru endIdx of t
end trimText

on uppercaseText(theText)
	set lower to "abcdefghijklmnopqrstuvwxyz"
	set upper to "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
	set result to ""
	repeat with i from 1 to length of theText
		set ch to character i of theText
		set p to offset of ch in lower
		if p > 0 then
			set result to result & character p of upper
		else
			set result to result & ch
		end if
	end repeat
	return result
end uppercaseText

on isAllLetters(t)
	set letters to "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
	repeat with i from 1 to length of t
		if letters does not contain (character i of t) then return false
	end repeat
	return true
end isAllLetters

on isAllDigits(t)
	set digits to "0123456789"
	repeat with i from 1 to length of t
		if digits does not contain (character i of t) then return false
	end repeat
	return true
end isAllDigits

-- =============================================================================
--  PORTING NOTES (only relevant if this isn't actually a Numbers document)
-- =============================================================================
--  Excel:  swap the bulk read/write calls for Excel's equivalents, e.g.
--            value of every cell of column c of used range  (read)
--            set value of every cell of column c of used range to {...}  (write)
--          Keep the "read whole column once, process in memory, write
--          whole column once" pattern — don't go back to per-cell loops.
--
--  CSV:    read the file with `read file ... as <<class utf8>>`, split on
--          return characters for rows and on "," for columns, run the
--          same in-memory logic in SECTIONS 5-7 against those lists,
--          then rebuild the CSV text and write it back out once.
-- =============================================================================
```
