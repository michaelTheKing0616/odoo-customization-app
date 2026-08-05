# PROGRESS — single source of truth for card status

Legend: `[ ]` not started · `[~]` in progress · `[x]` done (gate + checker passed) ·
`[SKIPPED]` user-approved skip (reason required). Update this file AND the card's own
CHECKLIST. Claiming done without both updated = failed card.

## Wave 0 — SAFE (repo baseline)
- [x] SAFE-1 Initial git commit baseline + .gitignore verification
- [x] SAFE-2 Close STATE.md law-firm follow-up (re-run + verify)
- [x] SAFE-2b Fix x_matter_party workflow/kanban re-promotion (SAFE-2 follow-up)
- [x] SAFE-2c Fix law-firm generation-gap regression (bill/compliance/deposit scaffold)

## Wave 1 — PCM (Protected Core Modules)
- [x] PCM-1 protected_modules.py classification engine
- [x] PCM-2 Path A source retrieval + Path B live merge + per-connection manifest
- [x] PCM-3 Guardrail prompt injection + structured refusal end-to-end — REM-2 complete 2026-08-03
- [x] PCM-4 Enforcement in builder/apply/automations/power-ops + UI badges + adversarial tests — REM-2 complete 2026-08-03

## Wave 2 — AI (prompt engineering + pipeline)
- [x] AI-1 Thinking mode + Qwen3 size ladder in LLMProvider
- [x] AI-2 Per-step temperature + prompt audit + anti-pattern blocks
- [x] AI-3 Self-consistency (N-sample vote/merge) behind AI_SELF_CONSISTENCY
- [x] AI-4 Dedicated workflow-states/transitions pipeline pass
- [x] AI-5 Five new domain packs (restaurant, real_estate, hotel, subscription, project)
- [x] AI-6 Draft→pack generalizer (fold customer projects into library, opt-in)
- [x] AI-7 Reverse-import partial-fidelity contract (custom_code_blocks)
- [x] AI-8 Component-grain generation (extensions for Odoo + custom apps, connect points, gallery) — added 2026-08-03
- [x] AI-9 Overlap/already-exists check before generation (4 sources, options panel) — 2026-08-03

## Wave 3 — BLK (bulk & workflow suite)
- [x] BLK-1 Generic bulk state transition + button discovery engine + BulkResult schema
- [x] BLK-2 Universal mass field edit
- [x] BLK-3 Generic duplicate detection & merge (any model, FK relink)
- [x] BLK-4 Cron manager (plain language, run now, create/edit)
- [x] BLK-5 Attachment housekeeping (orphans + checksum duplicates)
- [x] BLK-6 Bulk activities, security provisioning, portal access
- [x] BLK-7 Stored-computed recompute (touch technique) + threaded bulk send
- [x] BLK-8 Cross-report-type merged PDF
- [x] BLK-9 Inventory ID Generator port (all six AppleScript audit fixes)

## Wave 4 — TIER (hosting & edition coverage)
- [x] TIER-1 Capability matrix (hosting x edition x modules) replacing heuristics
- [x] TIER-2 Gating UX: three honest options + per-tier deployment paths + dry-run
- [x] TIER-3 Apps Store packaging assist + Odoo.sh migration assist
- [x] TIER-4 Post-upgrade health check
- [x] TIER-5 Enterprise feature drivers (studio approvals RPC, EE views, EE playbook actions)

## Wave 5 — EXP (Odoo Expert)
- [x] EXP-1 Docs ingestion + chunking + version-tagged embedding store
- [x] EXP-2 Live-instance grounding context assembly
- [x] EXP-3 /api/expert/ask generation endpoint (ground-or-decline, citations)
- [x] EXP-4 Evaluation regression set + harness
- [x] EXP-5 Expert UX surfaces (chat panel, explain-this, error mode, review companion)

## Wave 6 — UIX (UI/UX revamp)
- [x] UIX-1 Design tokens + typography + dark mode foundation
- [x] UIX-2 Component kit (20 components) + icon mapping — Input/Select/DataTable/DiffView/BulkResultTable/etc. + `/e2e/kit` expanded
- [x] UIX-3 App shell: sidebar nav, top bar, command palette, Expert panel mount
- [x] UIX-4a Page migrations: landing, connect, overview, Draft Studio
- [x] UIX-4b Page migrations: designer, projects diff, automations, access
- [x] UIX-4c Page migrations: power-ops/bulk, journal, remaining pages (menus, config, reports, modulespec, id-generator, builder, approvals, cron-manager, housekeeping; legacy hex purge on UIX-4c surfaces)
- [x] UIX-5 Copy guide application pass + iconography audit

