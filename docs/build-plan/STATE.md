# Build state (Orchestrator board; the only file the Orchestrator rewrites every role)

Root `STATE.md` keeps session retros. This file is the live board for the build.

## Now

| Field | Value |
|---|---|
| Plan gate | Phase 0 G2 approved 22 Oct. Later phases not asked. |
| Active phases | 0 |
| Week | 1 · allocation 40M · reserve 15% · spent 0 (tokens n/a) |
| Pilot | All three closed [Done, code] 21 Oct. L2/L3 reruns and the grok-4.6 P-1 run were not done. |
| Blocked on Tope | B0-JUNK stays Gate D. DEC-031 is settled by the live test. Project tsc is still red on b0_dist.test.ts. |

## Queue (next eligible cards; Orchestrator refreshes with `python3 docs/build-plan/tools/next_cards.py`)

| # | Card | Phase | Type | Tier | Budget | Depends on (done?) |
|---|---|---|---|---|---|---|
| 1 | B0-INV | 0 | docs | L1 | XS | none · done [Done, code] |
| 2 | NP-MERGE | 0 | docs | L1 | XS | none · done [Done, code] |
| 3 | V-CONNECT-FREEZE | 0 | verify | L1 | XS | none · done [Done, code] · ledger Partial |
| 4 | V-TOKEN-FILE | 0 | verify | L1 | XS | none · done [Done, code] |
| 5 | BL-08 | 0 | docs | L3 | S | none · Worker in flight |
| 6 | DOC-SPECS-INTAKE | 0 | docs | L1 | XS | none · waits; `docs/` overlaps open locks |
| — | B0-DBGUARD | 0 | test | L2 | M | done [Done, code] |
| — | B0-ISO | 0 | build | L2 | M | done [Done, code] |
| — | B0-JUNK | 0 | build | L2 | M | Gate D · not started |
| — | REG-NP-UI | 0 | regression | L1 | S | hold · 2/2 · AC2 AC3 · AC5 keyboard · AC6 pinned |

## File locks (one Worker per file set)

| Lock | Card | Role holding | Files / globs | Since |
|---|---|---|---|---|
| L-BL-08 | BL-08 | hold | apps/api/tests/test_bl_08.py, docs/handoff/COMMIT_PLAN.md | 2026-10-22 |
| L-REG-NP-GND | REG-NP-GND | hold | apps/api/tests/test_reg_np_gnd.py | 2026-10-22 |
| L-BL-07 | BL-07 | hold | apps/api/tests/test_no_mcp_write.py, apps/api/tests/test_bl_07.py | 2026-10-22 |
| L-REG-NP-BL | REG-NP-BL | hold | apps/api/tests/test_reg_np_bl.py | 2026-10-22 |
| L-REG-NP-T1 | REG-NP-T1 | hold | apps/api/tests/test_reg_np_t1.py | 2026-10-22 |
| L-REG-NP-UI | REG-NP-UI | hold | apps/api/tests/test_reg_np_ui.py | 2026-10-22 |

Rule: a card is dispatched only if none of its allow-list paths matches an open lock (prefix match on directories). Release on CLOSE or on stop.

## In flight

| Card | Role | Loop | Tier | Started | Packet in |
|---|---|---|---|---|---|
| BL-08 | hold | 1/2 | L2 | 2026-10-22 | d831da67-b459-4724-8436-744ee173418c |
| REG-NP-GND | hold | 1/2 | L2 | 2026-10-22 | d65dddae-1a95-4e15-bf0a-28424f78a48b |
| BL-07 | hold | 1/2 | L2 | 2026-10-22 | c5ccaef0-36ec-45a1-b9bf-8ba215de64ac |
| REG-NP-BL | hold | 2/2 | L2 | 2026-10-22 | e127a619-9d10-4fe9-966b-d947d1c6d3bf |
| REG-NP-T1 | hold | 1/2 | L2 | 2026-10-22 | 8d791eef-284f-464d-a0e9-957be55c89f0 |
| REG-NP-UI | hold | 2/2 | L2 | 2026-10-22 | 4607b8d4-5de6-41cb-a7e3-75e31a518c04 |

## Token ledger (cost-weighted units, `budget.json` `unit`)

