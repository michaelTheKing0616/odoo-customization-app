# MASTER PLAN — Odoo Customization Platform, Full Build-Out

> Orchestrator document. Written by the planning model; executed by Composer 2.5 (bulk coding)
> and Cursor Grok 4.5 (reasoning-heavy cards + checking). Workers receive ONLY their card file
> (`plans/cards/WAVE-*.md` section) plus the files named in the card's INPUT. This document is
> for the orchestrator/session lead.

## Mission

Build the best Odoo customization, configuration, and maintenance software in the world:
no-code metadata customization + real module generation + AI drafting (Draft Studio) + a
grounded RAG assistant (Odoo Expert) + a bulk-operations maintenance suite + full four-tier
hosting coverage + a premium UI + a monetized SaaS shell. Nothing is stubbed. Nothing is
silently skipped.

## Governing principles (bind every card)

1. **All four Odoo tiers are first-class:** Odoo Online, Odoo.sh, self-hosted Community,
   Enterprise. Detect per instance (installed modules, version, hosting), light up what exists,
   gate honestly (explain why + options) where absent. Never blanket-refuse by tier.
2. **Clean-room boundary (law):** never read, copy, or reverse-engineer Odoo Enterprise/Studio
   source code. Driving Enterprise features via public RPC on licensed instances is in scope.
   Public docs + our own original code only.
3. **Protected modules:** tier-1 financial/legal modules are link-only targets (Wave 1).
   The restriction is on the EFFECT, not the mechanism.
4. **Snapshot before risky mutation; sandbox before prod install; confirm gates on destructive
   ops** (existing infrastructure — reuse, never bypass).
5. **Honesty is a feature:** approximations, gates, partial failures are designed UI states.
6. **Checkbox discipline (see Execution Protocol):** every card has a CHECKLIST. No box left
   unchecked without an explicit SKIPPED marker + reason. Silent partial implementation is a
   failed card.

## What already exists — DO NOT REBUILD

Backend `apps/api/app/`: AI single+staged pipelines (`ai_ollama.py`, `ai_pipeline.py`), domain
packs (car_rental, hospital, law_firm, clinic, field_service), pack RAG (`ai_rag.py`), reuse
planner, quality/depth/critique passes, LLM provider (ollama + openai-compatible, format json),
live ModuleSpec apply (`spec_apply_ui.py`), code→spec import (`module_import.py`), Jinja export
(`packages/module-generator`), snapshots/rollback (`snapshots.py`), sandbox→promote
(`sandbox.py`, `promote.py`), pipelines (`routers/environments.py`), Power Ops (16 recipes),
data import + seeds, config ops, reports CRUD, menus builder, access, reminders, auth API keys,
rate limit, audit, zip safety. ~55 test files.

Frontend `apps/web/src/`: 20 working pages (connect, hub, builder, designer, wizard,
modulespec, projects, automations, access, menus, reports, config, import, power-ops, journal,
reminders, settings, pipelines), typed `api` client (`src/lib/api.ts`), Tailwind v4.

Packages/infra: `packages/odoo-client` (typed RPC, per-major adapters 16–19),
`packages/module-generator`, docker stacks 19/18/17/16 + sandbox :18069, gate scripts.

Cards extend these. A card that rewrites an existing working module without its card saying so
is a failed card.

## Wave order and card index

Progress board: `plans/PROGRESS.md` (the single source of truth for what is done).
Card files: `plans/cards/WAVE-<n>-<code>.md`.

- Wave 0 SAFE — repo baseline commit + STATE.md law-firm follow-up. (SAFE-1, SAFE-2)
- Wave 1 PCM — Protected Core Modules guardrail. (PCM-1..4)
- Wave 2 AI — Prompt-engineering + pipeline upgrades. (AI-1..7)
- Wave 3 BLK — Bulk & workflow-optimization suite + ID generator port. (BLK-1..9)
- Wave 4 TIER — Four-tier hosting/edition coverage + Enterprise drivers. (TIER-1..5)
- Wave 5 EXP — The Odoo Expert RAG assistant. (EXP-1..5; EXP-5 needs UIX-3)
- Wave 6 UIX — UI/UX revamp. (UIX-1, UIX-2, UIX-3, UIX-4a, UIX-4b, UIX-4c, UIX-5)
- Wave 7 CMP — Compendium completions. (CMP-1..11)
- Wave 7b ADV — Advanced designers & live editing. (TIER-6, UIX-6, UIX-7)
- Wave 8 PROD — Production hardening. (PROD-1..3)
- Wave 9 MON — Monetization: auth, billing, admin, pricing. (MON-1..4)

