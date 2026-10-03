# Cards — T8 P5 approval UX, P5B bot layer, P8 pilots

Self-contained. Bot layer rules: `../T8_BOT_ENGINE.md` lines 327–402 (Part 17). Approval rules: `../02_APPROVAL_FLOW.md`. UI rules: `../T7_UI_MOTION_COPY.md` and the route blocks in `../13_UI_SCREEN_SPECS.md`. No bot feature may weaken INV-01–INV-20.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **Bot-specific:** display name pattern `Ingenium Bot · {role}`; do not copy xAI, Grok, or Cursor brand assets (Grok notes are research only, conflict row 18); a checkmark or any reaction is never an approval; R ≥ 2 is never approved from chat without the diff page; Chief of Staff cannot approve, widen a grant, or apply; a team bot runs as the requester's role, never as admin (RT-39); presence is driven 100% by the state machine; routine "Test" performs zero writes and zero outbound; standing rules cover R0–R1 only (plus the L4 narrow band under D10), default expiry 90 days, 30 at L4; Guided Browser is Phase 9+ and not built here.

**Limits (copied):** max 50 bots and rooms per workspace; max 6 bots per room; max 50 routines per bot; last 20 routine runs retained; secrets ≤ 25 per bot by default. Rooms: 2–6 bots, typed handoff JSON, max hop 4, max fan-out 3, stall nudge once after 30 minutes then escalate, taint propagates. Routines: modes `report_only`, `draft_changeset`, `may_apply_r1`; schedule floor 15 minutes; Odoo poll floor 5 minutes; chatter poll floor 1–5 minutes; auto-pause after 3 consecutive failures. Effective permission = grant ∩ requester ∩ tenant ∩ model tier ∩ protected registry ∩ capabilities.

**Presence states (copied):** idle, acknowledged, thinking, working, waiting_user, waiting_approval, blocked, applying, verifying, done. **Cards (copied):** plan, approval, diff, access matrix, impact, simulation, verify, evidence, question, routine, handoff, drift, report, email draft. **Starter roster (copied):** Chief of Staff (R0), Configurator (R2), Studio (R2), Access (R3), Data (R3), Doctor (R0), Auditor (R0 plus drafts), Scribe (R0), Release, Front Desk (R0 plus drafts), Consultant (R0), domain specialists, Ops.

**Tables to add (copied; prefer extending `audit_logs`/the chain over a new audit table):** `bot`, `bot_grant`, `bot_memory`, `room`, `room_member`, `handoff`, `routine`, `routine_run`, `plugin_install`, `bot_template`, `workspace_file`, `presence_event`, `notification`, `standing_rule`, `identity_map`.