| Date | Card | Role | Tier | Tokens | Cap | % of cap | Note |
|---|---|---|---|---|---|---|---|
| 2026-10-21 | DOC-HANDOVER-ERRATA | Worker | L1 | n/a | 60000 | n/a | usage view not in this session |
| 2026-10-21 | DOC-HANDOVER-ERRATA | Tester | L2 | n/a | 25000 | n/a | T0 plan_lint errors=0; model interpreted |
| 2026-10-21 | DOC-HANDOVER-ERRATA | Reviewer | L1 | n/a | 20000 | n/a | APPROVE |
| 2026-10-21 | F1-CONTRAST-TOKENS | Tester | L2 | n/a | 150000 | n/a | PASS · vitest 3 · typecheck 0 · lint exit 1 is .next-e2e |
| 2026-10-21 | REG-HOSTGUARD | Worker | L1 | n/a | 150000 | n/a | usage view not in this session |
| 2026-10-21 | REG-HOSTGUARD | Tester | L2 | n/a | 60000 | n/a | PASS · 26 forward, 26 reverse, 26 shuffle seed 1 |
| 2026-10-21 | REG-HOSTGUARD | Reviewer | L1 | n/a | 45000 | n/a | APPROVE |
| 2026-10-21 | F1-CONTRAST-TOKENS | Worker | L1 | n/a | 400000 | n/a | dispatched L1; card routing says L2; allow-list gained tokens.css and theme.css |
| 2026-10-21 | F1-CONTRAST-TOKENS | Reviewer | L2 | n/a | 120000 | n/a | APPROVE |
| 2026-10-22 | NP-MERGE | Worker | L1 | n/a | 60000 | n/a | no files changed |
| 2026-10-22 | NP-MERGE | Tester | L2 | n/a | 25000 | n/a | PASS · 349 NP- rows · plan_lint errors=0 |
| 2026-10-22 | NP-MERGE | Reviewer | L1 | n/a | 20000 | n/a | APPROVE |
| 2026-10-22 | V-TOKEN-FILE | Worker | L1 | n/a | 60000 | n/a | verify file only |
| 2026-10-22 | V-TOKEN-FILE | Tester | L2 | n/a | 25000 | n/a | PASS |
| 2026-10-22 | V-TOKEN-FILE | Reviewer | L1 | n/a | 20000 | n/a | APPROVE |
| 2026-10-22 | V-CONNECT-FREEZE | Worker | L1 | n/a | 60000 | n/a | verify file only · partial |
| 2026-10-22 | V-CONNECT-FREEZE | Tester | L2 | n/a | 25000 | n/a | PASS · partial |
| 2026-10-22 | V-CONNECT-FREEZE | Reviewer | L1 | n/a | 20000 | n/a | APPROVE |
| 2026-10-22 | BL-08 | Oracle | L3 | n/a | 150000 | n/a | red · 4 failed, 0 passed |
| 2026-10-22 | B0-INV | Worker | L1 | n/a | 60000 | n/a | inventory only · no commit |
| 2026-10-22 | B0-INV | Tester | L2 | n/a | 25000 | n/a | PASS |
| 2026-10-22 | B0-INV | Reviewer | L1 | n/a | 20000 | n/a | APPROVE |
| 2026-10-22 | REG-NP-5B | Worker | L2 | n/a | 150000 | n/a | test file only · T0 2 passed, 2 passed |
| 2026-10-22 | REG-NP-5B | Tester | L2 | n/a | 60000 | n/a | PASS · [Done, code] |
| 2026-10-22 | REG-NP-L4 | Oracle | L3 | n/a | 150000 | n/a | green · 0 failed, 12 passed · pin already true |
| 2026-10-22 | REG-NP-L4 | Worker | L3 | n/a | 150000 | n/a | files none · falsifier lines only |
| 2026-10-22 | REG-NP-L4 | Tester | L2 | n/a | 60000 | n/a | PASS · 12 passed · [Done, code] |
| 2026-10-22 | REG-NP-L4 | Reviewer | L3 | n/a | 45000 | n/a | APPROVE · L4 stays off |
| 2026-10-22 | REG-NP-5C | Worker | L2 | n/a | 150000 | n/a | test file only · 131 passed both orders |
| 2026-10-22 | REG-NP-5C | Tester | L2 | n/a | 60000 | n/a | PASS · [Done, code] |
| 2026-10-22 | REG-NP-5C | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · L4 stays off |
| 2026-10-22 | REG-SANDBOX | Worker | L1 | n/a | 150000 | n/a | files none · falsifier only |
| 2026-10-22 | REG-SANDBOX | Tester | L2 | n/a | 60000 | n/a | PASS · 12 passed, 1 skipped |
| 2026-10-22 | REG-SANDBOX | Reviewer | L1 | n/a | 45000 | n/a | APPROVE · assert_isolated kept |
| 2026-10-22 | REL-STATIC-WRITE | Worker | L3 | n/a | 800000 | n/a | files none · oracle already green |
| 2026-10-22 | REL-STATIC-WRITE | Tester | L2 | n/a | 300000 | n/a | PASS · 4 passed |
| 2026-10-22 | REL-STATIC-WRITE | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · no snapshot field |
| 2026-10-22 | B0-AICACHE-ISO | Worker | L2 | n/a | 400000 | n/a | conftest cache path · live_ai skip |
| 2026-10-22 | B0-AICACHE-ISO | Tester | L2 | n/a | 150000 | n/a | PASS · 6 passed, 1 skipped |
| 2026-10-22 | B0-AICACHE-ISO | Reviewer | L2 | n/a | 120000 | n/a | APPROVE · no ~/.ingenium |
| 2026-10-22 | REG-NP-5A | Worker | L3 | n/a | 150000 | n/a | pins only · no product edit |
| 2026-10-22 | REG-NP-5A | Tester | L2 | n/a | 60000 | n/a | PASS · 24 passed, reverse 24 |
| 2026-10-22 | REG-NP-5A | Reviewer | L3 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | REG-NP-T8 | Worker | L3 | n/a | 150000 | n/a | pins only · no product edit |
| 2026-10-22 | REG-NP-T8 | Tester | L2 | n/a | 60000 | n/a | PASS · 14 passed, reverse 14 |
| 2026-10-22 | REG-NP-T8 | Reviewer | L3 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | REG-NP-T6 | Worker | L3 | n/a | 150000 | n/a | pins only · no product edit |
| 2026-10-22 | REG-NP-T6 | Tester | L2 | n/a | 60000 | n/a | PASS · 22 passed, reverse 22 |
| 2026-10-22 | REG-NP-T6 | Reviewer | L3 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | REG-NP-GND-FIX | Worker | L3 | n/a | 150000 | n/a | decline-only pass |
| 2026-10-22 | REG-NP-GND-FIX | Tester | L2 | n/a | 60000 | n/a | PASS · 18 passed |
| 2026-10-22 | REG-NP-GND-FIX | Reviewer | L3 | n/a | 45000 | n/a | APPROVE · install still gated |
| 2026-10-22 | B0-DIST | Worker | L3 | n/a | 800000 | n/a | distDir in the script |
| 2026-10-22 | B0-DIST | Tester | L2 | n/a | 300000 | n/a | PASS · vitest 8 · curl 200 |
| 2026-10-22 | B0-DIST | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · [Done, live] |
| 2026-10-22 | REG-NP-T4 | Worker | L3 | n/a | 150000 | n/a | import recorder |
| 2026-10-22 | REG-NP-T4 | E1 | E1 | n/a | 150000 | n/a | fix note only |
| 2026-10-22 | REG-NP-T4 | Tester | L2 | n/a | 60000 | n/a | PASS · 18 passed, reverse 18 |
| 2026-10-22 | REG-NP-T4 | Reviewer | L3 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | REG-NP-DEV | Worker | L3 | n/a | 150000 | n/a | phrase pin only |
| 2026-10-22 | REG-NP-DEV | Tester | L2 | n/a | 60000 | n/a | PASS · 2 passed, reverse 2 |
| 2026-10-22 | REG-NP-DEV | Reviewer | L3 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | B0-VITEST-STOCKMAP | Worker | L2 | n/a | 400000 | n/a | tooltip delay · stock map oracle |
| 2026-10-22 | B0-VITEST-STOCKMAP | Tester | L2 | n/a | 150000 | n/a | PASS · 1585 passed, 1 skipped |
| 2026-10-22 | B0-VITEST-STOCKMAP | Reviewer | L2 | n/a | 120000 | n/a | APPROVE |
| 2026-10-22 | B0-ALEMBIC | Worker | L3 | n/a | 800000 | n/a | startup ALTER removed |
| 2026-10-22 | B0-ALEMBIC | Oracle | L3 | n/a | 800000 | n/a | real upgrade head |
| 2026-10-22 | B0-ALEMBIC | Tester | L2 | n/a | 300000 | n/a | PASS · 6 passed |
| 2026-10-22 | B0-ALEMBIC | Reviewer | L3 | n/a | 240000 | n/a | APPROVE |
| 2026-10-22 | REG-AIOFF | Worker | L1 | n/a | 150000 | n/a | test file only · T0 2 passed, 2 passed |
| 2026-10-22 | REG-AIOFF | Tester | L2 | n/a | 60000 | n/a | PASS · [Done, code] |
| 2026-10-22 | REG-NP-BL | Worker | L1 | n/a | 150000 | n/a | test file only · T0 6 passed · reverse 6 passed · AC1 open |
| 2026-10-22 | REG-NP-5B | Reviewer | L2 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | REG-AIOFF | Reviewer | L1 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | B0-DIST | Oracle | L3 | n/a | 800000 | n/a | 4 failed, 4 passed · AC1 AC2 red |
| 2026-10-22 | REG-NP-UI | Worker | L1 | n/a | 150000 | n/a | test file only · 16 passed, reverse 16 |
| 2026-10-22 | REG-NP-UI | Tester | L2 | n/a | 60000 | n/a | FAIL · hold · AC2 AC3 AC5 AC6 |
| 2026-10-22 | REG-DRYINSTALL | Worker | L2 | n/a | 150000 | n/a | test file only |
| 2026-10-22 | REG-DRYINSTALL | Tester | L2 | n/a | 60000 | n/a | PASS · 14 passed, reverse 14 |
| 2026-10-22 | REG-DRYINSTALL | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · major 20 reads the 19 list |
| 2026-10-22 | REG-NP-UI-FIX | Worker | L2 | n/a | 150000 | n/a | text child throws before Children.only |
| 2026-10-22 | REG-NP-UI-FIX | Tester | L2 | n/a | 60000 | n/a | PASS · vitest 11 · regression 16 and 16 |
| 2026-10-22 | REG-NP-UI-FIX | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · text child named |
| 2026-10-22 | REG-NP-UI | Worker | L1 | n/a | 150000 | n/a | loop 2 · text-child pin · 17 and 17 |
| 2026-10-22 | REG-NP-UI | Tester | L2 | n/a | 60000 | n/a | loop 2 · FAIL · hold · AC5 keyboard |
| 2026-10-22 | REG-NP-BR | Worker | L1 | n/a | 150000 | n/a | test file only · 8 passed, reverse 8 |
| 2026-10-22 | REG-NP-BR | Tester | L2 | n/a | 60000 | n/a | PASS · 8 passed, reverse 8 |
| 2026-10-22 | REG-NP-BR | Reviewer | L1 | n/a | 45000 | n/a | APPROVE |
| 2026-10-22 | B0-DBGUARD | Worker | L2 | n/a | 400000 | n/a | loop 2 · query host/hostaddr/dbname · 15 and 15 |
| 2026-10-22 | B0-DBGUARD | Tester | L2 | n/a | 150000 | n/a | PASS · 15 passed twice |
| 2026-10-22 | B0-DBGUARD | Reviewer | L2 | n/a | 120000 | n/a | APPROVE |
| 2026-10-22 | B0-ISO | Worker | L2 | n/a | 400000 | n/a | loop 1 · 18 passed, reverse 18 |
| 2026-10-22 | B0-ISO | Tester | L2 | n/a | 150000 | n/a | loop 1 · FAIL · AC2 counts unread |
| 2026-10-22 | B0-ISO | Worker | L2 | n/a | 400000 | n/a | loop 2 · counts equal · 18 and 18 |
| 2026-10-22 | B0-ISO | Tester | L2 | n/a | 150000 | n/a | loop 2 · PASS · counts equal |
| 2026-10-22 | B0-ISO | Reviewer | L2 | n/a | 120000 | n/a | APPROVE |
| 2026-10-22 | V-STUDIODRAFT | Worker | L1 | n/a | 150000 | n/a | live test 3 passed · tsc red outside card |
| 2026-10-22 | V-STUDIODRAFT | Tester | L2 | n/a | 60000 | n/a | PASS · 3 passed · [Done, live] |
| 2026-10-22 | V-STUDIODRAFT | Reviewer | L1 | n/a | 45000 | n/a | CHANGES · restore applyStudioSession |
| 2026-10-22 | V-STUDIODRAFT | Worker | L1 | n/a | 60000 | n/a | loop 2 · single POST restored · 3 passed |
| 2026-10-22 | V-STUDIODRAFT | Tester | L2 | n/a | 60000 | n/a | loop 2 · PASS · [Done, live] |
| 2026-10-22 | V-STUDIODRAFT | Reviewer | L1 | n/a | 45000 | n/a | loop 2 · APPROVE |

