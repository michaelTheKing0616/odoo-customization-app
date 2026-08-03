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
- [x] Run the API test suite subset first:
      `cd apps/api && uv run pytest tests/test_ai_law_firm_pack.py tests/test_ai_model_quality.py -q` — all pass.
- [x] Start (or restart) the API with AI enabled; confirm `GET /api/ai/status` shows the
      provider up and `law_firm` pack registered.
- [x] POST `/api/ai/draft-module` with prompt: "Build a world-class law firm practice
      management app with matters, retainers, billing and conflict checks".
- [x] Verify in the returned draft: (1) fee-earner/time-line/hearing M2Os point at
      `x_attorney`, NOT `res.users`; (2) `x_matter.x_status` includes a terminal
      `closed`; (3) `x_matter_party` is NOT a workflow (no kanban view/action);
      (4) `x_document.x_name` is required; (5) warnings contain no unexplained
      "generation gap" for attorney/bill/compliance (or, if present, count decreased vs
      STATE.md's last run — record the count).
      **Results:** (1) PASS — `x_matter_line.x_attorney_id→x_attorney`, `x_event.x_attorney_id→x_attorney`.
      (2) PASS — selection includes `closed`. (3) **FAIL** (fixed in SAFE-2b) — was
      `is_workflow=true` + kanban; replay after fix: `is_workflow=false`, views list+form only.
      (4) PASS — `x_document.x_name` required.
      (5) PASS on first run — 0 generation-gap warnings; live re-run (SAFE-2 follow-up)
      count **2** (x_bill, x_compliance only — attorney gap absent). Recorded in
      `docs/research/lawfirm_run_2026-08-02_live_rerun.json`.
- [x] Update `STATE.md` Last run/Next with the results (≤15 lines).

DONE MEANS: all five verifications recorded with actual values from the real response;
STATE.md updated.

DO NOT: change generation code to force a pass — if a verification fails, record the failure
and stop for review; do not tweak `ai_*` files in this card.

GATE: pytest subset green + the real draft JSON saved to `docs/research/lawfirm_run_<date>.json`
for the checker.

RETURN: ≤10 lines — pass/fail per verification + path to saved JSON.

DEVIATIONS: Ollama model unavailable → stop and ask; do not substitute a different model.

---

## SAFE-2b — Fix x_matter_party workflow/kanban re-promotion (SAFE-2 follow-up)

TASK: Stop post-critique re-enrich from re-promoting `x_matter_party` to `is_workflow` and
adding kanban views/actions after quality demote.

INPUT: `apps/api/app/ai_model_quality.py`, `ai_rules.py`, `ai_enrich.py`, `ai_ollama.py`;
`docs/research/lawfirm_run_2026-08-02.json`; `tests/test_ai_law_firm_pack.py`.

CHECKLIST:
- [x] Add shared `is_party_link_model()` and use in demote + ensure_min_workflows.
- [x] `apply_pattern_rules`: do not set `is_workflow` on party-link models with `x_status`.
- [x] `ensure_default_ui`: skip kanban views and kanban view_mode for party-link models.
- [x] `draft_module_from_prompt`: final `repair_draft_integrity` after post-critique re-enrich.
- [x] Regression test: enrich + validate after demote keeps `x_matter_party` non-workflow, no kanban.
- [x] Re-run SAFE-2 verification script on saved JSON through full repair+enrich path — (3) PASS.

DONE MEANS: verification 3 passes on deterministic replay; regression test green.

DO NOT: change law-firm pack field names; weaken real workflow models.

GATE: `cd apps/api && uv run pytest tests/test_ai_law_firm_pack.py tests/test_ai_model_quality.py -q`

RETURN: ≤10 lines — root cause + files touched + replay verification result.

---

## SAFE-2c — Fix law-firm generation-gap regression (bill/compliance/deposit)

TASK: Eliminate `generation gap: pack supplied core model x_*` warnings on law-firm live
drafts when attorney/bill/compliance/deposit are LLM-omitted — SAFE-2 verification (5) must
pass with count **0** on live re-run.

INPUT: `apps/api/app/ai_model_quality.py`, `ai_ollama.py`, `ai_domain_packs.py`;
`docs/research/lawfirm_run_2026-08-02_live_rerun.json`; `tests/test_ai_law_firm_pack.py`.

CHECKLIST:
- [x] Root cause documented: generation gap fires only when `merge_domain_pack` adds a core
      model the LLM omitted; `llm_emit_missing_scaffold_models` is best-effort only.
- [x] Add `seed_missing_core_scaffold_models()` — deterministic pre-merge copy from scaffold
      for core masters (attorney/staff/bill/invoice/compliance/deposit/trust) still missing
      after LLM scaffold-gap repair.
- [x] Wire in `draft_module_from_prompt` between `llm_emit_missing_scaffold_models` and
      `merge_domain_pack`.
- [x] Regression test: draft missing x_bill/x_compliance → seed+merge → zero generation-gap
      warnings for attorney/bill/compliance/deposit.
- [x] Live re-run law-firm prompt; save `docs/research/lawfirm_run_<date>_verified.json`;
      verification (5) count **0** for attorney/bill/compliance/deposit gaps.
- [x] All five SAFE-2 verifications PASS on live verified artifact.

DONE MEANS: live draft has zero core generation-gap warnings; Wave 0 regression closure complete.

DO NOT: Remove generation-gap warnings for thin intentional test fixtures; do not weaken pack merge.

GATE: `cd apps/api && uv run pytest tests/test_ai_law_firm_pack.py -q` + live draft verification (5)=0.

RETURN: ≤10 lines — gap count before/after + path to verified JSON.
