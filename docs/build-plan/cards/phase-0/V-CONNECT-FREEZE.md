# V-CONNECT-FREEZE: Connect page freezes (measure before/after with 16k rows)

ID: V-CONNECT-FREEZE
Title: Connect page freezes (measure before/after with 16k rows)
Status: done
Phase: 0
Priority: P0
Type: verify
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: H-3.2-FREEZE;UIF-FREEZE
Depends on: none (phase order applies)
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F1 K0 V0 I0)
Context pack:
- `sed -n '216,218p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '715,727p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- docs/build-plan/FACTS.md
File allow-list:
- docs/build-plan/verify/V-CONNECT-FREEZE.md (new)
Goal: Measure whether the claim behind `V-CONNECT-FREEZE` is true today and record the evidence; no product change.
Steps:
1. Do not change product code. Measure exactly the claim in each AC using the commands below (tests, `rg`, a timed run, or a disposable `ingenium_*` live check). `docs/build-plan/verify/` does not exist yet; creating the allow-list file creates it.
2. Write `docs/build-plan/verify/V-CONNECT-FREEZE.md`: claim · command · measured output summary (counts, timings) · verdict (true / false / partial) · label proposal. Never upgrade a label without new evidence (INV-08).
3. If the verdict is false or partial, propose one ledger row (ID, one_line, card) in the Worker packet; do not fix it here.
4. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Connect page freezes (measure before/after with 16k rows) (source: ledger H-3.2-FREEZE, §3.2 L216-L218; §5.15)
- AC2: named failure: frozen Connect page (source: ledger UIF-FREEZE, §5.15)
- AC3: `docs/build-plan/verify/V-CONNECT-FREEZE.md` records claim, command, measured result and verdict; any false/partial verdict has a proposed ledger row
Symbols: `connectionsApi.listConnections` (`apps/web/src/lib/api/connections.ts` L5-7) calls `request<Connection[]>("/api/connections")` with no limit. `ConnectPage` (`apps/web/src/app/connect/page.tsx`) sets `SAVED_PAGE = 50` (L10), `shownSaved = matchingSaved.slice(0, savedLimit)` (L100), and renders `shownSaved.map` (L659). §5.15 L722 names "Frozen Connect page". §3.2 L216 is the freeze sentence; L217 is blank; L218 says "Frozen page".
Worked example (re-run; do not copy the verdict): command `rg -n "listConnections|SAVED_PAGE|shownSaved" apps/web/src/app/connect/page.tsx apps/web/src/lib/api/connections.ts`. A record that matches today's symbols: full `GET /api/connections`, first paint capped at 50. That record is `partial` until a 16_000-row disposable `ingenium_*` fixture is timed. `before` = time to materialise the full list; `after` = time until the first `SAVED_PAGE` cards paint. This card does not build a second product version.
Decision table:

| Evidence | Verdict |
|---|---|
| full `GET /api/connections` materialises every row AND a disposable 16_000-row fixture blocks the main thread (long task ≥ 50 ms) before the first `SAVED_PAGE` cards paint | true |
| the endpoint is paginated or the page never holds 16_000 `Connection` objects, AND that fixture paints the first page with no long task ≥ 50 ms | false |
| paint is capped at `SAVED_PAGE` but the 16_000-row fixture was not timed on a disposable `ingenium_*` DB | partial |
| the only 16k rows are on a non-`ingenium_*` DB | STOP-AND-ASK |

Test plan:
- `test -s docs/build-plan/verify/V-CONNECT-FREEZE.md` → exit 0
- the measurement commands recorded in that file, re-run by the Tester → same verdict
Common mistakes: citing a path that does not exist; restating the handover instead of citing its line; upgrading a label without evidence.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
