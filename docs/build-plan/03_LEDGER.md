# 03 REQUIREMENT LEDGER

Data: `ledger.csv` (the source of truth). Lint: `python3 scripts/plan_lint.py ledger`. Report: `coverage/ledger.md`.

## Totals after G0 amendments (script-made, 21 Oct; `tools/amend_g0.py`, idempotent)
1,166 rows · 0 uncovered · 758 planned cards · 20 holds (FA-S ITEMISE-AT-G2 only; every SPEC-TEXT-NEEDED hold is itemised) · 11 wildcard refs.
Added at G0: old pack `NP-*` 349 · Bridge `BR-ITEM-*` 32 · Code Runner `CR-ITEM-*` 29 · `CACHE-A..H` 8 · `GUARD-1..5` 5 · SPEC `VD-G-*` 14 · suite `SUITE-TOOL-*`, `BULK-20-*`, `SUITE-SAFE-7-*` · `AS-FIX-*` 8 · `AS-ANYBRIEF` · `AS-CH-BRIEF` · `UIX-00..19` + `UIX-TOUCHES` · `REL-BR-RETRYWINDOW`.
Superseded: the Stage 1 totals (664 rows, 459 cards).

## Columns
`ID, source_section, one_line, type, priority, status_label_today, card_ids, tope_decision`
- `source_section` names the handover § and line (`L460`). Cards copy ACs **verbatim** from those lines: `sed -n '460p' docs/specs/INGENIUM_MASTER_HANDOVER.md`. `one_line` is only a pointer.
- `status_label_today` is the handover's §0.1 label, unchanged. Extra labels: `Reported` (Tope said it, not in logs), `Discrepancy` (two sources disagree), `Unknown` (no status given), `SPEC-TEXT-NEEDED`, `ITEMISE-AT-G2`.
- `card_ids` holds the **planned** card IDs. A card file is authored at its phase's G2. One card can cover several rows. One row can point at several cards.
- `tope_decision`: `DEC-nnn` refers to `09_DECISIONS_FOR_TOPE.md`. `D10` is an existing MEMORY lock.

## ID families
| Prefix | Source |
|---|---|
| `P0-n-ACk`, `P1-n-ACk`, `P1-6-*`, `P1-10-*` | §4 items and their ACs |
| `ARCH-n`, `H-2.x-*` | §2 architecture and foundations |
| `H-3.x-*`, `AS-*`, `T318-*` | §3 modules (AS = App Studio, including §8) |
| `SUITE-01..48` | Configuration Suite ideas (§3.7, §4 P2-1) |
| `TOUCH-001..162` | every design touch. Built ones are regression guards. 103 is missing from the handover, so it is VERIFY |
| `FA-A01..A30`, `FA-B1..B8`, `FA-Snn` | FEATURE_AUDIT app-wide items, bold bets, per-section rollups |
| `UI-5.x`, `UIF-*` | §5 standard and named failures |
| `SEC-6.x-*` | §6 security |
| `REL-7.x` | §7 reliability |
| `PREM-9.x` | §9 premium aspects |
| `DOC-*`, `DISC-*` | docs work and discrepancies |
| `INV-H10-n` | §10 rules. These are invariants, enforced by `02_INVARIANTS.md` and not by cards |
| `UIREF-*`, `UIX-*` | the 21 Oct UI reference pack; Tope's area map (`UI_REFERENCE_MAP.md`) |
| `NP-<old id>` | old pack `docs/plans/next-phase/` (DEC-022). The card ID is the old ID, or `REG-NP-<track>` when DONE |
| `BR-ITEM-nn`, `CR-ITEM-nn`, `CACHE-x`, `GUARD-n` | BRIDGE_RUNNER_SPEC items |
| `VD-G-*`, `SUITE-TOOL-*`, `BULK-20-*`, `SUITE-SAFE-7-*`, `AS-FIX-*` | SPEC / CONFIG_SUITE_SPEC / FIX_PLAN items (status from GAP_AUDIT + handover) |

## Traceability rules (enforced by `plan_lint`)
1. Every ledger ID has ≥ 1 planned card or a Tope decision (ledger mode). Every planned card has a file with all required fields by its phase G2 (cards mode).
2. Every card lists every ledger ID that points to it. Every ID a card lists exists in the ledger.
3. A card's status is one of `todo`, `in-progress`, `blocked`, or `done`. "Partial" is never a terminal state. A ledger row closes only when all its cards are `done` with evidence.
4. The coverage report is a required artifact of every gate (G0, G1, G1B, G2 per phase, GATE-E, GATE-R).
5. Holds (`SPEC-TEXT-NEEDED`, `ITEMISE-AT-G2`) must be resolved into item rows before the G2 of the phase that owns them. Wildcard refs (`VD-*`, `SUITE-*`, `TOUCH-*`) must expand into concrete card IDs at that G2.
6. Score ≥ 6 needs Elite design notes and Oracle tests. Guarded paths need Worker L3 (INV-14). Cards are ≤ 150 lines.

## Holds (31): what each needs
- **SPEC-TEXT-NEEDED (9):** the SPEC, CONFIG_SUITE_SPEC, BRIDGE_RUNNER_SPEC (Bridge 1-32 and Code Runner 1-29), APP_STUDIO_HANDOFF/FIX_PLAN, GAP_AUDIT, BRAND_GUIDE + tokens + PLAYBOOK, and failure C. Each is unblocked by DEC-002 (copy the box files into `docs/specs/`). Until then, no card may guess their contents.
- **ITEMISE-AT-G2 (20):** the FEATURE_AUDIT per-section ideas (`FA-S01..S21`). The text is on disk (`docs/FEATURE_AUDIT.md`), so they are itemised at Phase 5 G2. That saves tokens now and loses nothing.

## Discrepancies found (each has a row)
README positioning; settings.py model defaults; 11 vs 12 packs; website scope; `attendee_client.py`; the Dockerfile grep; the `studio-draft.ts` reformat; `/tmp` backups; root patches. Found in this pass: **self-approval scope §2.4 vs §6.5** (DEC-020); **dead letter after 6 tries (§3.9) vs after 5 attempts (§7.8)** (DEC-021); **an existing 330-card pack in `docs/plans/next-phase/` that the handover does not mention** (DEC-022); the token file location `styles/globals/tokens.css` vs `app/globals.css`; the name `ODOO_HOSTING.md` vs the repo's `ODOO_HOSTING_AND_VERSION_KINGSHIP.md`; touch 103 not mentioned; the nav.ts path labelled Inferred in App. B but Verified in §3.9.
