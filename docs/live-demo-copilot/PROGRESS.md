# Live Demo Co-Pilot — Progress

Capture layer: **self-hosted Attendee** ([attendee-labs/attendee](https://github.com/attendee-labs/attendee)). WhatsApp permanently out of scope.

Production build order: (1) durable foundation → (2) Attendee ops → (3) Stage 1/2 → (4) overlay → (5) pilot.

## Phase 0 — Consent & disclosure

- [x] Visible disclosure endpoint + premium UI copy
- [x] Opt-out / decline path prevents launch
- [x] Launch API blocked without consent + attendee notification checkboxes
- [x] Default retention = do not retain (`retention_opt_in` false unless explicit)
- [x] Immutable consent audit rows (`live_demo_consent_audit`)
- [ ] Manual verification in a real test meeting (needs Attendee + Zoom/Meet)

## Phase 1 — Attendee integration + prod foundation

- [x] Settings: `ATTENDEE_*`, `APP_ENVIRONMENT`, webhook skew
- [x] Create / leave bot APIs (gated by consent)
- [x] HMAC-verified webhook; **no unsigned webhooks in production**
- [x] Webhook replay protection (`live_demo_webhook_receipts`)
- [x] Durable workspace-scoped sessions (`live_demo_copilot_sessions`)
- [x] Transcript lines in DB; purge on leave when retention off
- [x] Live SSE fan-out (process-local; durability is DB)
- [x] Mock mode blocked when `APP_ENVIRONMENT=production`
- [x] Alembic `i9j0k1l2m3n4_live_demo_copilot`
- [x] Docs: `docs/live-demo-copilot/ATTENDEE.md`
- [x] Bot status normalization (waiting room / fatal / permission denied)
- [x] Refresh status + leave/purge background job with retry
- [x] Presenter UX callouts for host-action states
- [x] Ops runbook: `docs/live-demo-copilot/OPS.md`
- [ ] Real Zoom/Meet join with self-hosted Attendee (operator setup)
- [ ] Measure speech→webhook latency in a live call

## Phase 2 — Stage 1/2 detection

- [x] Stage 1 relevance filter (heuristic question + Odoo terms) — `stage1_filter.py`
- [x] Stage 2 Expert RAG live brevity + confidence flags (surface low-confidence) — `stage2_answer.py`
- [x] Pipeline: transcript append → Stage 1 → Stage 2 → persist `LiveDemoAnswer` + SSE `answer`
- [x] Answers API (`/answers`, `/stage1-preview`, `/run-pipeline-sync`) + session UI section “4. Live answers”
- [x] Alembic `k1l2m3n4o5p6_live_demo_answers`
- [x] Tests: `tests/test_live_demo_copilot.py` — **13 passed** (incl. Stage 1/2) after fixing `_compress_with_llm` string literal

## Phase 3 — Presenter overlay

- [x] Pop-out overlay route `/live-demo-copilot/overlay?session=…` (no AppShell chrome)
- [x] Premium `PresenterOverlay` HUD (latest bullets, confidence flags, history, SSE status)
- [x] Screen-share guidance: share meeting/Odoo window only — never this overlay
- [x] Session page: **Open presenter overlay** + renumbered sections
- [x] Vitest: empty / answer / low-confidence

## Phase 4 — Pilot readiness

- [x] Presenter speaker ignore-list (`presenter_speakers_json`, create + PATCH)
- [x] Pipeline skips configured presenter speakers (host rhetorical Qs)
- [x] Session UI: display name field + Save presenter names
- [x] Alembic `l2m3n4o5p6q7_live_demo_presenter_speakers`
- [x] Fixed Stage 1 `\\b` word-boundary corruption in `stage1_filter.py`
- [x] Pilot checklist: `docs/live-demo-copilot/PILOT.md`
- [ ] Run first internal pilot on a real Zoom/Meet with Attendee (operator)
