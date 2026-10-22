# REG-NP-GND-FIX: Stock-app decline reaches the stop

ID: REG-NP-GND-FIX
Title: Stock-app decline reaches the stop
Status: done
Phase: 0
Priority: P2
Type: fix
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-GND-MOD
Depends on: B0-INV
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F2 K1 V1 I0)
Context pack:
- `sed -n '157,178p' apps/api/app/dry_run_middleware.py`
- `sed -n '1284,1323p' apps/api/app/routers/ai_studio.py`
- `sed -n '485,556p' apps/api/tests/test_reg_np_gnd.py`
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/app/dry_run_middleware.py
Goal: A stock-app decline is not an Odoo write, so the dry-run gate lets that one body through. Install stays gated. The oracle test is not edited.
Steps:
1. Read the context pack. The route at `ai_studio.py` already stops a decline. The gate rejects the POST before that route runs.
2. In `_action`, when the path is the stock-app route and the JSON body has `decision == "decline"`, return `pass`. Do not store a preview and do not call Odoo.
3. Leave `("POST", "/api/ai/sessions/{session_id}/stock-app")` in `GATED_ROUTE_TEMPLATES`. `decision == "install"` and every other stock-app body still reject until the same arguments were previewed.
4. Do not edit `apps/api/tests/test_reg_np_gnd.py`, `apps/api/tests/test_dry_run_ledger.py`, or `apps/api/app/routers/ai_studio.py`.
5. Run the Test plan. If `test_each_gated_tool_refuses_until_the_same_args_were_seen` fails, the exemption is too wide. Narrow it. Do not edit that test.
6. STOP-AND-ASK: a needed file is outside the allow-list; the change would let `install` through without a receipt; a live check would need a non-`ingenium_` DB, a forbidden port, a git write, or a new dependency.
Acceptance criteria:
- AC1: `POST /api/ai/sessions/{id}/stock-app` with `{"decision": "decline"}` reaches the route and the existing oracle asserts `stopped is True`, `status == "stopped"`, and the Sales-not-installed message. (source: ledger NP-GND-MOD)
- AC2: The same route with `{"name": "x"}` or `{"decision": "install"}` and no prior preview still returns 403 `dry_run_receipt_required`. (source: tests/test_dry_run_ledger.py)
Worked example:
- Decline body has no `dry_run` key. The gate returns `pass`. The route returns the stop payload.
- Install body with no prior preview still returns 403.
Test plan:
- `cd apps/api && uv run pytest -q tests/test_reg_np_gnd.py::test_ac6_decline_stops_stock_app_request tests/test_dry_run_ledger.py` → pass
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session) → Reviewer PASS (separate session; L3; write-gate).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]).
Rollback: Revert `apps/api/app/dry_run_middleware.py` only.
Definition of Done: AC1 and AC2 have evidence; the oracle file is unmodified; stock-app stays on the gated list; install still needs a receipt; no file outside the allow-list changed.
Elite design notes: This is a write-gate change (INV-14). Decline does not call `button_immediate_install`. The exemption is that one decision value on that one route. Install, apply, promote, and uninstall stay behind the receipt. The oracle pin stays locked.
Oracle tests: The pin is already in `apps/api/tests/test_reg_np_gnd.py::test_ac6_decline_stops_stock_app_request`. This card does not edit it. Score is 7, so no E1 review.
