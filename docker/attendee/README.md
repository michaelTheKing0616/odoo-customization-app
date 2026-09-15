# Attendee sidecar

We do **not** vendor Attendee’s Django app into this monorepo.

Run Attendee from upstream:

https://github.com/attendee-labs/attendee#running-in-development-mode

Then point this app at it via `ATTENDEE_*` env vars (see `docs/live-demo-copilot/ATTENDEE.md`).
