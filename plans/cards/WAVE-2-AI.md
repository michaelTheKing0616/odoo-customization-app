# Wave 2 — AI: prompt engineering & pipeline upgrades (Documents 4 + 2 gaps)

Shared context: LLM abstraction is `apps/api/app/llm_provider.py` (ollama +
openai-compatible, `format: json`). Pipelines: `ai_ollama.py` (single, default),
`ai_pipeline.py` (staged, `AI_PIPELINE_MODE=staged`). Settings in `settings.py`. Doc 4's
ordered levers: model ladder → thinking mode → temps → self-consistency → anti-patterns.
Regression safety net: `tests/test_mastery_regression_battery.py` must stay green after every
card here.

---

## AI-1 — Thinking mode + Qwen3 size ladder (Grok 4.5 card)

TASK: Add a `reasoning` flag and per-step model routing (bulk vs reasoning tier) to the LLM
provider and both pipelines.

INPUT: `llm_provider.py`, `settings.py`, `ai_ollama.py`, `ai_pipeline.py`, `ai_critique.py`,
`ai_model_quality.py` (`llm_emit_missing_scaffold_models`).

CHECKLIST:
- [ ] Settings: `AI_MODEL_BULK` (default `qwen3:8b`), `AI_MODEL_REASONING` (default
      `qwen3:14b`), `AI_THINKING` (`auto|on|off`, default auto). Existing `AI_MODEL`-style
      setting remains as fallback for both (backward compatible).
- [ ] `LLMProvider.generate(..., reasoning: bool = False)`: ollama backend sends the think
      parameter — VERIFY the exact param name against the installed Ollama version first
      (`ollama --version` + /api/chat docs probe); if unsupported, fall back to manual CoT:
      prepend step-by-step instruction, parse only after a `---JSON---` marker. openai-compat
      backend: map to `reasoning_effort` if the endpoint accepts it, else manual fallback.
      Thinking trace is ALWAYS discarded before JSON parse.
- [ ] Routing: reasoning=True + reasoning model for: scaffold/domain matching, relationships
      step, automations step, critique, `llm_emit_missing_scaffold_models`, (AI-4's workflow
      pass). reasoning=False + bulk model for: entity extraction, per-model fields.
      Single-pipeline draft call: reasoning model, thinking on.
- [ ] Schema-constrained decoding (cheap variant, per DEFERRALS decision 2026-08-02): probe
      whether the installed Ollama accepts a JSON SCHEMA in the `format` field (not just
      `"json"`). If yes: pass the step's response schema in `format` for pipeline steps with
      stable schemas (entities, fields, relationships), keeping the pydantic validate/repair
      pass as backstop; if no: keep `format: json` unchanged. Record the probe result. Do NOT
      add outlines/guidance or any new serving stack — that route is deferred.
- [ ] `GET /api/ai/status` reports both models + thinking support detection result + whether
      schema-in-format is active.
- [ ] Tests: provider unit tests with fake backends asserting param routing + trace
      stripping; settings matrix test.
- [ ] Run mastery battery — green.

DONE MEANS: both pipelines route models/thinking per table above; one real Ollama call with
thinking recorded to `docs/research/thinking_probe_<date>.json`.

DO NOT: hallucinate the Ollama API parameter — probe first (rule: verify Odoo/tooling API
claims against the live thing). Do not raise default latency for bulk steps.

GATE: `uv run pytest tests/test_ai_ollama.py tests/test_ai_module_generation.py tests/test_mastery_regression_battery.py -q` + real probe file.

RETURN: ≤10 lines incl. detected think-param syntax.

DEVIATIONS: conservative + log.

---

## AI-2 — Per-step temperature + prompt audit + anti-pattern blocks

TASK: Apply Doc 4 §5/§2/§3/§7 across every prompt: temperatures per step type, show-don't-tell
schema examples, closed vocab, explicit DO-NOT blocks, adjacent-not-identical exemplars.

INPUT: `llm_provider.py` (temperature pass-through), `ai_pipeline.py`, `ai_ollama.py`,
`ai_critique.py`, `ai_model_quality.py`, `ai_domain_packs.py` (teaching blob).

CHECKLIST:
- [ ] `generate(..., temperature: float | None)` plumbed to both backends.
- [ ] Temps: extraction/fields/relationships/validation 0.15; entities + automations 0.6;
      critique 0.15; single-pipeline 0.3 (documented constants, one module-level table).
- [ ] Audit EVERY prompt against Doc 4 §2: concrete example output shown (not described),
      closed ttype vocabulary listed, "Output ONLY the JSON" instruction present. Fix
      stragglers; record the audit as a table in the PR/return.
