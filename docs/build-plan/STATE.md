# Build state (Orchestrator board; the only file the Orchestrator rewrites every role)

Root `STATE.md` keeps session retros. This file is the live board for the build.

## Now

| Field | Value |
|---|---|
| Plan gate | Phase 0 G2 approved 22 Oct. Later phases not asked. |
| Active phases | 0, 1 |
| Week | 1 · allocation 40M · reserve 15% · spent 0 (tokens n/a) |
| Pilot | All three closed [Done, code] 21 Oct. L2/L3 reruns and the grok-4.6 P-1 run were not done. |
| Blocked on Tope | B0-JUNKb `--apply` stays off. REG-NP-T1b sets `install_ready` only when `prove_status` is proved; the 2026-10-22 capture is still ABSENT; no new sandbox prove. F1-CONTRAST-FIX and F1-CONTRAST-TEST wait on SPEC open decision 3 (`--brand`). Recommended default is handover §5.2: keep orange `#f97316` / `#fb923c` as the brand mark, never as a white-text background; primary buttons use teal `#0f766e` with white text in light mode and `#2dd4bf` with basalt text in dark mode; an orange control uses basalt text. F1-HYDRATE AC2’s 126-route Playwright crawl is outside the allow-list. Recommended default: do not add that spec on this card; the vitest pin is the done bar; a later card that lists the spec owns the crawl. F1-PAGINATE needs `apps/web/src/app/connect/page.tsx` and `apps/web/src/lib/api/connections.ts` to use the new page. Recommended default: allow those two files only. Until then, `GET /api/connections` with no limit returns the 50 newest rows. |

## Queue (next eligible cards; Orchestrator refreshes with `python3 docs/build-plan/tools/next_cards.py`)

| # | Card | Phase | Type | Tier | Budget | Depends on (done?) |
|---|---|---|---|---|---|---|
| 1 | REG-NP-T1b | 0 | regression | L3 | M | code sets install_ready only when proved · 2026-10-22 log still ABSENT · card still todo · lock held |
| — | B0-RANDOM-ORDER | 0 | test | L2 | M | merged 9e8e360b |
| — | B0-RANDOM-ORDER-b | 0 | test | L2 | M | done · no product diff · lock released |
| — | B0-JUNKb | 0 | build | L2 | S | blocked · `--apply` off |
| — | B0-TESTFIX-AIOFF | 0 | test | L2 | M | done · pin 3 passed twice · lock released |
| 2 | B0-TESTFIX-BASELINE | 0 | test | L2 | M | done · 10 passed, 1 xfailed · lock released |
| 3 | B0-TESTFIX-COPY | 0 | test | L2 | M | done · plain-language pin · lock released |
| 4 | B0-TESTFIX-MASTERY | 0 | test | L2 | M | done · hosting sentence pinned · lock released |
| 5 | B0-TESTFIX-ORDER | 0 | test | L2 | M | done · 12 passed both orders · lock released |
| 6 | B0-TESTFIX-TRANSPORT | 0 | test | L2 | M | done · 2 passed, 1 xfailed · lock released |
| 7 | B0-TESTFIX-UNDERSTAND | 0 | test | L2 | M | stopped · CL7 stays Open · lock held |
| 8 | F1-HYDRATE | 1 | test | L2 | M | stopped · AC2 crawl outside allow-list · lock held |
| 9 | F1-PAGINATE | 1 | build | L2 | M | stopped · Connect page outside allow-list · lock held |
| 10 | SEC-AUTH-BOOT | 1 | test | L3 | L | done · 2 passed twice · lock released |
| 11 | SEC-CACHE-SECRETS | 1 | test | L2 | M | done · 7 passed, 1 xfailed · lock released |
| 12 | SEC-TENANCY | 1 | test | L3 | L | done · 6 passed twice · lock released |
| 13 | SEC-TENANCY-OBJ | 1 | test | L3 | L | done · 2 passed, 2 xfailed · lock released |
| 14 | UI-SHELL-DRAWER | 1 | build | L3 | L | done · 2 passed · lock released |
| 15 | UI-REF-STUDY | 1 | ui-spec | L2 | M | done · spec 65 · lock released |
| 16 | UI-AUDIT-ALL | 0 | ui-spec | L2 | M | done · split kept · UIX-00 stays Poor · lock released |
| 17 | F1-VISUAL-REG | 1 | regression | L2 | S | stopped · harness card F1-VISUAL-HARNESS blocked · lock held |
| 18 | REG-AI-GUARDS | 1 | regression | L2 | S | done · 50 passed twice · CACHE-H-EMAIL stays Open · lock released |
| 19 | SEC-AUTH-ENUM | 1 | test | L3 | L | done · 2 passed, 15 xfailed · SEC-6.1-AC3 stays Open · lock released |
| 20 | SEC-AUTH-SESSION | 1 | test | L3 | L | done · 8 passed, 7 xfailed · SEC-6.1-AC2 stays Partial · lock released |
| 21 | SEC-CSRF | 1 | test | L3 | L | done · 1 passed, 2 xfailed · SEC-6.1-AC4 stays Open · lock released |
| 22 | SEC-FENCE-SWEEP | 1 | test | L3 | L | done · 4 passed, 2 xfailed · H-3.19-FENCE stays Open · lock released |
| 23 | SEC-HEADERS | 1 | test | L2 | M | done · 6 passed, 7 xfailed · SEC-6.8-AC stays Open · lock released |
| 24 | SEC-LEASTPRIV | 1 | test | L3 | L | done · 1 passed, 3 xfailed · SEC-6.4 stays Open · lock released |
| 25 | SEC-LOG-REDACT | 1 | test | L2 | M | tester aborted · SEC-6.3-AC2 stays Open · lock held |

## File locks (one Worker per file set)

