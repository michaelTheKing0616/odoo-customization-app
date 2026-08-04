# MEMORY.md — Decision Log

> Read at the start of every session. After any significant decision, add an entry below.
> Never contradict a logged decision in a new session without flagging it first.

## Format
```
### [Date] — [short decision title]
**Decided:** what was chosen
**Why:** the reasoning
**Rejected:** what alternatives were considered and why they lost
```

## Log

### 2026-08-03 — REM-1: staged pipeline guard + step wiring
**Decided:** Define `guard = guardrail_prompt(manifest)` at top of `run_staged_pipeline`;
pass `protected_manifest`/`odoo_version` from `draft_module_from_prompt`; step3/5 use
`reasoning=True`, `STEP_TEMPERATURES`, `append_prompt_blocks`, `FORMAT_SCHEMA_RELATIONSHIPS`
on step3; dedupe duplicate `_PACK_FACTORIES` block; `test_ai_staged_pipeline.py` with
RecordingProvider executes all steps.
**Why:** NameError crashed staged LLM path; AI-1/2 temps/reasoning were missing on steps 3/5.
**Rejected:** Mocking step functions in the gate test (RecordingProvider calls real step code).

**Decided:** `AUTH_MODE=accounts` with cookie-first sessions (`oc_session`), argon2id passwords,
server-side session records, workspace scoping on connections/projects; API key fallback in
accounts mode for CI; OAuth deferred [SKIPPED].
**Why:** Self-hosted SaaS without paid auth vendor; preserves `off`/`api_key` for local gates.
**Rejected:** JWT-first SPA auth (cookie simpler for same-origin Next.js); OAuth in v1 (time-box).

### 2026-08-03 — PROD-2: Alembic migration policy
**Decided:** Adopt Alembic for app metadata DB; `init_db()` uses `create_all` only when
`DB_MIGRATIONS=off` (tests/local); deploy profile sets `DB_MIGRATIONS=auto` →
`alembic upgrade head` on startup.
**Why:** MON-1/2 will add ALTERs; drift test gates model/revision parity.
**Rejected:** Breaking test fixtures that rely on create-all (kept via off mode).

### 2026-08-03 — PROD-3: Job runner v1
**Decided:** Keep in-process `ThreadPoolExecutor` with `JobRunner` protocol seam;
`mark_interrupted_jobs_on_boot`, per-kind timeouts, concurrent cap, sandbox cancel hook.
**Why:** Solo single-instance deploy; arq/Redis deferred until multi-instance need.
**Rejected:** Adding Redis/arq now (stack lock + no paying users).

### 2026-08-02 — PCM-4: enforcement beyond AI + UI badges
**Decided:** Shared `protected_enforcement.py` gates Builder, ModuleSpec apply
(`scrub_spec_for_protected_apply` → per-item skips), and Automations (chatter/activity
allowed on tier-1). 422 detail includes `reason`, `safe_alternative`, `docs`. Power Ops
account-move recipes get `protected_tier_note` and remain EXEMPT (Doc 7 batching). UI
badges from `GET /protected-modules` on hub/builder/automations.
**Why:** PCM-3 only covers AI path; direct API mutations must enforce the same effect rule.
**Rejected:** Blocking Power Ops account recipes; hard-failing ModuleSpec apply on one
violation; blocking link-only M2O from custom models into tier-1.

### 2026-08-02 — PCM-3: guardrail injection + structured refusal
**Decided:** Inject `guardrail_prompt(manifest)` into single-shot system/user prompts,
staged steps 2/3/5, and critique; resolve manifest from connection cache else vendored
community snapshot. Deterministic `strip_protected_module_effects` in `ai_rules.py` is
enforcement (strips tier-1 writes; keeps link-only M2O/O2M). API returns `refusals[]`;
wizard shows Protected module panel. Transcript: `docs/research/guardrail_run_2026-08-02.json`.
**Why:** Doc 5 — LLM prompt is first line only; effect-not-mechanism must be enforced.
**Rejected:** Relying on LLM alone; blocking link-only relations to protected models.

### 2026-08-02 — PCM-2: protected manifest Path A+B + per-connection cache
**Decided:** `fetch_community_modules_from_source` (git sparse-checkout → vendored JSON
fallback); `fetch_live_installed_module_names` via existing `client.list_modules`; merged
manifest cached on `odoo_connections.protected_manifest_json`, refreshed on create/probe;
endpoint `GET …/protected-modules`.
**Why:** PCM-1 classification needs version-aware module inventory without GitHub REST API.
**Rejected:** Blocking probe on network failure; 16–18 offline snapshots seeded from real 19.0
git list until per-branch snapshots refreshed.

### 2026-08-02 — SAFE-2c: pre-merge core scaffold seed eliminates generation gaps
**Decided:** After `llm_emit_missing_scaffold_models`, run `seed_missing_core_scaffold_models`
(attorney/bill/compliance/deposit/trust…) from pack scaffold before `merge_domain_pack`.
**Why:** Generation-gap warnings fire only when merge adds omitted core models; LLM repair is flaky.
**Rejected:** Removing generation-gap warnings in merge (would hide real LLM under-coverage in tests).

### 2026-08-02 — SAFE-2b: party-link models stay non-workflow after re-enrich
**Decided:** Extract `is_party_link_model()`; block `apply_pattern_rules` from setting
`is_workflow` on party links; skip kanban views/view_mode in `ensure_default_ui`; run final
`repair_draft_integrity` after post-critique re-enrich in `draft_module_from_prompt`.
**Why:** Quality demote worked but re-enrich + rules re-promoted `x_matter_party` (SAFE-2 v3 FAIL).
**Rejected:** Demote-only without fixing enrich/rules (bug recurred every live draft).

### 2026-08-02 — SAFE-1 baseline .gitignore hardening
**Decided:** Extend root `.gitignore` with `.env.*` + `!.env.example`, Playwright artifact
dirs, and docker bind-mount volume patterns before the initial commit.
**Why:** Card checklist required explicit coverage beyond the pre-existing minimal ignore file.
**Rejected:** Relying on `apps/web/.gitignore` `.env*` alone (would ignore `docker/.env.example` at root level inconsistently).

### 2026-08-02 — Orchestration plan package approved (55 cards, 11 waves)
**Decided:** Full build-out executes from `plans/MASTER_PLAN.md` + `plans/cards/` via cheap
models (Composer 2.5 default, Grok 4.5 for routed cards + all checking). Governing additions:
(1) all four Odoo tiers (Online/sh/Community/Enterprise) are first-class — Enterprise features
driven via public RPC on licensed instances are IN scope; only copying Enterprise/Studio
source stays forbidden. (2) Monetization is a product goal: Solo/Pro/Business/Agency tiers +
internal admin plan, self-hosted accounts auth (argon2id/TOTP/workspaces/roles), Stripe +
Paystack hosted checkout, entitlement registry gating. (3) Former deferral candidates promoted
to cards by user: barcode (CMP-9), approval processes (CMP-10), property parity (CMP-7), EE
view designers (TIER-6), live overlay editing (UIX-6), website editing (UIX-7),
multi-company/i18n/Documents (CMP-11). (4) Checkbox discipline: every card carries a CHECKLIST;
skips require user approval; checker diffs checklist vs code first.
**Why:** User approved the plan and requires cheap-model execution without quality drift.
**Rejected:** Deferring the promoted seven; auth-SaaS dependencies; deciding the 4 remaining
DEFERRALS.md candidates without the user.

### 2026-08-03 — Wave 13 DEV: first-class developer Python path (user-directed)
**Decided:** Three gated developer lanes (WAVE-13-DEV.md): DEV-1 Code Studio — live
`state=code` server actions/automations where a per-instance PROBE proves support (never
assumed by tier), editor + one-record test-run + advanced confirm/snapshot; DEV-2 —
`custom_code_blocks` become writable (developer role) with lint + one-click sandbox loop,
live-apply exclusion intact; DEV-3 — Script Runner: ad-hoc Python against the typed RPC
client in an isolated subprocess (resource limits, import allowlist, no fs/network), journaled
with write counts. All behind `developer` role + `dev_tools` entitlement + SafetyGate risk
class `code`; observer mode refuses. Completes (not contradicts) 2026-07-27 Option A +
advanced-confirm decisions: no-code stays default, code is explicit opt-in.
**Why:** User requires that developers can always write Python directly where instances
allow it.
**Rejected:** Assuming code-action availability by hosting tier; executing scripts in the
API process; letting code blocks into the live apply path.

