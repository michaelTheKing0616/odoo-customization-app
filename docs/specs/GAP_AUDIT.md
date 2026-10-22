# Ingenium gap audit (read-only, 2026-10-20 ~15:45 WAT)
Method: grep of symbols/routes over 2,831 .py/.ts/.tsx files in apps/ + packages/ on Tope's Mac (node_modules/.next excluded), plus apps/api/evals/v2/PROGRESS.md. Evidence means the code exists. It does NOT mean the live 17-20 acceptance was run, unless PROGRESS says so. Most "Done" rows have had no live acceptance run (see P-0).
Legend: D = Done, P = Partial, M = Missing (no symbol/route found).

## 1. SPEC.md (View Designer / Reports / App Studio adoption / Bots)
| Item | St | Evidence / gap |
|---|---|---|
| §2 engine load/normalize/compile/publish/revert | D | routers/views.py, view_engine.py |
| §11 Stage 1-2 logic (conditions, role preview, history, comments, cmd bar, proof loop) | D | WhoCanSeePanel, HistoryPanel, ReportDesignerShell page_break; live acceptance not re-logged |
| §11 Stage 3 styling | P | tokens done (Build 5 S1); `impeccable detect` and contrast-pair runs not logged |
| §11 Stage 4 adoption (App Studio/Draft Studio through engine, Open in View Designer) | D | lib/design-preview.ts, PROGRESS item 4; INP<200ms and keyboard walkthrough not logged → P on acceptance |
| §14 open decisions (live records, DESIGN.md page, --brand orange) | P | no recorded answer found |
| §14 Stitch adopts (chip bar, drop label, pinned comments, hint strip, tab badges, publish count) | D | builders 2b/2c components (assumed from stage-2 logs) |
| §15 who-can-see editable, impact words, can-a-person-see, why hidden | D | WhoCanSeePanel.tsx |
| §16 widget picker with live preview | M | no WidgetPicker |
| §16 inline field create / related by drag | P | not confirmed by grep |
| §16 Tidy up, screen health score | D | Builder2d tidy, view_engine_studio health_score |
| §16 list designer (widths, optional cols, totals, row colours) | M | no ListDesigner/optional_columns UI |
| §16 kanban card designer | P | engine supports kanban; no dedicated designer UI |
| §16 search designer | M | none |
| §16 translations side by side | P | ConfigScheduledI18n only; no View Designer translations panel |
| §16 history scrubber | D | HistoryPanel scrubber |
| §16 upgrade guard | P | version_watch exists; no screen re-check+fix flow found in designer |
| §16 reusable sections, move layout between DBs | D | SaveAsComponentButton; view_engine package |
| §16 presence / co-edit | D | useDesigner2c, EngineCanvas cursors |
| §16 perf hint heavy fields | P | not found |
| §16 reports: blocks anywhere, conditional, QR/barcode, watermark, email previews | D | BlockEditor, EmailDesigner |
| §17 full component library + new screen from blank | P | spec_apply_ui/new_screen; full Studio-parity library not verified |
| §18 heatmap, dashboard (graph/pivot) designer, a11y simulator | D | ViewDesignerShell heatmap, Builder2cSheet pivot, view_engine_2c |
| §18 report from photo/PDF (§19.14) | M | no from_photo route (Wireframe could feed it) |
| §18 scheduled publish, A/B layout test, digest | P | one weak hit each; ticker exists (builders_ticker advisory lock) |
| §19 2d ideas 2,3,4,5,13,16,17,18,19,20 | D/P | explain PDF (view_engine_2d), slack webhook, test email hits; 3 named approvers needs sign-in (see Bridge second approver) |
| §19.6 number tiles, §19.7 hide never-filled fields, §19.8 stage checklist | M | no symbols |
| §20.1 Edit with AI (views, reports, emails) | D | AIEditBox, view-engine-2b |
| §20.2 Expert + bot avatars | D | BotAvatar (suite Ask, StatesPreview), BOT_SPECIALTY |
| Out-of-scope website builder | — | correctly absent |
Counts: D 17 · P 11 · M 6

