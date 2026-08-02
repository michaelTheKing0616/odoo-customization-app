# PROGRESS — single source of truth for card status

Legend: `[ ]` not started · `[~]` in progress · `[x]` done (gate + checker passed) ·
`[SKIPPED]` user-approved skip (reason required). Update this file AND the card's own
CHECKLIST. Claiming done without both updated = failed card.

## Wave 0 — SAFE (repo baseline)
- [~] SAFE-1 Initial git commit baseline + .gitignore verification
- [ ] SAFE-2 Close STATE.md law-firm follow-up (re-run + verify)

## Wave 1 — PCM (Protected Core Modules)
- [ ] PCM-1 protected_modules.py classification engine
- [ ] PCM-2 Path A source retrieval + Path B live merge + per-connection manifest
- [ ] PCM-3 Guardrail prompt injection + structured refusal end-to-end
- [ ] PCM-4 Enforcement in builder/apply/automations/power-ops + UI badges + adversarial tests

## Wave 2 — AI (prompt engineering + pipeline)
- [ ] AI-1 Thinking mode + Qwen3 size ladder in LLMProvider
- [ ] AI-2 Per-step temperature + prompt audit + anti-pattern blocks
- [ ] AI-3 Self-consistency (N-sample vote/merge) behind AI_SELF_CONSISTENCY
- [ ] AI-4 Dedicated workflow-states/transitions pipeline pass
- [ ] AI-5 Five new domain packs (restaurant, real_estate, hotel, subscription, project)
- [ ] AI-6 Draft→pack generalizer (fold customer projects into library, opt-in)
- [ ] AI-7 Reverse-import partial-fidelity contract (custom logic preserved verbatim)

## Wave 3 — BLK (bulk & workflow suite)
- [ ] BLK-1 Generic bulk state transition + button discovery engine + BulkResult schema
- [ ] BLK-2 Universal mass field edit
- [ ] BLK-3 Generic duplicate detection & merge (any model, FK relink)
- [ ] BLK-4 Cron manager (plain language, run now, create/edit)
- [ ] BLK-5 Attachment housekeeping (orphans + checksum duplicates)
- [ ] BLK-6 Bulk activities + bulk security provisioning + bulk portal access
- [ ] BLK-7 Stored-computed recompute (touch technique) + threaded bulk send
- [ ] BLK-8 Cross-report-type merged PDF
- [ ] BLK-9 Inventory ID Generator port (all six AppleScript audit fixes)

## Wave 4 — TIER (hosting & edition coverage)
- [ ] TIER-1 Capability matrix (hosting x edition x modules) replacing heuristics
- [ ] TIER-2 Gating UX: three honest options + per-tier deployment paths + dry-run
- [ ] TIER-3 Apps Store packaging assist + Odoo.sh migration assist
- [ ] TIER-4 Post-upgrade health check
- [ ] TIER-5 Enterprise feature drivers (studio approvals RPC, EE views, EE playbook actions)

## Wave 5 — EXP (Odoo Expert)
- [ ] EXP-1 Docs ingestion + chunking + version-tagged embedding store
- [ ] EXP-2 Live-instance grounding context assembly
- [ ] EXP-3 /api/expert/ask generation endpoint (ground-or-decline, citations)
- [ ] EXP-4 Evaluation regression set + harness
- [ ] EXP-5 Expert UX surfaces (chat panel, explain-this, error mode, review companion)

## Wave 6 — UIX (UI/UX revamp)
- [ ] UIX-1 Design tokens + typography + dark mode foundation
- [ ] UIX-2 Component kit (20 components) + icon mapping
- [ ] UIX-3 App shell: sidebar nav, top bar, command palette, Expert panel mount
- [ ] UIX-4a Page migrations: landing, connect, overview, draft studio
- [ ] UIX-4b Page migrations: designer, projects diff, automations, access
- [ ] UIX-4c Page migrations: power-ops/bulk, journal, remaining pages
- [ ] UIX-5 Copy guide application pass + iconography audit

## Wave 7 — CMP (compendium completions)
- [ ] CMP-1 Manifest ordering tests + xpath move/$0 + ir.sequence verification
- [ ] CMP-2 Widget coverage + sample data + conditional attrs expression builder
- [ ] CMP-3 Niche widget palette + trigger capability checks + live palette extraction
- [ ] CMP-4 Visual QWeb report designer
- [ ] CMP-5 Approval rules (button gating; studio.approval.rule mode via TIER-5)
- [ ] CMP-6 Image pipeline (multi-resolution variants + bulk image import)
- [ ] CMP-7 Property fields full parity (probe-verified per major)
- [ ] CMP-8 Connect-to-Invoicing safe pattern
- [ ] CMP-9 Generic barcode scanning (in-app RPC path + exported OWL widget module)
- [ ] CMP-10 Standalone approval processes (multi-level chains; EE approvals RPC mode)
- [ ] CMP-11 Multi-company patterns + i18n depth + Documents integration

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
