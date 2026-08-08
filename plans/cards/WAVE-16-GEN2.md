# Wave 16 — GEN2: LLM reliability + semantic fidelity (2026-08-05 supermarket draft #2)

Evidence: second supermarket draft. Wave 15 machinery worked (pack, ambition, reuse, honest
depth) BUT the LLM call failed entirely (top-level `"error": "Invalid JSON …"` leaked into
the payload) — the whole draft is pack+rules with zero AI content. Timeout banner shown even
though `_depth.seeded=false`. Save the draft as fixture
`apps/api/tests/fixtures/draft_supermarket2_2026-08-05.json` (ask user / journal).
Order: GEN2-1 first (reliability), then any.

## GEN2-1 — LLM reliability: warm model, background drafts, budget ladder

The recurring root cause of both bad drafts is Ollama timing out in a request-scoped call.

- [x] Warm-up: on API start + before each draft, ping Ollama with `keep_alive` (e.g. 30m)
      so the model stays resident; config `OLLAMA_KEEP_ALIVE`.
- [x] Drafts run as background jobs (reuse existing jobs infra): wizard POST returns job id;
      UI polls step progress ("Extracting entities… 2/6") and renders partial results.
      No HTTP-timeout cliff. Cancellable (subprocess-kill path from REM-14 A4).
- [x] Per-step budget ladder: each LLM step gets its own timeout; on breach retry ONCE with
      the next-smaller model (existing size ladder) and shorter prompt; only then fall back
      to pack/seed with an explicit per-step status.
- [x] Structured `_llm_status` replaces error leakage: `{mode: "llm_full"|"llm_partial"|
      "pack_fallback"|"seed_fallback", failed_steps: [...], reason: "timeout"|...}`.
      Top-level `"error"` key NEVER ships in a successful draft response. Named test.
- [x] Tests: fake slow provider → downshift retry → fallback status; error-key absence;
      job progress events emitted per step.

## GEN2-2 — Honest, actionable status UI

- [x] Banner logic keyed off `_llm_status.mode`, three distinct messages:
      llm_partial → "Some AI steps timed out; pack templates filled in. Retry AI enrichment?";
      pack_fallback → "Built from the retail template — the AI model was unavailable. Retry
      AI enrichment for tailored results."; seed_fallback → current placeholder copy.
      Never claim placeholders when `_depth.seeded=false`.
- [x] "Retry AI enrichment" button: background job that re-runs ONLY the failed LLM steps
      and merges into the existing draft (no full regen, no pack re-merge) — cheap + fast.
- [x] Test: banner variant per mode; enrichment merge preserves user edits.

## GEN2-3 — Semantic workflow transitions (replace naive linear chain)

- [x] Classify selection keys with a small lexicon: terminal_success (done, delivered,
      received, paid, passed), terminal_negative (cancelled, void, failed, expired),
      active (everything else, in listed order).
- [x] Transition synthesis: active states chain in order; every active state also →
      terminal_negative; last active → terminal_success. Terminals have NO outgoing edges.
      `statusbar_visible` = active + terminal_success (negatives hidden, standard Odoo).
- [x] Non-workflow models (`is_workflow: false`) must not carry `state_field`, status
      selection buttons, or statusbar (x_party_role bug) — strip + warn.
- [x] Tests: supermarket fixture transitions have no outgoing edges from
      delivered/received/cancelled; party-role stripped; law-firm fixture unchanged
      semantics (no regression).

## GEN2-4 — Domain vocabulary + seed anchoring

- [x] Global domain-lexicon scrub for ALL scaffold/seed/core-seed output (not only
      depth_seed): banned terms (retainer, trust, disbursement, conflict check, hearing,
      matter, multi-party) → neutral or domain terms via the active pack's vocabulary map
      (packs get optional `vocab: {deposit: "Supplier deposit", compliance: "Food safety
      check", …}`).
- [x] Domain prefix derivation: multi-word head noun kept whole ("Super Market" → "Store"
      or pack-provided label) — never truncate to the first word ("Super Event").