| Lock | Card | Role holding | Files / globs | Since |
|---|---|---|---|---|
| L-REG-NP-T1b | REG-NP-T1b | Worker | apps/api/tests/test_reg_np_t1b.py | 2026-10-22 |
| L-B0-TESTFIX-UNDERSTAND | B0-TESTFIX-UNDERSTAND | Worker | apps/api/tests/test_b0_testfix_understand.py | 2026-10-24 |
| L-F1-HYDRATE | F1-HYDRATE | Worker | apps/web/src/app/globals.css, apps/web/src/components/ui/, apps/web/src/lib/nav.ts, apps/web/eslint.config.mjs, apps/web/src/lib/f1_hydrate.test.ts | 2026-10-24 |
| L-F1-PAGINATE | F1-PAGINATE | Worker | apps/api/app/routers/connections.py, apps/web/src/lib/connectScreen.ts, apps/web/src/app/connections/, apps/web/src/lib/f1_paginate.test.ts | 2026-10-24 |
| L-F1-VISUAL-REG | F1-VISUAL-REG | Worker | apps/web/src/lib/f1_visual_reg.test.ts | 2026-10-25 |
| L-SEC-LOG-REDACT | SEC-LOG-REDACT | Tester | apps/api/app/logging_config.py, apps/api/tests/test_sec_log_redact.py | 2026-10-26 |
| L-NF-BV-AUDIT | BV-AUDIT | Worker | apps/api/app/bot_verify/targets.py, store.py, models.py, walkthrough.py, flows.py, flow_library.py; apps/api/alembic/versions/*_bv_audit.py; apps/api/tests/test_nf_bot_verify_audit.py, test_nf_bot_verify_walkthrough.py, test_nf_bot_verify_flows.py, test_nf_bot_verify_store.py; apps/web/src/components/bots/VerifyRunPanel{,.test}.tsx | 2026-10-24 |
Rule: a card is dispatched only if none of its allow-list paths matches an open lock (prefix match on directories). Release on CLOSE or on stop.

## In flight

| Card | Role | Loop | Tier | Started | Packet in |
|---|---|---|---|---|---|
| REG-NP-T1b | Worker | 1/2 | L3 | 2026-10-22 | 365a150f STOP · install_ready absent |
| B0-TESTFIX-UNDERSTAND | Worker | 1 | L2 | 2026-10-24 | stopped · CL7 stays Open · no file |
| F1-HYDRATE | Worker | 1 | L2 | 2026-10-24 | c88df2f5 STOP · AC2 crawl outside allow-list |
| F1-PAGINATE | Worker | 1 | L2 | 2026-10-24 | 47b5d287 STOP · Connect page outside allow-list |
| F1-VISUAL-REG | Worker | 1 | L2 | 2026-10-25 | 6a7b806e STOP · harness absent |
| SEC-LOG-REDACT | Tester | 1 | L2 | 2026-10-26 | 280fce2b aborted · not resumed |
| SEC-LOG-REDACT | Worker | 1 | L2 | 2026-10-26 | 6a35f71e · 8 passed, 1 xfailed |

## Token ledger (cost-weighted units, `budget.json` `unit`)

| Date | Card | Role | Tier | Tokens | Cap | % of cap | Note |
|---|---|---|---|---|---|---|---|
| 2026-10-24 | F1-HYDRATE | Worker | L2 | n/a | 400000 | n/a | STOP · T0 10 passed · 2 it.fails · no product diff · c88df2f5 |
| 2026-10-24 | F1-PAGINATE | Worker | L2 | n/a | 400000 | n/a | STOP · T0 8 passed · API default 50 · 47b5d287 |
| 2026-10-26 | SEC-LOG-REDACT | Tester | L2 | n/a | 150000 | n/a | aborted · not resumed · SEC-6.3-AC2 stays Open · 280fce2b |
| 2026-10-26 | SEC-LOG-REDACT | Worker | L2 | n/a | 400000 | n/a | 8 passed, 1 xfailed · test file only · 6a35f71e |
| 2026-10-26 | SEC-LEASTPRIV | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · SEC-6.4 stays Open · 21802d70 |
| 2026-10-26 | SEC-LEASTPRIV | Tester | L2 | n/a | 300000 | n/a | PASS · 3 strict xfails · c0d8c1d5 |
| 2026-10-26 | SEC-LEASTPRIV | Worker | L3 | n/a | 800000 | n/a | 1 passed, 3 xfailed · test file only · 55044b7a |
| 2026-10-26 | SEC-LEASTPRIV | Oracle | L3 | n/a | 800000 | n/a | red · 2 failed, 0 passed · e773496f |
| 2026-10-26 | SEC-HEADERS | Reviewer | L2 | n/a | 120000 | n/a | APPROVE · SEC-6.8-AC stays Open · ab9bdf7d |
| 2026-10-26 | SEC-HEADERS | Tester | L2 | n/a | 150000 | n/a | PASS · 7 strict xfails · 2690c7cd |
| 2026-10-25 | SEC-HEADERS | Tester | L2 | n/a | 150000 | n/a | aborted · not resumed · SEC-6.8-AC stays Open · 1de79185 |
| 2026-10-25 | SEC-HEADERS | Worker | L2 | n/a | 400000 | n/a | 6 passed, 7 xfailed · test file only · 7fbac007 |
| 2026-10-25 | SEC-FENCE-SWEEP | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · H-3.19-FENCE stays Open · 9f7f9257 |
| 2026-10-25 | SEC-FENCE-SWEEP | Tester | L2 | n/a | 300000 | n/a | PASS · 2 strict xfails · c4ae6366 |
| 2026-10-25 | SEC-FENCE-SWEEP | Worker | L3 | n/a | 800000 | n/a | 4 passed, 2 xfailed · test file only · c562b683 |
| 2026-10-25 | SEC-FENCE-SWEEP | Oracle | L3 | n/a | 800000 | n/a | red · 2 failed, 0 passed · 2c182ed3 |
| 2026-10-25 | SEC-CSRF | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · SEC-6.1-AC4 stays Open · 12b06fef |
| 2026-10-25 | SEC-CSRF | Tester | L2 | n/a | 300000 | n/a | PASS · 2 strict xfails · 057bb5b3 |
| 2026-10-25 | SEC-CSRF | Worker | L3 | n/a | 800000 | n/a | 1 passed, 2 xfailed · test file only · b820d978 |
| 2026-10-25 | SEC-CSRF | Oracle | L3 | n/a | 800000 | n/a | red · 2 failed, 0 passed · b8107064 |
| 2026-10-25 | SEC-AUTH-SESSION | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · SEC-6.1-AC2 stays Partial · a555c8ee |
| 2026-10-25 | SEC-AUTH-SESSION | Tester | L2 | n/a | 300000 | n/a | PASS · 7 strict xfails · 9368f2bf |
| 2026-10-25 | SEC-AUTH-SESSION | Worker | L3 | n/a | 800000 | n/a | 8 passed, 7 xfailed · test file only · e5de7970 |
| 2026-10-25 | SEC-AUTH-SESSION | Oracle | L3 | n/a | 800000 | n/a | red · 2 failed, 0 passed · 6643b654 |
| 2026-10-25 | SEC-AUTH-ENUM | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · SEC-6.1-AC3 stays Open · 75c914d1 |
| 2026-10-25 | SEC-AUTH-ENUM | Tester | L2 | n/a | 300000 | n/a | PASS · 3 ENUM xfails · 12 rate-limit xfails · 6a3d7314 |
| 2026-10-25 | SEC-AUTH-ENUM | Worker | L3 | n/a | 800000 | n/a | 2 passed, 15 xfailed · test file only · 8ba3b417 |
| 2026-10-25 | SEC-AUTH-ENUM | Oracle | L3 | n/a | 800000 | n/a | red · 2 failed, 0 passed · 0b3380a3 |
| 2026-10-25 | UI-AUDIT-ALL | Reviewer | L2 | n/a | 120000 | n/a | APPROVE · UIX-00 stays Poor · UIX-TOUCHES stays Partial · 396ec4fb |
| 2026-10-25 | REG-AI-GUARDS | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · 50 passed twice · re-ran · CACHE-H-EMAIL stays Open · be7a0e07 |
| 2026-10-25 | UI-AUDIT-ALL | Tester | L2 | n/a | 150000 | n/a | PASS · split kept · 55fab758 |
| 2026-10-25 | REG-AI-GUARDS | Reviewer | L2 | n/a | 45000 | n/a | aborted · not closed · 8effb46a |
| 2026-10-25 | REG-AI-GUARDS | Tester | L2 | n/a | 60000 | n/a | AC1 FAIL on scan only · AC2–AC8 PASS · 2365d89d |
| 2026-10-25 | REG-AI-GUARDS | Worker | L2 | n/a | 150000 | n/a | returned · 50 passed twice · test file only · a6236196 |
| 2026-10-25 | F1-VISUAL-REG | Worker | L2 | n/a | 150000 | n/a | STOP · no toHaveScreenshot · UI-5.14-AC stays Open · 6a7b806e |
| 2026-10-25 | UI-AUDIT-ALL | Worker | L2 | n/a | 400000 | n/a | returned · 80 rows · 19 files · plan_lint 48 existing · 538a124d |
| 2026-10-25 | UI-REF-STUDY | Reviewer | L2 | n/a | 120000 | n/a | APPROVE · UI-5.1 [Done, code] · UIREF-PACK stays On-disk · 730c7638 |
| 2026-10-25 | UI-REF-STUDY | Tester | L1 | n/a | 150000 | n/a | PASS · AC1–AC4 · 99311dd1 |
| 2026-10-24 | UI-REF-STUDY | Worker | L2 | n/a | 400000 | n/a | returned · spec 65 · headings 9 · vitest 1 · plan_lint 48 existing · 1542eaee |
| 2026-10-24 | SEC-AUTH-BOOT | Oracle | L3 | n/a | 800000 | n/a | red · 2 failed, 0 passed · 56dbc17c |
| 2026-10-24 | SEC-AUTH-BOOT | Worker | L3 | n/a | 800000 | n/a | ready · 2 passed twice · caf4d207 |
| 2026-10-24 | SEC-AUTH-BOOT | Tester | L2 | n/a | 300000 | n/a | PASS · 2 passed twice · 4be7b753 |
| 2026-10-24 | SEC-AUTH-BOOT | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · [Done, code] · c6e06705 |
| 2026-10-24 | SEC-CACHE-SECRETS | Worker | L2 | n/a | 400000 | n/a | T0 7 passed, 1 xfailed · 0733a49e |
| 2026-10-24 | SEC-CACHE-SECRETS | Tester | L2 | n/a | 150000 | n/a | PASS · 7 passed, 1 xfailed twice · 3c2de714 |
| 2026-10-24 | SEC-CACHE-SECRETS | Reviewer | L2 | n/a | 120000 | n/a | APPROVE · [Done, code] · CACHE-H-EMAIL Open · 6ac6e75a |
| 2026-10-24 | SEC-TENANCY | Oracle | L3 | n/a | 800000 | n/a | red · 4 failed, 2 passed · ce9e53d7 |
| 2026-10-24 | SEC-TENANCY | Worker | L3 | n/a | 800000 | n/a | ready · 6 passed twice · 393102b4 |
| 2026-10-24 | SEC-TENANCY | Tester | L2 | n/a | 300000 | n/a | PASS · 6 passed twice · 131777ce |
| 2026-10-24 | SEC-TENANCY | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · [Done, code] · 3a6be8e6 |
| 2026-10-24 | SEC-TENANCY-OBJ | Oracle | L3 | n/a | 800000 | n/a | T0 1 failed, 1 passed · approvals 502 · flow rollback 409 · d4097f0b |
| 2026-10-24 | SEC-TENANCY-OBJ | Worker | L3 | n/a | 800000 | n/a | T0 2 passed, 2 xfailed · no XPASS · bd915f17 |
| 2026-10-24 | SEC-TENANCY-OBJ | Tester | L2 | n/a | 300000 | n/a | PASS · 2 passed, 2 xfailed twice · 8eb8a4da |
| 2026-10-24 | SEC-TENANCY-OBJ | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · SEC-6.2-AC2 stays Open · 619d70b1 |
| 2026-10-24 | UI-SHELL-DRAWER | Oracle | L3 | n/a | 800000 | n/a | red · 2 failed · harness 404 · 91be1aa7 |
| 2026-10-24 | UI-SHELL-DRAWER | Worker | L3 | n/a | 800000 | n/a | T0 2 passed · spec locked · 7273a9e4 |
| 2026-10-24 | UI-SHELL-DRAWER | Tester | L2 | n/a | 300000 | n/a | PASS · 2 passed · spec untouched · 3aa811bb |
| 2026-10-24 | UI-SHELL-DRAWER | Reviewer | L3 | n/a | 240000 | n/a | APPROVE · [Done, code] · 299f1f42 |
| 2026-10-23 | B0-RANDOM-ORDER | Tester | L2 | n/a | 150000 | n/a | rooted baseline 470 failed · 4985 passed · 364 errors · new was admin + tsc |
| 2026-10-23 | B0-RANDOM-ORDER | Tester | L2 | n/a | 150000 | n/a | FAIL · 81 failed · 1203 passed · 2 errors · b0262c8a |
| 2026-10-23 | B0-RANDOM-ORDER | Worker | L2 | n/a | 400000 | n/a | loop 3 ready · 3 xfailed · pin 1 passed · a9971a4a |
| 2026-10-23 | B0-RANDOM-ORDER | Worker | L2 | n/a | 400000 | n/a | loop 2 STOP · preview 404 · admin plan · 0aa31dcf |
| 2026-10-23 | B0-RANDOM-ORDER | Worker | L2 | n/a | 400000 | n/a | loop 1 STOP · apply_readiness isolation · 0aa31dcf |
| 2026-10-23 | DOC-SPECS-INTAKE | Reviewer | L1 | n/a | 20000 | n/a | APPROVE · [Done, code] · 64f8484c |
| 2026-10-23 | DOC-SPECS-INTAKE | Tester | L2 | n/a | 25000 | n/a | PASS · files none · 763b186d |
| 2026-10-23 | DOC-SPECS-INTAKE | Worker | L1 | n/a | 60000 | n/a | ready for Tester · files none · 21f5c6e5 |
| 2026-10-23 | BL-08b | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · [Done, code] · 1be79237 |
| 2026-10-23 | BL-08b | Tester | L2 | n/a | 60000 | n/a | PASS · 2 passed · 4672b01a |
| 2026-10-23 | BL-08b | Worker | L2 | n/a | 150000 | n/a | ready for Tester · 2 passed · 5270fa13 |
| 2026-10-23 | BL-07b | Reviewer | L1 | n/a | 45000 | n/a | APPROVE · [Done, code] · fe453e46 |
| 2026-10-23 | BL-07b | Tester | L1 | n/a | 60000 | n/a | PASS · 7 passed · 79c0bafd |
| 2026-10-23 | BL-07b | Worker | L1 | n/a | 150000 | n/a | ready for Tester · 7 passed · 72299899 |
| 2026-10-22 | REG-NP-T1c | Reviewer | L3 | n/a | 120000 | n/a | APPROVE · [Done, code] · 810a786b |
| 2026-10-22 | REG-NP-T1c | Tester | L2 | n/a | 150000 | n/a | PASS · 99 passed · 7415a639 |
| 2026-10-22 | REG-NP-T1c | Worker | L3 | n/a | 400000 | n/a | loop 2 · draft keep · T0 99 passed · 3fad8291 |
| 2026-10-22 | REG-NP-UIb | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · [Done, code] · 7fb79e9a |
| 2026-10-22 | REG-NP-UIb | Tester | L2 | n/a | 60000 | n/a | PASS · 18 passed · d74f556f |
| 2026-10-22 | REG-NP-T1c | Worker | L3 | n/a | 400000 | n/a | STOP · named 44 passed · AC21 red · c76d597a |
| 2026-10-22 | REG-NP-UIb | Worker | L2 | n/a | 150000 | n/a | ready for Tester · 48a93de5 · T0 18 passed |
| 2026-10-22 | B0-GREEN | Reviewer | L2 | n/a | 120000 | n/a | APPROVE · [Done, code] · bb9b278d · 69c314e6 |
| 2026-10-22 | REG-NP-BLb | Reviewer | L1 | n/a | 45000 | n/a | APPROVE · [Done, code] · bdcd8c8c |
| 2026-10-22 | REG-NP-BLb | Tester | L2 | n/a | 60000 | n/a | PASS · four commands match |
| 2026-10-22 | REG-NP-BLb | Worker | L2 | n/a | 150000 | n/a | baseline re-measure · 81db0ee7 |
| 2026-10-22 | REG-NP-T1 | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · [Done, code] · after CHANGES |
| 2026-10-22 | REG-NP-T1 | Tester | L2 | n/a | 60000 | n/a | PASS · 28 and 28 · after CHANGES |
| 2026-10-22 | REG-NP-T1 | Worker | L2 | n/a | 150000 | n/a | CHANGES · argv, SEEDED set, literal craft keys · 28 and 28 |
| 2026-10-22 | REG-NP-T1 | Reviewer | L2 | n/a | 45000 | n/a | CHANGES · AC1 argv and SEEDED · AC11 literal keys |
| 2026-10-22 | REG-NP-BL | Reviewer | L1 | n/a | 45000 | n/a | APPROVE · [Done, code] · AC1 on BLb |
| 2026-10-22 | REG-NP-UI | Reviewer | L1 | n/a | 45000 | n/a | APPROVE · [Done, code] · leftovers on UIb |
| 2026-10-22 | REG-NP-T1 | Tester | L2 | n/a | 60000 | n/a | PASS · 28 and 28 · date family kept |
| 2026-10-22 | REG-NP-BL | Tester | L2 | n/a | 60000 | n/a | PASS · 15 and 15 · AC1 on BLb |
| 2026-10-22 | REG-NP-UI | Tester | L2 | n/a | 60000 | n/a | PASS · 23 and 23 · leftovers on UIb |
| 2026-10-22 | REG-NP-T1 | Worker | L2 | n/a | 150000 | n/a | AC21 · date family kept · 28 and 28 |
| 2026-10-22 | REG-NP-BL | Worker | L1 | n/a | 150000 | n/a | loop 3 · 15 and 15 · AC1 split |
| 2026-10-22 | REG-NP-UI | Worker | L1 | n/a | 150000 | n/a | loop 3 · 23 and 23 · AC2 and keyboard split |
| 2026-10-22 | BL-08 | Tester | L2 | n/a | 60000 | n/a | FAIL · AC1 held · AC2 changeset exit 1 · dev 2 · scope 455 |
| 2026-10-22 | SEC-GATE-SCOPE | Worker | L3 | n/a | 400000 | n/a | scoped lookup before pause check |
| 2026-10-22 | SEC-GATE-SCOPE | Tester | L2 | n/a | 150000 | n/a | PASS · T0 461 and 461 |
| 2026-10-22 | SEC-GATE-SCOPE | Reviewer | L3 | n/a | 120000 | n/a | APPROVE · [Done, code] |
| 2026-10-22 | DEV-PYTEST-RANDOMLY | Worker | L2 | n/a | 150000 | n/a | pytest-randomly 5.0.0 MIT |
| 2026-10-22 | DEV-PYTEST-RANDOMLY | Tester | L2 | n/a | 60000 | n/a | PASS · 2 and 2 |
| 2026-10-22 | DEV-PYTEST-RANDOMLY | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · [Done, code] |
| 2026-10-22 | REG-NP-T1 | Worker | L2 | n/a | 150000 | n/a | loop 2 · no new pins · 21 and 21 |
| 2026-10-22 | REG-NP-T1 | Worker | L2 | n/a | 150000 | n/a | loop 3 · 27 and 27 · AC20 split · AC21 unpinned |
| 2026-10-22 | REG-NP-T1 | Tester | L2 | n/a | 60000 | n/a | PASS · hold · 27 and 27 · AC21 open |
| 2026-10-22 | REG-NP-T1 | Reviewer | L2 | n/a | 45000 | n/a | APPROVE · close blocked · AC21 unpinned |
| 2026-10-22 | BL-07 | Worker | L2 | n/a | 400000 | n/a | loop 2 · no_app_db mark · 8 and 2 |
| 2026-10-22 | BL-07 | Tester | L2 | n/a | 150000 | n/a | loop 2 · PASS · hold · AC4 open |
| 2026-10-22 | B0-JUNK | Worker | L2 | n/a | 400000 | n/a | dry-run refused 5433 · tests 15 |
| 2026-10-22 | B0-JUNK | Tester | L2 | n/a | 150000 | n/a | PASS · hold · AC2 AC3 open |
| 2026-10-22 | REG-NP-GND | Worker | L3 | n/a | 150000 | n/a | loop 2 · sale installed on 19 · DB dropped |
| 2026-10-22 | REG-NP-GND | Tester | L2 | n/a | 60000 | n/a | PASS · 12 passed · live 19 · DB dropped |
| 2026-10-22 | REG-NP-GND | Reviewer | L3 | n/a | 45000 | n/a | APPROVE · MOD [Done, live] · eight pins [Done, code] |
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
| 2026-10-22 | BL-08 | Worker | L3 | n/a | 150000 | n/a | loop 2 · plan refreshed · 5 groups · no commit |
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
TESTER SEC-LOG-REDACT · aborted · 280fce2b · not resumed
DISPATCH SEC-LOG-REDACT · Tester · T0 8 passed, 1 xfailed · no re-run
WORKER SEC-LOG-REDACT · 8 passed, 1 xfailed · test file only · 6a35f71e
CLOSE SEC-LEASTPRIV · SEC-6.4 stays Open · lock released
REVIEWER SEC-LEASTPRIV · APPROVE · 3 strict xfails · 21802d70
TESTER SEC-LEASTPRIV · PASS · 3 strict xfails · c0d8c1d5
WORKER SEC-LEASTPRIV · 1 passed, 3 xfailed · test file only · 55044b7a
ORACLE SEC-LEASTPRIV · 2 failed, 0 passed · e773496f
CLOSE SEC-HEADERS · SEC-6.8-AC stays Open · lock released
REVIEWER SEC-HEADERS · APPROVE · 7 strict xfails · ab9bdf7d
TESTER SEC-HEADERS · PASS · 7 strict xfails · 2690c7cd
TESTER SEC-HEADERS · aborted · 1de79185 · not resumed
DISPATCH SEC-HEADERS · Tester · T0 6 passed, 7 xfailed · no re-run
WORKER SEC-HEADERS · 6 passed, 7 xfailed · test file only · 7fbac007
CLOSE SEC-FENCE-SWEEP · H-3.19-FENCE stays Open · lock released
REVIEWER SEC-FENCE-SWEEP · APPROVE · 2 strict xfails · 9f7f9257
TESTER SEC-FENCE-SWEEP · PASS · 2 strict xfails · c4ae6366
WORKER SEC-FENCE-SWEEP · 4 passed, 2 xfailed · test file only · c562b683
ORACLE SEC-FENCE-SWEEP · 2 failed, 0 passed · 2c182ed3
CLOSE SEC-CSRF · SEC-6.1-AC4 stays Open · lock released
REVIEWER SEC-CSRF · APPROVE · 2 strict xfails · 12b06fef
TESTER SEC-CSRF · PASS · 2 strict xfails · 057bb5b3
WORKER SEC-CSRF · 1 passed, 2 xfailed · test file only · b820d978
ORACLE SEC-CSRF · 2 failed, 0 passed · b8107064
CLOSE SEC-AUTH-SESSION · SEC-6.1-AC2 stays Partial · lock released
REVIEWER SEC-AUTH-SESSION · APPROVE · 7 strict xfails · a555c8ee
TESTER SEC-AUTH-SESSION · PASS · 7 strict xfails · 9368f2bf
WORKER SEC-AUTH-SESSION · 8 passed, 7 xfailed · test file only · e5de7970
ORACLE SEC-AUTH-SESSION · 2 failed, 0 passed · 6643b654
CLOSE SEC-AUTH-ENUM · SEC-6.1-AC3 stays Open · lock released
REVIEWER SEC-AUTH-ENUM · APPROVE · 3 ENUM xfails · 12 rate-limit xfails · 75c914d1
TESTER SEC-AUTH-ENUM · PASS · 3 ENUM xfails · 12 rate-limit xfails · 6a3d7314
WORKER SEC-AUTH-ENUM · 2 passed, 15 xfailed · test file only · 8ba3b417
ORACLE SEC-AUTH-ENUM · 2 failed, 0 passed · 0b3380a3
CLOSE REG-AI-GUARDS · 50 passed twice · CACHE-H-EMAIL stays Open · lock released
CLOSE UI-AUDIT-ALL · split kept · UIX-00 stays Poor · lock released
REVIEWER REG-AI-GUARDS · APPROVE · re-ran · 50 passed twice · be7a0e07
REVIEWER UI-AUDIT-ALL · APPROVE · AC1 and AC2 stay open · 396ec4fb
DISPATCH UI-AUDIT-ALL · Reviewer · tester PASS · AC1 and AC2 stay open
TESTER UI-AUDIT-ALL · PASS · split kept · 55fab758
RECORD F1-VISUAL-HARNESS · build · blocked · not started
TESTER REG-AI-GUARDS · AC1 scan called vacuous · AC2–AC8 PASS · 2365d89d
WORKER REG-AI-GUARDS · 50 passed twice · test file only · a6236196
STOP F1-VISUAL-REG · harness absent · UI-5.14-AC stays Open · lock held
STOP UI-AUDIT-ALL · `/` and `/connections/[id]` on 01 and 04 · lock held
CLOSE UI-REF-STUDY · UI-5.1 [Done, code] · UIREF-PACK stays On-disk · lock released
REVIEWER UI-REF-STUDY · APPROVE · spec 65 · no route scores · 730c7638
TESTER UI-REF-STUDY · PASS · AC1–AC4 · 99311dd1
WORKER UI-REF-STUDY · 35 entries · spec 65 · headings 9 · 1542eaee
CLOSE SEC-TENANCY-OBJ · SEC-6.2-AC2 stays Open · lock released
REVIEWER SEC-TENANCY-OBJ · APPROVE · hard denials kept · two strict xfails
CLOSE UI-SHELL-DRAWER · SHELL-DRAWER [Done, code] · lock released
REVIEWER UI-SHELL-DRAWER · APPROVE · drawer below sm · docked from sm
DISPATCH UI-SHELL-DRAWER · Reviewer · tester PASS · 2 passed
TESTER UI-SHELL-DRAWER · PASS · 2 passed · spec untouched
WORKER UI-SHELL-DRAWER · drawer below sm · docked from sm · spec untouched
ORACLE UI-SHELL-DRAWER · 2 failed · GET /e2e/shell-drawer 404 · shell files untouched
NOTE UI-SHELL-DRAWER · added · shell path free of the hydrate lock · oracle dispatched
DISPATCH SEC-TENANCY-OBJ · Reviewer · tester PASS · 2 passed, 2 xfailed twice
TESTER SEC-TENANCY-OBJ · PASS · 2 passed, 2 xfailed · randomly the same
WORKER SEC-TENANCY-OBJ · step 4 xfail split · product files untouched
ORACLE SEC-TENANCY-OBJ · 1 failed, 1 passed · approvals 502 · flow change 409
DISPATCH SEC-TENANCY-OBJ · Oracle · red tests only · score 6
CLOSE SEC-TENANCY · SEC-6.2-AC1 and SEC-6.2-SHARED [Done, code] · lock released
REVIEWER SEC-TENANCY · APPROVE · middleware + scope + 40-gap baseline
DISPATCH SEC-TENANCY · Reviewer · tester PASS · 6 passed twice
TESTER SEC-TENANCY · PASS · 6 passed · randomly 6 passed · oracle untouched
DISPATCH SEC-TENANCY · Tester · T0 6 passed · randomly 6 passed
WORKER SEC-TENANCY · scope + middleware + baseline · oracle untouched
DISPATCH SEC-TENANCY · Worker · oracle locked · T0 4 failed, 2 passed
T0 SEC-TENANCY · 4 failed, 2 passed · randomly 4 failed, 2 passed
ORACLE SEC-TENANCY · red tests · no product file
DISPATCH SEC-TENANCY · Oracle · red tests only · score 6
CLOSE SEC-CACHE-SECRETS · [Done, code] · CACHE-H-EMAIL stays Open · lock released
REVIEWER SEC-CACHE-SECRETS · APPROVE · test file only
DISPATCH SEC-CACHE-SECRETS · Reviewer · tester PASS · 7 passed, 1 xfailed
TESTER SEC-CACHE-SECRETS · PASS · 7 passed, 1 xfailed twice · no XPASS
DISPATCH SEC-CACHE-SECRETS · Tester · T0 7 passed, 1 xfailed · CACHE-H-EMAIL
T0 SEC-CACHE-SECRETS · 7 passed, 1 xfailed · randomly 7 passed, 1 xfailed
WORKER SEC-CACHE-SECRETS · test file only · cloud email still cached
DISPATCH SEC-CACHE-SECRETS · Worker · test card · score 5
CLOSE SEC-AUTH-BOOT · SEC-6.1-AC1 [Done, code] · lock released
REVIEWER SEC-AUTH-BOOT · APPROVE · auth.py + main.py · oracle untouched
DISPATCH SEC-AUTH-BOOT · Reviewer · tester PASS · 2 passed twice
TESTER SEC-AUTH-BOOT · PASS · 2 passed · randomly 2 passed · oracle untouched
DISPATCH SEC-AUTH-BOOT · Tester · T0 2 passed · randomly 2 passed
WORKER SEC-AUTH-BOOT · auth.py + main.py · oracle file untouched
DISPATCH SEC-AUTH-BOOT · Worker · oracle locked · T0 2 failed
T0 SEC-AUTH-BOOT · 2 failed, 0 passed · assert_auth_mode_off_boot missing
ORACLE SEC-AUTH-BOOT · 2 failed both runs · no product file
DISPATCH SEC-AUTH-BOOT · Oracle · red tests only · score 6
T0 F1-PAGINATE · 8 passed · Connect page and API client not wired
STOP F1-PAGINATE · those two files are outside the allow-list · lock held
DISPATCH F1-PAGINATE · Worker · connections page size and virtual list
T0 F1-HYDRATE · 10 passed · 2 it.fails still red inside the suite · product files untouched
STOP F1-HYDRATE · AC2 Playwright crawl outside allow-list · lock held
DISPATCH F1-HYDRATE · Worker · test card · contrast waits on --brand
CLOSE B0-TESTFIX-BASELINE · CL2 [Done, code] · AC1 Open · lock released
TESTER B0-TESTFIX-BASELINE · PASS · strict xfail on the count test · constant stays 22
T0 B0-TESTFIX-BASELINE · 10 passed, 1 xfailed in 2.76s · -p randomly 10 passed, 1 xfailed in 2.70s
DISPATCH B0-TESTFIX-BASELINE · Tope yes · strict xfail on the count test · constant stays 22
CLOSE B0-TESTFIX-TRANSPORT · CL1 [Done, code] · AC1 Open · lock released
TESTER B0-TESTFIX-TRANSPORT · PASS · strict xfail on suite scan only · product files untouched
T0 B0-TESTFIX-TRANSPORT · 2 passed, 1 xfailed in 6.54s · -p randomly 2 passed, 1 xfailed in 6.75s
DISPATCH B0-TESTFIX-TRANSPORT · Tope yes · strict xfail on the suite scan only
TOPE B0-TESTFIX-UNDERSTAND · CL7 stays Open · no invented ids · no compound xfail
STOP B0-TESTFIX-UNDERSTAND · 1 failed, 51 passed · compound vehicle node outside allow-list · no file
CLOSE B0-TESTFIX-ORDER · CL5 [Done, code] · AC1 Open · lock released
TESTER B0-TESTFIX-ORDER loop 2 · PASS · compound matches HEAD · named 12 passed both orders
T0 B0-TESTFIX-ORDER loop 2 · named A 12 passed in 4.84s · B 12 passed in 4.52s · compound restored not inverted
TESTER B0-TESTFIX-ORDER · FAIL · compound vehicle asserts inverted to in names
T0 B0-TESTFIX-ORDER · A 12 passed in 5.33s · B 12 passed in 5.26s
REVIEWER B0-TESTFIX-MASTERY · APPROVE · hosting sentence · lock released
DISPATCH B0-TESTFIX-ORDER · Worker · P0-2-CL5 · no full suite
TESTER B0-TESTFIX-MASTERY · PASS · 14 passed twice · hosting.py unchanged
T0 B0-TESTFIX-MASTERY · 14 passed in 2.37s · -p randomly 14 passed in 2.05s
REVIEWER B0-TESTFIX-COPY loop 2 · APPROVE · legend toContain · lock released
DISPATCH B0-TESTFIX-MASTERY · Worker · P0-2-CL4 · conftest left untouched
TESTER B0-TESTFIX-COPY loop 2 · PASS · web 23 passed · legend toContain · product copy untouched
T0 B0-TESTFIX-COPY loop 2 · web 23 passed · legend sentence pinned
REVIEWER B0-TESTFIX-COPY · REJECT · expert-copy test only bans absent jargon
TESTER B0-TESTFIX-COPY · PASS · API 2 passed twice · web 23 passed · product copy untouched
T0 B0-TESTFIX-COPY · API 2 passed · shuffled 2 passed · web 23 passed
STOP B0-TESTFIX-BASELINE · measured 38 · constant 22 · no xfail · waiting on Tope
DISPATCH B0-TESTFIX-BASELINE · Worker · P0-2-CL2 · conftest left untouched
REVIEWER B0-TESTFIX-AIOFF · APPROVE · pin 3 passed twice · P0-2-CL6 done · P0-2-AC1 stays Open · lock released
TESTER B0-TESTFIX-AIOFF · PASS · 3 passed · shuffled 3 passed · pytest.ini unchanged
T0 B0-TESTFIX-AIOFF · 3 passed in 0.17s · -p randomly 3 passed in 0.16s
DISPATCH B0-TESTFIX-AIOFF · Worker · lock on conftest.py pytest.ini vitest.config.ts · port env stays
REVIEWER B0-RANDOM-ORDER-b · APPROVE · empty diff · status done · lock released
TESTER B0-RANDOM-ORDER-b · PASS · 63 passed, 15 warnings in 26.70s · AC1–AC3 pass · allow-list diff empty
T0 B0-RANDOM-ORDER-b · orchestrator re-run · exit 0 · 63 passed, 15 warnings in 26.70s · seed 1766196243 · log B0-RANDOM-ORDER-b_seed1766196243_t0.txt · no allow-list diff
DISPATCH B0-RANDOM-ORDER-b · Worker · seed 1766196243 · base 9e8e360b · lock L-B0-RANDOM-ORDER-b
TESTER B0-RANDOM-ORDER · green bar · default_c and default_d each 68 failed, 6192 passed, 88 skipped, 4 xfailed, 27 errors · same 95 nodes · new set empty once Tooltip tsc is left out · lists in the agent store B0-RANDOM-ORDER_default_c.txt and default_d.txt · lock released
TESTER B0-RANDOM-ORDER · rooted baseline 470 failed, 4985 passed, 364 errors · both 72 (P0-2-H001–H072) · fixed 762 · new: admin xfail (conftest drops internal plan) and tsc Tooltip (P0-2-TSC-UIB) · lists /tmp/B0-RANDOM-ORDER_baseline_nodes.txt, default_a_nodes.txt · post-fix pair default_c then default_d
TESTER B0-RANDOM-ORDER · default ×2 · pin 0 · opt-in cli 0 · opt-in env 0 · logs /tmp/B0-RANDOM-ORDER_default1.txt and default2.txt
TESTER B0-RANDOM-ORDER · loop 3 · FAIL · b0262c8a
81 failed, 1203 passed, 2 errors. Eight other files named. No reviewer.
TESTER B0-RANDOM-ORDER · first -p randomly · exit 2 · 81 failed, 1203 passed, 2 errors · interrupted at summary · do not rerun
TESTER B0-RANDOM-ORDER · loop 3 · dispatched · b0262c8a
T0 pin 1 passed. Three nodes xfailed. Full suite is the tester's run.
DISPATCH B0-RANDOM-ORDER · loop 3 · xfail three tests · Tope yes · a9971a4a
WORKER B0-RANDOM-ORDER · loop 2 · STOP · 0aa31dcf
3 isolation outside allow-list. 3 order leaks fixed in conftest.py. Full suite not run. No tester.
WORKER B0-RANDOM-ORDER · loop 2 · classify six nodes · 0aa31dcf
loop 1 STOP. apply_readiness fails alone. Other five are missing tables. No tester.
CLOSE DOC-SPECS-INTAKE · 2026-10-23
PROGRESS: copies non-empty, box-only files absent · [Done, code]
ledger: DOC-SPEC-SPEC DOC-SPEC-CSS DOC-SPEC-BRS DOC-SPEC-AS DOC-SPEC-GAP DOC-SPEC-BRAND → "[Done, code]"
locks released: L-DOC-SPECS-INTAKE
REVIEW DOC-SPECS-INTAKE · APPROVE · [Done, code] · 64f8484c
REVIEW DOC-SPECS-INTAKE · dispatched · 64f8484c
TESTER DOC-SPECS-INTAKE · loop 1 · PASS · 763b186d
AC1–AC6 pass. plan_lint 21 errors, 0 name this card. label proposal [Done, code]
TESTER DOC-SPECS-INTAKE · loop 1 · dispatched · 763b186d
T0 ls exit 0. Copies non-empty. Absence files absent. plan_lint errors=21, all NF, 0 name this card.
WORKER DOC-SPECS-INTAKE · ready for Tester · 21f5c6e5 · files none
DISPATCH DOC-SPECS-INTAKE · Worker · 21f5c6e5 · prove existing copies · box absent · no board edits
CLOSE BL-08b · 2026-10-23
PROGRESS: pytest 2 passed, 0 failed · [Done, code]
ledger: NP-BL-08b → "[Done, code]"
locks released: L-BL-08b
REVIEW BL-08b · APPROVE · [Done, code] · 1be79237
REVIEW BL-08b · dispatched · 1be79237
TESTER BL-08b · loop 1 · PASS · 4672b01a
AC1 pass. pytest 2 passed. One dotted setting key.
CLOSE BL-07b · 2026-10-23
PROGRESS: pytest 7 passed, 0 failed · [Done, code]
ledger: NP-BL-07b → "[Done, code]"
locks released: L-BL-07b
REVIEW BL-07b · APPROVE · [Done, code] · fe453e46
TESTER BL-08b · loop 1 · dispatched · 4672b01a
T0 exit 0. 2 passed. One dotted setting key. xmlid copied for read-back.
REVIEW BL-07b · dispatched · fe453e46
TESTER BL-07b · loop 1 · PASS · 79c0bafd
AC1 pass. pytest 7 passed. Second scan writes nothing.
TESTER BL-07b · loop 1 · dispatched · 79c0bafd
T0 exit 0. 7 passed. Second scan writes no file and opens no database.
DISPATCH BL-08b · Worker · 5270fa13 · setting_ops.py · dotted setting key
DISPATCH BL-07b · Worker · 72299899 · test_bl_07.py · second scan writes 0
DISPATCH B0-RANDOM-ORDER · Worker · 0aa31dcf · plugin already installed
CLOSE REG-NP-T1c · 2026-10-22
PROGRESS: pytest 99 passed, 0 failed · [Done, code]
ledger: NP-T1-RET → "[Done, code]"
locks released: L-REG-NP-T1c
REVIEW REG-NP-T1c · APPROVE · [Done, code] · 810a786b
REVIEW REG-NP-T1c · dispatched · 810a786b
TESTER REG-NP-T1c · loop 2 · PASS · 7415a639
AC1 pass. AC2 pass. pytest 99 passed. label proposal [Done, code]
TESTER REG-NP-T1c · loop 2 · dispatched · 7415a639
T0 exit 0. 99 passed. Draft and must-do both keep the six families.
WORKER REG-NP-T1c · loop 2 · ready for Tester · 3fad8291
CLOSE REG-NP-UIb · 2026-10-22
PROGRESS: vitest 18 passed, 0 failed · [Done, code]
ledger: NP-UI-F02 NP-UI-F06 → "[Done, code]"
locks released: L-REG-NP-UIb
REVIEW REG-NP-UIb · APPROVE · [Done, code] · 7fb79e9a
states at · density at · dark at · 390 at · copy at
WORKER REG-NP-T1c · loop 2 · dispatched · 3fad8291
AC1 quote: rows are kept. Draft path must keep the same families. Tester after the re-run.
REVIEW REG-NP-UIb · dispatched · 7fb79e9a
TESTER REG-NP-UIb · loop 1 · PASS · d74f556f
AC1 pass. AC2 pass. vitest 18 passed, 0 failed. label proposal [Done, code]
WORKER REG-NP-T1c · loop 1 · STOP · c76d597a
Named pytest 44 passed. test_ac21_uncued_date_family_is_kept fails: Type is kept.
Blocking file: apps/api/tests/test_reg_np_t1.py (outside the allow-list). No tester.
TESTER REG-NP-UIb · loop 1 · dispatched · d74f556f
T0 exit 0. states 7, Tooltip 4, a11y 7. 18 passed, 0 failed.
WORKER REG-NP-UIb · loop 1 · ready for Tester · 48a93de5
files: loading.tsx, connections/[id]/loading.tsx, states.test.tsx, Tooltip.tsx
REVIEW REG-NP-BLb · APPROVE · [Done, code]
Four commands match. Baseline doc only. SEEDED stayed SEEDED. Lock released.
WORKER B0-GREEN · loop 1 · STOP
tsc exit 0. Vitest 2 failed, 1587 passed. Do not close. Do not edit studio-draft.live.test.ts on this card.
API pytest collection abort (database_url guard). Red-team 88 errors: ingenium_b0_iso_* missing on 54329.
files: apps/web/src/lib/b0_dist.test.ts, apps/api/tests/test_b0_green.py
DISPATCH B0-GREEN · role: Worker · tier: L2 · loop: 1/2
card: docs/build-plan/cards/phase-0/B0-GREEN.md
context: .cursor/skills/ingenium-ui-excellence/SKILL.md
floor: docs/design/UI_DIRECTION.md · docs/design/bar/xray-floor.png
locks: L-B0-GREEN · apps/web/src/, apps/api/tests/
budget: M · this role cap 400000 · stop at 80%
input packet: none
rules: do not touch the three trial folders; do not edit pyproject.toml or any test except test_b0_green.py
DISPATCH REG-NP-BLb · role: Worker · tier: L2 · loop: 1/2
card: docs/build-plan/cards/phase-0/REG-NP-BLb.md
locks: L-REG-NP-BLb · docs/plans/next-phase/03_BASELINE.md
budget: S · this role cap 150000 · stop at 80%
input packet: none
rules: correct a row only when a command shows it is wrong; do not upgrade SEEDED to DONE
REVIEW REG-NP-T1 · APPROVE · [Done, code]
Date family kept. Three weak pins fixed. AC20 on T1b. Rest of scrub on T1c.
REVIEW REG-NP-T1 · CHANGES
AC1: `-u` order and the SEEDED set are not asserted. AC11 rebuilds keys from the tuple.
REVIEW REG-NP-BL · APPROVE · [Done, code]
AC1 stays on REG-NP-BLb. Test file only. Suspects not pinned.
REVIEW REG-NP-UI · APPROVE · [Done, code]
AC2 skeleton and AC5 keyboard stay on REG-NP-UIb. Test file only.
REVIEW REG-NP-T1 · APPROVE
close blocked: AC21 unpinned · AC20 split to REG-NP-T1b
Captured pins match. Older pins stayed green. No product diff.
```

```
TESTER REG-NP-T1 · loop 3 · verdict PASS · label hold
AC1 AC3 AC8 AC9 AC11 AC12 AC15 AC16 AC22 pass. Forward 27. Reverse 27.
AC20 split to REG-NP-T1b. AC21 open: no test, Due date scrub returns [].
```

```
WORKER REG-NP-T1 · loop 3
files: apps/api/tests/test_reg_np_t1.py +232. Card notes added after the run.
outside allow-list: none. oracles edited: new captured pins only.
commands for Tester:
  cd apps/api && uv run pytest -q -p no:randomly tests/test_reg_np_t1.py → 27 passed
  same 27 node ids, reversed, each quoted → 27 passed
ACs self-check: captured AC1 AC3 AC8 AC9 AC11 AC12 AC15 AC16 AC22 ✓ · AC20 split · AC21 suspect
ui: n/a
risks: build_ir seed_snapshot admits x_qqqz_marker. Scrub still drops Due date.
```

```
TESTER B0-JUNK · loop 1 · verdict PASS · label hold
AC1 pass. AC4 pass. T0 15 passed. Dry-run exit 2, deleted 0, port 5433 refused.
AC2 open: no apply yes. AC3 open: next.config.ts outside the allow-list.
```

```
WORKER BL-08 · loop 2 · no commit
files: docs/handoff/COMMIT_PLAN.md refreshed. Oracle not edited.
Five proposed commits. Old product folders are already in history.
Gate C: Tope's yes still required. AC1 and AC2 stay open.
```

```
TESTER BL-07 · loop 2 · verdict PASS · label hold
AC1 AC2 AC3 pass. T0: 8 passed, then 2 passed. Diff is pytestmark only.
AC4 open: this card does not run an Odoo plan. No further code loop.
```

```
WORKER REG-NP-T1 · loop 2/2 · hold
Pins added: none. Open ACs have no input and output in the pack: AC1 AC3 AC8 AC9 AC11 AC12 AC15 AC16 AC20 AC21 AC22.
Forward 21 passed. Reverse 21 passed. Test file unchanged.
outside allow-list: none
```

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
| 2026-10-22 | DEV-PYTEST-RANDOMLY | [Done, code] | 2026-10-22 · DEV-PYTEST-RANDOMLY · pytest -p randomly tests/test_reg_np_dev.py · 2 passed, deterministic 2 passed · [Done, code] |
| 2026-10-22 | REG-NP-GND | split | 2026-10-22 · REG-NP-GND · pytest test_reg_np_gnd.py · 12 passed · MOD [Done, live] · eight pins [Done, code] |
