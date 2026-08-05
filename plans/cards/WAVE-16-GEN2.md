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

GATE: `cd apps/api && uv run pytest -q -m "not integration"` 0 failed; fixture regression
suite green; one live background-job draft of the supermarket prompt recorded to
`docs/research/gen2_run_<date>.json` with `_llm_status.mode` ∈ {llm_full, llm_partial} (a
warm model MUST contribute; if hardware truly can't, log honest deviation + record the
pack_fallback run and the retry behavior). Update PROGRESS.md Wave 16 + STATE.md.
Commit only when user approves.

DO NOT: add hosted-LLM dependencies (still deferred); fake artifacts; rename existing API
fields (additive `_llm_status`); regress law-firm/first-supermarket fixtures.

RETURN per card: ≤8 lines + files changed.
