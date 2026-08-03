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
- [x] PCM-3 Guardrail prompt injection + structured refusal end-to-end
- [x] PCM-4 Enforcement in builder/apply/automations/power-ops + UI badges + adversarial tests

## Wave 2 — AI (prompt engineering + pipeline)
- [x] AI-1 Thinking mode + Qwen3 size ladder in LLMProvider
- [x] AI-2 Per-step temperature + prompt audit + anti-pattern blocks
- [x] AI-3 Self-consistency (N-sample vote/merge) behind AI_SELF_CONSISTENCY
- [x] AI-4 Dedicated workflow-states/transitions pipeline pass
- [x] AI-5 Five new domain packs (restaurant, real_estate, hotel, subscription, project)
- [x] AI-6 Draft→pack generalizer (fold customer projects into library, opt-in)
- [x] AI-7 Reverse-import partial-fidelity contract (custom_code_blocks)
- [x] AI-8 Component-grain generation (extensions for Odoo + custom apps, connect points, gallery) — added 2026-08-03

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
- [~] UIX-4a Page migrations: landing + connect on kit; overview + draft studio pending
- [ ] UIX-4b Page migrations: designer, projects diff, automations, access
- [ ] UIX-4c Page migrations: power-ops/bulk, journal, remaining pages
- [ ] UIX-5 Copy guide application pass + iconography audit

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
- [ ] TIER-6 Deep Gantt/Grid/Map/Cohort config designers (edition-gated)
- [ ] UIX-6 Live overlay editor on proxied Odoo frame
- [ ] UIX-7 Website page editing (block-based, website module detected)

## Wave 8 — PROD (production hardening)
- [ ] PROD-1 API Dockerfile + compose deploy profile
- [ ] PROD-2 DB migration strategy + export README audit
- [ ] PROD-3 Queue decision (arq vs in-process policy) + job hardening

## Wave 9 — MON (monetization)
- [ ] MON-1 Auth accounts: users/workspaces/roles/sessions/2FA
- [ ] MON-2 Billing: Stripe + Paystack, entitlements, feature gating
- [ ] MON-3 Admin console + internal-plan bootstrap (env-seeded admin)
- [ ] MON-4 Pricing page + upgrade/trial UX
