# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **EXP-3 shipped:** `POST /api/expert/ask` — `apps/api/app/expert/ask.py` +
  `apps/api/app/routers/expert.py` (retrieval + grounding + ground-or-decline generation,
  citation enforcement + one regenerate, tier-1 PCM-consistent refusal, legal/tax flag).
- Gate: `test_expert_ask` 10 passed; expert suite 28 passed (+1 live skip).
- Prior: EXP-2 `c2f6eb9`; EXP-1 ingest store (~7940+ chunks).

## Next
- **EXP-4** — evaluation regression set + harness (`plans/PROGRESS.md`).

## Rules
- Expert ingest cache: `.cache/expert/` (gitignored). CLI: `python -m app.expert.ingest --version 19.0`.
- Community Q&A: `EXPERT_COMMUNITY_SOURCE=dir` + `EXPERT_COMMUNITY_DIR=…` (off default).
- Expert ask: `POST /api/expert/ask` requires `AI_ASSIST`; optional live E2E → `docs/research/expert_runs_<date>/`.
