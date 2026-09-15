# Live Demo Co-Pilot — Attendee operations runbook

## Goal

Run meeting capture reliably for paid workspaces: one visible Attendee bot per live session, clear waiting-room / failure UX for the presenter, and durable leave + data purge.

## Platform topology (production)

```
Presenter browser (:443 app)
        │
        ▼
Our API (FastAPI)  ──webhook──►  Attendee (your VPC)
        │                              │
        │                              ├─ web / API
        │                              ├─ Postgres + Redis
        │                              └─ Bot pods (Kubernetes: LAUNCH_BOT_METHOD=kubernetes)
        ▼
App Postgres (sessions, consent audit, transcripts, webhook receipts)
```

**Do not** run production bots as Celery tasks in a shared worker (Attendee upstream: bots die on restart; audio can bleed across meetings). Use **one bot per Kubernetes pod**.

Attendee’s paid self-host plan documents the official k8s path. Open-source compose (`dev.docker-compose.yaml`) is for local/dev only.

## One-time platform setup

1. Deploy Attendee to a private cluster (separate namespace from the app API).
2. Set `LAUNCH_BOT_METHOD=kubernetes` per Attendee production guidance.
3. Create Zoom Marketplace **General App** with **Meeting SDK** enabled; paste client id/secret into Attendee Settings.
4. Create Deepgram (or configured STT) key; paste into Attendee Settings.
5. Create Attendee API token; store as `ATTENDEE_API_KEY` in the app API secrets.
6. Register webhook: `https://<api-host>/api/live-demo-copilot/webhooks/attendee`  
   Triggers: `bot.state_change`, `transcript.update`.  
   Store secret as `ATTENDEE_WEBHOOK_SECRET` (base64).
7. App env:
   - `APP_ENVIRONMENT=production`
   - `ATTENDEE_API_BASE=https://attendee.<internal>`
   - `ATTENDEE_ALLOW_MOCK=false` (ignored/blocked in production anyway)

## Presenter ops (happy + stuck paths)

| State | What presenter sees | What to do |
| --- | --- | --- |
| Joining | “Joining…” | Wait |
| Waiting room | Warning + host action | Admit bot in Zoom/Meet/Teams |
| Listening | Success | Demo normally |
| Recording permission denied | Danger + host action | Grant recording; **Refresh status** |
| Join failed / fatal | Danger | Check meeting URL, Zoom SDK app, Attendee logs; new session |
| Leave & end | Session ended; purge pending/succeeded | If purge failed → **Retry leave/purge** |

## Leave + purge reliability

On **Leave & end**:
1. Session marked `ended` immediately (presenter UX).
2. Background job `live_demo_leave_purge` retries Attendee `leave` (+ `delete_data` when retention off).
3. Local transcripts purged when retention is off (even if Attendee purge fails — minimize local retention).
4. `leave_purge_status`: `pending` → `succeeded` | `failed` (+ `last_ops_error`).

## Health checks

- Attendee `/health` (or UI login) from inside the VPC.
- Create a short internal Zoom meeting weekly: consent → launch → admit if waiting room → speak one sentence → leave → confirm `data_deleted` / purge succeeded.
- Alert on: webhook 4xx spike, `leave_purge_status=failed` count, fatal_error rate.

## Security notes

- Webhook HMAC required in production; unsigned rejected.
- Replay protection via payload hash receipts.
- Consent audit rows are append-only.
- Never put Attendee keys in the browser.

## Next product phases (not ops)

Stage 1/2 + presenter overlay + ignore-list are in-app. Run internal pilots via `PILOT.md`.
