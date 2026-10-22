# V-STUDIODRAFT: studio-draft.ts non-repo Prettier reformat; decideStudioStockApp + startOptionABatch recov

ID: V-STUDIODRAFT
Title: studio-draft.ts non-repo Prettier reformat; decideStudioStockApp + startOptionABatch recov
Status: todo
Phase: 0
Priority: P1
Type: verify
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: AS-STUDIODRAFT;DISC-STUDIODRAFT
Depends on: none (phase order applies)
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 2 (C0 U0 F1 K0 V1 I0)
Context pack:
- `sed -n '243p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '104p' apps/api/evals/v2/PROGRESS.md`
- docs/build-plan/FACTS.md
File allow-list:
- docs/build-plan/verify/V-STUDIODRAFT.md (new)
- apps/web/src/lib/api/studio-draft.ts
- apps/web/src/lib/api/studio-draft.live.test.ts (new)
Goal: Record the reconstructed-type claim, replace it with the route's real response shape, and prove that shape against a disposable API. Tope replaced the eyeball with this proof on 22 Oct.
Steps:
1. Do not change product code. Measure exactly the claim in each AC using the commands below (tests, `rg`, a timed run, or a disposable `ingenium_*` live check). `docs/build-plan/verify/` does not exist yet; creating the allow-list file creates it. Read-only `git log` / `git blame` only. No checkout, reset, stash, or commit.
2. Write `docs/build-plan/verify/V-STUDIODRAFT.md`: claim · command · measured output summary (counts, timings) · verdict (true / false / partial) · label proposal. Never upgrade a label without new evidence (INV-08).
3. If the verdict is false or partial, propose one ledger row (ID, one_line, card) in the Worker packet; do not fix it here.
4. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: `studio-draft.ts` was reformatted by a non-repo Prettier on 19 Oct and two methods (`decideStudioStockApp`, `startOptionABatch`) were recovered from a webpack cache. Tope should eyeball this file's diff. `startOptionABatch`'s return type is reconstructed. (source: INGENIUM_MASTER_HANDOVER.md L243)
- AC2: studio-draft.ts reformat review (source: ledger DISC-STUDIODRAFT, §3.3)
- AC3: `docs/build-plan/verify/V-STUDIODRAFT.md` records claim, command, measured result and verdict; any false/partial verdict has a proposed ledger row
Symbols (file `apps/web/src/lib/api/studio-draft.ts`, object `studioDraftApi`): `decideStudioStockApp: async (sessionId: string, decision: "install" | "decline")` (L135); `startOptionABatch: (sessionId: string) => request<{ session_id: string; pieces?: unknown[]; promote?: unknown }>` (L192-196). Incident text: `apps/api/evals/v2/PROGRESS.md` L104. Handover L243 still matches that sentence. Repo has no Prettier config. Tope's eyeball is DEC-031 (Gate A), not a Worker edit.
Worked example (re-run; do not copy the verdict): command `rg -n "decideStudioStockApp|startOptionABatch" apps/web/src/lib/api/studio-draft.ts`. Input `startOptionABatch("sess_example")`. Output type `{ session_id: string; pieces?: unknown[]; promote?: unknown }`. A record that still shows `unknown` on `pieces` and `promote` supports "return type is reconstructed".
Decision table:

| Evidence | Verdict |
|---|---|
| both methods exist on `studioDraftApi` AND `startOptionABatch` returns `{ session_id: string; pieces?: unknown[]; promote?: unknown }` AND PROGRESS.md L104 still describes the non-repo Prettier recovery | true |
| either method is missing, or the return type has no `unknown` | false |
| methods match the reconstructed type but L104 is gone, or the diff DEC-031 must eyeball is not recorded | partial |

Test plan:
- `test -s docs/build-plan/verify/V-STUDIODRAFT.md` → exit 0
- the measurement commands recorded in that file, re-run by the Tester → same verdict
Common mistakes: citing a path that does not exist; restating the handover instead of citing its line; upgrading a label without evidence.
Gate: none (DEC-031 eyeball replaced by proof on 22 Oct: tsc, a disposable API test, and the real response types). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