Weekly totals by tier (T0 / L1 / L2 / L3 / E1 / E2) and by phase are summed at each GATE-E and compared with `05_MODEL_ROUTING.md` projected shares.

## Escalations

| Date | Card | From→to | Trigger | Fix note | Tokens | Outcome |
|---|---|---|---|---|---|---|
| 2026-10-22 | REG-NP-T4 | L3→E1 | loop 2, AC6 `from app import llm_gateway` still passes | docs/build-plan/fix-notes/REG-NP-T4.md | n/a | APPROVE · [Done, code] |

## Packets (newest first; keep the last 20)

```
CLOSE V-STUDIODRAFT · 2026-10-22
PROGRESS: 2026-10-22 · V-STUDIODRAFT · vitest studio-draft.live.test.ts · 3 passed · [Done, live]
ledger: AS-STUDIODRAFT and DISC-STUDIODRAFT → [Done, live]
locks released: L-V-STUDIODRAFT · tokens: W n/a T n/a R n/a vs cap 150000/60000/45000
facts: FACTS.md +1 line · DEC-031 resolved by test · tsc still red on b0_dist.test.ts
```

```
CLOSE B0-ISO · 2026-10-22
PROGRESS: 2026-10-22 · B0-ISO · uv run pytest -q tests/test_b0_iso.py · 18 passed, reverse 18 passed · counts equal · [Done, code]
ledger: P0-3-AC1 and P0-3-AC2 → [Done, code] · ARCH-1 stays Verified · REL-7.6 stays Open
locks released: L-B0-ISO · tokens: W n/a T n/a R n/a vs cap 400000/150000/120000
facts: FACTS.md +1 line
```

