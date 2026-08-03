# Wave 5 — EXP: The Odoo Expert RAG assistant (Document 8, complete)

Shared context: different risk profile from the generator — advice acted on directly, no
validation layer between. Core rule: GROUND OR DECLINE. Shares infrastructure by
construction: PCM classification (advisory caution), TIER-1 matrix (accurate availability
answers), BLK-1 discovery (route to our bulk tools), ModuleSpec schema (in-progress work
awareness). Existing: `ai_rag.py` (MiniLM embeddings + Jaccard fallback), `llm_provider.py`
(+ AI-1 ladder/thinking). New module family: `apps/api/app/expert/`.

---

## EXP-1 — Knowledge base ingestion + version-tagged store

TASK: Build the static knowledge base: Odoo docs (RST, per version), this project's master
reference documents, optional curated community Q&A — chunked by headings, version-tagged,
embedded.

INPUT: `ai_rag.py` (embedding infra to extend, not duplicate), Doc 8 §3 spec, `settings.py`.

CHECKLIST:
- [x] Fetcher: sparse checkout `odoo/documentation` branches 16.0/17.0/18.0/19.0
      (`--filter=blob:none`, sparse-checkout `content`), same technique as PCM-2; ingestion
      CLI `python -m app.expert.ingest --version 19.0` with offline resume.
- [x] Chunker: RST heading-hierarchy chunking (docutils or regex-based section splitter —
      no heavyweight new deps; chunks carry breadcrumb path "Developer > Views > Inheritance"),
      target 300–900 tokens/chunk, never split mid-section below the target unless a section
      exceeds 2x max (then split at paragraph boundaries with continuation markers).
- [x] Project-docs source: ingest the 8-document master reference (store it at
      `docs/reference/MASTER_REFERENCE.md` if not already present — ask user for the file if
      missing rather than reconstructing) + selected `docs/*.md` capability docs, tagged
      `source: project`, version `all`.
- [x] Community Q&A: ingestion path implemented behind `EXPERT_COMMUNITY_SOURCE=off|dir`
      (off default) — reads a local directory of curated Q&A markdown (user curates; no
      scraping pipeline in v1 — flag as [SKIPPED] candidate ONLY the scraper, not the path).
- [x] Store: `expert_chunks` table (id, source, version, breadcrumb, text, embedding blob) in
      the app Postgres; embedding via existing MiniLM when installed, Jaccard fallback
      otherwise (mirror `ai_rag.py` pattern); cosine top-k retrieval with version filter +
      source weighting (project docs boosted).
- [x] Ingest run for 18.0 + 19.0 committed as a reproducible artifact count (chunk counts in
      return; store contents NOT committed to git — .gitignore the cache dir; ingestion is a
      setup step documented in README).
- [x] Tests: chunker on fixture RST (heading integrity, no mid-section splits), version
      filter, retrieval ranking sanity, fallback path.

DONE MEANS: `--version 19.0` ingest completes locally with chunk count reported; retrieval
returns relevant chunks for 5 sample queries (fixture-asserted).

DO NOT: scrape odoo.com HTML; hit GitHub REST API; commit the vector store.

GATE: `uv run pytest tests/test_expert_ingest.py -q` + real ingest run log.

RETURN: ≤10 lines + chunk counts per source/version.

DEVIATIONS: conservative + log.

---

## EXP-2 — Live-instance grounding (Grok 4.5 card)

TASK: Per-query context assembly that makes the Expert know THIS instance (Doc 8 §4).

INPUT: PCM-2 manifest cache, TIER-1 matrix, introspection endpoints, BLK-1 discovery cache,
frontend context contract (route, connection id, current model/ModuleSpec draft).

CHECKLIST:
- [x] `app/expert/grounding.py`: `assemble_context(connection_id?, ui_context?) -> GroundingBundle`
      — installed modules summary (names count + notable flags: base_automation, web_studio,
      account, l10n_*), detected version + hosting/edition, capability highlights relevant to
      the question (matrix rows matched by query keywords), current-screen context (model
      being edited: its fields/selections from draft or live), protected-tier flags for any
      model mentioned in the query.
- [x] Schema-aware error mode: if the query contains an RPC error pattern (model/field names,
      access error signatures), cross-check referenced model/field existence live and inject
      findings ("x_matter.x_status exists; x_mattr does not — likely typo").
- [x] Bulk-tool routing: query intent matching against our bulk suite registry — when the
      question is "how do I do X to many records", the bundle includes the matching in-app
      tool + deep link.
- [x] Version-filtered retrieval: grounding bundle sets the retrieval version filter from the
      connection (fallback: ask-user note in response when no connection given).
- [x] Token budget: bundle serializer caps sections (documented limits) so context stays
      within model window with retrieval chunks.
- [x] Tests: bundle assembly with fake caches; error-pattern extraction; intent routing table.

DONE MEANS: bundle for a docker-19 connection contains correct modules/version/capabilities;
error cross-check works live.

DO NOT: make live RPC calls beyond cached/introspection reads per query without caps
(performance); leak credentials into context.

GATE: pytest + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## EXP-3 — Generation endpoint: ground-or-decline + citations (Grok 4.5 card)

TASK: `POST /api/expert/ask` — retrieval + grounding + Qwen3 generation with citations,
refusal discipline, and protected-category caution (Doc 8 §5/§6/§7).

