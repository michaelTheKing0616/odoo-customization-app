# Wave 0 — SAFE: repo baseline (run before anything else)

Shared context: repo root `/Users/temitopeolaitanmichael/Odoo_Customization_App`. The git repo
exists on branch `master` with ZERO commits — the entire tree is untracked. Nothing may be
implemented by any model until SAFE-1 is done.

---

## SAFE-1 — Initial git commit baseline

TASK: Create the initial baseline commit of the entire current working tree, with a correct
.gitignore, so every later card has a rollback point.

INPUT: repo root; existing `.gitignore` files (root and per-app, if any); `.env.example`.

CHECKLIST:
- [x] Verify `.gitignore` covers: `.env`, `.env.*` (except `.env.example`), `node_modules/`,
      `.next/`, `__pycache__/`, `.pytest_cache/`, `.venv/`, `dist/`, `*.pyc`, `.DS_Store`,
      `docker/**/odoo-data`-style volume dirs if present, Playwright artifacts
      (`apps/web/test-results/`, `apps/web/playwright-report/`).
- [x] `git status --short` and confirm NO real secret file (`.env`, key files) would be added.
      If any exists tracked-eligible, add to .gitignore first and report it.
- [x] Stage everything: `git add -A`; re-verify with `git status --short` that ignored files
      stayed ignored.
- [x] Commit with message: `chore: baseline commit of existing platform (pre-orchestration)`.
- [x] Run `git log --oneline` and confirm exactly one commit exists.

DONE MEANS: one commit on `master` containing the full tree minus ignored files; no secrets
committed; `git status` clean afterward.

DO NOT: push anywhere; create branches; modify any source file except `.gitignore`.

GATE: `git log --oneline | wc -l` → 1; `git status --porcelain` → empty;
`git ls-files | grep -E "\.env$"` → empty.

RETURN: ≤10 lines — commit hash, file count, any secrets found and excluded.

DEVIATIONS: if a file looks like a secret but is ambiguous, exclude it and flag — never commit
and ask later.

---

## SAFE-2 — Close the STATE.md law-firm follow-up

TASK: Execute the pending verification in STATE.md "Next": restart the API, re-run the
law-firm generation prompt, verify the five expected outcomes, and update STATE.md.

INPUT: `STATE.md`; `apps/api/app/ai_domain_packs.py`, `ai_domain_pack_law_firm.py`,
`ai_model_quality.py`; docker Odoo 19 stack (`docker/docker-compose.yml`); Ollama running
with the configured model; `apps/api` dev server instructions in README/docs.

CHECKLIST:
- [ ] Run the API test suite subset first:
      `cd apps/api && uv run pytest tests/test_ai_law_firm_pack.py tests/test_ai_model_quality.py -q` — all pass.
- [ ] Start (or restart) the API with AI enabled; confirm `GET /api/ai/status` shows the
      provider up and `law_firm` pack registered.
- [ ] POST `/api/ai/draft-module` with prompt: "Build a world-class law firm practice
      management app with matters, retainers, billing and conflict checks".
- [ ] Verify in the returned draft: (1) fee-earner/time-line/hearing M2Os point at
      `x_attorney`, NOT `res.users`; (2) `x_matter.x_status` includes a terminal
      `closed`; (3) `x_matter_party` is NOT a workflow (no kanban view/action);
      (4) `x_document.x_name` is required; (5) warnings contain no unexplained
      "generation gap" for attorney/bill/compliance (or, if present, count decreased vs
      STATE.md's last run — record the count).
- [ ] Update `STATE.md` Last run/Next with the results (≤15 lines).

DONE MEANS: all five verifications recorded with actual values from the real response;
STATE.md updated.

DO NOT: change generation code to force a pass — if a verification fails, record the failure
and stop for review; do not tweak `ai_*` files in this card.

GATE: pytest subset green + the real draft JSON saved to `docs/research/lawfirm_run_<date>.json`
for the checker.

RETURN: ≤10 lines — pass/fail per verification + path to saved JSON.

DEVIATIONS: Ollama model unavailable → stop and ask; do not substitute a different model.