### 2026-08-03 — Production-trust posture + Wave 12 TRUST (user-directed)
**Decided:** Honest posture: architecture is safety-first (ORM/RPC-only as the user's own
credentials, no SQL — damage bounded to what the user's account can do; corruption-level
damage structurally out of reach) but NOT yet marketable as production-trustworthy: known
enforcement gaps (REM-2), unverified-live bulk paths, clean-instance-only validation,
partial-apply risk. Plan: Wave 11 REM first, then Wave 12 TRUST (WAVE-12-TRUST.md):
observer-mode default + least-privilege onboarding; SafetyGate single choke point with a
route-enumeration meta-test (no mutating endpoint ships ungated); sample-first execution +
caps + anomaly auto-pause + kill switch; backup-artifact-before-destructive + restore
drills; dirty-instance/chaos/concurrency gates; coverage floors + settings-matrix execution
policy; IDOR/supply-chain/app-DB-restore hardening; SAFETY.md trust contract + production
readiness checklist gating production write mode; design-partner beta with written GA
criteria. "Fool-proof" explicitly rejected as a claim — defense-in-depth with honest limits
is the standard.
**Why:** User asked whether live customer DBs are safe; review evidence says structural
safety yes, earned trust not yet.
**Rejected:** Marketing production-readiness now; per-router safety discipline (proven to
fail silently — choke point instead); external analytics SaaS for telemetry.

### 2026-08-03 — Orchestrator review verdict: gates real, claims inflated (Wave 11 REM)
**Decided / proved:** Full-board review after the implementation run claimed all 57 cards
done. Gates independently re-run and CONFIRMED green (API 667/2skip, lint 0 err, vitest 78,
build OK). Code-level diff of every checklist found: PCM-3/PCM-4/UIX-6 FAIL (refusal contract
absent in code, enforcement functions with zero call sites, overlay editor select-only);
confirmed `guard` NameError crashes staged pipeline (never executed by tests); stub tests
masquerading as gates (`kit.test.ts` name list; slot-gate test hits `/health`); BLK-2..7 live
smokes never run; CMP-9 widget lacks bundled zxing. Remediation = WAVE-11-REM.md (REM-1..12),
REM-1 (runtime bug) then REM-2 (security wiring) first. PROGRESS downgraded honestly.
**Why:** Maker-is-never-checker; checkbox discipline requires evidence, not marks.
**Rejected:** Accepting PROGRESS/STATE claims at face value; deleting the [x] history
(annotated downgrades instead); treating green suites as proof when the failing paths were
simply uncovered.

### 2026-08-03 — Hybrid pricing: active-project slots + Project Pass (user-approved)
**Decided:** Value metric = subscription tiers (unchanged) + ACTIVE-PROJECT SLOTS per tier
(Solo 1 / Pro 3 +$15 / Business 10 +$10 / Agency 25 + packs) + a $299 one-time Project Pass
(1 project, Pro-level build features, 60 days → read-only + basic maintenance; upgrade keeps
project). Projects gain active↔archived lifecycle; archiving frees slots instantly and
generously. HARD RULE: slots gate BUILD surfaces only — the operate/maintenance suite (bulk,
health checks, Expert, snapshots) is never project-gated. Pricing anchor = consultant
engagement costs, not SaaS peers. Encoded in WAVE-9-MON cards (MON-2/MON-4) +
`active_projects_limit` entitlement key.
**Why:** B2B/agency buyers derive episodic per-project value; flat monthly under-charged
heavy builders and offered nothing to one-project buyers facing $3k–$10k consultant quotes.
**Rejected:** Pure per-project pricing replacing subscriptions (lumpy, kills MRR + operate
stickiness); metering builds/exports instead of concurrent slots (gameable, disputes);
gating maintenance per-project (churn risk).

### 2026-08-03 — Component-grain AI generation (card AI-8, user-approved)
**Decided:** Draft Studio generates at three grains — field_pack / feature_slice / full_app —
with components plugging into stock Odoo apps OR existing custom apps: intent grading, live
host discovery (stock + `x_` models), an editable "connect points" pipeline step (host,
form tab, menu nesting, smart buttons, FK direction), extension ModuleSpecs (`mode: inherit`,
inferred depends), live-apply + small-module export, stacking collision detection, and a
component gallery (AI-6 generalizer extended; 4 authored seeds). Grok 4.5-routed. PCM rules
bind (tier-1 hosts link-only live; inherit views only — no primary mutation).
**Why:** User wants small connectable components, not only whole apps; generator's `_inherit`
support existed but the AI path never used it.
**Rejected:** A separate "extension builder" product path outside ModuleSpec; padding small
asks into full apps via depth floors.

