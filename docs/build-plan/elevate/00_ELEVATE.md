# Elevate: every Ingenium feature, raised above its spec (21 Oct 2026)

Tope (21 Oct): "massively upgrade **all** the features in Ingenium (EVERYTHING…) on UI, UX, security, functionality, reliability & fidelity, useablility… recommend features you think will take this app to the next level for every feature and add them to the plan."

**How this relates to the rest of the plan.** The ledger (1,186 rows) already maps every "What's left" item in handover §3.1-3.18, §4 and §5 to a planned Stage 3 card. Those cards bring each feature **to its spec**. Elevate adds two things on top, and never repeats a ledger item:
1. **One measurable Feature Excellence Bar** (§1) that every feature must pass. Each feature gets one BAR card that measures it and fixes the gaps.
2. **Next-level features** (§3) that are not in any spec today. Under INV-06 they are proposals: Tope approved them in principle on 21 Oct (DEC-045) and can strike any one. A struck card is set to `blocked` with the reason, never deleted.

Cards: `cards/phase-7/EL-*.md` (phase 7 = Elevate; it runs after a feature's Stage 3 spec cards are done). Every card is Grok-buildable: context pack, file allow-list, steps, testable ACs, Tester and Reviewer in separate sessions. Every owner-visible screen meets the UI bar (handover §5, `UI_REFERENCE_MAP.md`, `07_UI_EXCELLENCE_PROTOCOL.md` once Stage 2 writes it; Tope: "the absolute best design on every screen"). Brand: `docs/brand/README.md` (chrome rule, assets identical to `apps/web/public/brand/`, verified 21 Oct).

## §1 The Feature Excellence Bar (measured by `scripts/excellence_scorecard.py`, card EL-X-BAR)
A feature passes only when every check below is green for every route and endpoint it owns. The scorecard prints one row per check and exits non-zero on any red.

| Dimension | Check (how it is measured) |
|---|---|
| UI | Every screen has designed empty, loading (skeleton, not a bare spinner), error, offline and success states (states preview test); axe contrast AA in light and dark; tokens only, no raw hex (existing lint); one primary action per screen |
| UX | A keyboard-only walkthrough of the main task passes (Playwright); every action says what will happen before it happens; every write shows a receipt with Undo; copy passes the jargon guard (INV-04) |
| Security | Every API route declares an access dependency (EL-X-AUTHZ); every mutating endpoint takes a typed Pydantic body (no raw `dict`); every Odoo write goes through the write gate (REL-STATIC-WRITE); no secret or PII in logs (existing scrub test); any LLM input from the database is fenced (SEC-REDTEAM-EXT) |
| Reliability | Every async path handles errors into the one error envelope (EL-X-ERRORS); mutating endpoints accept an idempotency key; editors autosave drafts (EL-X-RESILIENT); the feature's SLO is defined and reported (OBS-HEALTH) |
| Fidelity | Anything that shows Odoo matches Odoo: structure re-read from the combined arch, live on 17-20 (EL-X-FIDELITY); every number on screen comes from the connected DB or says "Example" (INV-15) |
| Usability | Time to first success on the main task is measured in a scripted Playwright run and stays under the feature's target; help is one click away on every screen; nothing important hides behind hover only |
| Performance | Handover §5.12 budgets (INP < 200 ms, route JS budget) enforced on the feature's routes; lists over 200 rows are virtualised and paginated |

## §2 Cross-cutting cards (build first; every BAR card depends on EL-X-BAR)
Tenancy, the red-team pack, the static write check, observability and Code Runner limits are already handover requirements (§6.2, §6.6, §7.2, §7.7, §6.9). They live in SEC-TENANCY, SEC-REDTEAM-EXT, REL-STATIC-WRITE, OBS-HEALTH and V-SEC-CR-SANDBOX, which gained the Elevate additions (ratchet baselines; database labels from the view map in the red-team corpus; receipt-with-Undo check; per-feature SLOs; an escape corpus).
| Card | What it adds | Why it matters |
|---|---|---|
| EL-X-BAR | The scorecard script and per-feature route map | Turns "excellent" into a red/green list |
| EL-X-AUTHZ | Test that enumerates every FastAPI route and fails if one lacks an access dependency | One forgotten route is a data leak |
| EL-X-ERRORS | One error envelope and a plain-language error catalog (code → what happened → the fix → retry) across API and web | No raw stack traces, no "Something went wrong" |
| EL-X-RESILIENT | Network-loss banner, retry with backoff, autosave of every editor draft (brief, view, report, script, flow) | Nobody loses work |
| EL-X-FIDELITY | One structure-fidelity harness (render, apply, re-read combined arch, compare) shared by App Studio preview, View Designer, Wireframe and Report proof | "Looks like Odoo" becomes "is Odoo" |
| EL-X-EDGE-RECORDS | Edge-case record picker (longest name, empty fields, most lines, archived, other currency, right-to-left language) for any preview | Layouts break on real data, not demo data |
| EL-X-IMPACT-GATE | Before any delete, rename or type change in any tool: list every view, automation, report, server action, Bridge mapping and saved script that uses it (`SchemaGraph.find_usages`), and block until the owner confirms | Stops silent breakage across tools |

## §3 Features: bar card + next-level recommendations
Each feature has `EL-BAR-<F>` (measure with the scorecard, then fix every red within the feature's own files, one change at a time) plus the next-level cards below. App Studio's raise is the App Studio Pack (`app-studio/`), so it has no EL cards except where noted.

| Feature (handover §) | Next-level card | What it does for the user |
|---|---|---|
| Home / Command center (3.1) | EL-HOME-SINCE | "Since you were last here": what changed in each database (new apps, failed scheduled jobs, drift, dead letters, expiring keys), each with a one-click action. Computed by code |
| | EL-HOME-HEALTHX | Health score you can act on: every point lost links to the tool that fixes it, with a 30-day trend |
| Connect (3.2) | EL-CONN-LEASTPRIV | Rights advisor: checks the Odoo user Ingenium connects as and recommends a dedicated integration user with only the groups Ingenium needs, with a guide |
| | EL-CONN-DOCTOR | Background connection doctor: detects an Odoo version change, new or removed apps and key expiry, refreshes the live schema, and triggers the upgrade check |
| View Designer (3.4) | EL-VD-WHO-ELSE | Inheritance conflict view: shows every other module's view that touches the same spot and warns before an edit that would collide |
| | EL-VD-EDGE | Preview against edge-case records (EL-X-EDGE-RECORDS) with layout warnings |
| | EL-VD-GROUNDED-AI | "Edit with AI" places by labels and containers from the view map (AS-GROUND-VIEWMAP) and verifies by re-read |
| Report and email designer (3.5) | EL-RPT-EDGE | Proof against edge-case records: most lines, long names, other currency, other language |
| | EL-RPT-DELIVER | Email deliverability check: SPF, DKIM and DMARC of the sending domain, broken links, image weight, a plain verdict before "Send me a test" |
| Website builder (3.6) | (bar card only) | Scope is still unconfirmed (handover §3.6); next-level cards wait for that call |
| Configuration Suite (3.7) | EL-SUITE-BASELINE | Approved configuration baseline: snapshot "how this database should be set up", alert on changes made directly in Odoo, restore through a Change batch |
| Imports (3.8) | EL-IMP-RECONCILE | Control totals: sums and counts by key columns in the file versus Odoo after import, signed into the import report |
| Bridge (3.9) | EL-BR-REPLAY | Replay last week: run a new flow version against recorded real events in a sandbox and diff the results against the current version before rollout |
| | EL-BR-EGRESS | Outbound allow-list per flow: a flow can call only the hosts it declared; private and metadata addresses are always refused |
| Code Runner (3.10) | EL-CR-EXPLAIN | "What this run did", computed by code from the observed changes: records touched per model, fields changed, money moved |
| Bots and Expert (3.11) | EL-BOT-EVAL | Per-bot check suite (golden tasks + grant-violation attempts) with the result shown on the bots page ("passes 48 of 50 checks") |
| | EL-BOT-HANDOFF | When a bot can't do something, it opens a ready draft in the right tool (App Studio brief, Suite plan, Bridge flow) with the context filled in |
| Live Demo Co-Pilot (3.12) | EL-LDC-REPLAY | Meeting replay bench: recorded transcripts with timing run through the full pipeline offline, scoring question detection, label accuracy and answer latency without a live meeting |
| | EL-LDC-SHOWME | Every whispered answer carries a "Show me" link that opens the exact screen in the demo database |
| Wireframe (3.13) | EL-WF-ROUNDTRIP | After install, the built screen is re-read and laid over the sketch; each region shows matched, moved or missing |
| Approvals (3.14) | EL-APR-RISK | Risk-ranked inbox: each item scored by code on records affected, money, and whether it can be undone, with waiting time |
| History (3.15) | EL-HIST-WHY | "Why does this look like this?": click any element in an Odoo preview to see which change, tool, person and time put it there, with Undo |
| Cmd-K (3.16) | EL-CMDK-FRECENCY | Results ranked by how often and how recently this person used them, per database |
| Models, menus, access, automations (3.18) | EL-AUTO-BACKTEST | Automation backtest: "this rule would have fired 14 times in the last 30 days on these records", before it goes live |
| Job Autopilot (3.18) | EL-JOB-GOLIVE | Go-live readiness: users invited, access tested, numbering set, mail working, opening balances, backups, as one checklist and a signed readiness report |
| Settings, team, billing, admin (3.18) | EL-SET-SIGNIN | Ingenium sign-in hardening: two-step codes (TOTP), see and revoke sessions, optional single sign-on (OIDC); unlocks named approvers |
| Draft Studio (3.3) | AS-DRAFT-ADOPT (phase 3) | Draft Studio drops domain packs and runs the App Studio v3 pipeline, once v3 passes its release bars (DEC-043) |

Bar cards: EL-BAR-HOME, EL-BAR-CONN, EL-BAR-VD, EL-BAR-RPT, EL-BAR-WEB, EL-BAR-SUITE, EL-BAR-IMP, EL-BAR-BR, EL-BAR-CR, EL-BAR-BOT, EL-BAR-LDC, EL-BAR-WF, EL-BAR-APR, EL-BAR-HIST, EL-BAR-CMDK, EL-BAR-BUILD, EL-BAR-JOB, EL-BAR-SET, EL-BAR-CLIENT.

## §4 Order
1. EL-X-BAR and EL-X-AUTHZ (security first; small).
2. EL-X-ERRORS, EL-X-RESILIENT, EL-X-FIDELITY, EL-X-EDGE-RECORDS, EL-X-IMPACT-GATE.
3. Per feature, after its Stage 3 spec cards: EL-BAR-<F>, then its next-level cards.
4. Release: every feature's scorecard green on 17-20; Tope rates each screen ≥ 8.
