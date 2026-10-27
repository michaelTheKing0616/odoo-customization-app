# 09 DECISIONS FOR TOPE

Each decision has a recommended default. Reply `DEC-nnn: yes` to take the default, or give your answer. **Blocking for G0** = I cannot finish the stage without it. The rest are batched for G1, GATE-A, and GATE-D.

## Resolved 21 Oct (Tope's answers; G0 approved)

| ID | Answer as applied |
|---|---|
| DEC-001 | Planner chose **40M cost-weighted tokens/week** (`budget.json`, one value to change). Pilot recalibrates class caps |
| DEC-002 | Box specs now in `docs/specs/` (SPEC, IDEA, CONFIG_SUITE_SPEC, ODOO_CONFIG_CATALOG, BRIDGE_RUNNER_SPEC, APP_STUDIO_HANDOFF, APP_STUDIO_FIX_PLAN, GAP_AUDIT, stitch). DESIGN_TOUCHES and FEATURE_AUDIT copies are byte-identical. Remainder → DEC-038 |
| DEC-020 | **Any requester may self-approve**, audited (who, when, plan hash) and still behind money guard + dry-run receipt. §6.5 is corrected; SEC-6.5-AC2 inverted |
| DEC-021 | Code wins: dead letter after **6 attempts** (first try + 5 retries, `bridge/delivery.py` L30). §7.8 wording corrected. New finding → DEC-036 |
| DEC-022 | The old pack is **merged**: all 349 cards are ledger rows `NP-<id>` with their status; old IDs are reused verbatim as card IDs; DONE cards become per-track regression batches `REG-NP-<track>`. Every merged card is re-authored to this plan's card template and UI/security bar at its phase G2 |
| DEC-030 | Worker/Tester/Reviewer L1-L3 = **grok-4.7-xhigh**. `cursor-grok-4.6-high-fast` only for XS chores if the pilot shows an equal pass rate |
| DEC-035 | Five headline briefs: Customer Health & Retention (no file → DEC-037), `dev/rental_casual`, `dev/rental_structured`, `dev/bakery_ng`, `dev/event_hire` (each with `.gold.yaml`) |

## Resolved 21 Oct, second batch (Tope: "approve your recommendation" / "whatever you think is best")

| ID | Answer as applied |
|---|---|
| DEC-036 | Planner's call, **changed from the earlier default**: retry by **time, not count**. Keep exponential backoff with the 15-min cap and jitter, retry until **24 h** after the first attempt (one config value), then dead-letter. Show an "is late" warning in the Bridge inbox after 15 min. Dead letters stay one-click replayable (`bridge/reliability.replay`, L40). Idempotency keys already stop duplicates. Card BR-RETRY-WINDOW |
| DEC-037 | Planner's call: the fixture `apps/api/tests/fixtures/customer_health_brief.md` **is** the headline brief. AS-CH-BRIEF copies it to `evals/v2/dev/customer_health.md` with a DRAFT gold for Tope's review |
| DEC-038 | Planner's call: **nothing blocks on the box files.** The UI protocol uses the repo tokens (`apps/web/src/styles/globals/tokens.css`, studio-refinement tokens), `docs/brand/` SVGs and the reference pack. If the box files arrive, one reconcile card diffs them against the repo tokens. They never fork into a second visual language |
| DEC-039 | No original wording. Keep the reconstructions as dev briefs; gold attributes the owner never said are marked `unstated: true` (AS-GOLD-SPANS). New bar added the same day: senior-Odoo-developer output with no pack crutch (Pack §0a, `ODOO_CRAFT.md`, AS-CRAFT-*, AS-NO-PACKS) |
| DEC-040 | **1,500 calls / $30** hard stop for X0-X4, metered by AS-HARNESS |
| DEC-041 | **Yes**: v3 supersedes FIX_PLAN (a)/(b) under profile v3; legacy unchanged. Tope: "the best designs win; the absolute best design on every screen" |

## Resolved 21 Oct, third batch (Tope's sixth message)

