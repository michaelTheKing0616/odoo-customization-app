# App Studio — handoff for outside review (2026-10-19)

Ingenium App Studio turns a plain-language business brief from a non-technical owner into a working Odoo app (custom models, fields, views, menus, security, standard automations), previews it, installs it on the owner's live Odoo, and can revert it. Backend: FastAPI (Python), `apps/api/app/...`. Frontend: Next.js. LLM: gemini-3.8-flash via a shared client (`app/ai_client`: cache, guards, `ai_scope` cache staleness).

## 1. Pipeline end to end
| Stage | What happens | Key code |
|---|---|---|
| Brief | Owner types or dictates the brief. The original words are kept (`brief_checklist.set_original`). Any AI expansion of the brief (`brief_expand.py`) is held separately, and `source_brief(prompt)` returns the owner's words only. | `ai_conversation/brief_expand.py`, `brief_checklist.py` |
| Understand | Clauses are grounded against stock Odoo, and an **intent contract** is built: material interpretations with source spans and a decision per requirement (`metadata`, `stock_automation`, `option_a` (Python), `clarify`, `declined`). A verifier, conflict look and second look check the contract. | `understand.py`, `intent_contract.py`, `intent_llm.py`, `clause_grounding.py`, `conflict_look.py`, `app_design._call_intent_contract` |
| Questions / assumptions | An intent gate asks only must-ask questions. Everything else becomes a visible, editable assumption or checklist choice ("choices we made"), and "maybe later" items go to `left_out`. | `intent_gate.py`, `clarify.py`, `brief_checklist.py` |
| Diagnosis | Capability check (build / route / decline), stock-first routing (domain hosts such as sale.order and stock.picking are preferred over custom copies; generic hosts such as res.partner stay as extensions), and routes for outside services. | `diagnosis_decision.py`, `capability.py`, `stock_routing.py` |
| AI design | One LLM call returns an AppDesign JSON (`_DESIGN_SHAPE`): new_models, stock_extensions, integrations, groups, menus, python_needed. The model budget is `model_budget_for(prompt)` (3–12, about 4 for a paragraph). A critic can flag issues but never changes the design. | `app_design.design_system_prompt`, `design_user_prompt`, `_call_llm`, `_call_critic`, `build_app_design` |
| Repair / validate | `validate_and_repair` covers naming, relation targets, inverse names, selection options and admission (`_admission_repair`: currency, automation fields). Then `design_quality.strengthen_design` (lists become lines, factor lines, action/alert models, partner summary fields), then a re-validate, then `dedupe_fields`, `ensure_jobs`, `complete_from_brief` (duties, roles, company, rules, views, alert jobs) and `scope_and_limits` (caps). `_merge_outline` and `_cover_sections` make sure a big brief is never smaller than its own sections. | `app_design.py` ~1666–2080, 2700–2745; `ai_conversation/design_quality.py` |
| Preview | The draft is generated (POST /api/ai/sessions/{id}/generate) and the owner sees a summary, assumptions, left-out items, stock checks and a preview proxy. | `routers/ai.py`, `ai_studio.py`, `preview_proxy.py` |
| Apply / install | Odoo records (ir.model, ir.model.fields, views, menus, access, base.automation) are created through public RPC with a dry-run receipt (middleware refuses gated writes without one), a money guard, and approval. | `install_step.py`, `automation_records.py`, dry_run_middleware |
| Revert | An undo journal per install removes the created records in reverse order. | install journal / revert endpoints |
| Refine | The owner edits the design or assumptions; the design is refreshed. | `refine.py`, `design_refresh.py`, `apply_design_edits`, `apply_assumption_choices` |

## 2. Hard constraints
- Clean-room: only the public Odoo ORM through XML-RPC / JSON-RPC (execute_kw). No server-side modules, no copied Odoo source, Odoo 17, 18, 19 and 20 all supported.
- Stock Odoo first: extend or route to installed or installable stock apps before making custom models.
- **AI proposes, code authorizes:** every LLM output is data that deterministic code checks, repairs or refuses. The money guard applies everywhere.
- Plain-language UI: no technical names shown to the owner.
- **No per-brief patches or word lists for specific evals:** fixes must be general rules.
- Never invent beyond the brief. Maybe/future items are left out and named, not built.

