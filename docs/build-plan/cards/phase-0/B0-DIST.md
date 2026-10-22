# B0-DIST: next build never writes .next while dev runs; distDir set by script itself

ID: B0-DIST
Title: next build never writes .next while dev runs; distDir set by script itself
Status: done
Phase: 0
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: P0-4-AC1;P0-4-AC2;P0-4-AC3;P0-4-AC4;ARCH-2
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F2 K1 V0 I1)
Context pack:
- `sed -n '479p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '480p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '481p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '482p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '190p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/web/next.config.ts
- apps/web/package.json
- apps/web/playwright.config.ts
- .gitignore
File allow-list:
- apps/web/next.config.ts
- apps/web/package.json
- apps/web/playwright.config.ts
- .gitignore
- apps/web/src/lib/b0_dist.test.ts (new)
Goal: Make every AC below true for `B0-DIST` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. With `rg -n` inside the allow-list, find the current symbols this card changes; list each as `current symbol → new symbol (signature)` at the top of the Worker packet.
2. Confirm the oracle tests are red: run the Test plan command → expect failures named after the ACs.
3. Implement AC by AC with the smallest change, reusing existing helpers (write gate, `app/ai_client` + `fence_fields`, studio tokens, shared components). No new abstraction unless used twice.
4. Add tests: for each AC one positive and one negative case with concrete input → expected output. If the card writes to Odoo: an idempotency double-run (second run writes 0) and an undo round-trip.
5. Run the Test plan commands → all green; for web changes also `cd apps/web && pnpm typecheck && pnpm lint` → exit 0.
6. Write the Worker packet (`05_PACKETS.md`). Do not touch files outside the allow-list; do not edit oracle tests.
7. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: `next.config.ts` never builds into `.next` while `next dev` runs: any `next build` started by a script, test or agent uses a separate `distDir` (for example `.next-build` or `.next-e2e-<port>`), set by the script itself, not by remembering an env var. (source: INGENIUM_MASTER_HANDOVER.md L479)
- AC2: Playwright's web server config and every repo script that runs `next build` set the distDir explicitly. (source: INGENIUM_MASTER_HANDOVER.md L480)
- AC3: test: start `next dev` on `:3002`, run the production e2e build, then load three routes on `:3002`. All return 200 with no "missing chunk" or manifest errors. (source: INGENIUM_MASTER_HANDOVER.md L481)
- AC4: `.gitignore` covers every new distDir. (source: INGENIUM_MASTER_HANDOVER.md L482)
- AC5: The connections list is unpaginated. The Connect page loads every row. That is a likely cause of the frozen Connect page Tope reported. [Inferred] See P0-5. (source: INGENIUM_MASTER_HANDOVER.md L190)
- AC6: Idempotency: running the same plan twice on a disposable DB writes 0 records the second time
Symbols:
- `apps/web/next.config.ts`: `ingeniumDistDir` (`INGENIUM_DIST_DIR`), `isPlaywrightE2eBuild` (`PLAYWRIGHT_E2E_BUILD`). `distDir` is `.next-e2e` only when `PLAYWRIGHT_E2E_BUILD=1`; otherwise `output: "standalone"` writes `.next`.
- Scripts that run `next build`: `apps/web/package.json` `"build": "next build --turbopack"`; `playwright.config.ts` `webServer.command` (`PLAYWRIGHT_E2E_BUILD=1 pnpm exec next build && pnpm exec next start ...`). No other repo script runs `next build`.
- `.gitignore` has `.next/`, which does not cover `.next-e2e` or `.next-build`.
Worked example:
- `next dev` is serving `http://127.0.0.1:3002` from `.next`. Run the playwright `webServer.command` production build. `curl -s -o /dev/null -w '%{http_code}'` on `http://127.0.0.1:3002/`, `/connect`, and `/settings` each prints `200`. The dev server reports no `missing chunk` and no manifest error.
Decision:
| caller | distDir |
| `package.json` `dev` (`next dev` on port 3002) | `.next` |
| `package.json` `build` | a directory other than `.next`, set in that script |
| `playwright.config.ts` `webServer.command` | a directory other than `.next`, set in that command |
Test plan:
- `cd apps/web && pnpm vitest run src/lib/b0_dist.test.ts` → all pass
Common mistakes: raw hex instead of tokens; a bare `next build` (overwrites dev `.next`; use own distDir); spinner instead of skeleton; copy that fails the jargon guard; light text on light-ish backgrounds.
Elite design notes: Code Runner and Script Runner execute user code only in the sandbox container (handover §6.9): no host mounts, network only to the target Odoo, CPU/memory/wall-clock limits, killed on limit. Never run user code in the API process. Writes from scripts go through the observer connection + write gate (dry run = intercepted writes, no rollback; say so in the UI, CR-HONEST). Live checks only on `ingenium_*` DBs.
Oracle tests: Oracle-first: a separate L3 Oracle session writes red tests in `apps/web/src/lib/b0_dist.test.ts` (one positive + one negative per AC, named `test_ac<n>_...`) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
