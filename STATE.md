# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **REM-14 shipped** — closed Wave 11 residual punch list: staged pipeline guardrail/schema-in-format, PCM update_automation, sandbox subprocess kill, role matrix + entitlements tests, EE harness, live artifacts (staged run, expert runs/eval, BLK 7/7 + 17/18/19 probes, vision PNGs), one commit (not pushed).
- Gates: API **758 passed** / 2 skipped (`-m "not integration"`); web lint 0 errors, **91 vitest**, build OK; Playwright REM-14 specs **9/9** (1 ODOO_E2E skip).

## Next
- **REM-13** OAuth (Google + GitHub) — user-scheduled, not started.
- Then Wave 12 TRUST (`plans/cards/WAVE-12-TRUST.md`, TRUST-1..9). Order: TRUST-1 → TRUST-2 first.
- Optional: install `project`+`sale` on docker-19 for `test_inspection_checklist_live_odoo19`; fix deploy stack `/api/billing/plans` 404 for full LAUNCH-1.

## Rule
- Live LLM artifacts must have `"mode":"live"` — never relabel fixture runs.
- Playwright e2e harness pages need `CI=1` or fresh `next start` with `NEXT_PUBLIC_E2E=1` (reuse of deploy :3000 serves 404 on `/e2e/*`).