## 3. Eval harness (`apps/api/evals/v2/`)
- `score.py` calls the same entrypoint as the UI: POST /api/ai/sessions (diagnosis plus design), then /generate. It never installs. `EVAL_CONNECTION` is required (one production id is hard-refused). `--fresh` / `EVAL_FRESH=1` sends `x-ingenium-fresh` so nothing comes from the AI cache. The sealed holdout needs `EVAL_UNSEAL=yes`.
- Run: `EVAL_CONNECTION=<disposable conn> EVAL_FRESH=1 uv run python evals/v2/score.py --split holdout --repeats 1 --out /tmp/x.json`. The target is a throwaway Odoo 20 database (contacts, crm, sale_management).
- Splits: dev 20 briefs, holdout 8 (sealed), unseen 3. Each brief is `<id>.md` plus `<id>.gold.yaml` (needs with realizations, entities with attributes, exclusions, ambiguity_points, acceptable_alternates, lexical_lures, routes). The 28 dev and holdout gold files are ACCEPTED; the unseen ones are DRAFT.
- Metrics:
  - **need_coverage**: share of gold needs met.
    - Records: a custom model matching the need, OR a stock app used, OR the need converted onto an extended stock host.
    - Automation and access needs: at least 2 shared word stems.
  - **unauthorized_invention_rate**: per run, (custom models matching no gold entity or alternate) ÷ (all custom models), then the mean across runs.
  - **invented_severity**: model 3, automation 2, violated exclusion 5.
  - **exclusion_precision / recall**; **critical_must_ask_recall**; **unnecessary_question_rate**.
  - **stock_domain_conversion** / **stock_generic_kept**; **cannot_fired**.
  - **route_correctness**: N/A when there are no gold routes.
  - **custom_code_pieces**: python_needed that is not an online scheduled action.
  - **llm_calls_per_brief**; **latency**.
- Latest numbers (fresh sessions):

| | dev (before) | holdout before h-fix | holdout after h-fix |
|---|---|---|---|
| reached diagnosis | 15/20 | 7/8 | 7/8 |
| need_coverage | 0.50 | 0.444 | 0.528 |
| unauthorized_invention | 0.062 | 0.333 | 0.433 |
| invented_severity | 0.55 | 1.5 | 1.88 |
| exclusion_recall | – | 0.8 | 1.0 |
| custom_code_pieces | – | 0 | 2 |
| route_correctness | – | 0.0 (bug) | N/A |
| LLM calls / brief | – | 3.5 | 3.2 |
| latency s (after) | – | – | 55–185, median ~98, mean ~112, typical ~140 on rambling briefs |

- **The h-fix:** the template repairs in design_quality (Alert Rule model, res.partner x_score_* "customer 360" fields, jobs) were triggered by words in the AI's expansion of the brief ("alerts", "customer form"). They now read `source_brief()` only. Effect: terse_inventory's invented "Alert Rule" went away (0.333 → 0.0).

## 4. Current failure modes
**A. Detail promoted to a model (the main source of invention).** The owner mentions a concept as an attribute of the main record, and the AI makes it its own catalog or log model with many invented fields.
- salon_voice. Brief: "so like the salon, uh, appointments, which stylist, which service, the time, and um if the person no show we mark it. also future we fit do loyalty points but later." Gold: one entity, Appointment (customer, stylist, service, time, no-show); lure listed: "service". Output:
  - `Salon Service` [Service Name, Category, Standard Duration, Price, Product Link, Active, Description, Currency], why: "Centralized management of salon services…"
  - `Stylist Schedule` [Stylist, Day of Week, Shift Start/End, Max Concurrent Clients], why: "distinct from general resource calendar"
  - `Salon Appointment` (correct); extensions calendar.event, res.partner, res.users.
- ngo_rambling. Brief: "NGO distributing food packs, um, each beneficiary household, how many people, community, and each distribution day what they collected. donors want report per community monthly. maybe integrate with UN system someday." Gold: Household, Distribution. Output:
  - `Food Pack Type` [Pack Name, Description, Standard Contents, Status]
  - `Distribution Collection`
  - res.partner and stock.picking extensions.
  - The previous run invented `Community` instead, so the variant is unstable.
- generator_lure. Brief: "Our estate shares one diesel generator. Track fuel purchases (litres, cost, date) and who paid. The generator is serviced by an outside company, we don't track that." Gold: Fuel Purchase. Output:
  - `Generator Log` [running hours, fuel level estimate, hours since last log…]
  - `Resident Share` [billing period, allocated share, payment status…]
  - Extensions fleet.vehicle.log.fuel (wrong domain host) and res.partner; python "Calculated counts".
  - The previous run had no invention here.
- Dev case no_repair_maybe: a "maybe" Loyalty Account was built.

**B. Run-to-run variance.** The same brief with a fresh session gives different invented models (ngo: Community, then Food Pack Type; generator: none, then 2). With 8 holdout runs, one brief flipping moves the rate by about ±0.1.

**C. Coverage only 0.53.** Records needs are missed when the AI renames the main entity, or when stock-first routes it to a host that the scorer's word stems don't match.

