# REG-NP-UIb: Loading skeleton and tooltip keyboard delay

ID: REG-NP-UIb
Title: Loading skeleton and tooltip keyboard delay
Status: done
Phase: 0
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-UI-F02;NP-UI-F06;P0-2-TSC-UIB
Depends on: REG-NP-UI
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- .cursor/skills/ingenium-ui-excellence/SKILL.md
- `sed -n '38,48p' docs/plans/next-phase/cards/T7_UI_FOUNDATION.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/web/src/app/loading.tsx
- apps/web/src/app/error.tsx
- apps/web/src/app/not-found.tsx
- apps/web/src/app/connections/[id]/loading.tsx
- apps/web/src/app/connections/[id]/error.tsx
- apps/web/src/app/connections/[id]/not-found.tsx
- apps/web/src/app/states.test.tsx
- apps/web/src/components/ui/Tooltip.tsx
Goal: Finish the two REG-NP-UI leftovers. Do not restyle anything else.
Steps:
1. Read the UI skill first. Use its §1 Step 7 before editing a screen.
2. Make `states.test.tsx` cover all six loading, error, and not-found files. Each loading file uses the kit Skeleton.
3. Keyboard focus must not show the tooltip before 125 ms, and must show it by 200 ms. Hover stays hidden at 124 ms and shown by 200 ms. Escape still removes it.
4. Do not edit `apps/api/tests/test_reg_np_ui.py`. Do not edit or delete `apps/web/src/app/e2e/trial-xray-grok/` or `docs/vision-verify/trial-xray/`.
5. STOP-AND-ASK: a needed file is outside the allow-list.
Acceptance criteria:
- AC1: `states.test.tsx` covers the six route files, and each loading file uses the kit Skeleton. (source: ledger NP-UI-F02)
- AC2: Keyboard focus does not show the tooltip before 125 ms and does show it by 200 ms. (source: ledger NP-UI-F06)
Test plan:
- `cd apps/web && pnpm exec vitest run src/app/states.test.tsx` → pass
Gate: none (no Tope gate). Narrowest named test green → Tester PASS → Reviewer PASS.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]).
Rollback: Revert only the allow-list files.
Definition of Done: Both ACs have evidence; no file outside the allow-list changed.
