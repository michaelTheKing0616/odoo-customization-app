# REG-NP-UI: Dark-mode alert tokens

ID: REG-NP-UI
Title: Dark-mode alert tokens
Status: done
Phase: 0
Priority: P2
Type: regression
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-UI-F01;NP-UI-F03;NP-UI-F05;NP-UI-F07;NP-UI-F10;NP-UI-F11
Depends on: B0-INV
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L1 separate session · Score: 1 (C0 U0 F1 K0 V0 I0)
Context pack:
- `sed -n '33,48p' docs/plans/next-phase/cards/T7_UI_FOUNDATION.md`
- `sed -n '60,77p' docs/plans/next-phase/cards/T7_UI_FOUNDATION.md`
- `sed -n '93,103p' docs/plans/next-phase/cards/T7_UI_FOUNDATION.md`
- `sed -n '18,31p' apps/web/src/styles/globals/alerts.css`
- `sed -n '88,92p' apps/web/src/components/ui/DataTable.tsx`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_reg_np_ui.py (new)
Goal: Pin the already-fixed behaviour behind `REG-NP-UI` with a test that fails if it regresses; no product change.
Steps:
1. Read the context pack. State the fixed behaviour this regression pins, as input → expected output, one per AC.
2. Write the regression test only (product code is read-only for this card).
3. Prove it can fail: in the Worker packet name the product line whose deletion would make the test fail.
4. Run the Test plan command → green; run it in reverse/random order → green.
5. If the behaviour is already broken, stop: report the failing assertion; the Orchestrator opens a fix card.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: Dark-mode alert tokens (pressure 2) (source: ledger NP-UI-F01, next-phase cards/T7_UI_FOUNDATION.md)
- AC2: Split to REG-NP-UIb on 2026-10-22. This card does not pin kit Skeleton or `states.test.tsx` covering all six files. The six route sentences below stay as captured behaviour.
- AC3: EmptyState and Skeleton adopted on operate pages (pressure 5) (source: ledger NP-UI-F03, next-phase cards/T7_UI_FOUNDATION.md). Captured 2026-10-22: `13_UI_SCREEN_SPECS.md` marks no route "can be empty", so the set is empty.
- AC4: Tabs to Base UI (pressure 6) (source: ledger NP-UI-F05, next-phase cards/T7_UI_FOUNDATION.md)
- AC5: Hover and Escape stay on this card. Keyboard focus opens the tooltip immediately; that 125 ms sentence is split to REG-NP-UIb on 2026-10-22. This card does not pin it.
- AC6: Slot (Button asChild) (pressure 5) (source: ledger NP-UI-F07, next-phase cards/T7_UI_FOUNDATION.md)
- AC7: input-otp for TOTP (pressure 5) (source: ledger NP-UI-F10, next-phase cards/T7_UI_FOUNDATION.md)
- AC8: react-virtuoso for tables over 50 rows (pressure 6) (source: ledger NP-UI-F11, next-phase cards/T7_UI_FOUNDATION.md)
Worked examples (the regression reads these files; it does not restyle them):
- Pin AC1: `.odoo-form-alert--info` uses `background: var(--info-1)`, `border-color: var(--info-2)`, `color: var(--info-5)`. `--warning` and `--danger` use `--warning-1/2/5` and `--danger-1/2/5` the same way. No raw hex on those three rules.
- Pin AC4: `Tabs` imports `Tabs as BaseTabs` from `@base-ui/react/tabs`. ArrowRight moves `aria-selected` from the first tab to the second. `@radix-ui/react-tabs` is not imported by `Tabs.tsx`.
- Pin AC5 hover: `TOOLTIP_OPEN_DELAY_MS` is 200. Hover is hidden at 124 ms and shown by 200 ms. Escape removes the tooltip. Keyboard focus opens it immediately. That sentence is a suspect, owned by REG-NP-UIb, not a pin.
- Pin AC6: `Button` with `asChild` and one React element child renders that child through `SlotButton`. Zero or several children fail `Children.only`. One child that is not an element throws `Error` `"Button: asChild expects a single React element child."`
- Pin AC7: `TotpCodeInput` paste of `"123456"` sets the value to `123456` and calls `onComplete("123456")`. Paste of `"123 456"` becomes `123456`. The input has `autocomplete="one-time-code"`, `inputmode="numeric"`, `maxlength="6"`, and `data-input-otp`.
- Pin AC8: `shouldVirtualizeRows(50)` is False and `shouldVirtualizeRows(51)` is True (`DEFAULT_VIRTUALIZE_THRESHOLD` is 50). `DataTable` and `BulkResultTable` with 50 rows render 50 data rows. With 51 rows the rendered data-row count is below 51. ArrowUp / ArrowDown go through `stepActiveRowIndex`. Sort and filter of 5,000 rows finish in under 100 ms.

| `rowCount` | `shouldVirtualizeRows` |
|---|---|
| 50 | False, plain table |
| 51 | True, `TableVirtuoso` |
Captured 2026-10-22 route sentences (AC2 remainder, not the Skeleton check): root loading “Loading page”; root error “Load this page failed” plus Try again and Go home to `/`; root not-found “This page isn't here”; connection loading “Loading connection”; connection error “Load this connection failed” plus View connections at `/connections`; connection not-found “Find this connection failed”.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_ui.py` → pass
- `cd apps/api && uv run pytest -q tests/test_reg_np_ui.py` in reverse/random order → pass
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
