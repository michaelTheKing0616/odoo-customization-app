# Wave 15 — GEN: generation fidelity fixes (from 2026-08-05 supermarket draft review)

Evidence: a real draft for "A large mega Super Market with multiple branches" produced a
generic sales-order app with law-firm-flavored seed models (Event/Appointment,
Deposit/Retainer), NO branch model, a corrupt status selection with duplicate 'cancelled',
leaked internal scaffold in the response, and depth gates passed on seeded filler after an
Ollama timeout. Save that draft JSON as the regression fixture
`apps/api/tests/fixtures/draft_supermarket_2026-08-05.json` (get it from the user/journal if
not on disk). Deterministic fixes first — most need no LLM. Grep names below to locate code
(`ai_ollama.py`, `ai_pipeline.py`, rules/critique modules in `apps/api/app/`).

## GEN-1 — Selection + workflow merge correctness (data bugs)

- [x] Normalize every `selection` on merge: parse python-literal, coerce to tuples,
      DEDUPE by key (draft had 'cancelled' twice, mixed `[[…]]`/`(…)` syntax), re-serialize
      canonical. Reject unparsable with warning.
- [x] `ensure_terminal_workflow_statuses` (and any terminal-status merge) must APPEND to
      existing states — never replace `state_field.states` or `statusbar_visible` with
      terminals-only. Draft showed statusbar_visible="closed,on_hold,cancelled" hiding
      draft→confirmed→delivered.
- [x] Workflow completeness rule: `is_workflow` model with empty `transitions` gets a
      linear chain inferred from selection order (excluding terminals) + header buttons in
      the form view (the x_task pattern already does this — apply to all).
- [x] Tests: duplicate-key dedupe; terminal merge preserves flow states; supermarket
      fixture round-trips with valid selection + non-empty transitions.

## GEN-2 — Domain noun coverage gate (the branch miss)

- [x] New deterministic check `domain_noun_coverage`: extract candidate nouns from the user
      prompt (simple lemmatized noun list — no LLM needed; "branches" → branch). Each key
      noun must resolve to: a generated model, a reused Odoo model, or an explicit skip
      decision. Unresolved → completeness gap `noun_uncovered:<noun>` + draft warning
      "Prompt mentions 'branches' but no branch model or reuse decision exists."
- [x] Feed uncovered nouns into the critique pass as REQUIRED repairs (critique added
      x_sales_order but never noticed the missing branch).
- [x] Test: supermarket fixture flags `branch`; law-firm prompt does not false-positive.

## GEN-3 — Honest seed fallback + domain-adaptive seeds

- [x] Seeded models (`source: depth_seed`) must be domain-neutralized: strip law-firm
      strings ("Retainer", "Appointment", "Disbursement") — label from the entity role +
      prompt domain ("Store Event", "Order Task") or generic ("Related Event").
- [x] Depth gates must not be satisfied by seeds alone: compute metrics twice (with/without
      `depth_seed` models); if only-with passes, emit warning
      `depth met via generic seeds — regenerate recommended` and set `_depth.seeded=true`.
- [x] UI (wizard result panel): when `_depth.seeded` or field-deepen skipped (timeout),
      show a Callout: "The AI model timed out — generic placeholders filled the gaps.
      Regenerate for domain-specific results." + Regenerate button.
- [x] Timeout resilience: on Ollama timeout retry once at lower size/ctx before falling
      back to seeds (respect existing model ladder).
- [x] Tests: seed labels contain no law-firm lexicon; seeded-only depth sets flag.

## GEN-4 — Response hygiene + naming + automation quality

- [x] Strip internal scaffold from the returned draft: top-level `"json"` key (x_ex_*
      teaching blob + `anti_patterns`) must never ship in API responses. Named test.
- [x] `technical_name` + root menu derived from prompt when LLM omits them (slugify:
      "supermarket_branches", menu "Supermarket"); `custom_app` only as last resort +
      warning.
