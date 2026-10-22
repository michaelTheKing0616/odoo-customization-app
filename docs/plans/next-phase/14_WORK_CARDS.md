# 14 — Work cards (index)

**Cards live in `cards/`. Screen cards live in `13_UI_SCREEN_SPECS.md`.** This file is the index only. A worker loads the one card file named in the last column, and nothing else unless that card lists it under "Read first". The v1 inline cards are preserved, unchanged, in `cards/_LEGACY_14_v1.md`; the `cards/` files supersede them.

Generated on 2026-10-02 from the card files: 353 cards (352 plus GND-DEMO). Status counts: DONE 23, OPEN 240, OPERATOR 2, PARTIAL 15, SEEDED 73. Statuses were measured against the repo on that date. Another agent was editing `apps/api/app/changeset/*` and `agent_runtime/*` concurrently, so **re-measure every T8 status before starting** (run the card's named tests first).

## How to pick and run a card

1. Pick a card whose `depends_on` cards are all DONE. If any are OPEN, stop.
2. Open the card file. Read the file's shared header first (shared do-not, commands, audit events), then the card.
3. Paste the Grok prefix from `00_INDEX.md` if you are a cheap or Grok model.
4. Run the card's named tests **before** changing anything. If a "SEEDED" test already fails, record it in the progress log and stop. Do not fix unrelated code.
5. Do the steps. Stay inside "Change".
6. Run the commands. Fill the acceptance boxes with evidence: a command plus its output summary.
7. Append the build-log entry (shape in `11_LOGGING_AUDIT_OBSERVABILITY.md` §1) to `docs/plans/INGENIUM_NEXT_PHASE_PROGRESS.md`.
8. Hand off to a checker who is not the maker (`skills/verifier-subagent.md`). The checker re-runs the commands.

## Card format (every card has these fields)

ID · Track · Title · depends_on · Escalation pressure (six 0–3 scores + prior failures 0–2 → sum → band → route) · Read first (paths with line ranges) · Change (files) · Steps (numbered) · Acceptance (checkboxes, gate ids copied) · Negative tests · Commands (exact) · Do not · Build log + audit events · Rollback · Evidence of done. A card file may state shared fields once in its header. Those fields apply to every card in that file.

**Pressure scores.** The six scores are C (complexity), U (uncertainty), F (failure consequence), K (constraint density), V (verification difficulty), and I (irreversibility), plus prior failures.

| Sum | Band | Route |
|---|---|---|
| 0–5 | cheap | Cheap model, or a tool/script if deterministic |
| 6–9 | Grok standard | Grok 4.7 |
| 10–13 | Grok high | Grok 4.7 high effort |
| 14–16 | frontier | Frontier model |
| 17–20 | frontier + reviewer | Frontier model plus an independent "what could be wrong?" review by another model |

Escalate only the slice that failed, and only after a diagnosed capability gap. Two failed attempts add +1 each to the prior-failures score. Log the failure in `ERRORS.md` once there have been more than 2 attempts.

## Status legend

| Status | Meaning |
|---|---|
| OPEN | Nothing exists. Build it |
| SEEDED | Code or tests exist but the gate is not proven. Start by running the named tests, then fill the gaps |
| PARTIAL | Some acceptance boxes are proven; the card lists which remain |
| DONE | All boxes have evidence. Re-run to verify; do not rebuild |
| OPERATOR | Needs Tope or a human operator (credentials, live instance, sign-off) |
| BLOCKED | Waiting on an open question in `18` or an unmet dependency |

## Shared do-not (every card)

Do not weaken a lock in `01`. Do not log secrets. Do not run against a customer database or write to a non-sandbox Odoo. Do not vendor `odoo-config-agent` or read Studio Enterprise source. Do not assume uvicorn `:8001` reloads: kill and restart it. Do not delete, skip, or loosen a test to go green. No live LLM in a PR-blocking test. No destructive git (reset, force push, branch delete) without Tope's yes in the current message. Promote stays human. Refuse `write_mode=production`.

## Shared commands

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/<file>.py
uv run --directory packages/odoo-client pytest -q tests/<file>.py
pnpm --filter @odoo-custom/web test -- <path>
pnpm --filter @odoo-custom/web typecheck
pnpm --filter @odoo-custom/web test:e2e e2e/<spec>.ts
./docker/run-sandbox-major-gate.sh <16|17|18|19>
docker compose -p odoo20-custom-dev -f docker/docker-compose.odoo20.yml up -d   # port 8073
```

## Order

Run the sequence in `04_SEQUENCE.md`. In short:
1. BL;
2. T1-F0 and T5A, in parallel with T2;
3. T8 P0–P3, the engine;
4. T6 inbox, T5B, T5C, and T9;
5. T3 and T4;
6. T8 P4–P6;
7. T7 foundation, then screens, from P5 onward;
8. T8 P7 and P8.

UI foundation cards may run alongside API work because they touch different files.

## Card table

| ID | Title | Status | Pressure | Band | File |
|---|---|---|---|---|---|
| BL-01 | Re-verify the baseline | DONE | 3 | cheap | `cards/BL_BASELINE.md` |
| BL-02 | Request-id middleware | DONE | 6 | Grok standard | `cards/BL_BASELINE.md` |
| BL-03 | JSON log formatter | DONE | 3 | cheap | `cards/BL_BASELINE.md` |
| BL-04 | Lint and type slots | DONE | 4 | cheap | `cards/BL_BASELINE.md` |
| BL-05 | ADR folder | DONE | 2 | cheap | `cards/BL_BASELINE.md` |
| BL-06 | verified-facts and recon | DONE | 6 | Grok standard | `cards/BL_BASELINE.md` |
| BL-07 | Fix the MCP scan so it ignores tool caches | OPEN | 2 | cheap | `cards/BL_BASELINE.md` |
| BL-08 | Commit hygiene for the uncommitted slices | OPEN | 6 | Grok standard | `cards/BL_BASELINE.md` |
| T1-PF | Pre-flight PF-1 to PF-6 | DONE | 5 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-F0 | PR-F.0 entrypoint trace (blocking) | DONE | 9 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| GND-PKT | Live schema context packet | DONE | 10 | Grok high | `cards/T1_LIVE_CONTEXT.md` |
| GND-GEN | Draft Studio prompts get the packet | DONE | 12 | Grok high | `cards/T1_LIVE_CONTEXT.md` |
| GND-EXPERT | Expert cites the packet when a connection exists | DONE | 9 | Grok standard | `cards/T1_LIVE_CONTEXT.md` |
| GND-DEMO | Can Odoo do this, with no client database | DONE | 10 | Grok high | `cards/T1_LIVE_CONTEXT.md` |
| GND-AUTO | Autopilot, ingest, workflow drop unknown names | DONE | 10 | Grok high | `cards/T1_LIVE_CONTEXT.md` |
| GND-AGENT | Bot inspection tools read the same packet | OPEN | 11 | Grok high | `cards/T1_LIVE_CONTEXT.md` |
| GND-MOD | Install the missing stock app, then continue | DONE | 10 | Grok high | `cards/T1_LIVE_CONTEXT.md` |
| GND-G-PIPE | Draft pipeline calls read the packet | DONE | 8 | strong generalist | `cards/T1_LIVE_CONTEXT.md` |
| GND-G-OPTA | Option A authoring reads the packet | OPEN | 12 | Grok high | `cards/T1_LIVE_CONTEXT.md` |
| GND-G-MAP | Import column mapping keeps only live fields | DONE | 4 | cheap | `cards/T1_LIVE_CONTEXT.md` |
| GND-G-TEXT | Display text names only live structure | DONE | 5 | cheap | `cards/T1_LIVE_CONTEXT.md` |
| GND-GATE | New LLM call sites must join the allowlist | SEEDED | 6 | cheap | `cards/T1_LIVE_CONTEXT.md` |
| T1-INST | AI_IR_TRACE on Maintenance | DONE | 6 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-A1 | schema_client positive and negative tests (PR-A, addendum A2) | DONE | 4 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-A2 | TTL deny on stale (addendum A3) | DONE | 4 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-A3 | field_is_writable | DONE | 4 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-A4 | view_has_field stays as built (addendum A6) | DONE | 3 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-B1 | merge_proposals admit rules (PR-B) | DONE | 10 | Grok high | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-B2 | Rate Line and many2one regression (addendum A4) | DONE | 6 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-B3 | Sibling golden hook | DONE | 6 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-C1 | approved_craft defaults off (PR-C) | DONE | 7 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-C2 | Checklist copy | DONE | 5 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-D1 | Repair cap (PR-D) | DONE | 9 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-D2 | proved requires run_tests (D2) | DONE | 6 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-D3 | Verbatim sandbox log | DONE | 4 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-E1 | CI split (PR-E) | DONE | 6 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-E2 | D2 encoded | DONE | 3 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-F1 | Maintenance golden (PR-F) | DONE | 8 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-F2 | Service-cards golden | DONE | 8 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-F3 | One Option A module reaches install_ready on a real sandbox | DONE | 8 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-RET | Retire scrub | DONE | 9 | Grok standard | `cards/T1_SCHEMA_GROUNDING.md` |
| T1-GATE | Gates that stay even if the code already exists | DONE | 4 | cheap | `cards/T1_SCHEMA_GROUNDING.md` |
| T2-J1 | PR-J1 live `/doc` check | OPERATOR | 10 | Grok high | `cards/T2_JSON2.md` |
| T2-J2 | PR-J2 install port | SEEDED | 8 | Grok standard | `cards/T2_JSON2.md` |
| T2-J3 | PR-J3 grep | OPEN | 5 | cheap | `cards/T2_JSON2.md` |
| T2-J4 | PR-J4 honest docs | OPEN | 3 | cheap | `cards/T2_JSON2.md` |
| T2-SMOKE | Odoo Online smoke | OPERATOR | 6 | Grok standard | `cards/T2_JSON2.md` |
| BR-00 | Phase 0 exit | PARTIAL | 4 | cheap | `cards/T3_BRIDGE.md` |
| BR-01 | Contract schema, Tier I fail-closed | DONE | 10 | Grok high | `cards/T3_BRIDGE.md` |
| BR-02 | Connections verify before Tier I passes | SEEDED | 9 | Grok standard | `cards/T3_BRIDGE.md` |
| BR-03 | Secrets encrypted at rest (14+ family: secrets) | OPEN | 11 | Grok high | `cards/T3_BRIDGE.md` |
| BR-04 | Queue tables | DONE | 4 | cheap | `cards/T3_BRIDGE.md` |
| BR-05 | Connector interface (six methods) | DONE | 4 | cheap | `cards/T3_BRIDGE.md` |
| BR-06 | Shopify Tier II (six sandbox scenarios) | SEEDED | 11 | Grok high | `cards/T3_BRIDGE.md` |
| BR-07 | Shopify Tier III (seeded discrepancy) | SEEDED | 11 | Grok high | `cards/T3_BRIDGE.md` |
| BR-08 | Tier 3b generic REST + webhook (config only) | OPEN | 13 | Grok high | `cards/T3_BRIDGE.md` |
| BR-09 | Genericity proof (DoD 5) | OPEN | 14 | frontier | `cards/T3_BRIDGE.md` |
| BR-10 | Tier 3c generated connector | OPEN | 13 | Grok high | `cards/T3_BRIDGE.md` |
| BR-11 | Dead letter (Phase 3) | SEEDED | 7 | Grok standard | `cards/T3_BRIDGE.md` |
| BR-12 | Contract Studio | SEEDED | 8 | Grok standard | `cards/T3_BRIDGE.md` |
| BR-13 | Catalog gate (Phase 4) | OPEN | 6 | Grok standard | `cards/T3_BRIDGE.md` |
| BR-14 | Bridge addon methods (shared with T8-OD-BRIDGE) | SEEDED | 14 | frontier | `cards/T3_BRIDGE.md` |
| T4-PROG | Live progress on four surfaces (6.1, compiler DoD 8–10, master DoD 7) | DONE | 9 | Grok standard | `cards/T4_COMPILER_SURFACES.md` |
| T4-MCP0 | MCP Phase 0 hands-on | OPEN | 5 | cheap | `cards/T4_COMPILER_SURFACES.md` |
| T4-MCP1 | MCP Phase 1 read-only | PARTIAL | 11 | Grok high | `cards/T4_COMPILER_SURFACES.md` |
| T4-MCP5 | MCP Phase 5 research close | OPEN | 3 | cheap | `cards/T4_COMPILER_SURFACES.md` |
| T4-DASH | AI Dashboard Studio (6.3, master DoD 9) | OPEN | 12 | Grok high | `cards/T4_COMPILER_SURFACES.md` |
| T4-OFF | Offline queue (6.4, master DoD 10) | DONE | 13 | Grok high | `cards/T4_COMPILER_SURFACES.md` |
| T4-ISPEC | ISPEC round-trip (6.5, compiler DoD 1–2) | DONE | 14 | frontier | `cards/T4_COMPILER_SURFACES.md` |
| T4-SYNC | Recompile and Sync (compiler DoD 3–5, master DoD 11) | DONE | 15 | frontier | `cards/T4_COMPILER_SURFACES.md` |
| T4-BROWSER | Browser-testing sub-agent in Stage F (compiler DoD 6–7, master DoD 12) | DONE | 11 | Grok high | `cards/T4_COMPILER_SURFACES.md` |
| T4-WIRE | Wireframe to app (6.6, compiler DoD 12, master DoD 13) | DONE | 11 | Grok high | `cards/T4_COMPILER_SURFACES.md` |
| T4-LLM3 | Three-tier provider abstraction (6.7, master DoD 14) | DONE | 9 | Grok standard | `cards/T4_COMPILER_SURFACES.md` |
| T4-SKT | Skills, Sources, Triggers (6.8, compiler DoD 15–18, master DoD 15) — stop-ship | DONE | 16 | frontier | `cards/T4_COMPILER_SURFACES.md` |
| T4-E2E | Phase 6 continuous scenario (compiler DoD 19–20) | OPEN | 12 | Grok high | `cards/T4_COMPILER_SURFACES.md` |
| T4-GROUND | Dynamic tools grounded, RAG reuses the index, Odoo widgets (compiler DoD 11, 13, 14) | DONE | 8 | Grok standard | `cards/T4_COMPILER_SURFACES.md` |
| 5A-01 | classify_rpc with the verbatim lists, mapped to Bucket A/B/C | DONE | 12 | Grok high | `cards/T5A_GUARDRAILS.md` |
| 5A-02 | Structural dry-run hash on every write tool in T1, T3, T4 | DONE | 14 | frontier | `cards/T5A_GUARDRAILS.md` |
| 5A-03 | Plan fingerprint | DONE | 15 | frontier | `cards/T5A_GUARDRAILS.md` |
| 5A-04 | Never-allowed, no override | DONE | 15 | frontier | `cards/T5A_GUARDRAILS.md` |
| 5A-05 | Hash-chained audit | DONE | 13 | Grok high | `cards/T5A_GUARDRAILS.md` |
| 5A-06 | Snapshot before DESTRUCTIVE or BILLABLE on production | DONE | 11 | Grok high | `cards/T5A_GUARDRAILS.md` |
| 5A-07 | Zero MCP writes (code inspection) | DONE | 4 | cheap | `cards/T5A_GUARDRAILS.md` |
| 5A-08 | Production policy | DONE | – | – | `cards/T5A_GUARDRAILS.md` |
| 5A-09 | Staging policy | DONE | – | – | `cards/T5A_GUARDRAILS.md` |
| 5A-10 | Oracle tests | DONE | – | – | `cards/T5A_GUARDRAILS.md` |
| 5A-11 | Rollback tiers wired | DONE | 13 | Grok high | `cards/T5A_GUARDRAILS.md` |
| 5A-12 | Production budgets (blueprint §5.6) | DONE | 7 | Grok standard | `cards/T5A_GUARDRAILS.md` |
| 5B-01 | Schema: 47 sections in apply order | DONE | 6 | Grok standard | `cards/T5B_CONFIG.md` |
| 5B-02 | Idempotent apply through the change-set engine | SEEDED | 11 | Grok high | `cards/T5B_CONFIG.md` |
| 5B-03 | Fingerprint drift aborts | OPEN | 9 | Grok standard | `cards/T5B_CONFIG.md` |
| 5B-04 | Version briefing, probed live | OPEN | 10 | Grok high | `cards/T5B_CONFIG.md` |
| 5B-05 | `l10n_ng` adopt by xmlid | SEEDED | 6 | Grok standard | `cards/T5B_CONFIG.md` |
| 5B-06 | Importers | SEEDED | 8 | Grok standard | `cards/T5B_CONFIG.md` |
| 5B-07 | Custom fields | DONE | 3 | cheap | `cards/T5B_CONFIG.md` |
| 5B-08 | Oracle port | PARTIAL | 5 | cheap | `cards/T5B_CONFIG.md` |
| 5B-09 | Approval for destructive config | OPEN | 8 | Grok standard | `cards/T5B_CONFIG.md` |
| 5C-01 | One chassis for Tracks 1, 3, 4 | SEEDED | 14 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-02 | L2 pauses every write | DONE | 6 | Grok standard | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-03 | L3 on staging | DONE | 8 | Grok standard | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-04 | Multi-client lock | OPEN | 12 | Grok high | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-05 | Out-of-band drift aborts | DONE | 9 | Grok standard | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-06 | Adversarial embedded instruction | DONE | 8 | Grok standard | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-07 | Never-allowed at L4 (written before L4 is enabled) | DONE | 12 | Grok high | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-08 | Eval harness hook | OPEN | 8 | Grok standard | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-09 | Safety: 100% approval on billable and destructive repeats | DONE | 10 | Grok high | `cards/T5C_WORKERBOTS_L4.md` |
| 5C-10 | Flow checks | OPEN | 8 | Grok standard | `cards/T5C_WORKERBOTS_L4.md` |
| L4-01 | GATE-L4-01 | DONE | 16 | frontier + reviewer | `cards/T5C_WORKERBOTS_L4.md` |
| L4-02 | GATE-L4-02 | DONE | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-03 | GATE-L4-03 | DONE | 16 | frontier + reviewer | `cards/T5C_WORKERBOTS_L4.md` |
| L4-04 | GATE-L4-04 | DONE | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-05 | GATE-L4-05 | OPEN | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-06 | GATE-L4-06 | OPEN | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-07 | GATE-L4-07 | SEEDED | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-08 | GATE-L4-08 | SEEDED | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-09 | GATE-L4-09 | OPEN | 16 | frontier + reviewer | `cards/T5C_WORKERBOTS_L4.md` |
| L4-10 | GATE-L4-10 | OPEN | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-11 | GATE-L4-11 | DONE | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| L4-12 | GATE-L4-12 | DONE | 16 | frontier | `cards/T5C_WORKERBOTS_L4.md` |
| T6-01 | Role matrix enforced in code | DONE | 9 | Grok standard | `cards/T6_AUTH_INBOX.md` |
| T6-02 | Zero manual account linking (DoD 29, gate 6-1) | DONE | 11 | Grok high | `cards/T6_AUTH_INBOX.md` |
| T6-03 | Auth events in the one hash chain (DoD 31, gate 6-3) | DONE | 11 | Grok high | `cards/T6_AUTH_INBOX.md` |
| T6-04 | Inbox API binds to the fingerprint (14+ card) | DONE | 14 | frontier | `cards/T6_AUTH_INBOX.md` |
| T6-05 | Plan card render (nine sections from the engine) | DONE | 10 | Grok high | `cards/T6_AUTH_INBOX.md` |
| T6-06 | R3 one approval; heavy R4 keeps two people | DONE | 14 | frontier | `cards/T6_AUTH_INBOX.md` |
| T6-07 | Client scope on the inbox | DONE | 8 | Grok standard | `cards/T6_AUTH_INBOX.md` |
| T6-08 | Command center home | DONE | 8 | Grok standard | `cards/T6_AUTH_INBOX.md` |
| T6-09 | Per-client page | DONE | 7 | Grok standard | `cards/T6_AUTH_INBOX.md` |
| T6-10 | Team grants UI | DONE | 7 | Grok standard | `cards/T6_AUTH_INBOX.md` |
| T6-11 | 14b live five-track dashboard (DoD 32, gate 6-4) | OPEN | 11 | Grok high | `cards/T6_AUTH_INBOX.md` |
| T6-12 | SAML recorded as later | DONE | 1 | cheap | `cards/T6_AUTH_INBOX.md` |
| T6-13 | Approval links in channels | OPEN | 6 | Grok standard | `cards/T6_AUTH_INBOX.md` |
| UI-F00 | Clear the 13 pre-existing type errors, then add typecheck to CI | OPEN | 5 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F01 | Dark-mode alert tokens | DONE | 2 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F02 | loading, error, not-found | DONE | 3 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F03 | EmptyState and Skeleton adopted on operate pages | DONE | 5 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F04 | Dialog family to Base UI | OPEN | 10 | Grok high | `cards/T7_UI_FOUNDATION.md` |
| UI-F05 | Tabs to Base UI | DONE | 6 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-F06 | Tooltip to Base UI | DONE | 5 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F07 | Slot (Button asChild) | DONE | 5 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F08 | Sonner everywhere | PARTIAL | 5 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F09 | Motion primitives | SEEDED | 8 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-F10 | input-otp for TOTP | DONE | 5 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F11 | react-virtuoso for tables over 50 rows | DONE | 6 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-F12 | axe on every operate route | OPEN | 5 | cheap | `cards/T7_UI_FOUNDATION.md` |
| UI-F13 | One canvas reorder primitive | OPEN | 9 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| H1 | Eval case schema and capture | OPEN | 9 | Grok standard | `cards/HARNESS.md` |
| H2 | Review queue and versioning | OPEN | 8 | Grok standard | `cards/HARNESS.md` |
| H3 | CI and nightly eval set | OPEN | 10 | Grok high | `cards/HARNESS.md` |
| H4 | Judge sampling and trends | OPEN | 11 | Grok high | `cards/HARNESS.md` |
| H5 | Judge calibration | OPEN | 9 | Grok standard | `cards/HARNESS.md` |
| H6 | Shadow mode | OPEN | 12 | Grok high | `cards/HARNESS.md` |
| H7 | Canary and auto-rollback | OPEN | 12 | Grok high | `cards/HARNESS.md` |
| H8 | Harness end-to-end proof | OPEN | 10 | Grok high | `cards/HARNESS.md` |
| UI-SP-API | apps/web/src/lib/api.ts (6130) → src/lib/api/<domain>.ts with api | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-SP-WIZARD | connections/[id]/wizard/page.tsx (1892) | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-SP-STUDIO | connections/[id]/studio/page.tsx (1548) | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-SP-DESIGNER | connections/[id]/designer/page.tsx (1429) | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-SP-BULK | connections/[id]/bulk-suite/page.tsx (1312) | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-SP-OVERVIEW | connections/[id]/page.tsx (1225) | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-SP-CONFIG | connections/[id]/config/page.tsx (946) | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| UI-SP-CSS | src/styles/studio-refinement.css (1721), src/app/globals.css (1366 | OPEN | 7 | Grok standard | `cards/T7_UI_FOUNDATION.md` |
| ADR-01 | Stack and repo layout. Default: this repo (apps/api, apps/web, pa | OPEN | 4 | cheap | `cards/T8_ENGINE_CORE.md` |
| ADR-02 | LLM gateway: thin in-house vs LiteLLM. **Stays open until Tope accepts | OPEN | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| ADR-03 | Canonical message and tool schema (llm_gateway/types.py) | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-04 | Tool-call emulation ladder: native → emulated_json → emulated_text | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-05 | Union tools vs family tools, decided by an eval (GATE-P6-04) | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-06 | Executor Mode T vs Mode C | OPEN | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| ADR-07 | Staging and clone provider (OQ-STAGING) | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-08 | Who approves, two-person rule, expiry (../02 is the proposal) | OPEN | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| ADR-09 | Memory model and injection-safe persistence | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-10 | Skill package format and router | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-11 | Audit hash chain (../11 §2 is the proposal; audit_chain.py is the | OPEN | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| ADR-12 | Secrets, KMS, BYO keys (Fernet until a KMS is chosen) | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-13 | Eval harness and tier thresholds | OPEN | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| ADR-14 | Supported versions: D11, 17–20 GA, 16 experimental, ≤15 refused | OPEN | 4 | cheap | `cards/T8_ENGINE_CORE.md` |
| T8-P0-FIX | Fixtures and db reset (GATE-P0-03) | PARTIAL | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-P0-LINT | Import-boundary lint (GATE-P0-05, GATE-P1-07) | OPEN | 5 | cheap | `cards/T8_ENGINE_CORE.md` |
| T8-GW-TYPES | Canonical types | SEEDED | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-GW-NORM | Normalization rules 1–10 | SEEDED | 10 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-GW-C | Conformance C01–C20 with cassettes (GATE-P1-02) | SEEDED | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-GW-REG | Model registry | SEEDED | 6 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-GW-REST | Remaining P1 gates | SEEDED | 9 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-OD-TRANSPORT | Transport contracts (GATE-P2-01, P2-05, P2-06) | SEEDED | 10 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-OD-ENV | EnvProfile (GATE-P2-02) | SEEDED | 9 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-OD-GRAPH | SchemaGraph (GATE-P2-03, P2-04, P2-07) | SEEDED | 11 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-OD-BRIDGE | Bridge addon (GATE-P2-08, P2-09) — 14+ card | SEEDED | 15 | frontier | `cards/T8_ENGINE_CORE.md` |
| T8-OD-DRIFT | Version drift checklist (each row a test on 17, 18, 19, 20) | PARTIAL | 9 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-OP-SCHEMA | model.create, model.scaffold, field.create, field.update, fie | DONE | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-OP-UI | view.inherit.create, view.inherit.update, view.archive, view.cr | DONE | 10 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-OP-LOGIC | server_action.create/update, automation.create/update/disable, cr | DONE | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-OP-SEC | group.create, access.create/update, rule.create/update, field.g | OPEN | 15 | frontier | `cards/T8_ENGINE_CORE.md` |
| T8-OP-SET | setting.set, config_param.set, company.update, module.install, | DONE | 14 | frontier | `cards/T8_ENGINE_CORE.md` |
| T8-OP-DATA | data.create_batch, data.update_batch, data.archive_batch, data. | SEEDED | 13 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-PROT | Protected registry (14+ card) | SEEDED | 16 | frontier | `cards/T8_ENGINE_CORE.md` |
| T8-RISK | Risk escalation only goes up | SEEDED | 10 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-POLICY | Policy matrix (17+ card) | SEEDED | 17 | frontier + reviewer | `cards/T8_ENGINE_CORE.md` |
| T8-VALID | Validation stages 1–9 | SEEDED | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-SIM | Simulation | DONE | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-EXEC | Executor Mode T / Mode C with WAL and recovery (14+ card) | SEEDED | 18 | frontier + reviewer | `cards/T8_ENGINE_CORE.md` |
| T8-VERIFY | Verification (INV-16) | SEEDED | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-ROLLBACK | Undo as a change-set | SEEDED | 14 | frontier | `cards/T8_ENGINE_CORE.md` |
| T8-META | MetaSnapshot | DONE | 10 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-CARD | Plan card goldens (GATE-P3-10) | SEEDED | 8 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-CLI | LLM-free CLI end to end (GATE-P3-09) | DONE | 9 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-P3-COV | Engine coverage (GATE-P3-08) | OPEN | 5 | cheap | `cards/T8_ENGINE_CORE.md` |
| T8-RUN | Phase machine and loop guards (GATE-P4-01, P4-02, P4-03, P4-08) | SEEDED | 11 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-TOOLS | Tool surface | SEEDED | 8 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-PROMPT | Prompt layers and context budgets (GATE-P4-07) | OPEN | 10 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-CLARIFY | Clarification rules | OPEN | 8 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-CRITIC | Critic (cannot waive policy) | OPEN | 9 | Grok standard | `cards/T8_ENGINE_CORE.md` |
| T8-MEM | Memory (ADR-09) | OPEN | 10 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-P4-TIERA | Tier A on 60 scenarios (GATE-P4-04) and RT-01–09 (GATE-P4-05) | OPEN | 12 | Grok high | `cards/T8_ENGINE_CORE.md` |
| T8-S01 | Op conformance, every op | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S02 | Apply, verify, inverse, MetaSnapshot equality | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S03 | Idempotency | OPEN | 8 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S04 | Atomicity Mode T, compensation Mode C | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S05 | State-machine table | OPEN | 9 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S06 | Approval binding | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S07 | Drift becomes STALE | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S08 | Policy matrix + mutation ≥ 80% | OPEN | 14 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S09 | Protected registry + RT-10–16 | OPEN | 14 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S10 | Validator fuzz | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S11 | Crash injection at WAL boundaries | OPEN | 14 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S12 | Unknown-outcome writes | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S13 | Locking and concurrency | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S14 | Bridge | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S15 | Data-op safety | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S16 | Redaction and privacy | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S17 | Provider conformance C01–C20 | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-S18 | SSRF, scrubber, cross-tenant, IDOR | OPEN | 15 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-SK-T1-<ID> | Tier-1 full procedure skills (16 cards) | SEEDED | 8 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-SK-FAM-<A..I> | Remaining skills by family (9 cards) | SEEDED | 6 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-ROUTER | Skill router (GATE-P4-06) | OPEN | 11 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-EV-HARNESS | apps/api/app/evals/ runner: YAML scenario → scripted or live adapter | OPEN | 11 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-EV-SEED | EV-FLD-01–18, EV-AUT-01–08, EV-SEC-01–08, EV-DATA-01–08 (texts in ../ | OPEN | 8 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-EV-ASSIGN | EV-APP-01–16, EV-RPT-01–05, EV-AMB-01–08, EV-REF-01–08, EV-DIAG-01–08, | OPEN | 8 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-EV-INJ | EV-INJ = RT-01–09 as scored scenarios | OPEN | 6 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-EV-CFG | EV-CFGBOT-01–15 (../T8_BOT_ENGINE.md 363–381) | OPEN | 9 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-EV-BOT | EV-BOT-01–16 (383–402) | OPEN | 9 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-P6 | GATE-P6-01–06 | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-RT-A | RT-01–RT-09 (injection through records, chatter, CSV, arch comments, p | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-RT-B | RT-10–RT-16 (protected registry bypasses; shared with T8-PROT) | OPEN | 16 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-RT-C | RT-17–RT-27 (approval replay, self-approval, expiry, mid-flight policy | OPEN | 14 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-RT-D | RT-28–RT-36 (SSRF, key exfiltration, cost loop, rate-limit evasion, cr | OPEN | 15 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-RT-E | RT-37–RT-48 (bot-to-bot injection, handoff loops, team-bot laundering, | OPEN | 14 | frontier | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-CI | Four stages wired in .github/workflows/ci.yml: PR (lint, types, impo | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-CHAOS | toxiproxy: provider down, Odoo timeout, DNS lie; 24–72 h soak of routi | OPEN | 12 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-PEN | Pen-test slot: who performs it is OQ-PENTEST (blocking for GA); no ope | OPEN | – | operator (OQ-PENTEST) | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-PRIV | Privacy targets (GATE-P7-04): retention per ../T8_BOT_ENGINE.md 629; | OPEN | 9 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-RUNBOOK | docs/runbooks/ 1–13 (../11 §8) with a game-day for each (GATE-P7-0 | OPEN | 7 | Grok standard | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-KILL | Kill drills: global, tenant, provider, model, op type, skill, ingeniu | OPEN | 10 | Grok high | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-SBOM | SBOM clean (GATE-P7-07); extend scripts/security_supply_chain.sh | OPEN | 5 | cheap | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-HUMAN | 50 blind plans per release packet template; an incident becomes an eva | OPEN | 5 | cheap | `cards/T8_SUITES_SKILLS_EVALS.md` |
| T8-P5-E2E | GATE-P5-01 | OPEN | 10 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-P5-PAGE | GATE-P5-02 | SEEDED | 10 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-P5-SSE | GATE-P5-03 | OPEN | 9 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-P5-RBAC | GATE-P5-04 | SEEDED | 12 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-P5-A11Y | GATE-P5-05 | OPEN | 7 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-P5-KILL | GATE-P5-06 | OPEN | 10 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-ROSTER | Roster and limits (GATE-P5B-01, P5B-08) | OPEN | 8 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-GRANT | Effective permission (GATE-P5B-02) — 14+ card | SEEDED | 14 | frontier | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-ROOMS | Rooms and handoffs (GATE-P5B-03) | OPEN | 11 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-STEER | Steering (GATE-P5B-04) | OPEN | 10 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-PRESENCE | Presence | OPEN | 7 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-ROUTINE | Routines (GATE-P5B-05) | OPEN | 12 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-RECORD | Record Mode (staging only) | OPEN | 10 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-WORKBENCH | Workbench takeover (GATE-P5B-06) | OPEN | 9 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-SECRETS | Plugins and secrets (GATE-P5B-07) — 14+ family | OPEN | 14 | frontier | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-TEAM | Team Bots | OPEN | 12 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-STANDING | Standing rules | OPEN | 11 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-SLACK | Slack and Teams (link only) | OPEN | 9 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-CHATTER | Odoo chatter channel | OPEN | 9 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-CFG | Configurator bot (GATE-P5B-11) | OPEN | 12 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-A11Y | Bot UI accessibility and narrow R3 (GATE-P5B-09, P5B-10) | OPEN | 7 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-COS | Chief of Staff supervision | OPEN | 8 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-BOT-GATES | GATE-P5B-01–11 roll-up | OPEN | 4 | cheap | `cards/T8_BOTS_PILOTS.md` |
| T8-P8-PILOTS | GATE-P8-01 | OPEN | 8 | Grok standard | `cards/T8_BOTS_PILOTS.md` |
| T8-P8-RUN | GATE-P8-02, P8-03 | OPEN | 12 | Grok high | `cards/T8_BOTS_PILOTS.md` |
| T8-P8-TRUST | GATE-P8-04 | OPEN | 5 | cheap | `cards/T8_BOTS_PILOTS.md` |
| T8-P8-GA | GATE-P8-05 | OPEN | 2 | cheap | `cards/T8_BOTS_PILOTS.md` |
| O20-01 | Compose file | SEEDED | 5 | cheap | `cards/T9_ODOO20.md` |
| O20-02 | Registry lists 20 as GA | SEEDED | 4 | cheap | `cards/T9_ODOO20.md` |
| O20-03 | Adapters views_v20, automation_v20, security_v20 | PARTIAL | 10 | Grok high | `cards/T9_ODOO20.md` |
| O20-04 | `ir.access` compiler (frontier + reviewer) | SEEDED | 15 | frontier | `cards/T9_ODOO20.md` |
| O20-05 | Access screen on 20 | OPEN | 8 | Grok standard | `cards/T9_ODOO20.md` |
| O20-06 | Version-table tests (one per row) | PARTIAL | 9 | Grok standard | `cards/T9_ODOO20.md` |
| O20-07 | JSON-2 default on 20 | SEEDED | 5 | cheap | `cards/T9_ODOO20.md` |
| O20-08 | Snapshots without the db service (frontier review) | OPEN | 14 | frontier | `cards/T9_ODOO20.md` |
| O20-09 | Native MCP absent on Community | SEEDED | 3 | cheap | `cards/T9_ODOO20.md` |
| O20-10 | Major gate includes 20 | OPEN | 5 | cheap | `cards/T9_ODOO20.md` |
| O20-11 | Flows on 20 | OPEN | 9 | Grok standard | `cards/T9_ODOO20.md` |
| O20-12 | Designer on 20 | OPEN | 6 | Grok standard | `cards/T9_ODOO20.md` |
| O20-13 | Production checklist | OPEN | 5 | cheap | `cards/T9_ODOO20.md` |
| O20-14 | `name_search` uses `domain` | SEEDED | 4 | cheap | `cards/T9_ODOO20.md` |
| O20-15 | `formatted_read_group` | SEEDED | 5 | cheap | `cards/T9_ODOO20.md` |
| O20-16 | 19-to-20 spec replay | OPEN | 12 | Grok high | `cards/T9_ODOO20.md` |
| UI-S-01 | `/` — landing (144) | OPEN | 6 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-02 | `/pricing` (155) | OPEN | 5 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-03 | `/privacy`, `/terms` (27 each) | OPEN | 2 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-04 | `/login` (124) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-05 | `/signup` (78) | OPEN | 5 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-06 | `/reset-password` (99) | OPEN | 4 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-07 | `/verify` (53) | OPEN | 3 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-08 | `/connect` (537) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-10 | `/connections/[id]` — overview (1225) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-11 | `…/builder` (785) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-12 | `…/designer` (1429) — uses UI-F13 | OPEN | 10 | Grok high | `13_UI_SCREEN_SPECS.md` |
| UI-S-13 | `…/menus` (409) | OPEN | 6 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-14 | `…/website` (49) | OPEN | 4 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-15 | `…/automations` (696) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-16 | `…/approvals` — Odoo approval process (320) | OPEN | 6 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-17 | `…/reports` (482) — PDF Studio | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| PDF-01 | Premium paper canvas | OPEN | 8 | Grok standard | `cards/T7_PDF_STUDIO.md` |
| PDF-02 | Pointer drag and drop | OPEN | 6 | cheap | `cards/T7_PDF_STUDIO.md` |
| PDF-03 | Extend a stock report | OPEN | 13 | Grok high | `cards/T7_PDF_STUDIO.md` |
| PDF-04 | Create from scratch, grounded | OPEN | 10 | Grok high | `cards/T7_PDF_STUDIO.md` |
| PDF-05 | Unsafe template gate | OPEN | 12 | Grok high | `cards/T7_PDF_STUDIO.md` |
| PDF-06 | Reports screen restyle | OPEN | 7 | Grok standard | `cards/T7_PDF_STUDIO.md` |
| UI-S-18 | `…/code-studio` (394) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-19 | `…/access` (749) | OPEN | 10 | Grok high | `13_UI_SCREEN_SPECS.md` |
| UI-S-20 | `…/studio` — App Studio (1548) | OPEN | 11 | Grok high | `13_UI_SCREEN_SPECS.md` |
| UI-S-21 | `…/wizard` (1892) | OPEN | 10 | Grok high | `13_UI_SCREEN_SPECS.md` |
| UI-S-22 | `…/job` — Job Autopilot (747) | OPEN | 9 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-23 | `…/modulespec` (19) | OPEN | 3 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-24 | `…/projects` (19 + components) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-25 | `…/expert` (60) | OPEN | 6 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-26 | `…/import` (593) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-27 | `…/id-generator` (428) | OPEN | 4 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-28 | `…/ingest` (504) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-29 | `…/operations` (100) | OPEN | 3 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-30 | `…/bulk-suite` (1312) | OPEN | 9 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-31 | `…/power-ops` (409) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-32 | `…/cron-manager` (523) | OPEN | 5 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-33 | `…/housekeeping` (538) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-34 | `…/reminders` (241) | OPEN | 4 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-35 | `…/script-runner` (286) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-36 | `…/config` (946) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-37 | `…/live-demo-copilot` (528) | OPEN | 6 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-38 | `…/journal` (356) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-39 | `/live-demo-copilot/overlay` (104) | OPEN | 4 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-40 | `/connections` (9) | OPEN | – | n/a (redirect or blocked on OQ) | `13_UI_SCREEN_SPECS.md` |
| UI-S-41 | `/settings` (347) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-42 | `/settings/billing` (154) | OPEN | 4 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-43 | `/settings/trust-safety` (43) | OPEN | 3 | cheap | `13_UI_SCREEN_SPECS.md` |
| UI-S-44 | `/admin` (210) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-45 | `/pipelines` (359) | OPEN | 9 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-50 | `/approvals` — plan-card inbox (98, seeded) | OPEN | 12 | Grok high | `13_UI_SCREEN_SPECS.md` |
| UI-S-51 | `/command` — fleet command (34, seeded) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-52 | `/bots` — roster (new) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-53 | `/bots/rooms/[id]` — room (new) | OPEN | 9 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-54 | `/bots/[id]` — workbench (new) | OPEN | 9 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-55 | `/studio/dashboards` — Dashboard Studio (new) | OPEN | 9 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-56 | `/bridge/contracts/new` (123, seeded) | OPEN | 8 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-57 | `/bridge/connections` (new) | OPEN | 7 | Grok standard | `13_UI_SCREEN_SPECS.md` |
| UI-S-58 | `/onboarding` — first-run (new, optional) | OPEN | – | n/a (redirect or blocked on OQ) | `13_UI_SCREEN_SPECS.md` |
| UI-S-60 – UI-S-62 | — harness hygiene | OPEN | 4 | cheap | `13_UI_SCREEN_SPECS.md` |
| DEV-CS | Code Studio a customer can use alone | DONE | 15 | frontier | `cards/DEV_MODES_PRODUCTION.md` |
| DEV-SR | Script Runner a customer can use alone | OPEN | 16 | frontier | `cards/DEV_MODES_PRODUCTION.md` |
| DEV-PO | Power Ops a customer can use alone | OPEN | 16 | frontier | `cards/DEV_MODES_PRODUCTION.md` |
