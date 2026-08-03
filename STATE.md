# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **EXP-2 shipped:** `apps/api/app/expert/grounding.py` — `assemble_context()` →
  `GroundingBundle` (instance summary, tier capabilities, UI/draft context, protected-tier
  flags, RPC error cross-check, bulk-tool deep links, version filter + token-capped sections).
- Gate: `test_expert_grounding` 8 passed (+1 live skip); `test_expert_ingest` 10 passed.
- Prior: recovery commits `f01c4a1` / `ef1cb80`; EXP-1 ingest store (~7940+ chunks).

## Next
- **EXP-3** — `POST /api/expert/ask` ground-or-decline + citations (`plans/PROGRESS.md`).

## Rules
- Expert ingest cache: `.cache/expert/` (gitignored). CLI: `python -m app.expert.ingest --version 19.0`.
- Community Q&A: `EXPERT_COMMUNITY_SOURCE=dir` + `EXPERT_COMMUNITY_DIR=…` (off default).
- Grounding: pass `connection_id`, optional `ui_context`, `question`; live RPC checks capped at 8 refs.