- [x] Seed anchoring: seeds attach to the draft's HUB model (most-referenced by m2o —
      here x_branch), not the last-generated workflow model; anchor m2o is optional
      (required=false). Test: x_event/x_task anchor to x_branch, not x_branch_transfer.

## GEN2-5 — Reuse plan precision + link_only propagation bug

- [x] BUG: pack `reuse_stock` entries with `link_only: true` (stock.warehouse,
      purchase.order) arrive in plan.decisions as `link_only: false` — propagate the flag
      through merge; PCM treats link_only reuse accordingly. Named test.
- [x] Catalog fuzzy matches (report.account.report_invoice_with_payments, res.role noise):
      require relevance to prompt/entity nouns + confidence threshold; below it → drop;
      above it → `source:"catalog", confirmed:false` shown ONLY in the review UI
      suggestions list, never auto-added to plan.decisions/depends. Test: supermarket
      prompt yields no report.*/res.role decisions.

## GEN2-6 — Generated access rules: manager/user split

- [x] Default matrix: `<module>_user` group (read/write/create, NO unlink) +
      `<module>_manager` group (all perms, implied_ids user); record both groups in the
      module + live-apply path. Root menu visible to user group.
- [x] Draft warning when a model would have been all-perms-for-everyone under the old rule.
- [x] Tests: generated access_rules contain no perm_unlink for the user group; manager
      group present; module install smoke still green.

## GEN2-7 — Presentation polish (menus, smart buttons, totals)

- [x] Menu grouping: >8 leaf menus → auto submenus by model category (Operations /
      Inventory / People / Finance / Other) using a pack-provided or heuristic mapping.
- [x] Smart-button dedupe: same (on_model, related_model) with different relation_field
      gets label suffixes ("Transfers out", "Transfers in") — no identical labels.
- [x] Line totals: when a line model has qty × price fields, add draft suggestion (Callout
      + one-click) to create the advanced equation-compute automation for subtotal/total
      (goes through the existing advanced-action confirm flow; never silent).

## GEN2-8 — Punch list from 2026-08-06 draft #3 (graded 8/10)

Evidence: third supermarket draft ("…branches around the world", 07:32). Save as fixture
`apps/api/tests/fixtures/draft_supermarket3_2026-08-06.json` (ask user / journal).

- [x] BUG (priority): a step result leaked into the response ROOT — top level contains
      `"model": "x_branch"` + its own fields/automations/smart_buttons/anti_patterns
      spliced before the real spec keys. Find the enrichment-merge that writes step output
      to the root instead of `models[]`; add a response-shape validator (allowlist of
      top-level keys) that runs before returning ANY draft + named test. Also fixes the
      smart-button count drift (header 15 vs _meta 19).
- [x] BUG: form archs ignore `state_field.statusbar_visible` — arch generator must emit
      the filtered list (x_store_order/x_promotion/x_branch_transfer forms still show
      `cancelled` in statusbar_visible). Test: arch statusbar matches state_field for
      every workflow model.
- [x] Form layout for enriched models: >10 fields in one group → split into semantic
      groups (Contact / Location / Details heuristics by field name) or notebook pages;
      drop redundant `x_<role>_name` char fields when a same-role m2o exists
      (x_manager_name vs x_manager_id).
- [x] `_llm_status` finalization: populate `completed_steps`, and clear/finalize
      step/step_label in the terminal payload (no frozen "Retrieving domain context" at
      step 0 in a finished draft). Test.
- [x] Small semantics: branch model gets `x_country_id` (res.country) when prompt implies
      multi-country ("around the world", "international", "global"); slug stop-words
      (around, the, with, world) dropped from technical_name; automation floor for
      comprehensive ambition prefers one real per-workflow automation (e.g. notify on
      order delivered) over the generic on_create filler seed.

## GEN2-9 — Punch list from 2026-08-06 16:12 draft #4 (graded 7.5/10; first llm_full run)

Fixture: pull from ai_draft_cache → `apps/api/tests/fixtures/draft_supermarket4_2026-08-06.json`.
Infra is clean (llm_full, no leaks, honest status). These are content-quality bugs:

- [x] BUG (trust): critique logs repairs it never applied ("added field x_branch.x_warehouse_id",
      "added automation Inventory Reorder Alert" — neither in draft). Repairs list must be
      derived from actual applied diffs, not the LLM's claim; unapplied suggestions go to a
      separate `suggestions` list. Test: every logged repair verifiably present in the spec.
      (`finalize_critique_block`; `repair_orphan_relations` keeps reuse-model FKs like stock.warehouse)
- [x] BUG: enrichment fields never reach views — x_branch has 17 model fields, form arch
      shows 6 (LLM defaults/timezone absent everywhere; order-line discount/tax/total too).
      Re-run arch generation (or arch-patch) after every field-adding pass; test asserts
      every non-o2m stored field appears in its model's form arch.
      (`sync_form_archs_to_models` in enrich + quality pass)
- [x] LLM field quality gate: reject placeholder selections (Option A/B pattern, single-letter
      keys), collapse near-duplicate field sprays (5× x_default_*_pct), drop fields duplicating
      an existing one by name-similarity + same ttype (x_default_currency_id vs x_currency_id).
      Warn per rejection. (`gate_llm_field_quality`)
- [x] BUG: vocab scrub produced "expense / expense" (lowercase dup of "Disbursement / expense")
      on model description + menu + action while the smart button kept the old label. Scrub must
      do whole-label replacement with casing preserved and apply to ALL surfaces (descriptions,
      menus, actions, smart buttons, view strings) atomically. Test on this fixture.
- [x] BUG: pack-provided view archs bypass the statusbar_visible fix (x_store_order/x_promotion/
      x_branch_transfer forms still show cancelled) — run pack archs through the same arch
      generator/patcher as generated models. Test: no workflow form arch shows negative
      terminals in statusbar_visible.
- [x] Critique consistency: `ready:false` + note "lacks inventory management" AFTER adding
      x_branch_inventory — notes must be re-evaluated post-repair (or dropped when the repair
      addressed them). Off-schema checklist ids (audit_trail, data_export) either map to real
      spec checks or are excluded.