**D. Custom code pieces 2** ("Calculated counts" etc.): computed counts are drifting into python_needed despite the prompt saying "a listed count is not custom Python by itself".

**E. Latency** of 55–185 s per brief: 3–4 LLM calls plus validation and live schema reads.

**F. Dev reached diagnosis 15/20:** 5 dev briefs stop at a question or error before a design.

**Already tried:**
- Prompt rules ("create new x_* models only for genuinely new concepts", "mark new supporting models suggested true").
- Model budget.
- The critic (flags only).
- The source_brief gate for template repairs (worked for templates).
- A code-level "detail-not-model" authorizer was drafted and then cancelled by the product owner pending this review. No code from it remains.
- The `suggested` flag is shown in the UI ("remove any you don't need"), but nothing in code enforces it.

**Code excerpts**
Design system prompt (core rules, `app_design.design_system_prompt`):
```
...extend a stock model (res.partner, crm.lead, sale.order, account.move, helpdesk.ticket, project.project) when a field
belongs there; never create a model that duplicates contacts, invoices, tickets, leads or sale orders...; create new x_*
models only for genuinely new concepts (scores, histories, rules, risks, plans, configuration); ... milestones, tasks and
score factors become child line models (one2many) ... explainable scores get a factor line model; proactive actions get
their own model with a 'why' field; alert rules get their own model. ... The brief may be informal or incomplete: fill
obvious gaps a non-technical operator would expect (supporting models, selection options, views, menus) as ordinary
metadata, and mark new supporting models suggested true.
```
(Note the tension: "fill obvious gaps … supporting models" invites exactly failure A.)

Model-creation decision point (`build_app_design`, after the LLM call and validate_and_repair):
```python
if strengthen_design(design, prompt, sales_ok=sales_ok):      # template repairs (owner words only since h-fix)
    design, _ = validate_and_repair(design, grounding, packet=..., prompt=prompt, budget=design.model_budget, snapshot=live)
design.notes = list(dict.fromkeys(design.notes + dedupe_fields(design) + ensure_jobs(design, prompt)
    + complete_from_brief(design, prompt) + scope_and_limits(design, prompt)))
# No step removes or demotes an AI-proposed new_model; only the budget caps the count.
```
Repair step style (`design_quality._child`): adds a child line model plus a one2many on the parent, respecting `model_budget`.
Data shapes: `DesignModel{name,label,description,why,fields[DesignField],views,is_config,suggested,requirement_ids}`, `DesignField{name,ttype,string,required,selection,relation,inverse_name,help,requirement_ids}`, `AppDesign{new_models,stock_extensions,integrations,security_groups,menus,python_needed,intent_contract,automations,relations,record_rules,model_budget,notes,left_out,stock_checks,...}`.

## 5. Open bugs / blocked items
- tokens.css has others' uncommitted edits, so the border-strong token change to n6 is blocked.
- Script-runner and bridge source files have others' uncommitted edits; new work goes in a parallel package.
- Pre-existing test failures (not from this work): test_reports_default_qweb_has_t_name, test_expert_ask_imports_conversation_hooks, 2 intent_gate tests, test_autopilot_packet…, test_diagnosis_name… (order-dependent).
- Old harness note: a JSON-2 422 on res.partner/create (missing vals_list) seen during one diagnosis run; not investigated.
- The scorer matches by word stems; a renamed but correct entity can count as both invented and missed.

## 6. Request to the reviewer
Please give:
1. **Root cause** of failure A and of the variance (B). Weigh the prompt's "fill gaps / supporting models" instruction, no code authorization of new models, the budget acting as a quota, and temperature/sampling. Say what evidence in this file supports each.
2. **A general fix design** (no per-brief lists), in three parts:
   - (a) Prompt changes: exact wording, e.g. requiring per-model evidence (a quote span from the owner's brief plus its lifecycle/records/attributes) in the JSON.
   - (b) A deterministic **code-level authorizer** run after the design LLM call. It keeps, folds (selection/char/many2one onto the host, or a one2many line) or moves to "suggested, not built" each new model, using only the owner's words (`source_brief`), the intent contract spans, and model structure. Give patch-ready Python pseudocode against the data shapes above: function signatures, where to call it in `build_app_design`, how to rewrite referencing fields, menus, automations, record_rules and python_needed, and the owner-facing note.
   - (c) Eval changes to cut variance and score fairly: repeats, seed/temperature control, entity matching beyond stems, reporting a confidence interval, and separating "suggested" from "built".
3. **Verification plan:** unit tests (positive and negative cases, including a brief where the detail concept DOES have its own lifecycle and must be kept), expected metric movement on holdout and dev, and a guard against coverage regression.
4. Fixes for D (computed counts drifting into python_needed) and C (coverage) if they share a cause.
