# Ingenium build plan: index

Status: **G0 + G1B approved (21 Oct 2026). Stage 2 and every phase's card pack delivered → **G1 approved 21 Oct**; next: Grok pilot, then Phase 0 G2. 1,194 ledger rows, 847 cards, 0 uncovered, `plan_lint` 0 errors. Grok orchestrator starts from `ORCHESTRATOR_PROMPT.md`.**

| File | What | Stage |
|---|---|---|
| `HANDOVER_INDEX.md` | handover § to line ranges; which cited specs exist | 1 ✓ |
| `01_TOKEN_CHARTER.md` + `budget.json` | charter; budget unit, weekly allocation, class caps, phase shares (one file to edit) | 1 ✓ |
| `02_INVARIANTS.md` | 18 invariants + repo traps | 1 ✓ |
| `03_LEDGER.md` + `ledger.csv` | 1,194 requirements, each mapped to a planned card or a decision | 1 ✓ (G0 + G1B amended) |
| `tools/amend_g0.py` | idempotent script that applied Tope's G0 answers to the ledger | 1 ✓ |
| `coverage/ledger.md` | `plan_lint` coverage report (0 uncovered) | 1 ✓ |
| `09_DECISIONS_FOR_TOPE.md` | resolved + open decisions with defaults | 1 ✓ |
| `FACTS.md` | established facts, append-only | 1 ✓ |
| `UI_REFERENCE_MAP.md` | Tope's 19-area reference map; all 78 routes assigned to an area | 1 ✓ |
| `.cursor/rules/00-token-economy.mdc`, `01-ingenium-invariants.mdc` | installed after G0 (sources in `drafts/`) | 1 ✓ |
| `../../scripts/plan_lint.py` | ledger and card lint (`ledger` / `cards --phase N` / `all`); reads `budget.json` | 1 ✓ |
| `app-studio/00_PACK.md` (design, rev 2), `ORACLES.md` (locked tests), `01_REVIEW.md` (Fable 5 review + dispositions), `CODE_MAP.md`, `ODOO_CRAFT.md` (senior-Odoo idiom catalog), `cards/phase-3/AS-*.md` (61 cards incl. live-DB grounding AS-GROUND-* and Draft Studio on v3), `tools/amend_g1b.py`, `tools/amend_g1c.py` | App Studio: why it fails, the v3 design, and buildable cards | 2B ✓ |
| `elevate/00_ELEVATE.md`, `elevate/ORACLES.md`, `cards/phase-7/EL-*.md` (51 cards; 5 merged into handover cards at Stage 2) | Every other feature raised above spec: measured Feature Excellence Bar + next-level features | 2B ✓ |
| `04_PHASES.md` (order, graph, why), `phase_map.json`, `05_MODEL_ROUTING.md` (roster, rubric, pilot), `05_PACKETS.md`, `06_TEST_STRATEGY.md`, `07_UI_EXCELLENCE_PROTOCOL.md`, `REFERENCE_NOTES.md` (skeleton; UI-REF-STUDY fills it), `08_GATES.md` (incl. G2 Prep check), `STATE.md` (orchestrator board: queue, locks, token ledger) | plan skeleton | 2 ✓ |
| `cards/phase-0..7/` (847), `coverage/phases.md` (counts, tiers, caps), `tools/build_cards.py` (generator, verbatim ACs), `tools/next_cards.py` (dispatch queue) | card packs; each phase released after its G2 Prep check | 3 ✓ |
| `ORCHESTRATOR_PROMPT.md` | the prompt for the Grok orchestrator session | 3 ✓ |

UI quality bar: `docs/design/references/ingenium-ui/` (`MANIFEST.md`, `motion/MOTION_NOTES.md`, `_contact/`) + `UI_REFERENCE_MAP.md`.