### 2026-08-02 — UI identity: petrol teal supersedes Odoo purple (flagged supersession)
**Decided:** App chrome uses our own identity — warm neutral scale + petrol/teal accent
(~#0E7569), Inter UI type, dark mode. Supersedes 2026-07-28 "enforce Odoo brand colours"
(#714B67). Odoo-ish styling is allowed ONLY inside Odoo-preview surfaces (designer canvas,
proxied frames), optionally themed from the connected instance's own extracted palette (CMP-3).
**Why:** Approved UI/UX revamp requires a premium distinct identity; trading-dress caution
(Doc 3 §20) argues against shipping Odoo's brand purple as OUR brand.
**Rejected:** Keeping #714B67 as app primary; theming our chrome from customer instances.

### 2026-07-28 — Fix remaining pack/AI gaps (relations, party id, terminals)
**Decided:** Merge overwrites fee-earner M2Os that wrongly target `res.users` when pack has `x_attorney`; set required from pack; rename gold party to `x_matter_party` (match LLM); scaffold teaching lists `required_models` + staff/terminal rules; quality adds terminal statuses and collapses parallel `x_party`.
**Why:** User draft still wrong after prior polish because merge only *added* fields — existing `x_attorney_id→res.users` and truncated statuses stuck; pack `x_party` diverged from LLM `x_matter_party`.
**Rejected:** Leaving wrong relations for a later remap-only pass without merge fix.

### 2026-07-28 — Honest pack/AI split: deepen merge + staff FK + party demote
**Decided:** Merge upgrades thinner selections from pack; warn `generation gap` when pack adds core masters (attorney/bill/…); remap fee-earner M2Os from `res.users` → domain staff model; demote party/role-link `is_workflow` + kanban; scrub automation `filter_domain` status keys not on the model; require `x_name`.
**Why:** Latest draft looked world-class but warnings showed pack supplied attorney/bill/compliance; fee earner FKs pointed at users; party was a fake workflow; limitation auto referenced `closed` missing from status.
**Rejected:** Celebrating pack-filled drafts as pure AI excellence without measuring generation gaps.

### 2026-07-28 — Generation-first world-class (packs teach, not replace AI)
**Decided:** Raise MODEL_CREATION_RULES with WORLD-CLASS OPS DEPTH (11–15); expand few-shot exemplar (O2Ms, party, deposit statuses, line→bill); add `law_firm` pack from gold with canonical `x_attorney`/`x_matter`/… names; inject `scaffold_teaching_blob` into single-shot + staged prompts before generation; keep merge as field/model floor after LLM.
**Why:** User goal is the AI producing world-class ModuleSpecs on its own; domain richness must train generation, not only post-filter.
**Rejected:** Law-only hardcoding without prompt teaching; merge-only pack application as the quality strategy.

### 2026-07-28 — Excellence polish: parent O2Ms + ghost autos + placeholders
**Decided:** After critique/quality: remap/drop autos on missing models (hearing→event); scrub invalid selection values; dedupe per-model follow-up `next_activity` autos; ensure parent O2Ms for child M2Os; link line→bill; replace specialty_a placeholders; form O2M groups use field `string`; deepen task/party with `x_status`; critique refuses unknown-model autos.
**Why:** 8.7–9.0 drafts still had apply-unsafe critique autos on `x_hearing`, duplicate follow-ups, matter form with only hearing O2M + technical group title, and few-shot practice labels.
**Rejected:** Leaving critique autos for post-apply failure; unlimited identical next_activity automations.

### 2026-07-28 — O2M inverse + related_write scrub + partner button cap
**Decided:** Complete O2M fields missing `relation_field` from child M2O; drop duplicate O2Ms to the same child; scrub `related_write` that targets O2M / missing fields / placeholder values (`default`); collapse all `next_activity` rows per automation to one; cap Contacts smart buttons at 4 (prefer workflow headers); scrub `RNT/` help leaks; rebuild forms omitting O2M/binary.
**Why:** Depth-ok law-firm draft still had apply-unsafe shapes (hearing+event both → x_event without inverse; critique autos writing O2M status / `x_rate_id=default`; 9+ partner buttons; RNT exemplar help).
**Rejected:** Leaving incomplete O2Ms for apply-time failure; unlimited partner button_box noise.

### 2026-07-28 — Post-seed UI coverage + partner field canon
**Decided:** Canonical partner FK is always `x_partner_id` (rename `x_client_id`). Enrich fills missing actions/menus for seeded models; rebuilds view arches that reference missing fields; rules fill ACL stubs for every `x_*`. Quality fills empty selections, deepens rate models, dedupes automation safe_actions. Re-enrich triggers on `seeded`.
**Why:** Depth.ok draft still apply-broken — matter views/buttons pointed at `x_partner_id` while field was `x_client_id`; only 4/12 models had menus.
**Rejected:** Preferring `x_client_id` as the partner alias.

### 2026-07-28 — Generation-path model quality (not just post-filters)
**Decided:** Steer the LLM at create-time: `MODEL_CREATION_RULES` in system + staged prompts; few-shot substantive exemplar in every single-shot prompt; staged step1 bans type/tag/stage entities + requires loop_role; step2 enforces min fields + retry if thin; `run_model_quality_pass` collapses hollow catalogs → selections and LLM field-deepen before depth/critique; expand forbids hollow missing_models.
**Why:** User correctly flagged that scoring/stripping after the fact ≠ better model creation; each iteration must improve generation itself.
**Rejected:** Relying only on depth floors / gold JSON references as the quality strategy.

### 2026-07-28 — Depth quality: substantive models + strip unsafe autos
**Decided:** Depth floors count *substantive* models only (hollow name+code catalogs excluded); strip Python/`email_send`/empty critique automations; critique refuses those kinds. Law-firm gold reference: `docs/reference/law_firm_modulespec_gold.json` + `ai_reference_law_firm.py`. Prompt: prefer selections over empty taxonomy models.
**Why:** “World-class law firm” draft hit 11 models by padding type/category/tag/stage/priority stubs while missing time/trust/hearings; automations included forbidden `state=code`.
**Rejected:** Treating raw model_count as depth; allowing code automations through critique.

### 2026-07-28 — Depth-first AI ModuleSpec (packs secondary)
**Decided:** Consistent depth is enforced domain-agnostically via `ai_depth.py`: classify ambition (thin/standard/comprehensive) from the prompt; score models/fields/M2O/workflows/smart buttons/autos; deterministic repairs (synthesize smart buttons from M2O graph, currency/company/workflow fields); LLM expand when floors fail; critique no longer `skipped_complete` when depth gaps remain. System prompt teaches operational-loop depth without hospital-specific must-lists. Domain packs stay offline/retrieval fallbacks only.
**Why:** User priority — robust models for *any* prompt matters more than a hospital pack; prior thin drafts passed structural checklist and skipped critique.
**Rejected:** Relying on curated packs as the primary depth strategy; marking ready=true on menus/views alone.

### 2026-07-28 — Hospital AI depth: dedicated pack + stricter ModuleSpec system prompt
**Decided:** Added `hospital` domain pack (`ai_domain_pack_hospital.py`, 18 models / 20 smart buttons / 5 autos) retrieved before thin `clinic` for hospital/world-class prompts; tightened clinic regex (no bare patient|doctor); system prompt requires apply-ready `x_*` relation fields + `on_*` triggers + 12–20 models for comprehensive asks; rules repair bare `patient_id` / `create`/`write`; gold export `docs/reference/hospital_modulespec_gold.json`.
**Why:** User’s “world-class hospital” draft scored ~clinic toy depth with broken smart buttons/autos; checklist `_ready: true` was structural false confidence.
**Rejected:** Expanding clinic pack alone; claiming HIS/EMR parity (blood bank, HL7, full pharmacy inventory still out of ModuleSpec scope).

### 2026-07-28 — ModuleSpec apply must normalize draft JSON (smart buttons + triggers)
**Decided:** Live `apply_module_spec_ui` treats draft JSON as authoritative: alias smart-button keys (`source_model`/`target_model` → `on_model`/`related_model`), ensure M2O `relation_field` exists on **target** (create or invert if AI put FK on source), alias automation triggers (`create`→`on_create`, `write`→`on_write`), apply `access_rules` (ACL + `domain_force` record rules). Unit tests in `test_spec_apply_smart_buttons.py` / `test_spec_apply_automations.py`.
**Why:** Hospital AI draft had smart buttons + automations; apply yellow-skipped them on enum/key/relation mismatches — user: everything in JSON must be picked up.
**Rejected:** Leaving skips as “AI must emit perfect keys”; silent drop of incomplete buttons.

### 2026-07-28 — UI theme: enforce Odoo brand colours (retire mint green)
**Decided / proved:** Replaced hardcoded mint/green shell hexes across `apps/web` with Odoo brand family — primary `#714B67`, light accent `#c9a9c0`, teal secondary `#017E84` (tokens already in `globals.css`). Landing + app shells now purple radial; primary CTAs solid `#714B67` / white.
**Why:** User called out green theme still live despite prior MEMORY lock for Odoo colours.
**Rejected:** Keeping mint as “accent on purple”; claiming EE brand assets beyond public hexes.

### 2026-07-28 — CE lab: installed base_geolocalize + project on Odoo 19
**Decided / proved:** On `:8069` / `odoo_dev`: installed `base_geolocalize` + `project`. Partner geo fields present (`partner_latitude` / `partner_longitude`). **View types unchanged** — still no `map` / `gantt` / `cohort` (`web_map` / `web_gantt` / `web_cohort` ABSENT on CE). Live M2/A4 map/gantt/cohort creates remain skip-with-reason.
**Why:** User authorized CE-only install; EE still requires subscription they must provide.
**Rejected:** Claiming map/gantt unlocked on Community.

### 2026-07-28 — Live proof: M2/A4 finish smokes on Odoo 19 CE
**Decided / proved:** `tests/test_integration_m2_a4_live.py` — **6 passed**, 3 skipped: activity view, form Can Create attrs, inactive webhook + followers automations, SMS (module present), on_message_received trigger. Skipped map/gantt/cohort because `ir.ui.view` type selection lacks those on stock CE (Designer still emits arch; module-gated honesty correct). Playwright automations **6 passed**.
**Still blocked:** EE live RPC (no EE image).
**Why:** User said continue after unlock finish.
**Rejected:** Claiming map/gantt/cohort live create on CE without those view types in selection.

### 2026-07-28 — Unlock: finish all prior MEMORY-deferred mastery gaps
**Decided:** User authorized **full finish** of prior deferred items: M2 Activity/Map UI/Gantt/Cohort/search facets/form Can Create…/full A4 automations; M4 remaining snapshots; M5 extra EE playbook rows; M3-P2 domain playbooks; M4-P1 `requires_modules`. Order: Activity+search → Map+form attrs → A4 automations → Gantt+Cohort → snapshots → EE rows → docs/tests.
**Still blocked (infra, not defer):** EE **live** RPC against real Enterprise image — keep mocks/grey-out until EE Docker exists.
**Why:** User: “FINISH ALL FULLY” with orchestrator-chosen order.
**Rejected:** Leaving M2/M4/M5 residuals deferred after explicit unlock.

### 2026-07-28 — W0 + M3 fully closed (honest remainders named)
**Decided / proved:** W0 remainders closed where possible: `currency_field` live on 19 (persist) + 16 (omit safely); Odoo 18 live deepened (list models, view arch, ACL); production Automations Playwright (`e2e/automations-prod.spec.ts`). M3-P1: currencies / currency-rates / uom / fiscal-positions APIs with `available:false` when modules absent. Phase audit: `docs/MASTERY_PHASE_AUDIT.md`.
**Was deferred (now unlocked above):** EE live RPC (no EE image); M2 Activity/Gantt/Cohort/full A4 matrix.
**Why:** User required W0 and M3 fully done + full phase pass.
**Rejected:** Claiming EE live or full M2 Studio view parity.

### 2026-07-28 — Checker FAIL remediations (matrix honesty + M5 UI)
**Decided:** After mastery Checker **FAIL**, refresh matrix App column to match shipped code; mark P0 cleared/deferred explicitly in `MASTERY_BACKLOG.md`; add `EePlaybooksPanel` grey-out UI + HTTP tests for EE playbooks; thicken Power Ops pack tests. **Do not claim full M2** (Activity/Gantt/Cohort/A4 matrix remain MEMORY-deferred).
**Why:** Checker correctly rejected stale matrix + missing M5 UI + overstated M2.
**Rejected:** Re-labeling FAIL as PASS without matrix/UI fixes.

### 2026-07-28 — Capability mastery target + R0→M6 shipped
**Decided:** Product target = **customization + day-2 admin mastery** via public ORM/RPC + Option A — not full ERP rebuild, not Studio clone. Research artifact: `docs/research/ODOO_SURFACE_INVENTORY_RAW.md` + `docs/ODOO_CAPABILITY_MASTERY_MATRIX.md` + `docs/MASTERY_BACKLOG.md`.
**Shipped:** M1 hosting_hint / Online Python promote contract; M2 calendar/graph/pivot arch + Designer; M3 paperformat/defaults/property/cron/website; M4 matching-major pipeline + Power Ops packs + menu/report snapshots; M5 EE playbooks grey-out; M6 `docs/DEPLOY.md`.
**Why:** User approved exhaustive mastery plan execute.
**Rejected:** Studio source; claiming Online Python installs; promoting 16 to GA.

### 2026-07-28 — Upgrade-map Phases 0–D complete
**Decided / proved:** Upgrade-map remainders closed: Phase 0 re-verify + Checker PASS; A1–A4; B1 Online copy; C1 kanban + live round-trip; **C2 vision-verify Checker PASS** (`docs/vision-verify/`); C3 Power Ops 16/17. **§5 / HANDOVER §7 still refused.** **16 remains experimental.**
**Why:** User approved upgrade-map plan; remainders + polish only.
**Rejected:** Promoting 16 GA; implementing §5; editing `.cursor/plans/`.

### 2026-07-28 — Odoo 16 deepen batch (still experimental)
**Decided / proved:** Live `:8072` suite deepened — access create (`ir.model.access` + `ir.rule`), `mail_post`/`next_activity` server actions on `res.partner`, field inject inherit on partner form. **10 passed**; `ga` stays False; no `update_path` / related_write claim.
**Why:** CARD A2 deepen experimental 16 without promoting to GA.
**Rejected:** Setting `ga=True` for 16; silent best-effort when states missing (skip-with-reason honesty).

### 2026-07-28 — Promote Community 17 to GA (16 remains experimental)
**Decided:** **17 = GA** alongside 19 and 18 (`ga_majors() == {17, 18, 19}`). **16 stays experimental** (no `update_path` / related_write claim).
**Why / proof:** Live smokes on `:8071`/`:8072` — 12/12 passed including related_write e2e on 17, window action `tree,form`, menus, QWeb reports (see prior MEMORY *Odoo 16/17 menus+reports+related_write smoke deepened*). User authorized HANDOVER completion; do not silent-GA 16.
**Rejected:** Promoting **16** to GA; unlocking ≤15 or 20+.

### 2026-07-28 — Matching-major sandbox live proof (18)
**Decided / proved:** Ephemeral sandbox install OK for **Odoo 18** via `./docker/run-sandbox-major-gate.sh 18` → exit 0; `SandboxResult(ok=True, module=sandbox_smoke_m18, odoo_major=18)` on host **:18069** (`-p odoo-sandbox`, image `odoo:18`). Permanent `:8070` untouched.
**Why:** HANDOVER §4 priority 2 / §6 acceptance — code path existed; live proof was missing.
**Rejected:** Treating unit-only or Odoo-19-only sandbox gates as multi-major proof.

### 2026-07-28 — CI matching-major sandbox = manual dispatch only
**Decided:** `.github/workflows/odoo-sandbox.yml` gains gate `major-matrix` + `sandbox_major` (`matrix`|16–19); ephemeral only (no permanent stacks); weekly schedule stays **extension** on primary 19.
**Why:** Local `:18069` proof green for 16–18; CI remains opt-in (slow/flaky) per earlier audit-log MEMORY.
**Rejected:** Making major-matrix the default Sunday cron.

### 2026-07-28 — Odoo 16/17 menus+reports+related_write smoke deepened
**Decided / proved:** Live integration on `:8071`/`:8072` — 12 passed (related_write e2e on 17; window action `tree,form` + menus + QWeb reports on 16/17; 16 encode/update_path hard-refuse). STUDIO_PARITY menus/reports → ✅ for 16–19.
**Why:** HANDOVER §1.2 / §2.9 required smoke or honest downgrade; smoke succeeded.
**Rejected:** Leaving matrix at ⚠️ without proof; promoting **16** to GA (still no update_path).

### 2026-07-28 — HANDOVER implementable arc closed
**Decided:** `docs/HANDOVER_UNFINISHED_WORK.md` updated to DONE for implementable multi-version follow-through (docs, sandbox proof, CI major-matrix, UI caps, v16 hard-fail, GA **17**, list_view_for_major, Playwright caps e2e). **16 remains experimental.** Intentional §7 + ongoing keep-smokes-green + optional Power Ops/`account` on 16/17 + vision-verify/kanban polish left honest-open.
**Why:** User asked full HANDOVER completion; product floor still refuses silent 16-GA and Studio/§7 items.
**Rejected:** Claiming Property fields / kanban polish / vision-verify as done; promoting 16.

### 2026-07-27 — M2 unlock: Community 18 experimental (19 remains GA)
**Decided:** Allow connecting **Odoo Community 18** for the overlapping safe subset (fields, view inject inherit, safe automations including related_write/`update_path`). **19 stays GA**; 18 is experimental. Docker: `docker/docker-compose.odoo18.yml` on port **8070**. Refuse ≤17 until M3.
**Why:** User unlocked M2 per `MULTI_VERSION_ODOO_PLAN.md`; capability registry + adapters gate features without router `if major`.
**Rejected:** Unlocking 16/17 in this pass; treating 18 as GA; silent best-effort writes outside the declared capability set.

### 2026-07-27 — Promote Community 18 to GA + M3 unlock (17/16 experimental)
**Decided:**
1. **18 = GA** alongside 19 (smoke + Power Ops recipes green after `account` install on odoo18_dev).
2. **M3:** register **17 + 16** as experimental. 17 keeps full safe-subset caps; **16 omits** `RELATED_WRITE_DOTTED_PATH` and `OBJECT_WRITE_UPDATE_PATH` (no update_path-era claim). Docker ports **8071** (17) / **8072** (16). Support floor = **16**.
**Why:** User asked to do all remaining multi-version items; live 18 Power Ops 11/11 after account; plan M3 delivers 17 then 16.
**Rejected:** Claiming 16 related_write without a dedicated pre-update_path adapter; making 17/16 GA without live smoke evidence.

### 2026-07-27 — M4 Enterprise warn-only + Studio parity matrix
**Decided:** Enterprise (`server_version` with `+e` / “enterprise”) is **warn-only**: connect allowed; capability probe message + Designer/Connect banners; **same public-ORM capability set** as Community for that major. Never claim or use Studio/`web_studio`. Document per-major Studio-parity in `docs/STUDIO_PARITY_BY_MAJOR.md`. Power Ops recipes expose `tags` + `min_major`.
**Why:** Operators on Online Enterprise still need metadata customization; copying Studio is forbidden.
**Rejected:** Refusing Enterprise connections; offering Studio-parity features that require Enterprise modules.

### 2026-07-27 — Module export: one zip per connection major
**Decided:** Export produces **one** installable zip whose `__manifest__.py` `version` is `{connection_major}.0.1.0.0` (via `manifest_version_for_major`). Inherit list views use adapter list/tree type + matching xpath (`//tree` on ≤17). No multi-manifest / multi-series bundle in v1. Sandbox/run uses matching-major Docker (`odoo:{major}` on `:18069`).
**Why:** Install target must match the DB you customized; multi-manifest adds complexity without v1 demand.
**Rejected:** Always hard-coding `19.0.1.0.0`; shipping multiple manifests in one zip; validating 16–18 zips only on `odoo:19`.

### 2026-07-27 — Odoo 18 Power Ops gap (honest)
**Found:** Fresh `odoo:18` smoke DB has `account` **uninstalled** — `account.move` missing; accounting Power Ops recipes will fail until account (and deps) are installed in that instance.
**Decided:** Install `account` for Power Ops probe (`test_power_ops_odoo18.py` + `./docker/ensure-account-18.sh`); document that Power Ops needs account on the target DB. Do not auto-install account in every init-db-18 by default (heavy).
**Rejected:** Claiming Power Ops works on bare base-only 18.

### 2026-07-27 — Build system = Cursor Engineering Pipeline (Approach A)
**Decided:** Install pipeline (RULES/PIPELINE/AGENTS/MEMORY/ERRORS/STATE + skills + `.cursor/rules`) before Phase 0 code.
**Why:** Empty repo; compounding memory/gates/checker discipline must exist before RPC/UI work to prevent session drift and confident-but-wrong Odoo API usage.
**Rejected:** B (pipeline + Phase 0 in one pass — higher risk of wrong scaffold assumptions); C (brief-only — delays disk presence of session defaults).

### 2026-07-27 — Stack lock (from production plan)
**Decided:** Next.js/TS/Tailwind + FastAPI/Python 3.12 + Postgres metadata DB + odoorpc/xmlrpc + Jinja2 module gen + Docker sandbox; light queue (RQ/arq) over Celery until needed.
**Why:** Matches solo/budget constraints; Python-native Odoo tooling and future `pytest-odoo` sandbox path.
**Rejected:** Node-only backend (weaker Odoo ecosystem fit); Celery on day one (more moving parts than solo needs).

### 2026-07-27 — Competitive scan: "Odoo Studio Community" options (pending product decision)
**Found:**
1. `Odoo-Studio-Community` GitHub org — SEO shell, only `.github`, no product code. Ignore.
2. `MNametissa/odoo_studio_community` — claims "Studio ported for CE"; headers still say "Part of Odoo", license flipped from `OEEL-1` → `LGPL-3`, depends on `studio_community_base` stubs for `web_enterprise`. **Do not fork/use** — Enterprise IP risk; violates our "never reverse-engineer Studio" constraint.
3. `mahmoudegpro/odoo-studio-community` — clean-room-looking in-Odoo module (OWL editor + `studio.*` models wrapping `ir.model`/`ir.model.fields`, export wizard). Odoo **18**, 2 commits (May 2025), 4★, placeholder author. Possible reference, not a mature base.
4. `bluefoxconsultant/.../bf_studio_light` — narrow Odoo **18** CE field/view injector; active Jul 2026; explicitly not full Studio.
**Not decided yet:** build parallel (external RPC app) vs study/extend mahmoudegpro or bf_studio_light as in-instance module. Differentiator for *our* plan remains multi-instance + sandbox-before-prod, which in-Odoo modules don't give.

### 2026-07-27 — Product path = A (external app) + Studio parity learning (clean sources only)
**Decided:** Continue the external Next.js/FastAPI/RPC platform (Phase 0+). Aim for Studio-class capability/UX by studying **public** Studio feature docs + clean-room OSS (`mahmoudegpro`, `bf_studio_light`) — never Enterprise Studio source or the MNametissa port.
**Why:** Keeps multi-instance + sandbox-before-prod differentiators; avoids OEEL/IP risk; still raises the bar on functionality/polish.
**Rejected:** C (in-Odoo-only pivot); using MNametissa as base.

### 2026-07-27 — App metadata DB = separate Postgres on :5433
**Decided:** `app-db` service in docker-compose (`odoo_custom` DB) distinct from Odoo’s Postgres.
**Why:** Stack lock (Postgres); never mix builder metadata with customer/Odoo DB.
**Rejected:** SQLite-only for Phase 1 (would silently diverge from AGENTS.md).

### 2026-07-27 — Automations: safe subset only
**Decided:** Support create/write/unlink/archive/time triggers + `object_write` (literal value) and `next_activity`. Auto-`ensure_module_installed('base_automation')`.
**Why:** Matches Studio no-code value without code-injection surface (`state=code` / equation compute blocked).
**Rejected:** Exposing Execute Code, webhooks, or evaluation_type=equation in the builder UI.

### 2026-07-27 — Python path = Option A; advanced actions with confirm; rollback-first
**Decided:**
1. Custom Python automations: author → generate module → sandbox test → explicit promote/install to go live (Option A).
2. Admin/advanced actions (code, webhook, equation, destructive deletes, etc.) are **allowed** with Odoo-style warning UI + explicit API confirmation (`confirm_advanced=true` / typed confirm phrase). Operator is assumed to understand ERP risk.
3. Snapshot metadata before risky mutations; provide restore for reversible targets (views, automations, server actions, field defs where possible). Honest limits: dropped DB columns / deleted records may be unrestorable.
**Why:** Power users need Studio-plus depth; confirmation + rollback beats a permanent ban that blocks real admin work.
**Rejected:** B (one-click live `state=code` with only a soft confirm); permanent hard-block of all advanced actions; pretending field drops are fully reversible.

### 2026-07-27 — Phase 6 sandbox isolation
**Decided:** Ephemeral sandbox uses `docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml` on host port **18069** (moved off 8070 so permanent Odoo 18 can own `:8070`), with addons bind-mounted from `docker/sandbox-addons/`. Image is **matching-major** (`ODOO_SANDBOX_IMAGE=odoo:{16|17|18|19}` from connection `server_version` or `SandboxRunBody.odoo_major`). ≤18 DB init uses stop → drop → `compose run -i base,web` → start.
**Why:** Honest install validation for multi-version exports; avoid port clash with `odoo18` stack.
**Rejected:** Always forcing `odoo:19` for every export; sharing host port 8070 with permanent 18.
**Why:** Default compose project name is the folder (`docker`), so sandbox `down -v` previously tore down the primary Odoo stack on 8069.
**Rejected:** Sharing the primary compose project; installing unvalidated zips straight onto customer connections.

### 2026-07-27 — Promote = sandbox token + confirm; install path by target
**Decided:**
1. Promote requires sandbox validation (`validation_id` + matching zip sha256, 2h TTL) **or** `run_sandbox=true`, plus advanced confirm phrase.
2. Local Docker Odoo (`127.0.0.1:8069`): copy zip into `/mnt/extra-addons`, restart, `button_immediate_install`.
3. Remote / no filesystem: `install_mode=data` (ir.model XML) via `base_import_module` — Python model zips are rejected on remote.
**Why:** `base_import_module` cannot execute Python; Option A still needs sandbox before live install.
**Rejected:** Silent promote without sandbox; pretending Python zips import remotely.

### 2026-07-27 — Access rights builder (live ACL)
**Decided:** Live CRUD for `ir.model.access` + simple `ir.rule` (domain string + optional group) via `/access` API and UI page. Groups listed from `res.groups` (`full_name`).
**Why:** Completes Studio v1 parity checklist; custom models created via RPC otherwise lack usable ACL for non-admin users.
**Rejected:** Full ACL matrix / multi-company rule builder in this phase.

### 2026-07-27 — Related fields map to concrete Odoo ttype + `related=`
**Decided:** Studio picker type `related` is API/UI only. On create we send Odoo a concrete `ttype` (`char`, or `many2one` if `relation` set) plus `related=` path and `readonly=True`. Monetary accepts optional `currency_field`.
**Why:** `ir.model.fields` has no `ttype=related`.
**Rejected:** Passing `ttype=related` to Odoo RPC.

### 2026-07-27 — Field view inject defaults to inherit extension
**Decided:** `inject_field_into_views(strategy="inherit")` creates/updates child views named `{model}.custom.{field}.{type}` with xpath arch; `mutate` (write parent arch) requires advanced confirm.
**Why:** Mutating primary module arches breaks upgrades/interop; inherit is Studio-like and reversible.
**Rejected:** Default mutate; silent mutate without confirm.

### 2026-07-27 — Related UX = concrete type + optional related path
**Decided:** Builder dropdown drops standalone `related`; always-visible optional Related path; API still accepts deprecated `ttype=related` alias.
**Why:** Matches Odoo model (concrete ttype + related=); avoids inventing wrong types.
**Rejected:** Keeping related as primary dropdown type.

### 2026-07-27 — Module XML templates must escape user strings
**Decided:** Jinja `|xml` filter (with quote entities) on names/domains/help in data XML; Python code in automations uses CDATA; view `arch` stays raw XML.
**Why:** Adversarial `<`/`&` in labels/code must not break or inject XML.
**Rejected:** Autoescape-all (would corrupt arch).

### 2026-07-27 — Default ACL on model create + promote uninstall
**Decided:** `with_defaults=True` model create also grants `base.group_user` full CRUD via `ir.model.access`. Promote records history in app DB; uninstall requires confirm phrase and marks history `uninstalled`.
**Why:** Custom models were unusable for Internal Users without ACL; promote needed an honest undo path.
**Rejected:** Silent uninstall; auto-dropping DB tables beyond Odoo’s uninstall behavior.

### 2026-07-27 — Phase 7 app API auth = API keys
**Decided:** Protect the FastAPI app with `AUTH_MODE=api_key` (Bearer or `X-API-Key`). Keys hashed (SHA-256) in `app_api_keys`; optional `APP_API_KEY` env bootstrap; one-time `/api/auth/bootstrap` when no keys exist. Default `AUTH_MODE=off` for local pytest/gates.
**Why:** Multi-connection customization API must not stay open on a shared host; OAuth/user accounts are heavier than a solo operator needs for v1.
**Rejected:** Full user accounts / OAuth in Phase 7; auth-on-by-default breaking all existing local gates.

### 2026-07-27 — Record rules in export + CI + rate limit
**Decided:** Export live `ir.rule` rows into `security/record_rules.xml`. Mutating routes get a sliding-window IP rate limit (`RATE_LIMIT_PER_MINUTE`, default 120). CI runs unit + API-without-Odoo on Postgres service.
**Why:** Completes ACL export parity; protects shared API from abuse; keeps CI cheap without requiring Docker Odoo in Actions.
**Rejected:** Full sandbox gate in default CI (too slow/flaky for every PR).

### 2026-07-27 — Audit log + zip-scoped residuals + manual sandbox CI
**Decided:** Append-only `audit_logs` via middleware on mutating requests (`AUDIT_LOG_ENABLED`, default on); list at `GET /api/audit/logs` and Settings UI. On promote, parse model names from the zip into `promoted_modules.models_json` and use those for uninstall residual checks. Live Odoo+sandbox gate runs only via `workflow_dispatch` (`.github/workflows/odoo-sandbox.yml`).
**Why:** Operators need a trail of who changed what; prefix heuristics on uninstall were noisy; heavy sandbox CI must stay opt-in.
**Rejected:** Auditing GET traffic; requiring sandbox gate on every PR.

### 2026-07-27 — Full-phase deepen/harden (Waves A–D)
**Decided:** Ship breadth across all phases in one pass: zip safety + snapshot IDOR fix + connection cascade; destructive CRUD with confirm; search views/menus/XML escape/related; async sandbox jobs + trusted_proxy + DEPLOY.md; shared ConfirmDialog + Vitest; sandbox process lock.
**Why:** User asked to deepen/harden every phase, not only highest-impact items, with a separate rigorous test agent.
**Rejected:** Deferring Wave C Studio items; skipping web tests; leaving sandbox unlocked under async_job.

### 2026-07-27 — Module interop = depends + _inherit + inherit views
**Decided:** Live path keeps `x_*` on any model; field inject defaults to **inherit** xpath child views. Export packages stock-model extensions as `_inherit`, infers `depends` from models/relations (with explicit merge), and documents the model in `skills/module-interop.md`. App DB connection-scoped tables get `ON DELETE CASCADE` FKs.
**Why:** Customizations must compose with `sale`/`contacts`/peer addons the Odoo way — not by mutating primary arches or shipping orphan zips with `depends: ["base"]` only.
**Rejected:** Overwriting base views as the default; inventing a non-Odoo module merge format.

### 2026-07-27 — Extension sandbox + depends picker + Playwright confirm
**Decided:** UI picks installed `ir.module.module` names for export/sandbox `depends` (+ free-form). Sandbox can preload modules via `SANDBOX_EXTRA_MODULES` / `extra_modules` (extension gate uses `sale,account`). Playwright e2e covers ConfirmDialog phrase gate on a harness page (`NEXT_PUBLIC_E2E=1`); CI runs it. Manual workflow can choose smoke vs extension gate.
**Why:** Peer custom modules and stock apps need explicit depends; extension zips fail on a base-only sandbox; confirm UX needs automated coverage without full Odoo in every PR.
**Rejected:** Always installing sale/account on every smoke (too slow); requiring live Odoo for confirm e2e.

### 2026-07-27 — Required many2one needs on_delete restrict/cascade (Odoo 19)
**Decided:** `create_field` auto-sets `on_delete=restrict` when creating a required many2one (override via `CreateFieldRequest.on_delete`).
**Why:** Library loan smoke failed: Odoo 19 rejects required m2o with default `set null`.
**Rejected:** Leaving required m2o creation broken for relational apps.

### 2026-07-27 — Full-scale Library + speed program (plan)
**Decided:** Track work in `docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md`. Library is the reference vertical for “full-scale” (barcode, fines Option A, email reminders, kanban, mail.thread, reports, multi-company). Speed layer priority: wizard/templates → live preview → draft/apply → optional Ollama. No Studio forks, no Celery-by-default, no paid LLM hard dependency.
**Why:** Need a single checkbox tracker spanning domain depth and UX speed without losing Community/RPC constraints.
**Rejected:** Implementing P1 before a written plan; treating Library as a one-off codebase separate from the platform.

### 2026-07-27 — Module export supports model extensions (_inherit)
**Decided:** Generator `ModelSpec.mode=inherit` emits `_inherit` (no `_name`); data mode writes `ir.model.fields` via model search (no new `ir.model`). Views can set `inherit_xml_id` + mode=extension with xpath inject helpers. `ModuleSpec.infer_and_merge_depends()` maps stock models → modules (`sale.order`→`sale`, etc.). Export auto-detects stock models with manual `x_*` fields (`include_extensions`, optional `extend_models` / `depends` override).
**Why:** Interop requires packaging extensions on `res.partner` etc., not only new `x_*` models.
**Rejected:** Exporting only custom models; inventing ACL/xmlids for stock models.

### 2026-07-27 — App wizard scaffolds live with fixed library model names
**Decided:** `POST /connections/{id}/apps/scaffold` applies templates via RPC (`with_defaults` + field create + inherit inject). Library uses fixed `x_lib_category` / `x_lib_book` / `x_lib_loan` (optional `technical_prefix` override). Existing models are skipped with warning; missing fields still added. Requires advanced confirm phrase. Portable twin: `library_module_spec()` → zip for sandbox (`docker/run-sandbox-library-gate.sh`).
**Why:** Stable technical names for export/menus; idempotent re-runs; confirm matches other multi-mutation advanced actions.
**Rejected:** Always-uuid-suffixed model names (breaks stable menus/export); skip-confirm for library when AUTH off (inconsistent with advanced-actions skill).

### 2026-07-27 — P3 circulation: fines/reminders Option A + optional Ollama
**Decided:** Library portable zip includes (default on) fine `python_automations` + `action_compute_fine`, overdue `mail.template` + `ir.cron`, barcode form widget + search + window action. NL assist is `AI_ASSIST=off|ollama` — draft-only JSON, never auto-apply. Domain/selection visual builders for automations + record rules.
**Why:** Matches plan D3/D4; Community-safe barcode char+widget; Option A for Python fine logic.
**Rejected:** Live `state=code` without module path as default; paid LLM dependency; auto-apply NL drafts.

### 2026-07-27 — P4 reporting + multi-company naming split
**Decided:** Library menus are explicit (Books/Loans/Active Loans/Categories). Active Loans domain is `[('x_returned','=',False)]` (not `context_today`). Loans action includes pivot/graph. `multi_company` adds zip `company_id` + company_ids rules; live scaffold uses `x_company_id` (RPC x_* rule). Stats via `GET .../library/stats` + connection strip. UAT via `docker/run-library-uat.sh`; CI workflow_dispatch `library`.
**Why:** Odoo domain XML/eval for context_today is fragile; live fields must be `x_*`; zip follows stock multi-company field name.
**Rejected:** Shipping only overdue-with-context_today as default Active Loans domain; using non-x_ company field on live RPC create.


### 2026-07-27 — Full-scale library program scope approved
**Decided:** Treat Library as the **reference vertical** that drives the speed layer (wizard, preview, drafts, builders, async jobs, export/sandbox). Ship full-scale acceptance via portable zip + live scaffold; Option A for Python fines/reminders; Ollama optional draft-only; no Studio/Enterprise source.
**Why:** One vertical forces platform generality; public ORM/RPC + sandbox gates match product constraints.
**Rejected:** Separate Library product codebase; Celery day-one; paid LLM hard dependency; multi-version Odoo in v1.

### 2026-07-27 — Plan open questions closed
**Decided:** barcode = char+widget (no `barcodes` module dep); Open-in-Odoo over preview proxy; copies integer default; live scaffold default (draft opt-in); Mailhog deferred.
**Why:** Fastest correct Community 19 path; avoids iframe/X-Frame rabbit hole and inventory complexity.
**Rejected:** Same-origin proxy now; per-copy inventory as default; draft-as-default scaffold.

### 2026-07-27 — AppBlueprint + Designer A/B/C
**Decided:** Shared `odoo_client.blueprint` applies labeled form layouts for all scaffolds (library authored; CRM/Inventory auto Identity/Details/Lines). Designer defaults to inherit saves, parses arch round-trip, supports buttons/search filters/create-field/polish-form, and same-origin Odoo preview proxy. Settings load repo-root `.env` so `AI_ASSIST=ollama` works when uvicorn cwd is `apps/api`.
**Why:** Library-only layouts weren’t enough; Designer needed Studio-parity path without Enterprise source; AI looked “off” due to env file path.
**Rejected:** Keeping library-hardcoded layouts; iframe-only preview without proxy.

### 2026-07-27 — Designer buttons = type=action (not object stubs)
**Decided:** Form buttons bind to real `ir.actions.server` (safe `object_write`) and `ir.actions.act_window` (related `active_id` domain) via `type="action"` + numeric action id. Header + smart button box in FormViewSpec. Python `type="object"` / `state=code` remain Option A only.
**Why:** Custom `x_` models have no Python methods over pure RPC; verified on Odoo 19 that action-id buttons work. Matches Studio capability without Enterprise source.
**Rejected:** Fake `action_placeholder` object buttons; live `state=code` from Designer.

### 2026-07-27 — Phase 2 Studio polish + Automations bridge
**Decided:** Ship full M+L bar in one pass: `next_activity` + `mail_post` button/automation actions; smart-button computed counts (confirm); statusbar; DomainBuilder in Designer; list decorations info/muted; xpath inherit editor; preview no-store + banner + refresh; reciprocal Designer↔Automations nav. Automations was intentionally skipped in Phase 1 (Designer-only) and is now connected.
**Why:** User asked for Phase 2 + finish labeled Next(M)/Later(L) without leaving Automations orphaned. Computed count fields verified creatable via `ir.model.fields` compute on Community 19.
**Rejected:** Leaving Automations disconnected; count badges only via Option A Python modules.

### 2026-07-27 — Activity assignee field resolution
**Decided:** `next_activity` generic assignee resolves `user_id` → `create_uid` → `write_uid` on the target model.
**Why:** Live UAT on `x_lib_book` crashed with KeyError `user_id`; custom models usually lack CRM user fields.
**Rejected:** Requiring operators to always pass `user_type=specific`.

### 2026-07-27 — Robust AI drafts = Ollama + domain packs + Generate UI
**Decided:**
1. Enrich NL drafts with curated **domain packs** (first: `car_rental`) merged after Ollama (or alone when AI is off and the prompt matches).
2. Post-process every draft: default actions/menus/list+form(+kanban) arches, statusbar when `x_status` exists, smart_buttons + automations metadata.
3. Wizard **reuse** picker feeds existing models (`res.partner`, …) into the prompt/draft.
4. **Generate UI from JSON** (`POST …/module-spec/apply`) creates models/fields/views/menus/smart buttons with advanced confirm — automations remain review-only.
5. First-class **Car Rental** wizard template shares the same pack.
**Why:** Thin LLM ModuleSpecs (Car + Rental Request) are not product-grade; packs + apply-UI close the gap without auto-mutating from draft alone.
**Rejected:** Auto-apply on draft; inventing new domains without packs; live `state=code` automations from AI.

### 2026-07-27 — AI architecture: provider + staged pipeline + rules + meta sidecar
**Decided:**
1. `LLMProvider` interface with `ollama` and `openai-compatible` backends; default Ollama model `qwen2.5:7b-instruct-q4_K_M`; always `format:json` / `response_format=json_object`.
2. Domain library expands (car rental, clinic, field service) with regex + Jaccard tag retrieval (embeddings deferred — no sentence-transformers until needed).
3. `AI_PIPELINE_MODE=single|staged` — staged runs Step 0–6 (LLM for judgment steps; views/menus deterministic).
4. `ai_rules.validate_and_enrich_draft` is the reliability backbone (integrity, sequences, mail mixins, overdue safety net, access stubs, checklist).
5. Generated zips embed `.meta.json` ModuleSpec for own-output Code→UI round-trip; arbitrary AST/XML import remains Later.
**Why:** Matches the design doc’s highest-ROI path without paying RAG/embedding tax yet; keeps ModuleSpec as the single contract.
**Rejected:** Hosted paid LLM as v1 default; full third-party module AST parser in this pass; requiring embeddings for 3 packs.

### 2026-07-27 — Tranche 1: MiniLM RAG + self-critique (stable)
**Decided:** Ship AI-quality tranche first: optional `sentence-transformers` RAG (`AI_RAG=auto`, extra `ai-rag`) with Jaccard/regex fallback; self-critique (`AI_CRITIQUE=auto`) with deterministic checklist always + LLM repair of missing `x_*` fields/models/automations. Defer visual ModuleSpec builder and third-party AST/XML import until this path is solid.
**Why:** User chose approach 1 (AI prompt/response quality) over all-four parallel; fallbacks keep drafts working without the embedding package.
**Rejected:** Blocking drafts on embeddings; critique inventing non-`x_` fields.

### 2026-07-27 — ModuleSpec visual builder + Code→UI import
**Decided:** Ship `/connections/{id}/modulespec` visual editor bound to ModuleSpec; `POST /api/module-spec/import` parses zip/.meta.json/.py/.xml via AST + ElementTree; unmapped methods/records preserved as `unmapped` (view-as-code). Wire Wizard drafts + Projects “Edit ModuleSpec”.
**Why:** Completes the deferred contract surfaces after RAG/critique; partial-fidelity import is safer than silent drops.
**Rejected:** Full Python execution of imported modules; pretending all business methods are visually editable.

### 2026-07-27 — Smart buttons = inherit only (never stock primary)
**Decided:** Generate UI injects smart buttons via upsert inherit `{model}.studio.smart_buttons` (`button_box` inside, or create box before first sheet child). Never rewrite stock primary forms; refuse explicit-view / polish writes on non-`x_` models.
**Why:** Mutating `res.partner` primary broke Contacts inherits (`//field[@name='phone']`). Inherit matches field-inject / Designer patterns and stays user-friendly (Contacts smart buttons still appear).
**Rejected:** Skipping partner back-ref buttons entirely; mutating primary then hoping stock xpaths survive.

### 2026-07-27 — Config Ops: Import + Power Ops + Odoo chrome
**Decided:**
1. Differentiator = Odoo.sh-class power on Online via RPC orchestration (not “document refusals”).
2. Bulk CSV/XLSX import (`/data-import`) with dry-run + phrase confirm on commit.
3. Power Ops recipe engine (`purge_journal_entries` = button_draft→unlink flagship).
4. Odoo colour tokens (`#714B67`) + FormCanvas; view overwrite/stock polish require ConfirmAdvanced; access/rule rollback implemented.
**Why:** Operator pain is UI one-by-one and missing bulk tools, not missing API rights.
**Rejected:** Treating Online UI limits as API impossibles; mutating stock primaries without phrase.

### 2026-07-27 — Phase D: related_write + ACL matrix + change journal + config
**Decided:**
1. `related_write` is a first-class safe automation (`update_path` = `relation.field` via `object_write`).
2. Access matrix (groups × models) is now in scope (supersedes earlier “reject full matrix” Phase-1 deferral).
3. Change journal = connection snapshots + Undo; audit logs secondary/filtered.
4. Settings page covers company, sequences, field-label CSV, and app menu builder — not full i18n packs.
5. ModuleSpec / Generate UI **auto-applies** safe automations by default (`apply_automations=True`): related_write, update_field/object_write, activity when `activity_type_id` present.
**Why:** Car-rental / day-2 ops need related writes and ACL grids; drafts should not leave related_write as manual-only.
**Rejected:** Full `ir.translation` UI as v1; visual menu builder / multi-env promote in this pass.
**Supersedes:** Same-day rejection of auto-applying related_write from Generate UI.

### 2026-07-27 — Multi-version Odoo = plan only; v1 stays 19
**Decided:** Draft `docs/MULTI_VERSION_ODOO_PLAN.md` (capability matrix + adapters + Docker matrix). Do not unlock non-19 writes until M0/M1 extract and an explicit MEMORY stack-lock change.
**Why:** Cross-major automation/view drift is real; claiming “any version” without adapters is unsafe.
**Rejected:** Silently relaxing AGENTS.md “Community 19 only” without gates.

### 2026-07-27 — M0 compat extract shipped (still 19-only runtime)
**Decided:** Add `packages/odoo-client/compat/` with `CapabilityId` + 19-only registry; extract automation encoding + view-inject naming into `adapters/automation_v19.py` and `adapters/views_v19.py`. `OdooClient.connect()` still refuses non-19.
**Why:** Plan M0 prerequisite before multi-version; routers stay facade-only; encoding lives in one place for future majors.
**Rejected:** Registering 16–18 capability sets or unlocking non-19 writes in this pass.

### 2026-07-27 — M1 capability probe UI (still 19-only writes)
**Decided:** Expose registry-backed `capabilities` on `ConnectionOut` / `ProbeResult`; show badge + expandable checklist on `/connect` and connection browse. No live per-feature RPC probes in M1.
**Why:** Operators see what the platform claims for this major before first write; grey-out of builder features waits until non-19 majors exist.
**Rejected:** Overloading Power Ops recipe probe; persisting capabilities in DB (derived from `server_version`).

### 2026-07-27 — Report lite → module zip export
**Decided:** Live export packages custom QWeb PDFs (`x_*` models + `custom.*` keys) into `report/reports.xml` via existing `ReportSpec`; generator path renamed from `loan_reports.xml`.
**Why:** Round-trip report lite into Path C (sandbox → promote) without a second report model.
**Rejected:** Emitting paperformat records / full raw arch passthrough in this pass; unlocking M2 multi-version without MEMORY change.

### 2026-07-27 — Phase D+ ops surfaces fully wired
**Decided:**
1. Settings covers company (expanded), sequences CRUD, mail templates, activity types, lang-scoped translation CSV.
2. Visual menus/actions at `/menus` (tree + bind + delete confirm).
3. Report lite at `/reports` (QWeb create/edit + paperformat).
4. Multi-env at `/pipelines`: sandbox → staging → prod; prod requires prior staging hop for same zip sha256.
5. Industry seed packs on Bulk Import (car_rental, library, clinic, field_service, partners, products).
**Why:** Operators asked for full (non-stub) day-2 parity beyond matrix/related_write.
**Rejected:** Stub pages; treating Online UI limits as blockers for promote hops.

### 2026-07-28 — B1 Online SaaS / Enterprise packaging copy (closed)
**Decided:** Canonical packaging copy in `docs/USER-GUIDE.md` § Odoo Online / Enterprise and aligned `docs/STUDIO_PARITY_BY_MAJOR.md` decision lock #4: **warn-only** banner UX (probe + Designer), **public ORM/RPC metadata only** (Community-like caps per major; **never** Studio/`web_studio`), Online **version follows host** (packaging wording only), **Power Ops RPC-first** regardless of Online vs self-hosted.
**Why:** CARD B1 — one operator-facing story without implying Studio parity or a fake Online capability tier.
**Rejected:** Editing `docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md` for this card; unlocking **16** to GA.

### 2026-07-28 — B2 FULL-SCALE Library 19-primary (confirmed)
**Decided:** `docs/FULL-SCALE-LIBRARY-AND-SPEED-PLAN.md` §1.3 unchanged — platform multi-version live; Library reference vertical smoke, UAT, and CI gates remain **19-centric** (19-primary).
**Why:** CARD B2 confirmation; compat layer serves other majors without moving Library full-scale gates off 19.

### 2026-08-03 — REM-14 live-evidence deviations
**Decided:**
1. Staged live run uses `qwen3:8b` with 300s step timeout (`docs/research/staged_run_fixed_2026-08-03.json`, `"mode":"live"`).
2. Stripe extra-slot checkout already `mode=subscription` — no SKU rename (A7 satisfied as-is).
3. `test_inspection_checklist_live_odoo19` skipped — docker-19 lacks `project` module; unit + sandbox paths cover AI-8.
4. Deploy-stack `LAUNCH-1` partial — `/health` OK but `/api/billing/plans` 404 on deploy API image (log: `docs/research/launch_compose_smoke_2026-08-03.log`).
5. Playwright e2e harness requires fresh build with `NEXT_PUBLIC_E2E=1` — reusing deploy :3000 serves 404 on `/e2e/*`.
**Why:** Honest live gates without fixture relabeling; deviations are env gaps not code stubs.

---

## GA decision log template (TRUST-9 — copy for each GA review)

**Date:** YYYY-MM-DD  
**Reviewer:**  
**Evidence sources:** `GET /api/admin/trust-telemetry`, `GET /api/admin/ga-criteria`, partner weekly attestations, `test_safety_route_registry` CI green

| Criterion | Threshold | Observed | Pass? |
| --- | --- | --- | --- |
| Beta partner workspaces | ≥ `BETA_GA_MIN_WORKSPACES` (default 8) | | |
| Weeks active per workspace | ≥ `BETA_GA_MIN_WEEKS` (default 4) | | |
| Unrecoverable-data incidents | 0 | | |
| SafetyGate bypasses | 0 | | |

**Telemetry roll-up (beta partners only):** bulk runs __ · refusals __ · aborts __ · restores __ · anomaly trips __

**Decision:** ☐ Proceed to GA (`PRODUCTION_WRITE_MODE_GA_UNLOCKED=1`) · ☐ Extend beta · ☐ Block — reason:

**Follow-ups:**