| ID | Decision |
|---|---|
| DEC-042 | **Module route** (Tope). Python-backed idioms (reference numbers, smart-button counts, totals from lines, constraints, printable reports) are built only in the generated module from fixed reviewed templates, never LLM-written, sandbox-tested, promoted by a person. The live lane shows them as "ready when you install it as a module" |
| DEC-043 | **Draft Studio drops domain packs and uses the App Studio v3 pipeline** once v3 passes AS-RELEASE-BARS (Tope). Cards AS-DRAFT-ADOPT, then AS-PACK-RETIRE (file deletion still asks for a yes at that time, INV-05/18). The AGENTS.md Draft Studio pack sentence is edited when AS-DRAFT-ADOPT ships, with Tope's approval of the wording |
| DEC-044 | **Upgrade chips are not capped** (Tope asked whether 3 was too restrictive; it was). Every matching upgrade is offered: top 3 inline, the rest under "More suggestions (n)", with Add all. The ≤ 3 *questions* rule stays: it is handover §8.7 AC7, and overflow questions already become visible suggestions |
| DEC-045 | **Elevate program approved in principle** (Tope: "feel free to recommend features… and add them to the plan"). `elevate/00_ELEVATE.md`: a measured Feature Excellence Bar for every feature, 6 cross-cutting cards, 19 bar cards, 25 next-level cards (5 duplicates of handover §6/§7 cards merged into them at Stage 2) (`cards/phase-7/`). Tope may strike any next-level card; it is then set to `blocked`, not deleted. Website next-level cards wait on the open scope call (handover §3.6) |
| DEC-038 (update) | Brand kit confirmed at `docs/brand/` (README chrome rule + 14 logo and mark files, byte-identical to `apps/web/public/brand/`, checked 21 Oct). Colours, type and motion stay in the repo tokens; every UI card cites both |

## New (blocking only the named card)

| ID | Decision | Recommended default |
|---|---|---|
| (none open) | | |

## Resolved 21 Oct, fourth batch (G1 approved: Tope "yes to decisions"; every default taken)

| ID | Decision | Answer as applied |
|---|---|---|
| DEC-046 | Who writes locked oracle tests for cards outside App Studio and Elevate (scored ≥ 6) | A separate L3 Grok "Oracle" session writes them from the card's verbatim ACs before the Worker starts. E1 (Opus) reviews them when the score is ≥ 10 |
| DEC-047 | Add dev-only test dependencies `pytest-randomly` (MIT) and, at the first card that needs it, `hypothesis` (MPL-2.0) | Yes. Needed for random-order runs and property tests. Dev group only |
| DEC-048 | Phase order deviates from the master skeleton (Phase 7 Elevate added; Reports, Code Runner and bots go in Phase 4) | Accept, as in `04_PHASES.md` |
| DEC-049 | Generated cards (735) are released per phase only after the G2 Prep check (paths, symbols, examples, clarity sample) | Yes. Prep may tighten a card, never drop or weaken an AC |
| DEC-003 | `--brand` orange use (SPEC open decision 3) | Orange is the brand mark and highlight only. Primary is teal `#0f766e` with white text (light) and `#2dd4bf` with basalt text (dark). Marketing orange buttons use basalt text |
| DEC-004 | Sidebar IA grouping (§5.3, Inferred) | Home · Build · Set up · Connect systems · Meetings · Review · Settings, as proposed |
| DEC-005 | Website scope (SPEC 12 out vs FEATURE_AUDIT 7 approved) | FEATURE_AUDIT 7 wins, phased into Phase 5. Publish goes through the write gate first |
| DEC-015 | Confirm the §8.6 release bars | Accept as written |
| DEC-024 | Retirements under INV-05: old Reports/Mail templates/QWeb pages, script-runner and code-studio, per-page snapshot panels, Draft Studio fold, Projects/App plan move, Reminders fold, Numbering rename, /ingest redirect, Dashboard Studio hide | FEATURE_AUDIT "all" (17 Oct) counts as the approval. Each card still lists the preserved features |
| DEC-026 | Who reviews gold outputs for new briefs and the holdout | Tope, with the 20+ new briefs reviewed in two sittings |
| DEC-027 | Live LLM budget for App Studio experiments (Stage 2B and P1-1 AC3) | Cap at $15 and 200 calls. Offline replay first |
| DEC-028 | Elite budget for the App Studio Design Pack | One Stage 2B session at ≤ 25% of one week |
| DEC-029 | Reference map swaps. The pack has no in-app Attio, the n8n in-app capture is only a signup gate, and there are no Raycast clips | Keep the map. For Records tables use Airtable/Notion in-app plus the official Attio images. For the flow canvas use official n8n and Make images. For Cmd-K use Linear and Vercel in-app clips |
| DEC-032 | UI reference media in git | Ignored (done). Only the `.md` notes are tracked |

## G1 batch

Approved 21 Oct (see the fourth batch above).

## Resolved 22 Oct (Tope: "approve both and continue")

Phase 0 G2 approved. DEC-031 was later replaced by a live test, recorded below. Other GATE-A decisions stay open and block only their own cards.

