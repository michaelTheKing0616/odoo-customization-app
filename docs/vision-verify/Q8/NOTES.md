# Q8 — one-time screenshot round (Oct 20, 2026)

17 leap screens captured from the e2e harness (NEXT_PUBLIC_E2E=1, 1440×900): `round/UI-S-<n>.png`; contact sheets `sheet-round-1..3.jpg`.

Findings and actions:
- Fixed in this round: leftover "Dry-run"/"Dry run" labels (Bulk, Power Ops, Config, Import, Ingest, Housekeeping, Cron, Code runner) → "Test run" (step test ids kept); Live Demo "Stage 1/Stage 2/RAG" limits text rewritten plainly; History "T5A-03 chain verify" line rewritten plainly.
- Open (frame consistency, A2): Operations (29), Bulk Suite (30) and Fleet (51) use a light header; the other 14 use the dark studio bar.
- Open (harness only): Code Studio (18) harness lacks a connection mock, so it shows "Request failed … GET /api/connections/demo-conn" plus a duplicate toast; raw request paths should never reach the screen.
- Open (wording): Automations kicker "Option A for Python. Promote stays human."; ID generator "PREFIX / INITIALS / NUMBER"; API settings "Auth mode / bootstrap / Env APP_API_KEY". These are e2e harness copy or need Tope's wording call.
