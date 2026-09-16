# Live Demo Co-Pilot — Internal pilot checklist

Related: founder live RPC UAT is `docs/WEEK6-LIVE-RPC-UAT.md` (separate from this meeting pilot).

Use this for the first internal demos (consultant/SE/trainer as presenter). Clients only see the Attendee bot + disclosure; answers stay in the private overlay.

## Pre-flight

- [ ] API `:8001` and web `:3002` running; DB migrations applied through `l2m3n4o5p6q7`
- [ ] `ATTENDEE_*` configured **or** `ATTENDEE_ALLOW_MOCK=true` + `APP_ENVIRONMENT=development` for dry runs
- [ ] Real Zoom/Meet: Meeting SDK OAuth + Deepgram set in Attendee Settings (see `ATTENDEE.md` / `OPS.md`)
- [ ] Second display (or spare window) ready for the presenter overlay
- [ ] Know your **meeting display name** exactly as Zoom/Meet/Teams shows it

## Session flow

1. Open **Operations → Live Demo Co-Pilot** for a connection (first item in Operations; also on the ops hub).
2. Paste meeting URL; set bot name; enter **your display name(s)** (comma-separated) so Stage 1/2 ignores your rhetorical questions.
3. Create session → accept disclosure → confirm attendees notified → Launch bot.
4. Admit the bot / grant recording if the host-action callout appears.
5. Click **Open presenter overlay** → move that window to the second display.
6. In the meeting app: **Share window** (Zoom/Meet/Teams or Odoo tab) — **never** entire screen, **never** the overlay window.
7. Have a colleague ask an Odoo question; confirm 2–3 bullets + confidence flag appear in the overlay (not meeting chat).
8. Ask a rhetorical Odoo question yourself; confirm **no** new answer card (presenter ignore-list).
9. **Leave & end** → confirm leave/purge succeeds (or Retry leave/purge).

## Pass criteria

| Check | Pass |
| --- | --- |
| Consent required before launch | ✓ |
| Bot join + status callouts honest | ✓ |
| Client Odoo Q → overlay bullets | ✓ |
| Presenter name ignored | ✓ |
| Overlay never in shared window | ✓ |
| Leave purges when retention off | ✓ |

## After the pilot

- Note speech→answer latency and any missed questions (Stage 1 vocabulary gaps).
- File follow-ups in `PROGRESS.md` (real join UAT, latency measurement still open under Phase 1).