```
CLOSE B0-DBGUARD · 2026-10-22
PROGRESS: 2026-10-22 · B0-DBGUARD · uv run pytest -q tests/test_b0_dbguard.py · 15 passed, reverse 15 passed · [Done, code]
ledger: SEC-6.7-AC → [Done, code]
locks released: L-B0-DBGUARD · tokens: W n/a T n/a R n/a vs cap 400000/150000/120000
facts: FACTS.md +1 line
```

```
CLOSE REG-NP-BR · 2026-10-22
PROGRESS: 2026-10-22 · REG-NP-BR · uv run pytest -q tests/test_reg_np_br.py · 8 passed, reverse 8 passed · [Done, code]
ledger: NP-BR-01, NP-BR-04, NP-BR-05 → [Done, code]
locks released: L-REG-NP-BR · tokens: W n/a T n/a R n/a vs cap 150000/60000/45000
```

```
TESTER REG-NP-UI · loop 2 · FAIL
T0: 17 passed and reverse 17 passed
AC6 text child pinned. AC2 AC3 no worked example. AC5 keyboard sentence stays unpinned.
label: hold · loops 2/2
```

```
CLOSE REG-NP-UI-FIX · 2026-10-22
PROGRESS: 2026-10-22 · REG-NP-UI-FIX · vitest Button.asChild.test.tsx · 11 passed · regression 16 and 16 · [Done, code]
ledger: NP-UI-F07 stays on REG-NP-UI
locks released: L-REG-NP-UI-FIX · tokens: W n/a T n/a R n/a vs cap 150000/60000/45000
```