**Code today:** `apps/api/app/bots/grant.py` (`BotGrant`, `decide`, `install_template_grant`; `test_grant_intersection_blocks_a_wider_request`, `test_grant_cannot_permit_r4`, `test_template_grant_is_not_installed_without_a_human`, `test_runtime_drops_an_op_outside_the_grant`). Nothing else in the bot layer exists.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_handlers_grants_skills.py tests/bots
pnpm --filter @odoo-custom/web test -- src/app/bots
pnpm --filter @odoo-custom/web test:e2e e2e/bots.spec.ts   # created by T8-BOT-ROSTER; does not exist yet
```

**Audit events:** `handoff`, `routine_run`, `approval`, `apply`, `grant`, `revoke`, `tool_call`, `error`.

---

## P5 — approval UX and API

| Card | Gate | Status | Acceptance | Pressure |
|---|---|---|---|---|
| T8-P5-E2E | GATE-P5-01 | OPEN | Playwright: ask → plan card → approve → apply → verify on a fake port | 10 |
| T8-P5-PAGE | GATE-P5-02 | SEEDED (`/approvals`, T6-04/05) | approval page renders the nine sections; R3 two slots; expiry visible | 10 |
| T8-P5-SSE | GATE-P5-03 | OPEN | SSE stream resumes after a reconnect from the last event id | 9 |
| T8-P5-RBAC | GATE-P5-04 | SEEDED (T6-07) | RBAC, IDOR, isolation tests on every new bot route | 12 |
| T8-P5-A11Y | GATE-P5-05 | OPEN | axe + narrow viewport on the approval and run pages | 7 |
| T8-P5-KILL | GATE-P5-06 | OPEN | kill switch stops runs within seconds (measure) | 10 |

## P5B — bot layer (depends_on T8-EXEC and T6-04)

### T8-BOT-ROSTER — Roster and limits (GATE-P5B-01, P5B-08)
- **Status:** OPEN
- **Pressure:** C2 U1 F1 K2 V1 I1 +0 = 8 → Grok standard
- **Change:** migration for `bot`, `bot_grant`; `apps/api/app/bots/roster.py`; `routers/bots.py`; web `apps/web/src/app/bots/page.tsx`.
- **Acceptance:** [ ] limits enforced (50 / 6 / 50 / 20 / 25); [ ] starter roster onboarded in under 15 minutes (timed walkthrough); [ ] display names follow the pattern.
- **Negative:** the 51st bot is refused with a plain message.

### T8-BOT-GRANT — Effective permission (GATE-P5B-02) — 14+ card
- **Status:** SEEDED (`bots/grant.py`).
- **Pressure:** C2 U2 F3 K3 V2 I2 +0 = 14 → frontier + reviewer
- **Acceptance:** [ ] intersection of grant, requester, tenant, model tier, protected registry, capabilities; [ ] personal vs team: the stricter grant wins (EV-BOT-14); [ ] a low-privilege team bot is denied (EV-BOT-10).
- **Negative:** RT-37 (bot-to-bot injection widens a grant) and RT-40 (template poisoning) refused.

### T8-BOT-ROOMS — Rooms and handoffs (GATE-P5B-03)
- **Status:** OPEN
- **Pressure:** 11 → Grok high effort
- **Acceptance:** [ ] typed handoff JSON schema; max hop 4; fan-out 3; stall nudge once after 30 min, then escalate; taint propagates; [ ] EV-BOT-02 (Studio → Access → Release), EV-BOT-03, EV-BOT-04 (router ≥ 90%).
- **Negative:** RT-38 handoff loop or fan-out bomb stops at the cap.

### T8-BOT-STEER — Steering (GATE-P5B-04)
- **Status:** OPEN
- **Pressure:** 10 → Grok high effort
- **Acceptance:** [ ] EV-BOT-05: a mid-run steer queues, revalidates, and voids approvals; [ ] EV-BOT-06: a steer during APPLYING waits and does not interrupt.

### T8-BOT-PRESENCE — Presence
- **Status:** OPEN
- **Pressure:** 7 → Grok standard
- **Acceptance:** [ ] EV-BOT-15: presence equals the phase 100% (property test over the phase machine); [ ] no decorative avatar that implies emotion.

### T8-BOT-ROUTINE — Routines (GATE-P5B-05)
- **Status:** OPEN
- **Pressure:** 12 → Grok high effort
- **Acceptance:** [ ] EV-BOT-07 Test = zero writes, zero outbound; [ ] EV-BOT-08 outside-grant routine blocked; [ ] floors 15 min / 5 min / 1–5 min; [ ] auto-pause after 3 failures; [ ] 7-day soak recorded.
- **Negative:** RT-41 routine escalates to R2+ refused.

### T8-BOT-RECORD — Record Mode (staging only)
- **Status:** OPEN
- **Pressure:** 10 → Grok high effort
- **Flow (copied):** snapshot S0 → human performs the change on staging → snapshot S1 → emit a macro plus a skill plus evals → replay on a second input → save. Production untouched.
- **Acceptance:** [ ] EV-BOT-09.

### T8-BOT-WORKBENCH — Workbench takeover (GATE-P5B-06)
- **Status:** OPEN
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] a human can take over a run; the apply button shows only when the card is approved.

### T8-BOT-SECRETS — Plugins and secrets (GATE-P5B-07) — 14+ family
- **Status:** OPEN
- **Pressure:** 14 → frontier + reviewer
- **Acceptance:** [ ] RT-48: a secret pasted in chat never reaches the model or the logs (scrub before the gateway; test captures the outbound adapter payload); [ ] RT-43: a plugin or MCP call to a non-allowlisted host refused; [ ] RT-44 path traversal refused; [ ] ≤ 25 secrets per bot.

### T8-BOT-TEAM — Team Bots
- **Status:** OPEN
- **Pressure:** 12 → Grok high effort
- **Acceptance:** [ ] RT-39: a team bot runs as the requester's role; [ ] EV-BOT-11: an unmapped Slack identity is Ask-only.

### T8-BOT-STANDING — Standing rules
- **Status:** OPEN
- **Pressure:** 11 → Grok high effort
- **Acceptance:** [ ] R0–R1 only (outside L4); default expiry 90 days; [ ] EV-BOT-13: a standing rule for R2 outside L4 is rejected; [ ] RT-42: no expiry or scope creep refused. L4 standing rules are T5C cards L4-04 and L4-05.

### T8-BOT-SLACK — Slack and Teams (link only)
- **Status:** OPEN
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] cards link to `/approvals/<hash>`; no approve action for R ≥ 2; [ ] RT-45 forged signature refused (Slack signing secret, Teams JWT).

### T8-BOT-CHATTER — Odoo chatter channel
- **Status:** OPEN
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] EV-BOT-16: a mention polls, links only, and does not leak to other readers; [ ] RT-46 spoofed mention refused.

### T8-BOT-CFG — Configurator bot (GATE-P5B-11)
- **Status:** OPEN
- **depends_on:** T5B-02
- **Pressure:** 12 → Grok high effort
- **Acceptance:** [ ] EV-CFGBOT-01–15 on a Tier A model (nightly); [ ] loadouts recorded.

### T8-BOT-A11Y — Bot UI accessibility and narrow R3 (GATE-P5B-09, P5B-10)
- **Status:** OPEN
- **Pressure:** 7 → Grok standard
- **Acceptance:** [ ] axe on `/bots`, `/bots/[id]`, `/bots/rooms/[id]`; [ ] at 390 px width the R3 card shows the full diff.

### T8-BOT-COS — Chief of Staff supervision
- **Status:** OPEN
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] supervises every 15 minutes, nudges a stall once; [ ] EV-BOT-01 reuses Studio rather than creating a bot; [ ] cannot approve, widen a grant, or apply (negative test per action).

### T8-BOT-GATES — GATE-P5B-01–11 roll-up
- **Status:** OPEN
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] each of the 11 gate ids has a test or an evidence line in the progress log.

## P8 — pilots

| Card | Gate | Acceptance | Pressure |
|---|---|---|---|
| T8-P8-PILOTS | GATE-P8-01 | 3–5 pilots selected; each covers several of journeys J1–J12 (J1 field + views + access, J2 CRM pipeline, J3 record rules, J4 automation, J5 bulk fix, J6 diagnose visibility, J7 fleet of 20 DBs, J8 undo days later, J9 audit + config book, J10 import, J11 PDF report, J12 multi-company) | 8 |
| T8-P8-RUN | GATE-P8-02, P8-03 | 30 days, 0 critical incidents; verify-fail < 2%; rollback < 5% | 12 |
| T8-P8-TRUST | GATE-P8-04 | trust survey recorded (SUS / SEQ, not NPS) | 5 |
| T8-P8-GA | GATE-P8-05 | GA sign-off by Tope. An agent never checks this box | 2 |

P6, P7, and P8 are the only T8 phases that may be deferred past the first GA candidate, and only if the `../15` DoD items that depend on them are marked "not yet claimed".