## Wave 7 — CMP (compendium completions)
- [x] CMP-1 Manifest ordering tests + xpath move/$0 + ir.sequence verification
- [x] CMP-2 Widget coverage + sample data + conditional attrs expression builder
- [x] CMP-3 Niche widget palette + trigger capability checks + live palette extraction
- [x] CMP-4 Visual QWeb report designer
- [x] CMP-5 Approval rules (button gating; studio.approval.rule mode via TIER-5)
- [x] CMP-6 Image pipeline (multi-resolution variants + bulk image import)
- [x] CMP-7 Property fields full parity (probe-verified per major)
- [x] CMP-8 Connect-to-Invoicing safe pattern (live m2m + count field + merge-into-spec + draft RPC)
- [x] CMP-9 Generic barcode scanning (in-app @zxing/browser + exported OWL widget + tier gate)
- [x] CMP-10 Standalone approval processes (multi-level chains; EE approvals RPC mode)
- [x] CMP-11 Multi-company patterns + i18n depth + Documents integration

## Wave 7b — ADV (advanced designers & live editing)
- [x] TIER-6 Deep Gantt/Grid/Map/Cohort config designers — REM-8: grid panel EE-gated, map routing, gantt default_scale/dependency_field, e2e harness
- [x] UIX-6 Live overlay editor on the proxied Odoo frame — REM-6 shipped six ops + e2e harness; live docker loop via `ODOO_E2E=1` + `ODOO_E2E_CONNECTION_ID` (see `e2e/overlay-editor.spec.ts`)
- [x] UIX-7 Website page editing — REM-7: image upload, reorder, publish, nav gating, byte-identical locked round-trip

## Wave 8 — PROD (production hardening)
- [x] PROD-1 API Dockerfile + compose deploy profile
- [x] PROD-2 DB migration strategy + export README audit
- [x] PROD-3 Queue decision (arq vs in-process policy) + job hardening

## Wave 9 — MON (monetization)
- [x] MON-1 Auth accounts: users/workspaces/roles/sessions/2FA
- [x] MON-2 Billing: Stripe + Paystack, entitlements, feature gating
- [x] MON-3 Admin console + internal-plan bootstrap (env-seeded admin)
- [x] MON-4 Pricing page + upgrade/trial UX

## Wave 10 — LAUNCH (post-monetization)
- [x] LAUNCH-1 Deploy smoke script + DEPLOY.md operator checklist
- [x] LAUNCH-2 Operator runbook (`docs/OPERATOR.md`)

## Wave 11 — REM (remediation from 2026-08-03 orchestrator review; cards in WAVE-11-REM.md)
Re-verified 2026-08-03 (orchestrator + 3 checkers); REM-14 closed residual gaps 2026-08-03.
- [x] REM-1 Fix staged-pipeline NameError + AI-1/2 step wiring — guardrail + schema-in-format + live staged artifact (`docs/research/staged_run_fixed_2026-08-03.json`)
- [x] REM-2 PCM-3/PCM-4 completion — update_automation PCM check + tier-1 422 test
- [x] REM-3 AI-8 finish — wizard/sandbox unit green; docker init-db installs sale+project+crm for live apply
- [x] REM-4 BLK live-smoke sweep — 7/7 live on 19; 17/18/19 probes recorded in `blk_probe_matrix_2026-08-03.json`
- [x] REM-5 UIX kit honesty — DataTable virtualization test added
- [x] REM-6 UIX-6 overlay editor — API live loop + overlay-editor.png
- [x] REM-7 UIX-7 website editor — extended live smoke + website-editor.png
- [x] REM-8 TIER-6 designer — map marker fields + gantt progress harness/e2e
- [x] REM-9 EXP/PROD polish — live expert runs/eval; sandbox subprocess kill on cancel
- [x] REM-10 MON completion — slot-limit operate test hardened; role matrix breadth; Stripe slots already subscription mode
- [x] REM-11 CMP-9 widget module — sandbox barcode live smoke green
- [x] REM-12 UIX evidence sweep — overlay/website PNGs added via Playwright
- [x] REM-13 OAuth login: Google + GitHub (authlib, linking rules, TOTP-after-OAuth, UI)
- [x] REM-14 Punch list from re-verification + live evidence + one-pass commit (user-approved)