```
CLOSE REG-DRYINSTALL · 2026-10-22
PROGRESS: 2026-10-22 · REG-DRYINSTALL · uv run pytest -q tests/test_reg_dryinstall.py · 14 passed, reverse 14 passed · [Done, code]
ledger: H-2.9-DRYINSTALL → [Done, code]
locks released: L-REG-DRYINSTALL · tokens: W n/a T n/a R n/a vs cap 150000/60000/45000
```

```
TESTER REG-NP-UI · loop 1 · FAIL
oracle: 16 passed, 3.43s and reverse 16 passed, 1.84s
AC1 AC4 AC7 AC8 met. AC2 AC3 no worked example. AC5 keyboard sentence not pinned. AC6 error string not pinned.
label: hold
```

```
CLOSE REG-NP-5B · 2026-10-22
PROGRESS: 2026-10-22 · REG-NP-5B · pytest tests/test_reg_np_5b.py · 2 passed · [Done, code]
ledger: NP-5B-01, NP-5B-07 → [Done, code]
locks released: L-REG-NP-5B · tokens: W n/a T n/a R n/a vs cap 150000/60000/45000
```

```
CLOSE REG-AIOFF · 2026-10-22
PROGRESS: 2026-10-22 · REG-AIOFF · pytest tests/test_reg_aioff.py · 2 passed · [Done, code]
ledger: H-2.7-AIOFF → [Done, code]
locks released: L-REG-AIOFF · tokens: W n/a T n/a R n/a vs cap 150000/60000/45000
```

```
REVIEW REG-NP-5B · APPROVE
```

```
REVIEW REG-AIOFF · APPROVE
```

```
ORACLE B0-DIST
tests: apps/web/src/lib/b0_dist.test.ts
cases: 8 · AC1 AC2 red (4 failed) · AC3 AC4 passed
red: pnpm exec vitest run src/lib/b0_dist.test.ts → 4 failed, 4 passed
ambiguities resolved: AC3 live curl on existing :3002; AC5 no pagination; AC6 no database
```

```
WORKER REG-NP-BL · loop 1
files: ?? apps/api/tests/test_reg_np_bl.py (133 lines)
outside allow-list: none
T0: 6 passed, exit 0 · reverse node ids 6 passed, exit 0
AC1 open: card says do not write 03_BASELINE.md and do not freeze counts
oracles edited: no
```

```
TESTER REG-AIOFF · loop 1 · verdict PASS
AC1 pass · off+gemini → None · off+mock → MockLLMProvider · label [Done, code]
T0: 2 passed, then mock-then-gemini 2 passed
```

```
TESTER REG-NP-5B · loop 1 · verdict PASS
AC1 pass · AC2 pass · label [Done, code]
T0: 2 passed, then 2 passed
```

```
ORACLE REG-NP-L4
tests: apps/api/tests/test_reg_np_l4.py
cases: 12 · source: card ACs
red: 0 failed, 12 passed (pin already true; test left green)
ambiguities: none
```

