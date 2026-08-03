# Wave 11 — REM: remediation of verified review gaps (2026-08-03 checker sweep)

Source: independent review by the orchestrator + six verification agents comparing every
card CHECKLIST against actual code. Independently confirmed gates: API 667 passed / 2
skipped; web lint 0 errors; vitest 78 passed; production build OK. Each card below cites the
exact confirmed gap. Same execution protocol as MASTER_PLAN (checkboxes, gates, Grok checker).
Order: REM-1 first (runtime bug), then REM-2 (security enforcement), then any order.

---

## REM-1 — Fix staged-pipeline NameError + finish AI-1/2 step wiring (Grok 4.5 card)

TASK: `run_staged_pipeline` crashes with NameError when reaching LLM steps; steps 3/5 miss
the AI-1/AI-2 routing that their cards claimed.

CONFIRMED GAPS: `apps/api/app/ai_pipeline.py` lines ~337/~415 pass `guardrail=guard` but
`guard` is never defined; `step3_relationships`/`step5_automations` never pass
`reasoning=True`, per-step temperatures, or schema-in-format; `FORMAT_SCHEMA_RELATIONSHIPS`
imported unused; no test executes the staged path far enough to catch any of this.

CHECKLIST:
- [x] Define/thread the guardrail string correctly through `run_staged_pipeline` (connection
      manifest when available, static fallback — per PCM-3 contract).
- [x] Steps 3 (relationships) + 5 (automations) + step 4 (workflow): reasoning model,
      `reasoning=True`, temps from `ai_prompt_constants.STEP_TEMPERATURES`,
      `append_prompt_blocks` anti-pattern DO-NOTs, schema-in-format where probed available.
- [x] New test: full staged run with fake provider that EXECUTES every step function
      (no mocking past the crash site) — would have caught the NameError; assert guardrail
      text present in step prompts.
- [x] Dedupe duplicate `_PACK_FACTORIES` entries (`ai_domain_packs.py`).
- [x] Mastery battery + full AI subset green.

GATE: `uv run pytest tests/ -q -k "ai"` + one real staged run (`AI_PIPELINE_MODE=staged`)
recorded to `docs/research/staged_run_fixed_<date>.json`.

---

## REM-2 — PCM-3/PCM-4 completion: refusal contract + wire enforcement (Grok 4.5 card)

TASK: The protected-modules guardrail is half-wired: refusal shape diverges from the card,
full_app drafts return empty refusals, and the enforcement functions exist but nothing calls
them.

CONFIRMED GAPS: refusal schema is `kind/model/reason` not the card's
`protected_module_conflict/requested_capability/protected_module/safe_alternative`;
`strip_protected_module_effects` runs only on component grain (`ai_ollama.py` ~511);
`check_automation_create` and `scrub_spec_for_protected_apply`
(`app/protected_enforcement.py`) have ZERO call sites in `routers/automations.py` /
`spec_apply_ui.py`; `ProtectedTierBadge.tsx` rendered nowhere; no `protected_tier_note` on
recipes; no `tests/test_protected_guardrail.py` adversarial suite; no wizard refusal panel;
no PROTECTED MODULES section in `MODEL_CREATION_RULES`; `pos_financial` regex deviates from
card (`(.*?_)?(stripe|…)` vs `.*_(stripe|…)` — reconcile, prefer card unless tested reason).

CHECKLIST:
- [x] Adopt the card's refusal object shape (extend `ProtectedModuleRefusal` with
      `requested_capability` + `safe_alternative`; keep `kind/model` as internals) — API
      schema + docs updated.
- [x] Deterministic strip + refusal generation runs on EVERY grain incl. full_app.
- [x] Wire `check_automation_create` into automations create/update; wire
      `scrub_spec_for_protected_apply` into spec apply (per-item skip results).
- [x] Render `ProtectedTierBadge` in metadata browser + builder/automations model pickers;
      wizard refusal panel (Callout: capability, why, safe alternative).
- [x] `protected_tier_note` on Power Ops recipes + exemption boundary docstring.
- [x] PROTECTED MODULES section in `MODEL_CREATION_RULES` (token-light).
- [x] `tests/test_protected_guardrail.py`: ≥6 adversarial prompts incl. mechanism-swap; plus
      API-level tier-1 mutation attempts in the adversarial suite (builder/apply/automations
      rejected; link-only succeeds).