- [x] Carry-over from GEN2-8 (not yet shipped in this run): form grouping + statusbar now fire
      via `sync_form_archs_to_models` on fixture #4; `x_country_id` still prompt-gated
      (global/international cues only — draft #4 prompt lacks them).

## GEN2-10 — Punch list from 2026-08-07 09:20 draft #5 (graded 8/10; enrichment-merge run)

Fixture: pull from ai_draft_cache → `apps/api/tests/fixtures/draft_supermarket5_2026-08-07.json`.
GEN2-9 verifiably landed (honest repairs+suggestions, fields-in-views, pack statusbar sync,
country, vocab). Remaining: critique output bypasses the scaffolding pipeline.

- [x] BUG (structural): critique-added models get NO views/actions/menus/access rules
      (x_branch_transfer_line, x_inventory_adjustment, x_compliance_check,
      x_event_registration — 14 models, 10 actions). After the critique pass, re-run the
      SAME scaffolding chain as pack/LLM models (views, action, menu placement, access user+
      manager, kanban-if-workflow). Harden completeness: `has_views` verifies EVERY model
      has ≥ list+form; new per-model checks for action/menu/access. Test on fixture.
- [x] BUG: line models must link their parent — `*_line` model requires m2o to the parent
      (x_branch_transfer_line lacks x_transfer_id; instead duplicates parent's from/to
      branch, date, country — drop those, add o2m back-ref + smart button on parent).
      Deterministic rule keyed on `_line` suffix / critique "line" intent.
- [x] BUG: normalizer must run post-critique — critique-added selections shipped as
      array-of-arrays (canonical = python-literal string); is_workflow models with x_status
      but no state_field get workflow synthesis (x_inventory_adjustment regression) +
      kanban + statusbar arch. Test: no non-string selections, no workflow model without
      state_field anywhere in final draft.
- [x] Noun-coverage stop-words: share the slug stop-word list + noun filter — no more
      `noun_uncovered:around` / `noun_uncovered:world` false positives. Test.
- [x] Lifecycle ordering: state classifier orders by lifecycle lexicon (planned/draft/new <
      open/active < closed/done) instead of trusting LLM listing order — fixes
      open→planned→closed on x_branch. Button labels from target state ("Close") not
      generic "Complete".
- [x] Critique automation quality: `on_create` + `object_write`-status combos are rewritten
      to mail_post/next_activity (auto-confirming every record contradicts its own draft
      state) or dropped with warning; names humanized (no snake_case); empty descriptions
      filled from name.
- [x] Polish: `_llm_status` step/step_label finalized on the enrichment path too (frozen at
      0 again); repair log says "merged (already present)" when the field pre-existed
      (x_currency_id); near-dup detector flags same-label different-ttype (x_address char vs
      x_address_id m2o both "Address"); enrichment merge must PRESERVE the existing draft's
      prompt-derived technical_name/display_name (became pack id "retail_supermarket").

## GEN2-11 — 10/10 finisher: production-shaped drafts (search, sequences, money, rules, arch polish)

Defect-free ≠ 10/10. These are the things every real Odoo app has that drafts still lack.

- [x] Search views: every model with an action gets a search arch — filters for status
      (per state), date ranges (this month/overdue where date fields exist), my-records
      (user m2o), plus group-by for every m2o to a draft model + status. Deterministic
      generation from fields; test: every actioned model has a search view with ≥2 filters.
- [x] Wire ir.sequence for real: x_code fields emit a sequence spec (prefix from model,
      padding 5) consumed by module export AND live apply (base_automation on_create or
      default via ir.sequence — use the existing CMP-1 verified mechanism). Help text
      "wire later" is replaced by the actual wiring. Test + sandbox smoke.
- [x] Money correctness: float amount fields with a sibling currency m2o become monetary
      widget pairs in archs (`widget="monetary"` + currency_field); status selections get
      `tracking=True` (chatter logs transitions); defaults: status = first active state,
      date fields named x_date/x_date_order default today where sensible. Tests.
- [x] Multi-company record rules: when models carry x_company_id, emit the standard
      company ir.rule (`['|',('x_company_id','=',False),('x_company_id','in',company_ids)]`)
      per model in module + live apply (CMP-11 templates). Test.
- [x] Arch polish: o2m lists move to notebook pages with meaningful columns (not just
      x_name — include qty/price/date/status when present); kanban cards show 2–3 key
      fields + status badge; smart buttons render in a button-box; widget hints
      (many2one_avatar_user for res.users m2o, date widgets). Golden-file tests on the
      supermarket fixture.

## GEN2-12 — Automated draft scorecard (encode the orchestrator's rubric; gate ≥9)

Make 10/10 measurable instead of orchestrator-vibes. Deterministic scorer, no LLM needed.

- [x] `draft_scorecard(spec) -> {score_0_10, dimensions, findings}` scoring five dimensions
      (weights): domain_fit (prompt nouns covered, no foreign-domain lexicon) 25%;
      structure (per-model views/action/menu/access/search, line-parent links, no orphans)
      25%; semantics (workflow transitions sane per lifecycle lexicon, no terminal
      outgoing edges, automations have domains/sane actions) 20%; ux (search filters,
      monetary pairing, notebook/o2m, kanban richness, menu grouping, no dup labels) 15%;
      hygiene (canonical selections, no placeholder options, no leaked internals, counts
      consistent, honest _llm_status) 15%. Every finding names the offending element.
- [x] Run automatically after every draft; result in `_scorecard` + wizard chip
      ("Draft quality: 9.2/10") with expandable findings list per COPY_GUIDE.
- [x] Regression: score all 5 supermarket fixtures + law-firm fixture — asserts monotonic
      floor (fixture 5 ≥ 8, post-GEN2-10/11 live regen ≥ 9). CI gate: live regen scoring
      < 9 fails the wave gate with findings printed.
- [x] Feed critique: scorecard findings become the critique pass's required-repairs input
      (closing the loop: score → repair → rescore; stop at ≥9 or 2 iterations).

## GEN2-13 — Draft #6 punch list + scorecard hardening (self-score 10.0, orchestrator 8.5)

Fixture: cache 08/08 → `apps/api/tests/fixtures/draft_supermarket6_2026-08-08.json`.
Meta-finding: the scorecard was Goodharted — every remaining defect sits in its blind
spots. Two thrusts: (A) fix defects, (B) make 10/10 un-gameable.

### A. Defects

- [x] A1 BUG: empty `<field />` tags in list archs (x_store_order_line, x_branch_transfer,
      x_inventory_count ×3, x_inventory_adjustment) — fix the generator path that leaves
      empty elements when fields are removed/moved.
- [x] A2 BUG: `company_id` (no x_ prefix) on custom models + record rules referencing it —
      live ir.model.fields apply requires x_ prefix. Use `x_company_id` everywhere on the
      live path; module export MAY keep company_id (document choice); record-rule domains
      follow the chosen name. Test both paths.
- [x] A3 BUG (security semantics): "Branch manager scope" rules attached to the USER group
      lock out non-manager staff (they manage no branch). Redesign: manager-scoping only
      as an OPT-IN suggestion, default rules = multi-company only; if branch scoping is
      offered, base it on membership (x_branch_id in user's allowed branches via a
      user⇄branch link), never manager-of-branch for all users. Named test: a plain user
      group member can read records.
- [x] A4 BUG: duplicate parent m2o — post-critique line rule added x_inventory_count_id
      beside existing x_count_id; smart button uses the dup. Near-dup detector must catch
      same-relation different-name; line rule reuses the existing parent field.
- [x] A5 BUG: _depth metrics/metrics_without_seeds swapped (15 vs 17 inverted) + _meta vs
      completeness count drift — single counting function, one source of truth, test.
- [x] A6 Polish: no menus for `*_line` models (reachable via parent form only); sequence
      prefixes from whole words (PROMO/, TRANSFER/, CHECK/ — wordlist truncation, not
      8-char cut); monetary pairing for x_staff_rate.x_rate; drop or justify domain-filler
      models (x_multi_party_link needs a pack-declared reason or is omitted; no sequences
      on link tables); remove filler search filters ("All", "Has name" on required fields).

### B. Scorecard hardening (un-gameable 10)

- [x] B1 XML validator as a scorecard input: parse every arch with lxml — no empty <field/>,
      every field name exists on the model, statusbar fields exist, buttons reference valid
      states. ANY validator error caps score at 6 and lists findings.
- [x] B2 Consistency validator: _meta/_completeness/_depth counts must agree; with/without
      seeds sanity (without ≤ with); duplicate same-relation m2o detector; live-path field
      naming (x_ prefix) check. Errors cap score at 7.
- [x] B3 Anti-gaming: search-view credit only for meaningful filters (status/date/m2o —
      "All" and required-field "Has name" score zero); menu credit deducts root-level line
      menus; sequence credit requires clean prefixes.
- [x] B4 Calibration set: score all 6 supermarket fixtures + law-firm; assert expected
      bands (fixture 1 ≤ 5, #4 ∈ [7,8.5], #6 ∈ [8,9] — NOT 10). CI fails if any known-bad
      fixture scores 10. A live regen must reach ≥9.5 with zero validator errors to claim
      the gate.
- [x] B5 Wizard: score chip shows validator status separately ("10.0 · all validators
      green") so a capped score explains itself; scorecard findings feed critique repairs
      (existing loop).

GATE: full API suite 0 failed; calibration bands green; one live regen ≥9.5 with zero
validator errors recorded to `docs/research/gen2_13_run_<date>.json`; sandbox install smoke
of the exported module (catches A1/A2 classes for real). No commit until user approves.

GATE: `cd apps/api && uv run pytest -q -m "not integration"` 0 failed; fixture regression
suite green; one live background-job draft of the supermarket prompt recorded to
`docs/research/gen2_run_<date>.json` with `_llm_status.mode` ∈ {llm_full, llm_partial} (a
warm model MUST contribute; if hardware truly can't, log honest deviation + record the
pack_fallback run and the retry behavior). Update PROGRESS.md Wave 16 + STATE.md.
Commit only when user approves.

DO NOT: add hosted-LLM dependencies (still deferred); fake artifacts; rename existing API
fields (additive `_llm_status`); regress law-firm/first-supermarket fixtures.

RETURN per card: ≤8 lines + files changed.