```
WORKER REG-AIOFF · loop 1
files: ?? apps/api/tests/test_reg_aioff.py (48 lines)
outside allow-list: none
T0: uv run pytest -q tests/test_reg_aioff.py → 2 passed, exit 0
T0: mock node then gemini node → 2 passed, exit 0
oracles edited: no
```

```
WORKER REG-NP-5B · loop 1
files: ?? apps/api/tests/test_reg_np_5b.py (88 lines)
outside allow-list: none
T0: uv run pytest -q tests/test_reg_np_5b.py → 2 passed, exit 0
T0: two named tests → 2 passed, exit 0
oracles edited: no
```

```
CLOSE B0-INV · 2026-10-22
PROGRESS: 2026-10-22 · B0-INV · plan_lint all · errors=0 · commit: no · [Done, code]
ledger: P0-9-AC1..AC4, VD-REG-CLASSIC, DOC-WORKTREE, DISC-TMP, DISC-ROOTPATCH → [Done, code]
locks released: L-B0-INV · tokens: W n/a T n/a R n/a vs cap 60000/25000/20000
```

```
REVIEW B0-INV · APPROVE
```

```
ORACLE BL-08 · red
tests: apps/api/tests/test_bl_08.py
cases: 4 · source: card ACs AC1 AC2
red: python3 -m pytest tests/test_bl_08.py -q --tb=line --noconftest → 4 failed, 0 passed
ambiguities: none
```

```
REWRITE clarity · 1d358345-2b45-449f-a66c-97223c557081
cards: 4 · AC lines changed: none
B0-GREEN, B0-TESTFIX-ORDER, REG-NP-GND, UI-AUDIT-ALL readings locked
plan_lint cards --phase 0: errors=0
ASK Phase 0 G2 sent. Not approved.
```

```
CLARITY phase-0 sample · 45726b6c-b2a3-453b-ba54-85d3813266ac
5 of 44 (every 9th). Ambiguities: B0-GREEN 4, B0-TESTFIX-ORDER 5, REG-AIOFF 1, REG-NP-GND 5, UI-AUDIT-ALL 4.
Rewrite: the four cards over 2. REG-AIOFF stays. AC lines not to be weakened.
```

```
PREP phase-0 batch 4 · 2792e41e-cb6b-4421-9bf0-01be48047f15
cards: 10 · AC changes: none · path fixes: none
ambiguities held: REG-NP-T1 AC1 AC3 AC8 AC9 AC11 AC12 AC15 AC16 AC20 AC21 AC22; REG-NP-T4 AC1 AC3 AC4 AC5 AC9; REG-NP-UI AC2 AC3; REL-STATIC-WRITE AC2
```

```
PREP phase-0 batch 3 · b21aab10-fccc-49d1-a818-1f5d1c743a0e
cards: 10 · AC changes: none · REG-HOSTGUARD stays done
path fixes: none
ambiguities held: NP-MERGE AC1 (330 vs 349); REG-DRYINSTALL AC1 (major 20 vs empty list); REG-NP-5A AC2, AC7, AC8; REG-NP-BL AC1
```

```
PREP phase-0 batch 2 · 5fff8b5e-2cff-4707-9b8f-633bd50426f2
cards: 10 · AC changes: none · DOC-HANDOVER-ERRATA stays done
path fixes: cluster test files added on the six B0-TESTFIX cards; BL-07 allow-list is now test_no_mcp_write.py plus test_bl_07.py (new)
ambiguities held: shared AC2 cluster paragraph on every TESTFIX card; UNDERSTAND names no node ids; VITEST-STOCKMAP AC2; BL-07 AC2 and AC4; BL-08 AC1 and AC2 vs COMMIT_PLAN.md only
```

```
PREP phase-0 batch 1 · 232d5980-e317-4181-95d3-cf31fe000ddb
cards: 10 · AC changes: none
path fix: B0-DIST allow-list gained .gitignore (AC4)
ambiguities held: B0-AICACHE-ISO title vs AC1; B0-ALEMBIC AC3; B0-DIST AC3, AC5, AC6; B0-GREEN AC2; B0-ISO AC2, AC3, AC5; B0-JUNK AC3, AC4 (GATE-D not run); B0-TESTFIX-AIOFF AC1, AC2
```

```
PREP phase-0 batch 5 · 01ca55a4-2d9f-4818-8c65-96f726eea3c3
cards: 4 · AC changes: none
path fixes: UI-AUDIT-ALL spec path; V-STUDIODRAFT method names; V-TOKEN-FILE import
ambiguities held: UI-AUDIT-ALL AC1, AC2, AC3; V-STUDIODRAFT AC2
```