## 2. CONFIG_SUITE_SPEC.md
| Item | St | Evidence / gap |
|---|---|---|
| Stage 1 shell, routes, /home, /capabilities, /inspector | D | routers/suite.py routes; suite/{ask,change,explore,safety,setup,states,upkeep} |
| Stage 1 Bulk Setup structure (catalog, plans, workbook) | D | /setup/catalog, /setup/plans, /setup/workbook |
| Stage 2 Check→Run→Review, schedule, stop, undo, duplicates, upkeep, upgrade, localization, ask/guide | D | /batches/*, /runs/*/undo, /duplicates/scan, /upkeep/*, /safety/*, /ask/guide |
| Stage 2 live 17-20 acceptance list | P | no full-list live run logged |
| Stage 2B import docs (DOCX, hr.version, ingest redirect), waves, undo plan | D | suite_import.py, suite_catalog.py, SetupWorkspace |
| Stage 2B §20.12 live acceptance (l10n_ng, units, access on 20, injection) | P | not logged as run |
| Stage 3 styling + zero-jargon scan on 15 tools | P | jargon-guard.test.ts exists; impeccable/contrast runs not logged |
| Stage 4 polish (motion, a11y, ⌘K batch plans, "Check on every version", "Before you upgrade") | M | Stage 4 not started (Tope's list); no before_you_upgrade |
| Ideas 1-34 (§16) | P | Found: 2 scheduled runs, 3 recipes, 26 estimate, 14 mail health (partial), 23 why-stuck (Co-Pilot only). Missing: 1 rehearsal replay, 4 filters from words, 5 data quality board, 6 leaver, 7 reassign, 8 archive dependency check, 9 tag manager, 10 two-DB compare, 11 handover pack, 12 role x-ray, 13 access hygiene, 15 numbering check, 17 translation coverage, 18 automation catalogue, 19 unused apps, 20 custom field clean-up, 21 storage forecast, 22 import aftercare, 24 record time-travel, 25 watch this (27-34 not grepped individually) |
| Ideas 35-48 (§20.14, approved) | P | 39 plan from DB (config_as_code importers), 40 sign-off (PlanLedger), 41 MCP check (partial), 47 provenance chip. Missing: 35 diff-only rerun (unverified), 36 rehearsal on copy, 37 many companies table, 38 setup score, 42 out-of-hours window, 43 industry plans (unverified), 44 setup handover, 45 email-in address, 46 price-list diff, 48 import health |
| D1-D6 decisions | D | old routes redirect; D2/D3 approvals; Oct 20 self-approval for CoA/tax/journal (write_gate) |
Counts: D 6 · P 6 · M 1 group (ideas missing about 30 individually)

## 3. BRIDGE_RUNNER_SPEC.md
Code runner (29): the routes cover 1-28. Monaco + vim/emacs (CodeRunnerEditor), autocomplete (odooLanguage), lint, versions, ai, snippets, runs control/resume/undo/export, library versions/diff/restore, comments, params, share, gallery, runbook, tests, promotions, audit, vault, settings/disclosure (29).
- P: 24 live co-editing (comments only), 18 perf profile (no symbol), 1 split/minimap unverified. Full browser click-through not done (known item).
Counts: D 25 · P 4 · M 0

Bridge (32): routes for gallery+secrets+health (1,3,4), import-spec (2), mapping suggest/match/rules (7-9), dead-letters+replay (12), contract-tests (13), sandbox-run (15), propose/approve/rollout/rollback (16), backfill plan (17), reconcile (18,22), trace (20), alerts preview (21), quota (30), recipes (27), draft (6), score (28), export (24-26), canvas (5), agent-call (29), client mode (32).
- P: 5 canvas is not "Figma-grade" (no flow-canvas library; known gap); 10 triggers / 11 delivery engine (idempotency only in contract studio; durable queue not confirmed); 14 drift alerts (generic drift hits); 19 live monitor + 23 SLA (ops.py, thin); 3 OAuth refresh (one hit in gallery.py); 24 middleware generator (export.py only; no Dockerfile output found); 31 PII masking in logs (scrub.py); second approver when sign-in is off (FlowsBoard, known open); AI on spec import (known open).
Counts: D 21 · P 10 · M 1 (AI on spec import)

LLM caching (a-h): D a (shared client), b (ai_cache), c (context_cache.py), e, g (AiSavingsCard), h (fresh answer); M d semantic cache; P f batching.
AI guards (1-5): D 3 output checks, 4 topic_guard (ai_client/guards.py); P 1 injection classifier (guard module exists; "small model on all untrusted text" not verified), 2 PII redaction (scrub.py, wireframe), 5 red-team pack (1 file; no pre-release hook).
Counts: D 8 · P 5 · M 1

## 4. FEATURE_AUDIT.md (app-wide + approved "all")
| Item | St | Evidence / gap |
|---|---|---|
| A1 new menu | D | nav.ts groups (PROGRESS) |
| A2 one page frame | P | frame row on 14 headers + one dark header (Oct 20 n/u); ErrorNotice/empty state not on every page |
| A3 jargon sweep + guard test | D | lib/jargon-guard.test.ts |
| A4 one History | P | journal timeline + History snapshots; per-page snapshot panels removal not confirmed |
| A5 shared Run sheet | D/P | app/write_gate.py in bulk, id-gen, power-ops, import, config/report; remaining: dedupe merge, recompute, portal access (listed "next" in Oct 20 w, not logged done) |
| A6 Cmd-K deep | D | CommandPalette records + History (Oct 20 m) |
| A7 Edit with AI for Access/Automations/Menus/Models | M | AIEditBox only in designers |
| Top-5 #1 Power Ops lock | D | LOCKED_RECIPES, UI band |
| #4 one "Bring data in" (merge Import+Ingest+suite import) | P | nav label only; three flows still separate |
| #5 plain-sentence Automations (Reminders folded) + Access "test as user / on a real record" | M | no symbols |
| Per-page ideas §1-21 and Part 2 (about 150 lines) | P | not audited line by line. Spot checks: Wireframe D (routes status/read/clarify/map), Connect D, Co-Pilot partial (below) |
| Tope add 1: term card + registry + fail test | P | lib/terms.ts, <Term> on 3 screens only; the "fails if a mapped label has no card" test not found |
| Tope add 2: Co-Pilot demo builder from BRD/SOW, requirement-coverage ticks, one-click demo-data undo | M | no demo_builder / coverage / demo undo |
| Tope add 2: 4 answer labels | D | live_demo_copilot/db_grounding.py, guards.py |
| Tope add 3: Connect rebuild | D | Build 5 S3, hosting detect, run checks, groups, test copy |
| Q7 meeting bot (Vexa) join/transcript/after-meeting | P | routes exist; never joined a real meeting; chat post/speak not possible in Vexa |
| B1-B8 bold capabilities | M (B4 P) | B4 agent mode exists (studio_agent; lost head-to-head, deferred); B1,B2,B3,B5,B6,B7,B8 none |
Counts: D 7 · P 9 · M 4 (+7 bold ideas)

## 5. APP_STUDIO_FIX_PLAN.md + HANDOFF
| Step | St | Evidence / gap |
|---|---|---|
| 1 metric fixes + record/replay, re-baseline | D | evals/v2/replay.py, rescore*.py |
| 2 authorizer offline | D | ai_conversation/model_authorizer.py |
| 3 schema+prompt + 3 experiments | P | contract_experiment.py/design_experiment.py; brief-contract fix "paused" |
| 4 python gate + orphan repair | D | orphan_repair.py, intent_gate.py |
| 5 shadow mode ~1 week on real sessions | M | no shadow mode found (1-week trial waits on Tope) |
| 6 fresh holdout before claiming | P | holdout_fresh/ exists; result not logged |
| JSON-2 res.partner/create vals_list 422 | M | not fixed (only code_runner/child.py reads vals_list) |
| Handoff §5 pre-existing failures | P | api 82 failed / 4,898 passed (Oct 20 y) |
| PROGRESS OPEN: reminder offset lost; junk fields from non-field phrases; non-JSON requests bypass the dry-run gate; TTL mismatch 300s vs 15min | M | still marked OPEN |
| Agent-mode re-run with sandbox API key | M | deferred by Tope ("when I tell you") |
Counts: D 3 · P 4 · M 5

## 6. DESIGN_TOUCHES (Q2 is another worker; from PROGRESS only)
About 30 left, mostly big or data-dependent. Blocked as logged: 60/61 (need multi-chart screens), 79 marquee, 131 margins overlay, 103 n/a. Welcome letter needs Tope's words.

## Prioritised Missing/Partial queue
P-0 Live 17-20 acceptance runs for the suite (Stage 2 + §20.12), the SPEC Stage 4 checks (keyboard, INP) and Stage 3 `impeccable`/contrast. Most "Done" rows have no live proof logged.
1. Safety: non-JSON requests bypass the dry-run gate (OPEN in PROGRESS).
2. A5: finish write_gate on dedupe merge, recompute and portal access.
3. AI guards: confirm the injection classifier runs on all untrusted text; red-team pack as a pre-release gate; PII redaction before every cloud call.
4. Bridge: second approver when sign-in is off.
5. Bridge: Figma-grade flow canvas (live data).
6. Bridge: durable delivery engine (queue, retries, ordering, pacing), OAuth refresh, middleware generator with Docker output.
7. Co-Pilot: BRD/SOW demo builder + requirement-coverage view + one-click demo-data undo.
8. Co-Pilot: first real meeting test (Vexa server on the Mac; needs Tope's go).
9. Suite Stage 4 (motion, a11y, ⌘K batch plans, Check on every version, Before you upgrade).
10. Suite ideas 1-34 and 35-48: about 30 not built (data quality board, leaver playbook, two-DB compare, handover pack, role x-ray, access hygiene, automation catalogue, record time-travel, watch this, email-in, setup score…).
11. Feature audit #5: plain-sentence Automations (Reminders folded in) + Access "test as user"; A7 Edit with AI beyond the designers; #4 one "Bring data in".
12. View Designer premium gaps: widget picker, list designer, search designer, kanban card designer, translations panel, number tiles, hide never-filled fields, stage checklist, report from photo.
13. App Studio: brief-contract fix (paused), shadow mode week, fresh holdout, reminder offset + junk-field bugs, JSON-2 vals_list, TTL unification, agent-mode re-run (deferred).
14. Term card on every mapped label + its failing test; A2 frame (error/empty states) on every page; A4 removal of the per-page snapshot panels.
15. Code runner: browser click-through, perf profile, live co-editing; LLM semantic cache + call batching.
16. Bold B1-B8 (upgrade co-pilot, process mining, DB doctor, knowledge capture, benchmarking, training, compliance packs): none built.
17. Decisions still open: SPEC §14 (live records, DESIGN.md page, --brand orange); test briefs review; 1-week trial; old failing tests (82); leftover dev servers.

## Status update (build pass, Oct 20 15:31–16:10 WAT)
| Queue # | Item | New status | Evidence |
|---|---|---|---|
| 1 | Non-JSON test-run bypass | Done | already fixed Oct 19 (dry_run_middleware + tests/test_dry_run_non_json.py); content-type check now case-insensitive |
| 2 | Shared write checks (A5) | Done | PROGRESS Oct 20 aa/ab (dedupe merge, recompute, portal, config writes) |
| 3 | AI guards | Done (core) | shared_client sweeps unfenced prompts (guards.sweep_unfenced); cloud redaction enforced in shared client; red-team pack in default pytest; tests/test_ai_guards_unfenced.py |
| 13 | App Studio small bugs | Done | reminder offset + junk fields (S12b live), JSON-2 vals_list mapper, one TTL (code_runner too) |
| P-0 | Live 17-20 acceptance | Partial (most done) | Suite stage 2 18/18 on all four; Bulk Setup NG plan (order, money guard, approval, run, undo) pass on all four; 2 bugs found + fixed (16-char kind column; after-install steps). Left: workbook bad rows, ir.access role, mid-run failure, documents batch, View Designer stage 3-4 |
| 4 | Bridge second approver | Done | flows.approve two names when sign-in off; FlowsBoard name box |
| 6 | Bridge delivery engine / token refresh | Done (backend) | bridge/delivery.py, bridge/tokens.py, routes /events /deliver /queue /token/refresh; trace station+ms; publish log; tests/test_bridge_delivery.py |
| 14 | Term card everywhere + test | Done | 33 labels wrapped; src/lib/term-guard.test.ts |
| 14 | Page frame error/empty states | Partial | error boundaries global; empty states not audited |
| 9 | Suite stage 4 | Partial | forecast + check-every-version APIs; UI, ⌘K batch plans, motion/a11y open |
| 10-12, 15-16 | Suite ideas, FA #5, VD premium, Co-Pilot builder, Figma canvas, bold ideas | Missing (not started this pass) | — |

### Update 2026-10-20 (G8)
- DONE: live checks for the bad-row workbook, access roles (17–20, new `access` step), a step forced to fail mid-run, and the mixed-document import. All pass on 17/18/19/20.
- Fixed along the way: workbook duplicate rows, update-after-create, prefixed import headers, access op policy key.
- STILL OPEN: View Designer stage 3–4 live (contrast, keyboard, INP); Suite stage 4 screens; Cmd-K batch plans; motion and accessibility; queue items 8–13.

### Update 2026-10-20 (G9)
- DONE: View Designer stage 3–4 live (contrast light/dark, keyboard, INP), Suite stage 4 screens, ⌘K batch plans, Suite motion/a11y pass.
- Item 8: 15 look-only ideas built (5, 8, 10, 12, 13, 15, 17, 18, 19, 20, 21, 22, 24, 29, 33). Still missing: 1 rehearsal replay, 4 filters from words, 6 leaver, 7 reassign, 9 tag manager, 11 handover pack, 16 multi-company, 25 watch this, 27–34 rest, 35–48 rest.
- Next: rest of item 8 (the ones that write go through Change batches), then 9–13.
