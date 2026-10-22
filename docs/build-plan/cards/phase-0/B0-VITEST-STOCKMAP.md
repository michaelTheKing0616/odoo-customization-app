# B0-VITEST-STOCKMAP: web Vitest passes in full (last 1571 pass + 1 StockMapPanel error)

ID: B0-VITEST-STOCKMAP
Title: web Vitest passes in full (last 1571 pass + 1 StockMapPanel error)
Status: done
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-1-AC2;H-3.13-VITEST
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 3 (C0 U1 F1 K1 V0 I0)
Context pack:
- `sed -n '461p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '372p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/web/src/components/
- apps/web/vitest.setup.ts
- docs/build-plan/FACTS.md
File allow-list:
- apps/web/src/components/
- apps/web/vitest.setup.ts
- apps/web/src/lib/b0_vitest_stockmap.test.ts (new)
Goal: Make every AC below true for `B0-VITEST-STOCKMAP` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output.
2. Write the tests in the allow-list files. Each test must fail if the behaviour were removed: name in the Worker packet the product line whose deletion would make it fail.
3. Run the Test plan command twice (second time `-p randomly` for API once DEC-047 lands) → identical green results.
4. If a test exposes a real defect, do not fix product code: mark it `xfail(strict=True, reason=<new ledger row>)` and report it in the Worker packet.
5. Write the Worker packet.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: web Vitest passes in full (last logged: 1,571 pass with 1 unrelated `StockMapPanel` error). (source: INGENIUM_MASTER_HANDOVER.md L461)
- AC2: Known bugs. One `StockMapPanel` vitest error noted during G9 "from another worker". Verify. (source: INGENIUM_MASTER_HANDOVER.md L372)
Symbols: `briefFromMap` L10 and `StockMapPanel` L31 in `apps/web/src/components/wireframe/StockMapPanel.tsx`. Tests in `apps/web/src/components/wireframe/StockMapPanel.test.tsx`, describe `Q6 StockMapPanel`: `brief prefers stock: extends the stock model when the person says so`, `asks at most the open questions, then hands the brief to App Studio`, `outlines each box on the sketch and strengthens the hovered one`.
Worked example: `briefFromMap(MAP, { model: "extend" })` with `MAP.target.maybe = { model: "fleet.vehicle", name: "Vehicle" }`, a reuse row label `Email` field `email` field_label `Email`, and a new row label `Plate number` type `char`. The string includes `Add to Odoo’s Vehicle (fleet.vehicle)`, `Use the fields Odoo already has: Email → Email`, and `Add new fields: Plate number (char)`. AC1 passes when `pnpm vitest run` (include `src/**/*.test.{ts,tsx}` from `apps/web/vitest.config.ts`) reports 0 failed. The logged 1,571 is the last pass count.
Decision (box overlay, the third `it`):

| imageUrl | row.box | hover | DOM |
| null | any | n/a | no `wireframe-box-*` |
| set | absent | n/a | no box for that region (`wireframe-box-r2` is absent in the test) |
| set | `[0.1, 0.2, 0.5, 0.1]` | none | `wireframe-box-r1` has `style.left` `10%` |
| set | that box | mouseEnter the row | `className` matches `/border-2/` |

Test plan:
- `cd apps/web && pnpm vitest run src/lib/b0_vitest_stockmap.test.ts src/components/wireframe/StockMapPanel.test.tsx` → all pass
- `cd apps/web && pnpm vitest run` → 0 failed (AC1)
Common mistakes: raw hex instead of tokens; a bare `next build` (overwrites dev `.next`; use own distDir); spinner instead of skeleton; copy that fails the jargon guard; light text on light-ish backgrounds.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