```
CLOSE F1-CONTRAST-TOKENS · 2026-10-21
PROGRESS: 2026-10-21 · F1-CONTRAST-TOKENS · vitest f1_contrast_tokens.test.ts · 3 passed, typecheck 0 · [Done, code]
ledger: P0-6-AC1 → [Done, code]
locks released: L-F1-CONTRAST-TOKENS · tokens: W n/a T n/a R n/a vs cap 400000/150000/120000
facts: FACTS.md +1 line. Pilot matrix not measured.
```

```
REVIEW F1-CONTRAST-TOKENS · APPROVE
agent: 44db7fea-78e2-4095-9eae-5112cfe24fe9
```

```
CLOSE REG-HOSTGUARD · 2026-10-21
PROGRESS: 2026-10-21 · REG-HOSTGUARD · pytest tests/test_reg_hostguard.py · 26/26/26 · [Done, code]
ledger: H-2.9-HOSTGUARD → [Done, code]
locks released: L-REG-HOSTGUARD · tokens: W n/a T n/a R n/a vs cap 150000/60000/45000
facts: FACTS.md +1 line. B0-INV still todo.
```

```
REVIEW REG-HOSTGUARD · APPROVE
AC1 pass. Pin: deleting getaddrinfo assignment fails test_reg_hostguard.py:88.
Allow-list: only the new test. Label [Done, code].
agent: 179cd8bd-7b48-4e07-ac5d-18359fbac817
```

```
TESTER F1-CONTRAST-TOKENS · loop 1 · verdict PASS
AC1 pass · vitest 3 passed, 410ms
guards: tsc ✓ · lint not (.next-e2e; 0 hits in card files) · contrast ✓
label proposal: [Done, code]
```

```
DISPATCH F1-CONTRAST-TOKENS · role: Reviewer · tier: L2 · loop: 1/2
card: docs/build-plan/cards/phase-1/F1-CONTRAST-TOKENS.md
budget: M · reviewer cap 120000 · stop at 80%
input: Tester PASS above
agent: 44db7fea-78e2-4095-9eae-5112cfe24fe9
```

```
DISPATCH DOC-HANDOVER-ERRATA · role: Worker · tier: L1 · loop: 1/2
card: docs/build-plan/cards/phase-0/DOC-HANDOVER-ERRATA.md
locks: L-DOC-HANDOVER-ERRATA · docs/
budget: XS · this role cap 60000 · stop at 80%
input packet: none
rules: .cursorrules + 01_TOKEN_CHARTER.md + 02_INVARIANTS.md. Do only this card.
```

```
DISPATCH F1-CONTRAST-TOKENS · role: Worker · tier: L1 · loop: 1/2
card: docs/build-plan/cards/phase-1/F1-CONTRAST-TOKENS.md
locks: L-F1-CONTRAST-TOKENS · globals.css, components/ui/, components/shell/, lib/nav.ts, eslint.config.mjs, lib/f1_contrast_tokens.test.ts
budget: M · this role cap 400000 · stop at 80%
input packet: none
rules: .cursorrules + 01_TOKEN_CHARTER.md + 02_INVARIANTS.md. Do only this card.
```

## Done this week