DEC-034 resolved 22 Oct (Tope: yes). `AUTH_MODE=accounts` for any shared deployment. Local stays off. Unblocks `APR-NAMED`, `SEC-2APPROVER`, and `VD-APPROVERS`.

DEC-031 resolved 22 Oct by test, not by an eyeball. `startOptionABatch` returns `StudioOptionABatchResponse`. The live test passed 3 against a disposable `ingenium_*` database. Project `tsc --noEmit` is still red on `src/lib/b0_dist.test.ts` TS5097, outside this card.

## GATE-A batch (before the owning card starts)

| ID | Decision | Default |
|---|---|---|
| DEC-006 | `attendee_client.py` (ELv2) | Remove it after a grep proves it has no callers |
| DEC-007 | Deploy Vexa self-hosted on the Mac, and the timing | Phase 4, on ports 8201+, with your go |
| DEC-008 | Agent-mode re-run timing (P2-3) | After P1-1 AC5 and an eval DB API key exist. Wait for your "now" |
| DEC-009 | Shadow mode on real sessions for one week | Start once AS-SHADOW ships. Shadow logs only, with no owner-visible change |
| DEC-010 | Authorizer default-on | Only after P1-1 AC4 passes. You confirm |
| DEC-011 | Pricing and tiers | Plans as data now, prices blank until you set them |
| DEC-012 | Payment providers | Paystack + Flutterwave (NGN) and Stripe (other), all hosted checkout |
| DEC-013 | Welcome letter text (touch 127) | You supply it. I write nothing |
| DEC-014 | i18n languages | English first. French, Portuguese, Arabic (RTL) as candidates. Phase 6 |
| DEC-023 | SPEC 14: read up to 80 live records in the browser, and a DESIGN.md live reference page | 80 records yes, read-only and PII-masked in logs. DESIGN.md page later |
| DEC-025 | Three first-time testers for the switcher (10 s) and onboarding (5 min) tests | You recruit 3 people. I prepare the script and timer |
| DEC-033 | Actually send Slack/Teams payloads and chat approvals | Off until SUITE-31 ships signed links. Then on per workspace |

## GATE-C / GATE-D batch

| ID | Decision | Default |
|---|---|---|
| DEC-016 | Delete about 16k junk connections (`pg_dump -Fc` first) | Dry-run list first, then you say yes |
| DEC-017 | Accept each remaining `xfail` | Per test, after B0 cards |
| DEC-018 | Keep `/tmp` backups (`designer_classic.bak`, `fp_*.bak`, `no_school_casual.gold.bak`, eval outputs) | Copy them to `docs/handoff/tmp-backups/` before the next reboot |
| DEC-019 | Commit plan for 848 modified and 804 untracked files | B0-INV proposes feature-grouped commits. Nothing is committed without your yes |

## New-features batch (DEC-050..074; proposals until Tope answers; source: new-features brief 22 Oct)

DEC-052..074 resolved 22 Oct (Tope: accept as recommended). Two changes from the written default: scan retention is set per workspace, default and maximum 90 days (DEC-052); Zoho Books is a first-wave migration source (DEC-066). Design: `docs/build-plan/new-features/`. Index: `NEW_FEATURES_INDEX.md`.