- [x] Critique/LLM-added automations REQUIRE a non-null `filter_domain` when trigger is
      `on_write` (draft's "Notify on order confirmation" fires on every write) — else
      downgrade to draft-warning and drop the automation.
- [x] `_critique.ready=false` with empty checklist/notes is contradictory — when critique
      finds nothing, ready=true; when not ready, notes must say why (surface in UI).
- [x] PCM refusal rendering: "Model: res" truncation — show full model name.
- [x] Tests: scaffold-strip, slug naming, on_write-domain rule, critique consistency.

## GEN-5 — Model-count adequacy (ambition + packs + honest floor)

- [x] Ambition auto-scale: prompt cues (mega/large/multiple branches/chain/franchise) bump
      to `comprehensive` via `classify_ambition_with_notes` + `_SCALE_RE`.
- [x] `retail_supermarket` domain pack (8 models incl. `x_branch`, store orders, transfers,
      promotions) + `reuse_stock` entries registered in `ai_domain_packs.py`.
- [x] Seed-free model floor: `depth_gaps` / `depth_checklist` count models excluding
      `source: depth_seed`; `_depth.seeded` when seeds pad but seed-free gaps remain.
- [x] Noun-driven expansion: `expand_uncovered_noun_models` adds branch (etc.) during
      `repair_draft_integrity`.
- [x] Tests: ambition scale, pack match, seed-free floor, noun expand branch.

## GEN-6 — Intuitive stock-model reuse (no manual selection needed)

Evidence: reuse plan only contained operator-selected basics (res.partner/users/company/
currency). A supermarket prompt should have auto-proposed product/purchase/inventory reuse.

- [x] Deterministic noun→stock-model inference map, applied to prompt nouns + generated
      entities BEFORE model generation: product→product.template/product.product,
      supplier/vendor→res.partner(+purchase.order if purchase installed),
      staff/employee→hr.employee, inventory/stock/warehouse→stock.warehouse/stock.quant
      (link-only), invoice/bill→account.move (link-only per PCM), sale/order→sale.order,
      expense→hr.expense, event→calendar.event. Extendable table, not hardcoded ifs.
- [x] Gate by connection reality: module installed → add inferred reuse decision
      (`source:"inferred"`, `confirmed:false`) + forbid_parallel (no x_product when
      product.template reused); module installable-not-installed → draft warning offering
      "Install <module> and reuse" vs "Generate custom x_ model"; not available → generate
      custom, note why.
- [x] PCM interplay: inferred reuse of tier-1 models is LINK-ONLY (m2o/o2m + additive x_
      fields where allowed) — decision records the boundary; never mutation logic.
- [x] Surface in the existing reuse/connect-points review UI: inferred rows shown with
      "Suggested — uses your installed Odoo Products app" copy + one-click confirm/reject;
      rejection regenerates a custom model. Never silently final.
- [x] Domain packs declare `reuse_stock` entries (retail pack from GEN-5: product.template,
      uom.uom, purchase.order) instead of generating parallel models when installed.
- [x] Tests: supermarket prompt + product installed → inferred product reuse +
      forbid_parallel blocks x_product; product absent → custom model + honest warning;
      tier-1 inference stays link-only (adversarial: "track invoices" → account.move
      link, no mutation automation).

GATE: `cd apps/api && uv run pytest -q -m "not integration"` 0 failed + one live staged
regeneration of the supermarket prompt recorded to `docs/research/gen_fix_run_<date>.json`
showing: branch coverage resolved, valid selections, no scaffold leak, honest seed flag.
Update PROGRESS.md Wave 15 + STATE.md. Commit only when user approves.

DO NOT: add new LLM calls beyond the existing retry ladder; touch UI beyond the two
callout/refusal items; rename existing API fields (additive only: `_depth.seeded`, gap ids).

RETURN per card: ≤8 lines + files changed.
