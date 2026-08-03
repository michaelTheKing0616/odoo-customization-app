# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **Recovery complete (post git-restore incident):** 0 git deletions; wave work restored from
  agent transcript + PCM-4 subagent (`f5c2c283`).
- Restored: full `protected_enforcement.py`, `test_protected_enforcement.py`, vendored
  `apps/api/app/data/community_modules_{16,17,18,19}_0.json` (654 modules incl. `base`).
- Fixed replay corruption: `ai_rag.py` cosine recursion, `tier_matrix.py` dupes, `builder.py`
  duplicate route blocks (~380 lines removed), missing `safe_alternative_for`.
- Gates green: recovery battery **95 passed**; PCM-4+bulk+expert **139 passed**.
- **EXP-1** still shipped: expert ingest + 7940+ chunks in Postgres (cache gitignored).

## Next
- **Commit recovered work** (single baseline commit risk — strongly recommended before EXP-2).
- **EXP-2** — live-instance grounding context assembly (`plans/PROGRESS.md`).

## Rules
- Expert ingest cache: `.cache/expert/` (gitignored). CLI: `python -m app.expert.ingest --version 19.0`.
- Community Q&A: `EXPERT_COMMUNITY_SOURCE=dir` + `EXPERT_COMMUNITY_DIR=…` (off default).
