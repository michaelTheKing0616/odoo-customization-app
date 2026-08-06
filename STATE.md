# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-07
- **Deploy API follow-up:** rebuilt `odoo-custom-deploy-api` with vision env;
  `OLLAMA_BASE_URL=http://host.docker.internal:11434` (not container 127.0.0.1);
  stamped/upgraded deploy app-db to `f2a3b4c5d6e7`; moved `httpx` to runtime deps.
  Verified: `/health` ollama_reachable; `/ingest/vision/status` enabled+ready qwen3-vl:8b.
- Prior: GEN2-9 + ingest finish pushed as `ab83197`.
- **Cannot complete:** Tongyi Qianwen EU commercial agreement (human/legal only)

## Next
- Owner: file Tongyi agreement before marketing vision OCR in EU
- Optional: live vision OCR on a real invoice scan (smoke used blank PNG)

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
