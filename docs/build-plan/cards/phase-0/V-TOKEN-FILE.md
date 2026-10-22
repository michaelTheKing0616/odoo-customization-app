# V-TOKEN-FILE: token file location: styles/globals/tokens.css vs app/globals.css

ID: V-TOKEN-FILE
Title: token file location: styles/globals/tokens.css vs app/globals.css
Status: done
Phase: 0
Priority: P1
Type: verify
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: UI-5.2-TOKENFILE
Depends on: none (phase order applies)
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F1 K0 V0 I0)
Context pack:
- `sed -n '27,36p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '622,633p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '12p' docs/build-plan/FACTS.md`
- docs/build-plan/FACTS.md
File allow-list:
- docs/build-plan/verify/V-TOKEN-FILE.md (new)
Goal: Measure whether the claim behind `V-TOKEN-FILE` is true today and record the evidence; no product change.
Steps:
1. Do not change product code. Measure exactly the claim in each AC using the commands below (tests, `rg`, a timed run, or a disposable `ingenium_*` live check). `docs/build-plan/verify/` does not exist yet; creating the allow-list file creates it.
2. Write `docs/build-plan/verify/V-TOKEN-FILE.md`: claim · command · measured output summary (counts, timings) · verdict (true / false / partial) · label proposal. Never upgrade a label without new evidence (INV-08).
3. If the verdict is false or partial, propose one ledger row (ID, one_line, card) in the Worker packet; do not fix it here.
4. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: token file location: styles/globals/tokens.css vs app/globals.css (source: ledger UI-5.2-TOKENFILE, §0.2 vs §5.2)
- AC2: `docs/build-plan/verify/V-TOKEN-FILE.md` records claim, command, measured result and verdict; any false/partial verdict has a proposed ledger row
Symbols: §0.2 L35 names `apps/web/src/styles/globals/tokens.css`. §5.2 L623 says the box `tokens.css` is mirrored into `apps/web/src/app/globals.css`. FACTS L12 also names `apps/web/src/styles/studio-refinement/tokens.css`. `--r-sm` is declared in `apps/web/src/styles/globals/tokens.css` (L155).
Worked example (re-run; do not copy the verdict): command `rg -n '^@import' apps/web/src/app/globals.css`. One measured line that satisfies the import check: `2:@import "../styles/globals/tokens.css";`. Record whether `--accent` and `--r-sm` are defined in the imported file or in `app/globals.css` itself.
Decision table:

| What the files do | Verdict |
|---|---|
| `app/globals.css` only imports `styles/globals/tokens.css`, and the custom properties live in the imported file | true (the two handover sentences name different paths; the import links them) |
| `app/globals.css` defines the custom properties and does not import `styles/globals/tokens.css` | false (§5.2 is the location; §0.2's path is not the defining file) |
| both files define the same properties, or `studio-refinement/tokens.css` also defines `--accent` or `--r-sm` | partial |

Test plan:
- `test -s docs/build-plan/verify/V-TOKEN-FILE.md` → exit 0
- the measurement commands recorded in that file, re-run by the Tester → same verdict
Common mistakes: citing a path that does not exist; restating the handover instead of citing its line; upgrading a label without evidence.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
