# Ingenium next phase — build pack index

**Status:** specification only. No product code ships from this pack until a work card in `14_WORK_CARDS.md` is picked up.
**Date:** 2026-10-02
**Supersedes as the working spec:** `docs/plans/INGENIUM_NEXT_PHASE_CONSOLIDATED_BUILD_SPEC.md` (kept, header-only redirect). Source documents under `/Users/temitopeolaitanmichael/Downloads/ingenium new phase/` remain the technical authority where this pack and a source disagree, except where `01_LOCKS_DECISIONS_CONFLICTS.md` records a later locked decision (D1–D12).
**Living log:** `docs/plans/INGENIUM_NEXT_PHASE_PROGRESS.md`

## How to use this pack

A builder loads only the file for the card they hold. They do not reread the Downloads folder unless a card says a line range is the oracle.

1. Read `01` locks before any edit. A task that would weaken a lock stops. Write the conflict in the progress log. Do not reinterpret the lock.
2. Read `03` for what already exists. Do not rebuild an "exists" row.
3. Take one card from the `14` index and open its file under `cards/` (screen cards: `13`). Obey its route band, files, acceptance IDs, commands, and do-not list. Status legend: OPEN (build it), SEEDED (code or tests exist, gate unproven: run the named tests first), PARTIAL, DONE (re-verify only), OPERATOR (needs Tope or a live instance), BLOCKED (open question or dependency).
4. A gate is met only with a command, a log excerpt, a test name, or a screenshot path in the progress log. A demo is not a gate.
5. Negative tests are first-class. A happy path without the named rejection test does not close a card.
6. UI cards load the Prime skills named on the card before editing screens.
7. After the card: append the build-log shape in `11_LOGGING_AUDIT_OBSERVABILITY.md`.

## Grok adapter prefix (paste at the top of every card prompt)

> Cost-aware agent mode: inspect narrowly, act incrementally, verify every important change, and escalate effort only when the evidence demands it. Do not repeat failed attempts without changing the hypothesis or strategy.

## Cheap-model challenge (bands 0–9)

1. Attempt with the minimum capable model.
2. List assumptions, unknowns, competing designs, failure modes, and what could not be verified.
3. Continue if the unknowns are low-risk.
4. If they are material, send only that uncertainty upward.

## Reviewer escalation (bands 17–20)

The reviewer answers only "what could be wrong?" They do not rewrite the card. Send the proposal, the evidence, the exact unresolved question, the constraints, and what is already verified.

## Escalation pressure

Score each 0–3, plus previous failed attempts 0–2 (cap +2). Sum 0–20.

| Dimension | 0 | 2 | 3 |
|---|---|---|---|
| Complexity | 1–2 components | 3–5 | 6+ |
| Uncertainty | known pattern | several plausible solutions | novel |
| Failure consequence | easy to revert | moderate rework | migration, security, or data loss |
| Constraint density | one requirement | several must hold together | many hard constraints |
| Verification difficulty | tests can falsify it | partial | hard to test |
| Irreversibility | changeable tomorrow | costly to unwind | locks a protocol, data model, or trust boundary |

| Pressure | Route |
|---|---|
| 0–5 | cheapest capable model, or a deterministic tool |
| 6–9 | strong efficient generalist (Grok 4.7 standard) |
| 10–13 | strong generalist at higher reasoning effort |
| 14–16 | frontier model |
| 17–20 | frontier plus an independent reviewer |

Cards already scored at 14+ in `cards/` (see the Band column of `14`): policy matrix, plan-hash binding, WAL executor, audit chain, protected registry, L4, `ir.access` compiler, tenant isolation, never-allowed list, Trigger-confirmation gate.

## Reading order by role

| Role | Read |
|---|---|
| Orchestrator | `00`, `01`, `04`, the card's track file, `14` header |
| Worker | the one card file in `cards/` (or its `13` block); it copies the lists and gates it needs |
| Checker | the card's acceptance IDs, `10` row for that test type, `17` coverage row |
| Judge | `01` locks, `02` if the card writes, `15` DoD item the card claims |

## File map

| File | Contents |
|---|---|
| `01_LOCKS_DECISIONS_CONFLICTS.md` | Product locks, INV-01–20, D1–D12, conflict table |
| `02_APPROVAL_FLOW.md` | Plain-English approval, R0–R4, policy, L0–L4, GATE-L4 |
| `03_BASELINE.md` | Exists / partial / missing, measured 2026-10-02 |
| `04_SEQUENCE.md` | Global order and parallel lanes |
| `T1_SCHEMA_GROUNDING.md` | Track 1 gates |
| `T2_JSON2.md` | Track 2 gates |
| `T3_BRIDGE.md` | Track 3 gates |
| `T4_COMPILER_MCP_DASH_OFFLINE_MODELS.md` | Track 4 gates |
| `T5_GUARDRAILS_CONFIG_WORKERBOTS.md` | Track 5 gates and verbatim lists |
| `T6_AUTH_COMMAND_CENTER.md` | Track 6 gates |
| `T7_UI_MOTION_COPY.md` | UI migration and motion rules |
| `T8_BOT_ENGINE.md` | Agent spec Parts 4–17 inlined |
| `T9_ODOO20_GA.md` | Odoo 20 GA track |
| `10_TESTING_MATRIX.md` | Every test type |
| `11_LOGGING_AUDIT_OBSERVABILITY.md` | Build log, audit chain, SLOs, runbooks |
| `12_SECURITY_PRIVACY.md` | Threats, injection, SSRF, secrets, NDPA |
| `13_UI_SCREEN_SPECS.md` | One block per route; also the card file for screen cards UI-S-01–62 |
| `14_WORK_CARDS.md` | Card index: format, status legend, routing, shared do-not and commands, table of all 330 cards with status, pressure, and file |
| `cards/T1_LIVE_CONTEXT.md` | GND-PKT–GATE: every LLM surface that names Odoo structure sees the live schema first |
| `cards/HARNESS.md` | H1–H8 continuous eval, LLM-as-judge, shadow and canary |
| `cards/T7_PDF_STUDIO.md` | PDF-01–06, premium printout designer (extends the existing reports editor) |
| `cards/*.md` | The executable cards, one file per track slice (BL, T1, T2, T3, T4, T5A, T5B, T5C, T6, T7 foundation, T7 screens pointer, T8 engine core, T8 suites/skills/evals, T8 bots/pilots, T9). `cards/_LEGACY_14_v1.md` is the superseded v1 card list, kept unchanged |
| `BL04_LINT_SLOT.md` | BL-04 output note (lint slots), written by the builder that took BL-04 |
| `15_DOD_AND_E2E.md` | Master DoD, compiler DoD, E2E, new DoD |
| `16_RISKS.md` | Risk register |
| `17_COVERAGE_MATRIX.md` | Source ID → pack location |
| `18_OPEN_QUESTIONS.md` | Unresolved questions |

## Glossary (short)

Change-set: a closed list of typed ops. Plan hash: `sha256` of the canonical change-set, approval binds to it plus the schema fingerprint. Mode T: Bridge, one transaction. Mode C: plain RPC, compensating undo, risk +1. R0–R4: risk classes. L0–L4: autonomy. Tier A/B/C: model trust, not Odoo version. P1: Bridge installed. P2: transport only.