- [ ] Anti-pattern DO-NOT block appended per step (Doc 4 §7): no invented ttypes; no relations
      to models not in the entity list; no `id` field name; no prose around JSON; plus the
      protected-modules one-liner (PCM-3's section).
- [ ] Exemplar check: few-shot exemplar for a domain must be thematically adjacent, never the
      matched pack itself (Doc 4 §3) — assert in code (skip exemplar if same pack id).
- [ ] Mastery battery + law-firm pack tests green; one real generation compared before/after
      saved to `docs/research/temp_tuning_<date>/`.

DONE MEANS: audit table complete (every prompt listed with its temp + schema-example status);
tests green.

DO NOT: change prompt SEMANTICS beyond the listed additions; no new pipeline steps here.

GATE: `uv run pytest tests/ -q -k "ai"` full AI subset.

RETURN: audit table + ≤10 lines.

DEVIATIONS: conservative + log.

---

## AI-3 — Self-consistency behind AI_SELF_CONSISTENCY

TASK: N-sample vote/merge for the two highest-stakes steps: domain-scaffold selection and
workflow-state definition.

INPUT: `ai_pipeline.py`, `ai_ollama.py` (scaffold retrieval + AI-4's workflow pass),
`ai_rag.py`, `settings.py`.

CHECKLIST:
- [ ] Setting `AI_SELF_CONSISTENCY=off|on` (default off; docs note ~2–3x calls on those steps).
- [ ] Scaffold selection: 3 samples at temp 0.5 → majority vote on pack id; tie → highest
      retrieval score; disagreement logged as warning.
- [ ] Workflow states: 3 samples → merge = union of states appearing ≥2 times, order by
      average position; transitions kept when endpoints survive; merge notes in warnings.
- [ ] Deterministic with seeded fake provider in tests (vote + merge + tie paths).
- [ ] `GET /api/ai/status` reports the flag.

DONE MEANS: flag off = zero behavior change (regression suite proves); flag on = vote/merge
paths tested.

DO NOT: apply to bulk steps; no user-facing latency change while off.

GATE: `uv run pytest tests/test_ai_rag_critique.py tests/test_mastery_regression_battery.py -q` + new tests.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## AI-4 — Dedicated workflow pass (Step 4) (Grok 4.5 card)

TASK: Add the explicit Doc 2 §3 Step 4: for every `is_workflow` entity, an LLM pass defines
status states AND valid transitions; transitions feed statusbar buttons and automation
suggestions.

INPUT: `ai_pipeline.py` (between relationships and automations), `ai_ollama.py` (single-path
equivalent enrichment), `ai_enrich.py` (statusbar/buttons), `ai_rules.py`,
`packages/module-generator` (spec fields for transitions).

CHECKLIST:
- [ ] Spec extension: `state_field` gains `transitions: [[from, to], ...]` (schema +
      round-trip in module-generator .meta.json; additive, optional — old specs stay valid).
- [ ] Staged pipeline: new step calling reasoning model (thinking on, temp 0.15) per workflow
      entity; validates states exist, transitions reference real states, terminal states have
      no mandatory outgoing edge.
- [ ] Single pipeline: quality pass derives/validates transitions from emitted selections
      (deterministic default chain draft→…→terminal when LLM omitted them).
- [ ] `ai_enrich.py`: form statusbar buttons generated FROM transitions (confirm/cancel/etc.
      per edge) instead of generic pairs; existing behavior preserved when no transitions.
- [ ] Automation suggestions may reference transitions (e.g. overdue only from active states).
- [ ] Tests: staged step unit test (fake provider), enrich buttons-from-transitions test,
      regression battery green.

DONE MEANS: drafts contain validated transitions; forms show transition-derived buttons; no
regression.

DO NOT: make transitions required; break `.meta.json` round-trip compatibility.

GATE: `uv run pytest tests/ -q -k "ai or module_generation"` + one real staged run saved.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## AI-5 — Five new domain packs

TASK: Build restaurant/POS-lite, real_estate/property, hotel/PMS, subscription/membership,
and simple project/task packs at law-firm depth.

INPUT: `ai_domain_pack_law_firm.py` + `ai_reference_law_firm.py` (the pattern to follow),
`ai_domain_packs.py` (registry + retrieval), `ai_domain_pack_hospital.py`,
`docs/reference/law_firm_modulespec_gold.json` (depth bar).

CHECKLIST (repeat per pack — check each pack line only when ALL sub-items done for it):
- [ ] Pack: restaurant (tables/reservations/orders/menu items/kitchen statuses; POS-adjacent
      but NO payment logic — link-only per PCM).
- [ ] Pack: real_estate (properties/units/leases/viewings/maintenance requests/deposits;
      lease workflow with terminal states).
- [ ] Pack: hotel (rooms/room types/bookings/check-in-out workflow/housekeeping tasks/rate
      plans; booking↔invoice link-only).
- [ ] Pack: subscription (plans/subscriptions/renewal workflow/usage lines; NO recurring
      billing logic — link to invoicing pattern only, sale_subscription is tier-1).
- [ ] Pack: project_tracker (projects/tasks/milestones/time entries; assignee = res.users
      login rule respected).
Per pack requirements (the checker verifies each): gold-spec module file
`ai_domain_pack_<id>.py` (+ reference module if following law-firm split); canonical `x_`
names the generator already emits; rich selections (no placeholder keys); parent O2Ms;
line→bill links where domain warrants; party/role models NOT workflows; staff FK rules
(domain staff model vs res.users login); anti_patterns list; tags for retrieval; registered
in `_PACK_FACTORIES`; retrieval test (prompt → pack id, score ≥ threshold); merge-deepens-thin-
draft test; teaching-blob depth test — mirror `tests/test_ai_law_firm_pack.py` structure as
`tests/test_ai_pack_<id>.py`.

DONE MEANS: 5 packs registered, 5 test files green, retrieval disambiguation test (hotel vs
real_estate vs restaurant prompts pick correctly) green, mastery battery green.

DO NOT: touch existing packs; introduce payment/tax logic in any pack (tier-1).

GATE: `uv run pytest tests/ -q -k "pack"` + full AI subset.

RETURN: ≤10 lines — models-per-pack counts.

DEVIATIONS: conservative + log.

---

## AI-6 — Draft→pack generalizer (library flywheel)

TASK: Opt-in tool that generalizes a finished ModuleSpec draft/project into a candidate
domain-pack file for human review (Doc 2 §4's compounding moat).

INPUT: `ai_domain_packs.py`, a saved project (`routers/projects.py`), law-firm pack shape.

CHECKLIST:
- [ ] `POST /api/ai/generalize-pack` (input: ModuleSpec JSON or project id): strips
      instance-specific naming to canonical `x_` names, extracts selections/relations/
      automations/smart buttons, emits a ready-to-review `ai_domain_pack_candidate_<slug>.py`
      source string + tags suggestion (LLM reasoning call for tags/anti-patterns; deterministic
      for structure).
- [ ] Output is DOWNLOAD/response only — never auto-registered (human reviews then commits).
- [ ] Round-trip test: law-firm gold spec → generalizer → output parses + classify-compatible.
- [ ] Wizard/projects UI: "Suggest as template" button with consent note (permission framing
      per Doc 2 §4).

DONE MEANS: endpoint + UI button + tests green.

DO NOT: auto-write files into `apps/api/app/`; skip the consent framing.

GATE: pytest new tests + web build.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## AI-7 — Reverse-import partial-fidelity contract

TASK: Guarantee Doc 2 §7's promise: anything the importer can't confidently map is flagged
"custom logic — view as code", preserved VERBATIM, and re-exported unchanged.

INPUT: `module_import.py`, `packages/module-generator` (export), `spec_apply_ui.py` (must
ignore opaque blocks), ModuleSpec editor UI (`ModuleSpecEditor.tsx`).

CHECKLIST:
- [ ] Import: unrecognized Python (compute methods, constrains, business logic) captured into
      `custom_code_blocks: [{source_file, kind, content, model?}]` on the spec — never dropped.
      Same for unrecognized XML nodes (custom widgets/JS assets refs).
- [ ] Export: blocks re-emitted verbatim into the generated module (correct file placement;
      byte-identical content test).
- [ ] Live apply: opaque blocks are skipped with an explicit per-item warning (never partial-
      applied).
- [ ] UI: ModuleSpec editor "Custom code" tab — read-only viewer with file/kind labels and the
      "not editable visually" explanation (COPY_GUIDE tone).
- [ ] Round-trip test: import a module containing a compute method + custom XML → export →
      diff shows blocks byte-identical; `tests/test_module_import.py` extended.

DONE MEANS: no silent drops — a fuzz test importing 3 OCA-style sample files shows zero lost
content (everything mapped OR in blocks).

DO NOT: attempt to parse arbitrary Python semantics; execute imported code.

GATE: `uv run pytest tests/test_module_import.py tests/test_report_export.py -q` + zip safety suite.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.
