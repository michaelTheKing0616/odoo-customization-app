# 08 Gates

Tope's time is a resource. Every ask is batched (`05_PACKETS.md` "Ask Tope"), ≤ 15 lines, each item with a recommended default and the cards it blocks. "Explicit yes" means a yes **in Tope's current message** (INV-18).

## Plan gates

| Gate | What Tope approves | Status |
|---|---|---|
| G0 | charter, invariants, ledger + coverage, decision list | approved 21 Oct |
| G1 | phases, dependency graph, routing summary, budget shares, pilot plan, open decisions | approved 21 Oct (DEC-003..005, 015, 024, 026..029, 032, 046..049) |
| G1B | App Studio Design Pack | approved 21 Oct (DEC-036..045) |
| G2 (per phase) | that phase's card pack, after the readiness check below | Phase 0 approved 22 Oct; later phases pending |

### G2 readiness check (Orchestrator, before asking Tope; per phase)

1. `python3 scripts/plan_lint.py cards --phase N` → 0 errors.
2. Holds: every `ITEMISE-AT-G2` row for the phase is itemised (FA-S01..S21 at Phase 5) and every itemise card for the phase (`FA-S*`, `DOC-SPEC-*`) is done, so its new rows and cards exist. `SPEC-TEXT-NEEDED` rows have text or a DEC.
3. Card prep (the `Prep` role, L2, one session per ≤ 10 cards): for each card, confirm every allow-list path exists (or is marked `(new)`), the context-pack line ranges are current, the ACs are measurable, and the Grok-ready standard holds (exact symbols, worked examples, decision table where logic branches, STOP-AND-ASK triggers). Prep may tighten wording, fix paths and add examples; it may **not** drop or weaken an AC (INV-05). Changes are listed in the G2 ask.
4. Clarity test on a 10% sample (min 3): a fresh L1 session reads the card and lists what it would do and any ambiguity. More than 2 ambiguities → rewrite.
5. Ask Tope once: card count, budget estimate (class caps × cards), GATE-A items, changes from prep, and the default "approve all".

## Card gates

| Gate | When | What happens |
|---|---|---|
| none | most cards | Tester PASS + Reviewer APPROVE closes the card |
| **A** pre-start | card needs a Tope decision (pricing, payment providers, Vexa, agent re-run timing, welcome letter, brand, IA grouping, website scope, i18n languages, authorizer default-on) | card stays `blocked-A` until the DEC is resolved in `09_DECISIONS_FOR_TOPE.md` |
| **B** UI visual | every P1-10 screen and every flagship ui-build card | Tope reviews the contact sheet (`docs/vision-verify/<screen>/`) before close |
| **C** commit/merge | a card group is ready to commit | Orchestrator proposes commit groups and messages; **no git history change without Tope's explicit yes** (INV-01) |
| **D** destructive or non-disposable | DB cleanup (`pg_dump -Fc` first), stopping processes, deleting files, anything on Tope's ports/services, Vexa deploy, non-sandbox installs | Tope's explicit yes in the current message; evidence of the backup logged first |
| **E** phase exit | all cards of the phase done | full suites twice in random order; `plan_lint` 0 uncovered for the phase; E2 (Fable) zero-loss audit; E1 sample review of score ≥ 10 and guarded-path cards; token ledger review vs `budget.json`; `STATE.md` retro |
| **R** release | P6 and P7 GATE-E passed | every handover §8.6 bar, every §4 AC, ASVS L2 checklist, live matrix 17–20 green, **or** Tope's written exception per item |

## Stop conditions (the Orchestrator stops and reports, never improvises)

- A card hits 80% of its role cap.
- Escalation ladder exhausted (`05_MODEL_ROUTING.md`).
- Any invariant would have to be broken to finish (git write, non-`ingenium_*` DB, forbidden port, Enterprise source, non-FOSS licence, secrets in logs, sealed holdout).
- A Worker needs a file outside its allow-list, or two cards need the same file at once.
- An oracle test looks wrong (ESCALATE, never edit).
- Weekly allocation in `budget.json` would be exceeded.
