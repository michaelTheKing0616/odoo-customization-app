# REG-NP-UI-FIX: asChild names a non-element child

ID: REG-NP-UI-FIX
Title: asChild names a non-element child
Status: done
Phase: 0
Priority: P2
Type: fix
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-UI-F07
Depends on: B0-INV
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U0 F1 K1 V1 I0)
Context pack:
- `sed -n '94,126p' apps/web/src/components/ui/Button.tsx`
- `sed -n '73,77p' docs/plans/next-phase/cards/T7_UI_FOUNDATION.md`
- docs/build-plan/FACTS.md
File allow-list:
- apps/web/src/components/ui/Button.tsx
- apps/web/src/components/ui/Button.asChild.test.tsx
Goal: One `asChild` child that is not an element throws `Button: asChild expects a single React element child.` Zero or several children still fail `Children.only`. One element child still renders through `SlotButton`.
Steps:
1. Read the `asChild` branch. `Children.only` runs first, so a string child never reaches the error on the next line.
2. When `asChild` has one child and that child is not a React element, throw `Error` `"Button: asChild expects a single React element child."` before `Children.only`.
3. Keep the call `Children.only(children)` for zero children and for several children. Do not change the one-element path, classes, disabled, or loading.
4. Add one case to `Button.asChild.test.tsx`: a single text child throws that exact message. Leave the existing cases as they are.
5. Do not edit `apps/api/tests/test_reg_np_ui.py`, `Tooltip.tsx`, or any other file.
6. STOP-AND-ASK: the change would alter a valid element child; a needed file is outside the allow-list; a live check would need a non-`ingenium_` DB, a forbidden port, a git write, or a new dependency.
Acceptance criteria:
- AC1: `Button` with `asChild` and one text child throws `Error` `"Button: asChild expects a single React element child."` (source: ledger NP-UI-F07)
- AC2: `Button` with `asChild` and zero children, or several element children, still throws `React.Children.only`. One element child still renders that child. (source: Button.asChild.test.tsx)
Worked example:
- `<Button asChild>text</Button>` throws the Button message.
- `<Button asChild></Button>` and two `<a>` children throw `React.Children.only`.
- `<Button asChild><a href="/connect">Go connect</a></Button>` renders the anchor.
Test plan:
- `cd apps/web && pnpm exec vitest run src/components/ui/Button.asChild.test.tsx` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_ui.py` → pass
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session) → Reviewer PASS (separate session).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]).
Rollback: Revert `apps/web/src/components/ui/Button.tsx` and `apps/web/src/components/ui/Button.asChild.test.tsx` only.
Definition of Done: AC1 and AC2 have evidence; `Children.only(children)` remains in `Button.tsx`; the regression file is unmodified; no file outside the allow-list changed.