Dependencies: Wave 0 first, always. Wave 1 before Wave 2/5 (guardrail feeds prompts).
Wave 6 UIX-1/2/3 before UIX-4*, EXP-5, MON-4, and Wave 7b UI cards. Waves 3/4 parallel-safe
with Wave 6. Wave 9 last (entitlement keys already named in earlier cards' DONE MEANS).

## Model routing (per skills/model-routing.md, mapped to available Cursor models)

- **Cursor Grok 4.5** (high-reasoning tier): PCM-3, PCM-4, AI-1, AI-4, EXP-2, EXP-3, CMP-5,
  CMP-10, MON-1, MON-2, UIX-6, TIER-1 — architecture/security/correctness-sensitive.
  Also ALL checker sessions.
- **Composer 2.5** (agentic coding tier): everything else — SAFE-*, PCM-1/2, AI-2/3/5/6/7,
  BLK-*, TIER-2/3/4/5, EXP-1/4/5, UIX-1/2/3/4a/4b/4c/5/7, CMP-1/2/3/4/6/7/8/9/11, PROD-*,
  MON-3/4, TIER-6.
- Rule of thumb: default down a tier; escalate only after the checker fails the same card
  twice; log escalations in ERRORS.md.

## Execution protocol (every session, every card)

1. **Session start:** read `AGENTS.md`, `MEMORY.md`, `ERRORS.md`, `STATE.md`,
   `plans/PROGRESS.md`. Then open ONLY your assigned card.
2. **Pick work:** the first unchecked card in wave order unless the user assigns one.
   Mark it in-progress in PROGRESS.md (`[ ]` → `[~]`).
3. **Checkbox discipline (mandatory):**
   - Every card has a CHECKLIST of concrete sub-items. As you complete each, flip `- [ ]` to
     `- [x]` IN THE CARD FILE.
   - If you cannot or should not do an item, mark it `- [SKIPPED]` with a one-line reason and
     STOP to ask the user — skipping is a user decision, never a model decision.
   - A card is complete only when every box is `[x]` or user-approved `[SKIPPED]`, the gate
     passed, and PROGRESS.md is updated (`[~]` → `[x]`).
   - The checker's first job: diff the CHECKLIST against the actual code diff. Unchecked-but-
     claimed-done or checked-but-not-implemented = automatic FAIL.
4. **Gates (before checker):** run the card's GATE commands: pytest targets; live RPC smoke
   against docker Odoo 19 per `skills/odoo-rpc-gate.md` (16/17/18 too when the card says so);
   Playwright + screenshots per `skills/vision-verify-ui.md` for UI cards. No RPC claim ships
   without instance proof (ERRORS.md #7).
5. **Checker:** separate NEW chat session on Cursor Grok 4.5, given the card + the diff +
   gate output. Pass/fail only, per `skills/verifier-subagent.md`. Maker is never the checker.
6. **Failure handling:** same approach fails twice → log to ERRORS.md and stop
   (RULES.md stop conditions). Check ERRORS.md before retrying any failed pattern.
7. **Session end:** update STATE.md retro (≤15 lines); decisions → MEMORY.md.
8. **Deviations:** conservative option + log under "deviations" in the return. Never silently
   improvise; never widen scope beyond the card.

## Universal DO-NOTs (apply to every card, in addition to the card's own)

- Do not touch files outside the card's scope. Do not reformat/rename/refactor
  opportunistically.
- Do not commit unless the card says to. Never force-push. Never commit secrets/.env.
- Do not write to any non-sandbox Odoo instance without the existing confirm gates.
- Do not add paid-SaaS dependencies. New OSS deps only if the card lists them.
- Do not invent Odoo API behavior — verify against the local instance or `packages/odoo-client`.
- Do not remove or weaken existing tests to make a gate pass.

## Copy & design authority

All UI copy follows `plans/COPY_GUIDE.md` (voice, glossary, gating templates). All UI work
follows Part C of the approved plan as embedded in the UIX cards (tokens, kit, shell). Models
do not invent terminology, colors, or icon choices — the cards specify them.

## Kickoff prompt (paste into a new Composer 2.5 chat to run the whole program)

```
You are the implementation lead for this repo. Read, in order: .cursorrules, AGENTS.md,
MEMORY.md, ERRORS.md, STATE.md, plans/MASTER_PLAN.md, plans/PROGRESS.md.

Then execute cards strictly per plans/MASTER_PLAN.md "Execution protocol":
1. Take the first unchecked card in wave order from plans/PROGRESS.md. Open ONLY its card
   section in plans/cards/. Mark it in-progress in PROGRESS.md.
2. Model routing: if the card is listed under "Cursor Grok 4.5" in MASTER_PLAN's routing
   table, do NOT implement it yourself — spawn a subagent with model
   cursor-grok-4.5-high-fast and pass it the card verbatim plus its INPUT files. If subagent
   model selection is unavailable, pause and tell me to switch this chat's model to
   Cursor Grok 4.5 for that card, then continue.
3. Implement with checkbox discipline: flip every CHECKLIST box to [x] in the card file as
   you complete it. If any item can't be done, mark [SKIPPED] with a reason and STOP for my
   approval — you may never skip silently or leave a box unchecked while claiming done.
4. Run the card's GATE commands (pytest / RPC smoke vs docker Odoo / Playwright). Paste real
   output. If a gate needs Docker or Ollama running, start it or ask me.
5. Verification: spawn a NEW checker subagent on cursor-grok-4.5-high-fast with the card,
   the diff, and gate output. Checker returns PASS/FAIL only; its first job is comparing the
   CHECKLIST against the actual diff. On FAIL, fix and re-gate. Same approach failing twice →
   log ERRORS.md and stop.
6. On PASS: mark the card [x] in PROGRESS.md, update STATE.md (≤15 lines), log decisions to
   MEMORY.md, then continue to the next card.
Pause only for: spending money, external sends, destructive/non-sandbox Odoo writes, SKIPPED
approvals, or judgment calls only I can make. Otherwise run continuously.
Start now with the first unchecked card.
```