- [x] Regenerate the guardrail transcript with the real shape
      (`docs/research/guardrail_run_<date>.json` — current one claims a shape the code
      doesn't produce).

GATE: new suites + existing PCM/power-ops tests + RPC smoke 19.

---

## REM-3 — AI-8 finish: wizard wiring, pre-generation connect points, live gates

TASK: AI-8's backend exists but the product flow is dead-wired and the live gates never ran.

CONFIRMED GAPS: `wizard/page.tsx` never sends/renders grain, `gallery_id`, or
`connect_points` (`api.ts` `draftModuleFromPrompt` omits them); connect-points review happens
post-draft, card requires BEFORE generation; no "Save as component" UI
(`generalize_spec_to_component_template` API-only); `SuggestTemplateButton` imported but not
rendered in wizard; no docker-19 live smoke or sandbox component-install test despite checked
boxes.

CHECKLIST:
- [x] `api.ts` + wizard: pass grain override + gallery selection; render detected-grain chip;
      connect-points review step gates generation (approve/edit → then full draft).
- [x] "Save as component" button (projects + wizard results) → gallery template flow.
- [x] Render `SuggestTemplateButton` in wizard results.
- [x] Live smoke: gallery seed "inspection checklist" applied onto project.task on docker 19
      (fields on form, sub-menu, smart button) — automated test.
- [x] Sandbox gate: exported component (host sale.order) installs with
      `SANDBOX_EXTRA_MODULES=sale`.

GATE: pnpm e2e wizard component flow + `uv run pytest tests/test_ai_components*.py -q` +
both live gates recorded.

---

## REM-4 — BLK live-smoke sweep + honesty fixes

TASK: BLK-2..7 shipped without the live RPC smokes their cards required; two behavior gaps.

CONFIRMED GAPS: only BLK-1/8/9 have live 19 tests; BLK-7's send test never leaves dry-run
(asserts `posts == []`); BLK-3 raises when Odoo's partner-merge wizard exists instead of
offering it; BLK-4 cron `method_direct_trigger` probe not recorded for 17/18; BLK-8 render
probe only on 19.

CHECKLIST:
- [x] Live docker-19 smokes: mass edit (BLK-2), dedupe merge with child relink (BLK-3),
      cron run-now (BLK-4), attachment scans on seeded fixtures (BLK-5), activities + portal
      grant (BLK-6), recompute probe + threaded send asserting per-record message_ids
      (BLK-7) — one integration module, `-m integration`.
- [x] BLK-7 execute-path unit test (fake RPC): message_post called per record.
- [x] BLK-3 partner path: when `base_partner_merge` present, offer it as an option (not an
      error); generic engine remains for other models.
- [x] Probe logs recorded 17/18: cron trigger + report render (capability matrix rows
      updated with results).

GATE: `uv run pytest -q -m integration -k "bulk or report_merge"` against docker 19 (+17/18
probes) — output attached.

---

## REM-5 — UIX kit honesty: real tests, designer migration, legacy purge

TASK: UIX-2/4b claims exceed reality: the kit "test" is a name list, the designer never
migrated, and the legacy purge isn't done.

CONFIRMED GAPS: `src/components/ui/kit.test.ts` asserts a string array only; `CodeBlock` has
no syntax highlighting; `ConfirmDialogV2` lacks the danger-variant UI (red header +
consequences list); `designer/page.tsx` retains ~103 legacy `--odoo-primary`/hex usages;
landing lacks real product screenshots + has multiple competing CTAs; card checkboxes in
WAVE-6 were never flipped.

CHECKLIST:
- [x] Replace kit.test.ts with per-component Vitest (render + variant + interaction per the
      UIX-2 contracts; DataTable sort/selection/virtualization; BulkResultTable filters;
      Callout actions; Toast lifecycle).
- [x] CodeBlock: real highlighting (Shiki or refractor) + copy + wrap toggle.
- [x] ConfirmDialogV2 danger variant per card (red header, consequences list, snapshot line).
- [x] Designer page migrated onto kit tokens/components; repo-wide legacy grep
      (`--odoo-primary|#714B67|mint hexes list`) returns empty outside Odoo-preview surfaces.
- [x] Landing: real screenshots (capture from running app), single primary CTA.
- [x] Retro-flip WAVE-6-UIX.md checkboxes to match verified reality (item-by-item, honest).

GATE: pnpm lint/test (new suites) + build + legacy grep output empty.

---

## REM-6 — UIX-6 overlay editor: implement the six v1 operations (Grok 4.5 card)

TASK: The overlay currently only selects and shows a notice — the card's core DONE MEANS
(six edit operations → inherit save → reload loop) is unimplemented.

CONFIRMED GAPS: `OverlayEditor.tsx` + designer wiring stop at select→notice
(`designer/page.tsx` ~3526); no move/hide/relabel/add-field/set-widget/group-label ops; no
overlay Playwright loop; no vision artifacts. Reality-check + postMessage bridge + resolve
endpoint DO exist (`preview_proxy.py`, `test_preview_proxy_reality.py`,
`views.resolve-field`).

CHECKLIST:
- [x] Six operations wired from selection → inspector actions → inherit-view save via
      existing endpoints (snapshot-first), frame reload on save.
- [x] Ambiguity picker for multi-match nodes; xpath code peek on every save.
- [x] Honesty panel listing non-v1 capabilities → "open View Designer".
- [x] Playwright loop on harness (`e2e/overlay-editor.spec.ts`) + vision artifact
      `docs/vision-verify/overlay-editor.png`; live docker loop gated `ODOO_E2E=1`.

GATE: e2e live loop + screenshots; STOP-and-report if the reality check regresses.

---

## REM-7 — UIX-7 website editor completion

TASK: Website editing shipped as text-only; card requires image replace, reorder, publish,
nav entry, byte-identical preservation proof.

CONFIRMED GAPS: `website/page.tsx` text inputs only; not registered in `lib/nav.ts`;
round-trip test asserts substring (not byte-identical locked blocks); no live e2e.

CHECKLIST:
- [x] Image replace (upload → ir.attachment → src swap), link/button href+label, block
      reorder within section, publish/unpublish toggle.
- [x] Nav entry (Build or dedicated group) with website-module gating.
- [x] Locked-block byte-identical round-trip assertion (full arch diff).
- [x] Live smoke on docker 19 + website: edit paragraph + replace image + publish toggle
      (`test_website_live.py`, env-gated `ODOO_E2E=1`).

GATE: pytest website suite + live smoke + e2e. **SHIPPED 2026-08-03**

---

## REM-8 — TIER-6 designer completion (grid + missing attrs)

TASK: EE view designers shipped without the Grid panel and with attrs missing vs card.

CONFIRMED GAPS: no `grid` view type in designer; map/gantt panels omit documented attrs the
arch layer supports (`routing`, `default_scale`, dependency arrows, marker popup fields,
grid adjustment/measure) — `view_arch.py` supports them, UI never emits.

CHECKLIST:
- [x] Grid panel (row/col/adjustment/measure) in designer, edition-gated.
- [x] Map: routing toggle + marker popup field list; Gantt: default_scale + progress +
      dependency attr per major; Cohort: mode option — all emitting through existing arch
      helpers with golden fixtures extended.
- [x] Designer e2e per panel (emit + save path, gated visibility) — `/e2e/designer-ee`.

GATE: golden suite + designer e2e + conditional EE live (env-gated, honest skip). **SHIPPED 2026-08-03**

---

## REM-9 — EXP/PROD polish: artifacts, job timeouts, real drift check

TASK: Expert and hardening waves are code-complete but claim-incomplete.

CONFIRMED GAPS: no `docs/research/expert_runs_*` live transcripts; no
`docs/reference/MASTER_REFERENCE.md` (project-docs ingestion source — NEEDS THE USER to
provide the 8-document master text); EXP-4 baseline is CI-fake not live; EXP-5 e2e lacks
explain-this/error-mode + vision shots; `JOB_TIMEOUTS` logged but not enforced, cancel test
is a noop; alembic "drift" test only checks head/env import.

CHECKLIST:
- [x] 3 real /expert/ask runs vs docker 19 + Ollama → `docs/research/expert_runs_<date>/`
      (fixture transcripts + `EXPERT_RUNS_LIVE=1` recorder).
- [x] Ingest `docs/reference/MASTER_REFERENCE.md` — `test_master_reference_ingest.py`.
- [x] EXP-5 e2e: explain-this from builder, error-diagnose flow; vision screenshots.
- [x] Enforce job timeouts (kill + status=timeout) + cancel + timeout tests.
- [x] Real drift check: autogenerate empty diff + `d4e5f6a7b8c9` FK repair migration.
- [x] PROD-1 compose boot smoke — `LAUNCH_COMPOSE_SMOKE=1 ./scripts/launch_smoke.sh`.

GATE: pytest new suites + artifacts on disk. **SHIPPED 2026-08-03**

---

## REM-10 — MON completion: real gates, slot billing, authz breadth (Grok 4.5 card)

TASK: Billing/auth core is real, but key protections are stubs and slot add-ons unbuilt.

CONFIRMED GAPS: `test_operate_bulk_not_slot_gated` only GETs `/health` — proves nothing;
extra-slot Stripe/Paystack wiring absent (card `[~]`); no webhook signature-fail test, no
Paystack webhook suite; role matrix tested only for one case; pricing page hand-copies
`DISPLAY_FEATURES` + `MONTHLY_USD` (card requires registry-driven); trial/upgrade e2e
deferred; OAuth [SKIPPED] awaiting user approval; live processor smokes need user test keys.

CHECKLIST:
- [x] Real operate-not-gated test: workspace at slot limit → bulk suite, health check,
      expert, snapshots endpoints all 200; build surfaces 403 with feature key.
- [x] Extra-slot add-ons: Stripe subscription-item quantity + Paystack equivalent + admin
      grant path + UI in upgrade sheet.
- [x] Webhook hardening tests: Stripe signature-fail, Paystack HMAC-fail, replay dedupe,
      out-of-order events.
- [x] Role-matrix test suite per router family (viewer/builder/admin/owner × read/mutate/
      destructive/billing).
- [x] Pricing page rows + prices rendered from the entitlements/plans API only (delete
      hand-copied tables).
- [x] Trial/upgrade/downgrade e2e specs.
- [ ] USER DECISIONS RESOLVED 2026-08-03: OAuth scheduled as REM-13 (not part of this card);
      live Stripe/Paystack checkout smokes DEFERRED until the user provides test keys — see
      DEFERRALS.md entry 5. Everything else in this card proceeds without keys (fake-webhook
      suites + test-mode bootstrap scripts stay in scope).

GATE: pytest billing/authz suites + e2e (live checkout smoke excluded per deferral).

---

## REM-13 — OAuth login: Google + GitHub (scheduled by user 2026-08-03)

TASK: Implement the OAuth sign-in that MON-1 stubbed (`OAUTH_PROVIDERS` env existed, no
implementation).

INPUT: MON-1 accounts stack (`account_models.py`, `account_service.py`, session issuance),
authlib (already the approved dep in the MON-1 card), login/signup pages, settings.

CHECKLIST:
- [ ] `authlib` integration: Google + GitHub authorization-code flow behind
      `OAUTH_PROVIDERS=google,github` (off default); redirect URIs env-configured; state +
      PKCE where supported; no client secrets in repo (env only, documented in
      `.env.example` placeholders).
- [ ] Account linking rules: OAuth email matches existing verified account → link provider
      identity (new `oauth_identities` table: provider, subject, user_id — Alembic
      migration); no match → create account with email_verified=true (provider-verified);
      NEVER auto-link to an UNVERIFIED existing email (account-takeover guard — named test).
- [ ] Sessions issued through the same server-side session path as password login (cookie,
      rotation); 2FA: if the linked account has TOTP enforced, OAuth login still passes the
      TOTP step.
- [ ] UI: provider buttons on login + signup (kit styling, COPY_GUIDE labels), settings page
      shows linked identities with unlink (blocked if it would leave no login method).
- [ ] Tests: mocked-provider flow (authlib test transport) — new-user create, verified link,
      unverified-collision refusal, unlink guard, TOTP-after-OAuth; adversarial: forged
      state rejected.

DONE MEANS: full mocked-provider e2e green for both providers; providers-off default leaves
existing auth untouched (regression suite proves); no secrets committed.

DO NOT: implement additional providers; roll custom OAuth (authlib only); weaken the
unverified-email link guard for convenience.

GATE: `uv run pytest tests/test_oauth.py tests/test_accounts*.py tests/test_adversarial_security.py -q` + web e2e login specs.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## REM-11 — CMP-9 widget module: bundle the scanner library

TASK: The exported barcode widget relies on the browser `BarcodeDetector` API only (poor
coverage, esp. Safari/Firefox) — card required our OSS lib bundled locally, no CDN.

CONFIRMED GAP: `packages/module-generator/src/module_generator/barcode_widget.py` emits
BarcodeDetector-only code; README says "if you bundle" instead of bundling; zxing attribution
missing from module README.

CHECKLIST:
- [x] Bundle a minified zxing (or equivalent OSS) build into the generated module's
      `static/lib/` with manifest asset wiring; BarcodeDetector used as fast path when
      available, bundled lib as fallback.
- [x] Apache-2.0 attribution + our license headers in module README.
- [x] Sandbox install + form render smoke (asset loads, no console error) re-run.

GATE: sandbox gate + zip content assertions.

---

## REM-12 — UIX evidence sweep: vision-verify + UIX-5 audit tables

TASK: Produce the visual and audit evidence the UIX cards required but never generated.

CONFIRMED GAPS: `docs/vision-verify/` holds only designer shots; no tokens/kit/shell/page
screenshots (light+dark); UIX-5 audit tables (strings, empty/loading/error state matrix,
gating-template instances) never produced; UIX-1 semantic ramps 3 steps vs 5 specified.

CHECKLIST:
- [x] Extend semantic ramps to 5 steps with AA contrast table comment.
- [x] Playwright screenshot sweep: tokens page, kit page, shell, 8 primary pages —
      light + dark → docs/vision-verify/; vision-verify pass per skill.
- [x] UIX-5 audit tables written to `docs/UIX_AUDIT.md` (page × state matrix complete;
      gating instances enumerated; copy sweep confirmations).
- [x] Retro-flip remaining WAVE-6 checkboxes to verified truth.

GATE: artifacts on disk + axe re-run clean.

---

## REM-14 — Punch list from 2026-08-03 re-verification + one-pass commit (Composer card)

TASK: The orchestrator + three verifiers re-checked REM-1..12 against the working tree.
Verdict: every group PARTIAL. Fix the confirmed residual gaps below, produce the missing
live evidence (Docker Desktop is now running; app-db healthy on :5433), then commit ALL
uncommitted work in ONE commit. User has explicitly approved the commit.

Environment notes: start Odoo stacks with `docker compose -p odoo-custom-dev -f
docker/docker-compose.yml up -d <services>` (19 always; 17+18 for the probe items). Check
`ollama list` before live LLM runs; if the model can't run, log the deviation — do NOT fake
artifacts (fixture-mode files are what caused this card).

### A. Code fixes (do first — one failing test in the suite right now)

- [x] A1 `apps/api/app/ai_pipeline.py`: thread guardrail into `step2_fields` (add
      `guardrail: str = ""` kwarg, wrap system via `append_prompt_blocks(...,
      guardrail=guardrail)`, pass `guardrail=guard` at the call site ~line 379). This fixes
      the currently-failing `tests/test_ai_staged_pipeline.py::test_staged_pipeline_runs_all_steps_with_guardrail`.
- [x] A2 Steps 4 (workflow sample in `ai_workflow.py`) + 5 (`step5_automations`): pass
      schema-in-format (`format_schema=`) like steps 2/3 — define minimal JSON schemas if
      missing.
- [x] A3 `routers/automations.py` `update_automation`: run `check_automation_create`-style
      PCM check on the updated definition (not just create). Named test: updating an
      automation to target a tier-1 model returns 422 refusal.
- [x] A4 Job cancel must actually kill the sandbox subprocess: track pid, terminate→kill on
      cancel. Test proves a genuinely running subprocess dies (not a noop id).
- [x] A5 `tests/test_entitlements.py::test_operate_bulk_not_slot_gated`: at project limit,
      assert bulk AND expert endpoints return 200 (not just "not a slot feature_key").
- [x] A6 `tests/test_role_matrix.py`: extend to per-router-family breadth — projects,
      automations, power-ops/bulk, expert, admin, billing, connections, invitations
      (viewer/builder/admin/owner each).
- [x] A7 Slot add-on billing: buy extra slots as a recurring Stripe subscription item
      (quantity), not one-time Checkout line items — or, if deliberately one-time, rename the
      SKU/copy to say so and log the deviation in MEMORY.md.
- [x] A8 `apps/web/src/components/ui/kit.test.tsx`: add a DataTable virtualization case
      (large row count → only a window rendered).
- [x] A9 `apps/api/tests/test_website_live.py`: extend beyond publish-toggle to the card
      scope — paragraph text edit + image replace + publish, verified via RPC read-back.
- [x] A10 `apps/web/e2e/overlay-editor.spec.ts` `ODOO_E2E` describe: replace the
      visible-only stub with a real loop (select element → preview → apply → verify arch
      changed → restore snapshot).
- [x] A11 EE designer e2e harness: make map "marker fields" an editable list (parity with
      real designer) and add gantt progress control to the harness + spec.

### B. Live evidence (Docker is up — no more "written but never run")

- [x] B1 Bring up odoo19 (+ odoo17, odoo18 for B3) via the dev compose project.
- [x] B2 Real staged run: `AI_PIPELINE_MODE=staged` against local Ollama, full trace
      step0→step6, saved to `docs/research/staged_run_fixed_<date>.json` (replace the
      timed-out artifact; raise client timeout if needed).
- [x] B3 BLK probes on 17 + 18 → real results into `docs/research/blk_probe_matrix_<date>.json`
      + capability matrix updated; run `tests/test_bulk_suite_blk_live.py` and save the GATE
      log under `docs/research/`. BLK-6 live: real (non-dry-run) activities+portal on the
      sandbox DB; BLK-7 live: assert per-record `message_ids` growth, not `search_count`.
- [x] B4 Expert: real live transcripts (not `"mode": "fixture"`) for the REM-9 scenario set
      → `docs/research/expert_runs_<date>/`; run the live eval baseline (`EXPERT_EVAL_LIVE=1`)
      and record scores.
- [~] B5 Run `tests/test_ai_components_live.py` (docker 19 incl. sandbox + `sale`) and save
      output under `docs/research/` — `test_inspection_checklist_live_odoo19` skipped (project
      module not installed on docker-19 instance); unit + sandbox barcode paths green.
- [x] B6 Run the barcode sandbox install smoke (`test_barcode_widget_sandbox_live.py`) and
      save output.
- [x] B7 Playwright: run overlay-editor, website-editor, designer-ee-panels specs to green;
      produce `docs/vision-verify/overlay-editor.png` + `docs/vision-verify/website-editor.png`;
      clear stale `test-results` failure residue.
- [~] B8 Run the compose deploy smoke (`LAUNCH_COMPOSE_SMOKE` path in
      `scripts/launch_smoke.sh`) once and record the result — health OK; deploy API
      `/api/billing/plans` returns 404 (pre-existing deploy routing gap); log in MEMORY.md.

### C. Bookkeeping + the one-pass commit (user-approved)

- [x] C1 Full gates green: `cd apps/api && uv run pytest -q -m "not integration"` (0 failed)
      + `cd apps/web && pnpm lint && pnpm test && pnpm build`.
- [x] C2 Update PROGRESS.md Wave 11 lines + card checklists to verified truth (flip REM-14
      boxes only when actually done; anything not done stays `[ ]` with one honest line why).
- [x] C3 STATE.md retro (≤15 lines) + MEMORY.md entry for any deviation taken.
- [x] C4 `git add -A` and ONE commit of all uncommitted work. Message: summary line
      "Wave 11 REM: remediation + REM-14 punch list (verified)" + body listing wave-level
      changes. Do NOT push.

DONE MEANS: 0 failed tests in both suites; every B artifact is real (traceable command +
output, no fixture-mode stand-ins) or has an honest logged deviation; single commit created.

DO NOT: fake artifacts; split into multiple commits; push; touch Wave 12/13 scope; amend
existing commits.

GATE: C1 output pasted into the RETURN summary.

RETURN: ≤15 lines — per-section (A/B/C) done counts, any deviations, the commit hash.
