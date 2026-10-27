# F1-VISUAL-HARNESS: Playwright screenshot harness for every route and state

ID: F1-VISUAL-HARNESS
Title: Playwright screenshot harness for every route and state
Status: blocked
Phase: 1
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: UI-5.14-HARNESS
Depends on: none (phase order applies)
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F2 K1 V1 I0)
Context pack:
- docs/build-plan/cards/phase-1/F1-VISUAL-REG.md
- apps/web/src/lib/f1_visual_reg.test.ts
- docs/build-plan/FACTS.md
File allow-list:
- apps/web/playwright.visual-reg.config.ts (new)
- apps/web/e2e/visual-regression.spec.ts (new)
- apps/web/e2e/visual-reg/ (new snapshots)
Goal: Add the Playwright screenshot harness that F1-VISUAL-REG found missing. Not started. Tope, 25 Oct. Do not dispatch this card in that session.
Elite design notes: One config, one spec, snapshots for every route and state. A pixel diff over the threshold fails unless the update was approved. Do not edit screen components. Do not take ports 3002, 8001, 8002, 8012, 5433, 5436, 8069-8073, or 11434. Do not write `.next` or `.next-e2e`.
Oracle tests: The pin in `f1_visual_reg.test.ts` is `it.fails` until a config contains `maxDiffPixel` and a spec contains `toHaveScreenshot`. That pin file is not on this allow-list.
Steps:
1. Do not start until this status is set back to todo. Tope, 25 Oct: record only.
2. Add the config, the spec, and the snapshots. Threshold blocks an unapproved diff.
3. Do not edit `apps/web/src/lib/f1_visual_reg.test.ts` while `L-F1-VISUAL-REG` holds it.
4. STOP-AND-ASK before any product screen edit, a non-`ingenium_` DB, a forbidden port, or a git write.
Acceptance criteria:
- AC1: Playwright snapshots exist for every route and state; a pixel diff over the threshold needs an approved update (source: ledger UI-5.14-HARNESS, handover §5.14 L713)
Test plan:
- The harness spec exits 0. Counts only. Do not mark `UI-5.14-AC` done from this card.
Gate: none (no Tope gate). Not started.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md` when a later session actually runs it.
Rollback: Revert this card's allow-list files only.
Definition of Done: AC1 has a green harness run; no file outside the allow-list changed; `UI-5.14-HARNESS` updated; status set to done. Not this session.