INPUT: EXP-1 store, EXP-2 grounding, AI-1 provider (ladder + thinking), PCM guardrail
reasoning, COPY_GUIDE tone.

CHECKLIST:
- [x] Request: {question, connection_id?, ui_context?, conversation: prior turns (capped)}.
      Response: {answer_markdown, citations: [{source, version, breadcrumb, chunk_id}],
      grounded: bool, declined: bool, suggested_tools: [], caution_flags: []}.
- [x] Routing: factual lookup → bulk model, thinking off; multi-step walkthrough/diagnosis →
      reasoning model, thinking on (intent classifier: cheap heuristic + doc-length of
      retrieval; documented). Temperature 0.15.
- [x] System prompt: Odoo Expert persona + Doc 8 §6 ground-or-decline text VERBATIM +
      citation requirement + protected-category caution behavior (explain why the constraint
      exists, point to the legitimate path incl. our tools, stop short of bypass
      instructions) + no definitive legal/tax/compliance conclusions rule.
- [x] Grounding enforcement is structural, not just prompted: if top retrieval scores below
      threshold → `declined: true` with the honest low-confidence message (COPY_GUIDE);
      every answer paragraph must map to ≥1 citation — post-parse check strips/flags
      uncited claims (regenerate once with stricter instruction, then flag).
- [x] Consistency with generator: a question asking for tier-1 logic returns the same
      reasoning PCM-3's refusal gives (shared category text) — named test.
- [x] Conversation memory: last N turns included (cap by tokens); no server-side profile
      building in v1.
- [x] Tests: fake-provider suite — grounded answer with citations, decline path,
      protected-category path, legal-question deflection, bulk-tool routing surfaced.

DONE MEANS: all behavior tests green + 3 real end-to-end asks against docker 19 + local
Ollama recorded to `docs/research/expert_runs_<date>/`.

DO NOT: answer from parametric knowledge when retrieval is empty (the whole point);
stream in v1 unless trivial (SSE optional later).

GATE: `uv run pytest tests/test_expert_ask.py -q` + real-run transcripts.

RETURN: ≤10 lines + transcript paths.

DEVIATIONS: conservative + log.

---

## EXP-4 — Evaluation regression set

TASK: Curated Q/A eval set + harness rewarding grounding and calibrated uncertainty
(Doc 8 §9).

INPUT: EXP-1..3; the 8-document master reference (source of verified answers).

CHECKLIST:
- [x] `apps/api/tests/expert_eval/eval_set.jsonl`: ≥40 items — {question, must_contain[],
      must_not_contain[], expect_decline: bool, expect_caution: bool, version_scope}.
      Coverage: doc-grounded facts (≥15), instance-grounded (≥5, fixture-driven),
      protected-category caution (≥5), should-decline no-source questions (≥5),
      version-differing answers (≥5), bulk-tool routing (≥5).
- [x] Harness `tests/test_expert_eval.py`: runs against fake provider deterministically in CI
      mode; `EXPERT_EVAL_LIVE=1` mode runs real model + reports score (not hard-fail) —
      scoring: grounding rate, citation presence, decline correctness, contamination
      (must_not_contain hits).
- [x] Baseline recorded: one live run's scores committed to
      `docs/research/expert_eval_baseline_<date>.md`; MASTER note: re-run on any change to
      chunking/retrieval/model.

DONE MEANS: CI-deterministic suite green; live baseline recorded.

DO NOT: overfit prompts to eval items (checker compares eval phrasing vs system prompt).

GATE: `uv run pytest tests/test_expert_eval.py -q` + baseline file.

RETURN: ≤10 lines + baseline scores.

DEVIATIONS: conservative + log.

---

## EXP-5 — Expert UX surfaces (requires UIX-3 shell)

TASK: The four surfaces: persistent chat panel, inline explain-this, error mode,
post-generation review companion (Doc 8 §10).

INPUT: UIX-3 shell (right slide-over mount + context provider), EXP-3 endpoint, wizard +
builder + designer + automations pages, COPY_GUIDE.

CHECKLIST:
- [x] Chat panel: slide-over on every connection page — thread UI, markdown rendering with
      citation chips (hover → source/breadcrumb/version), grounded/declined states styled per
      kit, suggested-tool deep links, conversation persists per connection
      (sessionStorage v1).
- [x] Context wiring: panel auto-sends ui_context (route, model under edit, draft summary)
      from the shell provider; visible "Using context: x_matter (draft)" chip the user can
      toggle off.
- [x] Explain-this affordances: small help icon next to field-type picker (builder), widget
      picker (designer), trigger picker (automations) → opens panel pre-filled with the
      contextual question ("Explain many2one vs many2many for this field on x_matter").
- [x] Error mode: paste-an-error box in the panel (and a "Diagnose" button on API error
      toasts) → routes through EXP-2's schema cross-check path; renders diagnosis +
      existence-check results distinctly.
- [x] Review companion: after a wizard draft completes, "Ask why" per model/automation row →
      pre-filled question with the draft context.
- [x] Playwright: panel open/ask/citation render (mocked API), explain-this from builder,
      error mode flow; vision-verify screenshots.

DONE MEANS: all four surfaces working against the live endpoint locally; Playwright green.

DO NOT: build a separate help site; block page interaction while the panel loads.

GATE: `pnpm test && pnpm test:e2e` (expert specs) + screenshots.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.