## Wave 12 — TRUST (production-trust hardening; cards in WAVE-12-TRUST.md; AFTER Wave 11)
- [x] TRUST-1 Read-only connections by default + least-privilege onboarding — write_mode migration, RPC choke point, unlock API, badge/panel, docs
- [x] TRUST-2 SafetyGate choke point + risk-class registry + route meta-test + kill switch — core shipped 2026-08-03; bulk receipt on transitions/run only; admin UI deferred
- [x] TRUST-3 Blast-radius limits — sample-first + caps + batched executor + anomaly auto-pause on transitions/run; BulkResultTable continue/abort UI
- [x] TRUST-4 Data-loss proofing (field delete core) — deprecate default, hard-delete CSV pre-export, artifact download, PCM gate
- [x] TRUST-5 Dirty-instance & chaos validation — dirty gate script, RPC resilience, mutation lock, SAFETY.md limits
- [x] TRUST-6 Runtime coverage floor + settings-matrix execution policy — CI coverage gate, matrix/error-path tests, coverage-gate skill
- [x] TRUST-7 App-side security: IDOR sweep, role matrix, supply chain, app-DB restore — core 2026-08-03
- [x] TRUST-8 SAFETY.md trust contract + production readiness checklist gate — core 2026-08-03
- [x] TRUST-9 Design-partner beta protocol + GA evidence criteria — core 2026-08-03

## Wave 14 — UIF (UI friendliness; cards in WAVE-14-UIF.md; can run before Wave 12)
- [x] UIF-1 Dedupe instance identity badges (3× on Overview) + raw-error sweep + double-render bugs (Bulk Suite ×2, Housekeeping ×2, sidebar dual-active) — 2026-08-05
- [x] UIF-2 Sidebar IA: collapsible groups, unique icons, Operations hub, Developer captions — 2026-08-05
- [x] UIF-3 Overview declutter: tabs + first-run start-here card — 2026-08-05
- [x] UIF-4 Copy/density pass: subtitles, jargon sweep, Advanced disclosures, screenshot re-run — 2026-08-05 (Playwright sweep: run locally)

## Wave 15 — GEN (generation fidelity; cards in WAVE-15-GEN.md; from 2026-08-05 supermarket draft review)
- [x] GEN-1 Selection dedupe/normalize + terminal-merge preserves flow + transitions inferred
- [x] GEN-2 Domain noun coverage gate (missing-branch class of miss) + critique required repairs
- [x] GEN-3 Honest seed fallback: domain-neutral seeds, seeded-depth flag + UI callout, timeout retry
- [x] GEN-4 Response hygiene: scaffold strip, prompt-derived naming, on_write domain rule, critique consistency, PCM label
- [x] GEN-5 Model-count adequacy: ambition auto-scale from prompt cues, retail_supermarket pack, seed-free floor, noun-driven expansion
- [x] GEN-6 Intuitive stock-model reuse: noun→model inference gated by installed modules, PCM link-only, confirm-in-UI, pack reuse_stock entries

## Wave 16 — GEN2 (LLM reliability + semantic fidelity; cards in WAVE-16-GEN2.md; from 2026-08-05 draft #2)
- [x] GEN2-1 LLM reliability: warm keep_alive, background draft jobs + step progress, budget ladder, _llm_status (no error leak)
- [x] GEN2-2 Honest status UI: banner per _llm_status.mode + retry-failed-steps-only enrichment
- [x] GEN2-3 Semantic transitions (terminals branch, not chain) + strip state from non-workflow models
- [x] GEN2-4 Domain vocab scrub (law-firm lexicon ban + pack vocab) + hub-anchored optional seeds + prefix fix
- [x] GEN2-5 Reuse precision: link_only propagation bug + catalog match threshold (no report.*/res.role noise)
- [x] GEN2-6 Access rules manager/user split (no unlink for user group)
- [x] GEN2-7 Menu auto-grouping, smart-button label dedupe, line-total compute suggestion
- [x] Bonus: AI draft JSON auto-cache (`ai_draft_cache` table + GET list/restore + wizard saved drafts)

## Wave 13 — DEV (developer code path; cards in WAVE-13-DEV.md; AFTER Wave 12)
- [x] DEV-1 Code Studio: live code server actions + automations (probe-gated per instance) — core 2026-08-03
- [x] DEV-2 Module code authoring: Option A with a real editor (custom_code_blocks writable) — 2026-08-03
- [x] DEV-3 Script Runner: ad-hoc Python via typed RPC client in isolated subprocess — 2026-08-03