| Date | Card | Label | PROGRESS line |
|---|---|---|---|
| 2026-10-21 | DOC-HANDOVER-ERRATA | [Done, code] | 2026-10-21 · DOC-HANDOVER-ERRATA · plan_lint all · errors=0 uncovered=0 · [Done, code] |
| 2026-10-21 | REG-HOSTGUARD | [Done, code] | 2026-10-21 · REG-HOSTGUARD · pytest tests/test_reg_hostguard.py · 26 forward, 26 reverse, 26 shuffle seed 1 · [Done, code] |
| 2026-10-21 | F1-CONTRAST-TOKENS | [Done, code] | 2026-10-21 · F1-CONTRAST-TOKENS · vitest f1_contrast_tokens.test.ts · 3 passed, typecheck 0 · [Done, code] |
| 2026-10-22 | NP-MERGE | [Done, code] | 2026-10-22 · NP-MERGE · plan_lint all · errors=0 · np_rows=349 · [Done, code] |
| 2026-10-22 | V-TOKEN-FILE | [Done, code] | 2026-10-22 · V-TOKEN-FILE · rg @import globals.css · tokens.css holds --accent and --r-sm · [Done, code] |
| 2026-10-22 | V-CONNECT-FREEZE | [Done, code] | 2026-10-22 · V-CONNECT-FREEZE · full list, paint 50, no 16k timing · partial · [Done, code] |
| 2026-10-22 | B0-INV | [Done, code] | 2026-10-22 · B0-INV · plan_lint all · errors=0 · 9 APPLY scripts and 13 patches in tree · commit: no · [Done, code] |
| 2026-10-22 | REG-NP-5B | [Done, code] | 2026-10-22 · REG-NP-5B · uv run pytest -q tests/test_reg_np_5b.py · 2 passed, then 2 passed · [Done, code] |
| 2026-10-22 | REG-AIOFF | [Done, code] | 2026-10-22 · REG-AIOFF · uv run pytest -q tests/test_reg_aioff.py · 2 passed, then mock-then-gemini 2 passed · [Done, code] |
| 2026-10-22 | REG-NP-L4 | [Done, code] | 2026-10-22 · REG-NP-L4 · uv run pytest -q tests/test_reg_np_l4.py · 12 passed · [Done, code] |
| 2026-10-22 | REL-STATIC-WRITE | [Done, code] | 2026-10-22 · REL-STATIC-WRITE · uv run pytest -q tests/test_rel_static_write.py · 4 passed · [Done, code] |
| 2026-10-22 | B0-AICACHE-ISO | [Done, code] | 2026-10-22 · B0-AICACHE-ISO · uv run pytest -q tests/test_b0_aicache_iso.py · 6 passed, 1 skipped · [Done, code] |
| 2026-10-22 | REG-NP-5A | [Done, code] | 2026-10-22 · REG-NP-5A · uv run pytest -q tests/test_reg_np_5a.py · 24 passed, reverse 24 passed · [Done, code] |
| 2026-10-22 | REG-NP-5C | [Done, code] | 2026-10-22 · REG-NP-5C · uv run pytest -q tests/test_reg_np_5c.py · 131 passed, reverse 131 passed · [Done, code] |
| 2026-10-22 | REG-SANDBOX | [Done, code] | 2026-10-22 · REG-SANDBOX · uv run pytest -q tests/test_reg_sandbox.py · 12 passed, 1 skipped · [Done, code] |
| 2026-10-22 | REG-NP-T8 | [Done, code] | 2026-10-22 · REG-NP-T8 · uv run pytest -q tests/test_reg_np_t8.py · 14 passed, reverse 14 passed · [Done, code] |
| 2026-10-22 | REG-NP-T6 | [Done, code] | 2026-10-22 · REG-NP-T6 · uv run pytest -q tests/test_reg_np_t6.py · 22 passed, reverse 22 passed · [Done, code] |
| 2026-10-22 | REG-NP-GND-FIX | [Done, code] | 2026-10-22 · REG-NP-GND-FIX · decline pin plus dry-run ledger · 18 passed · [Done, code] |
| 2026-10-22 | B0-DIST | [Done, live] | 2026-10-22 · B0-DIST · pnpm build then curl /, /connect, /settings · 200 · vitest 8 passed · [Done, live] |
| 2026-10-22 | REG-NP-T4 | [Done, code] | 2026-10-22 · REG-NP-T4 · uv run pytest -q tests/test_reg_np_t4.py · 18 passed, reverse 18 passed · [Done, code] |
| 2026-10-22 | REG-NP-DEV | [Done, code] | 2026-10-22 · REG-NP-DEV · uv run pytest -q tests/test_reg_np_dev.py · 2 passed, reverse 2 passed · [Done, code] |
| 2026-10-22 | B0-VITEST-STOCKMAP | [Done, code] | 2026-10-22 · B0-VITEST-STOCKMAP · pnpm vitest run · 1585 passed, 1 skipped, 0 failed · [Done, code] |
| 2026-10-22 | B0-ALEMBIC | [Done, code] | 2026-10-22 · B0-ALEMBIC · uv run pytest -q tests/test_b0_alembic.py · 6 passed · [Done, code] |
| 2026-10-22 | REG-DRYINSTALL | [Done, code] | 2026-10-22 · REG-DRYINSTALL · uv run pytest -q tests/test_reg_dryinstall.py · 14 passed, reverse 14 passed · [Done, code] |
| 2026-10-22 | REG-NP-BR | [Done, code] | 2026-10-22 · REG-NP-BR · uv run pytest -q tests/test_reg_np_br.py · 8 passed, reverse 8 passed · [Done, code] |
| 2026-10-22 | REG-NP-UI-FIX | [Done, code] | 2026-10-22 · REG-NP-UI-FIX · vitest Button.asChild.test.tsx · 11 passed · regression 16 and 16 · [Done, code] |
| 2026-10-22 | B0-DBGUARD | [Done, code] | 2026-10-22 · B0-DBGUARD · uv run pytest -q tests/test_b0_dbguard.py · 15 passed, reverse 15 passed · [Done, code] |
| 2026-10-22 | B0-ISO | [Done, code] | 2026-10-22 · B0-ISO · uv run pytest -q tests/test_b0_iso.py · 18 passed, reverse 18 passed · counts equal · [Done, code] |
| 2026-10-22 | V-STUDIODRAFT | [Done, live] | 2026-10-22 · V-STUDIODRAFT · vitest studio-draft.live.test.ts · 3 passed · [Done, live] |
