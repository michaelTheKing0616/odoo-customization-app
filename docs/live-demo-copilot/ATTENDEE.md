# Attendee setup for Live Demo Co-Pilot

## What Attendee is

Open-source meeting bot API (Zoom, Google Meet, Microsoft Teams). We self-host it and call its REST API; it sends `transcript.update` webhooks into our FastAPI app.

Upstream: https://github.com/attendee-labs/attendee  
Docs: https://docs.attendee.dev/

## Honest constraints

- The bot is **visible** in the meeting (not Zoom RTMS no-bot).
- Production Attendee recommends **Kubernetes** isolation per bot; `dev.docker-compose.yaml` is for local/dev.
- Zoom requires a Zoom Marketplace **Meeting SDK** app (client id/secret) entered in Attendee Settings.
- Transcription typically needs a **Deepgram** API key in Attendee Settings.
- Our API listens on `:8001`; Attendee default UI/API is `:8000` — no port clash.

## Local Attendee (dev)

```bash
git clone https://github.com/attendee-labs/attendee.git ~/attendee
cd ~/attendee
docker compose -f dev.docker-compose.yaml build
docker compose -f dev.docker-compose.yaml run --rm attendee-app-local python init_env.py > .env
# edit .env (AWS/S3 or local storage per upstream README)
docker compose -f dev.docker-compose.yaml up
# other terminal:
docker compose -f dev.docker-compose.yaml exec attendee-app-local python manage.py migrate
```

1. Open http://localhost:8000 — create account (confirm link appears in docker logs).
2. Settings → enter Zoom OAuth + Deepgram.
3. API Keys → create key.
4. Settings → Webhooks → URL `https://<public-tunnel>/api/live-demo-copilot/webhooks/attendee`  
   Triggers: `transcript.update`, `bot.state_change`. Copy webhook secret (base64).

For local webhooks from hosted Attendee, use ngrok/cloudflare tunnel to your `:8001` API.

## App `.env` (this repo)

```bash
ATTENDEE_API_BASE=http://127.0.0.1:8000
ATTENDEE_API_KEY=your_attendee_api_token
ATTENDEE_WEBHOOK_SECRET=base64_secret_from_attendee
# UI/consent testing without Attendee:
# ATTENDEE_ALLOW_MOCK=true
```

## App flow

1. Open **AI Studio → Live Demo Co-Pilot** for a connection.
2. Paste meeting URL → Create session.
3. Complete disclosure checkboxes → Record consent.
4. Launch bot (blocked until consent).
5. Transcript lines stream via SSE; Leave ends bot and calls Attendee `delete_data` unless retention opt-in.

## Security

Webhook signature: base64 HMAC-SHA256 of canonical JSON (`X-Webhook-Signature`), matching Attendee’s realtime example.


## Production hardening (this app)

- Set `APP_ENVIRONMENT=production` — mock bot launch is refused even if `ATTENDEE_ALLOW_MOCK=true`.
- `ATTENDEE_WEBHOOK_SECRET` is required in production; unsigned webhooks are rejected.
- Optional `X-Webhook-Timestamp` (unix seconds): rejected when skew exceeds `ATTENDEE_WEBHOOK_MAX_SKEW_S` (default 300).
- Duplicate webhook payloads are acknowledged but not re-applied (replay protection).
- Sessions are workspace-scoped in Postgres (`live_demo_copilot_sessions`). Apply Alembic revision `i9j0k1l2m3n4` (or `create_all` in local test DBs).
- On leave without retention opt-in: Attendee `delete_data` + local transcript purge.