| ID | Decision | Default (recommended) | Blocks |
|---|---|---|---|
| DEC-050 | Approve the 27 NF epics (the brief's 26 ideas + the SCAN foundation) as build scope (INV-06) | **Resolved 22 Oct (Tope: 'approve all').** Approve all; they enter phases 4–6 per the index and are released per phase at G2 | all NF cards (at G2) |
| DEC-051 | Phase placement | **Resolved 22 Oct (Tope: 'approve').** Fold into phases 4, 5 and 6 per the index; no Phase 8 | phase_map NF prefixes |
| DEC-052 | What scans store and for how long | **Resolved 22 Oct.** Counts, record ids and masked samples only; no field values. Each workspace sets retention; the default and the maximum are 90 days | SCAN-02, all scan epics |
| DEC-053 | Usage signal source | **Resolved 22 Oct.** Records created/changed and log-ins only; no click-tracking addon in client Odoo | USAGE-* |
| DEC-054 | Upgrade rehearsal data source | **Resolved 22 Oct.** No customer DB clone (AGENTS). Fresh target sandboxes with customisation replay, or an owner-supplied upgraded Test copy. OpenUpgrade (AGPL-3.0) is not bundled or run | UPG-* |
| DEC-055 | Studio-to-code production takeover | **Resolved 22 Oct.** Zip + sandbox proof only; production install is a human Option A promote with the field-takeover warning | S2C-* |
| DEC-056 | Effort table and rate card | **Resolved 22 Oct.** Workspace sets rates; effort defaults are labelled "Example" until 10 real projects calibrate them | FITGAP-06, SOW-03, UPG-05 |
| DEC-057 | Manual media | **Resolved 22 Oct.** Text plus sandbox screenshots with Example data now; video later (Playwright + LGPL ffmpeg build only) | MANUAL-05, BOLD-B7 video part |
| DEC-058 | UAT on Live connections | **Resolved 22 Oct.** Refused; Live gets read-only checks only | UAT-04 |
| DEC-059 | Undo scope for drift restore and cleanup | **Resolved 22 Oct.** Restore views, menus, actions, automations and access rules; fields and data are report-only | DEBT-04, DRIFT-04 |
| DEC-060 | Default SoD rule set | **Resolved 22 Oct.** Ship a starting set as data, labelled "review with your auditor" | SOD-03 |
| DEC-061 | Nigeria rules table source | **Resolved 22 Oct.** You supply an adviser-reviewed table (VAT, WHT, PAYE bands, pension) with effective dates and sources; until then values show as Example | NG-04 |
| DEC-062 | E-invoicing scope | **Resolved 22 Oct.** Readiness checks and a sample payload export from the published spec you supply; no transmission; nothing written to posted invoices | NG-06 |
| DEC-063 | Bank statement samples | **Resolved 22 Oct.** You supply ≥ 2 anonymised statements for each of 5 banks (default: Access, GTBank, Zenith, First Bank, UBA); Ingenium converts and dry-runs, the owner imports | NG-08 |
| DEC-064 | PAYE and pension | **Resolved 22 Oct.** Compute-only report and export; no journal entries; Community has no payroll app [Inferred; NG-LIVE verifies] | NG-07 |
| DEC-065 | Connector landing and targets | **Resolved 22 Oct.** Payment events land in the Bridge inbox or an x_ staging record for human reconciliation, never account.payment; Paystack and Flutterwave first; bank-feed aggregator chosen later | CXB-04, CXB-05, CXB-07 |
| DEC-066 | Migration sources, samples, file retention | **Resolved 22 Oct.** Excel/CSV, QuickBooks Online, Sage 50 and Zoho Books first; you supply sample exports; files kept 7 days | MIG-03 |
| DEC-067 | In-Odoo assistant install path | **Resolved 22 Oct.** Addon via sandbox then human promote on Odoo.sh and on-prem; Online gets a link-out | HOWDO-06, HOWDO-LIVE |
| DEC-068 | Who sees NL report results | **Resolved 22 Oct.** Runs as the connection user; client-mode users see only reports the consultant shared | NLR-05 |
| DEC-069 | Marketplace model | **Resolved 22 Oct.** Free; metadata plans only (no Python); private plus curated public; no revenue share | MKT-* |
| DEC-070 | Client requests and Run | **Resolved 22 Oct.** Clients create requests and approve; they never trigger Run | PORTAL-04, PORTAL-05 |
| DEC-071 | Effort tracker writes | **Resolved 22 Oct.** No writes to any Odoo, including the agency's own; CSV/PDF export only | EFFORT-04 |
| DEC-072 | Process mining window | **Resolved 22 Oct.** 180 days, tracked fields only, sampling above 200k events | PMINE-02 |
| DEC-073 | Performance probe budget | **Resolved 22 Oct.** ≤ 60 calls per run, ≥ 250 ms apart, stop on 429/503 | PERF-02 |
| DEC-074 | Who writes the labelled eval sets (fit-gap 120 lines, NL reports 50, how-do-I 60 per DB) | **Resolved 22 Oct.** A separate L3 Oracle drafts them from seeded DBs; you spot-check 10%; never from holdout_fresh | FITGAP-07, NLR-06, HOWDO-07 |

## Resolved 22 Oct: UI trial result

| ID | Decision | Answer as applied |
|---|---|---|
| DEC-075 | Who builds new-features UI, and the UI bar after the X-ray trial | **Tope, 22 Oct, after viewing both live routes (not blind):** Grok's entry preferred. The Grok bot builds every NF card, backend and UI, in the NF stream; the main stream keeps all phase 0–7 UI. Grok's trial sheet (`docs/design/bar/xray-floor.png`) is the floor for every screen in both streams; it is not a one-off. Grok writes `docs/design/UI_DIRECTION.md` so the main stream can match and surpass it. Rules: `ORCHESTRATOR_PROMPT.md` § Parallel worktree conditions 9 and 10 and the UI-bar Hard rule; `07_UI_EXCELLENCE_PROTOCOL.md` §4 step 5a |
