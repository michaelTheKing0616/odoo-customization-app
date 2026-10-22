# Worktree state (B0-INV)

Checked 2026-10-22. Read-only `git status --porcelain -uall` and `git diff --shortstat`. Nothing was committed. This session started no processes and deleted nothing. `/tmp` files were left in place.

Snapshot: **849 modified, 1 deleted, 40399 untracked** (41249 paths). Tracked diff: **850 files changed, 48318 insertions, 14942 deletions** (the 849 edits plus the 1 deletion). Untracked paths are not in that diff.

Handover: §4 P0-9 AC1–AC4 (L508–L511) and known bugs (L261). Each group below has paths, one proposed commit message, and `commit: no`. Tope's yes is required before any commit.

## Do not commit

### Local package store
paths: `.pnpm-store/` (34981 untracked)
message: do not commit the local package store
commit: no

### Web build caches
paths: `apps/web/.next-uis26leap/`, `apps/web/.next-uis30leap/`, `apps/web/.next-uis30b/`, `apps/web/.next-uis35/`, `apps/web/.next-uis36/`, `apps/web/.next-uis37/`, `apps/web/.next-uis38/`, `apps/web/.next-uis41/`, `apps/web/.next-uis42/`, `apps/web/.next-uis50/`, `apps/web/.next-uis2951/`, `apps/web/.next-uiconnect/` (2383 untracked)
message: do not commit Next.js build caches
commit: no

### Tool caches
paths: `.cache/` (99 untracked)
message: do not commit local tool caches
commit: no

### Scratch database files
paths: `apps/api/.pt.sqlite`, `apps/api/.pt.sqlite-shm`, `apps/api/.pt.sqlite-wal`
message: do not commit local test database files
commit: no

### Sealed eval folder (not opened)
paths: `apps/api/evals/v2/holdout_fresh/` (27 untracked). Names only. Contents were not read.
message: do not commit; this folder stays sealed
commit: no

## Feature groups

### Build plan
paths: `docs/build-plan/` (884 untracked, including `cards/`, `tools/`, `FACTS.md`, `ledger.csv`, `budget.json`)
message: docs: add the phase build plan, cards, and ledger
commit: no

### Screen-check shots
paths: `docs/vision-verify/` (891 untracked)
message: docs: add screen-check shots for the operate screens
commit: no

### Specs, plans, brand, and notes
paths: `docs/specs/` (12 files, including `INGENIUM_MASTER_HANDOVER.md`, `SPEC.md`, `CONFIG_SUITE_SPEC.md`, `BRIDGE_RUNNER_SPEC.md`, `FEATURE_AUDIT.md`), `docs/plans/` (18), `docs/brand/` (logos and `README.md`), `docs/copy/GLOSSARY.md`, `docs/handoff/DOC-MAIL-NOTES.md`, `docs/handoff/DOC-QWEB-NOTES.md`, `docs/handoff/DOC-WEBSITE-NOTES.md`, `docs/design/references/`, `docs/DESIGN_TOUCHES.md`, `docs/FEATURE_AUDIT.md`, `docs/research/staged_run_fixed_unit_test.json` (modified)
message: docs: add product specs, phase notes, brand files, and handoff notes
commit: no

### This inventory
paths: `docs/handoff/WORKTREE_STATE.md`
message: docs: record the uncommitted worktree and a commit plan
commit: no

### Web app
paths: `apps/web/` source and config, not the `.next-*` caches (1050 paths). Largest folders: `src/app/connections` (61), `src/components/studio` (50), `src/components/view-designer` (40), `src/app/e2e` (39), `src/components/designer` (36), `src/components/ui` (35), `src/components/overview` (33), `src/lib/api` (27), `src/components/reports` (26), `src/components/suite` (26), `src/components/access` (23), `src/components/bulk` (21), `src/components/expert` (19), `src/components/odoo-preview` (19), `src/components/draft-studio` (17), `src/components/job-autopilot` (17), plus the other `src/components/*`, `src/lib/*`, `src/styles/`, `e2e/`, `public/`, `next.config.ts`, `package.json`, `tsconfig.json`, `vitest.config.ts`, `playwright.doc-qweb.config.ts`. Also modified: `apps/web/package-lock.json`, `pnpm-lock.yaml`.
message: feat: land the uncommitted web screens, routes, and checks
commit: no

### API app
paths: `apps/api/app/` (477 paths). Largest folders: `routers` (60), `ai_conversation` (24), `expert` (23), `job_autopilot` (19), `changeset` (17), `bridge` (15), `batch_os` (13), `code_runner` (13), `bulk_suite` (11), `ingest` (11), `config_packet` (8), `data` (8), `live_demo_copilot` (8), plus other packages and loose modules directly under `apps/api/app/`. Also `apps/api/alembic/` (8), `apps/api/pyproject.toml`, `apps/api/pytest.ini`, `apps/api/scripts`, `uv.lock`.
message: feat: land the uncommitted API modules and database revisions
commit: no

### API tests
paths: `apps/api/tests/` (235 paths, including `fixtures/` and `engine/`)
message: test: land the uncommitted API checks
commit: no

### Eval sets other than the sealed folder
paths: `apps/api/evals/` outside `holdout_fresh/` (97 paths). Includes `v2/dev` (40), `v2/dev2` (17), `v2/holdout` (16), `v2/unseen` (6), `v2/live` (2). `holdout_fresh` is the separate sealed group above.
message: test: land dev eval briefs and score notes, not the sealed folder
commit: no

### Shared packages
paths: `packages/odoo-client/` (17, `src/` and `tests/`), `packages/module-generator/` (8, `src/`, `tests/`, `templates/`)
message: feat: land the uncommitted Odoo client and module generator
commit: no

### Root apply scripts and patch files
paths: the 9 `APPLY_*.sh` and 13 `*.patch` files at the repo root (listed in the next section). Untracked among them: all 13 patches and `APPLY_INVENT_FAMILIES_ARC3_ON_MAC.sh`. The other 8 scripts are already tracked and clean.
message: chore: archive the root apply scripts and patch files
commit: no

### Repo session files
paths: `AGENTS.md`, `ERRORS.md`, `MEMORY.md`, `PROGRESS.md`, `STATE.md` (repo root, modified), `apps/PROGRESS.md` (untracked), `.env.example`, `.gitignore`, `.github/workflows/ci.yml`, `docker/docker-compose.ingenium-sandbox.yml`, `.cursor/rules/adaptive-agent.mdc` (modified), `.cursor/rules/00-token-economy.mdc`, `.cursor/rules/01-ingenium-invariants.mdc`, `scripts/plan_lint.py`, `scripts/icons/gen_ingenium_icons.py`
message: chore: land session rules, locks, and the sandbox compose file
commit: no

### Deleted research file
paths: `apps/docs/research/blk_probe_matrix_2026-08-03.json` (deleted in the worktree). Why it was removed was not investigated on this card.
message: chore: drop the old research probe matrix
commit: no

## Root APPLY scripts (9) and patch files (13)

Checked with `ls` at the repo root, `git ls-files`, and `git apply --check`. Every named file is on disk, so each mark is `in tree`. Every path named inside each patch also exists. `git apply --check` does not replay cleanly: eight patches stop because their apply script is already present; five stop on later edits (`ai_constraint_ast.py`, `ai_apply_readiness.py`, `ai_enrich.py`, `ai_brief_cues.py`). The patch header commit ids are not objects in this repository.

| file | mark |
|---|---|
| `APPLY_ANY_CUSTOMIZATION_P0_ON_MAC.sh` | in tree |
| `APPLY_ATLAS_ELITE_P4_ON_MAC.sh` | in tree |
| `APPLY_BUILD_SPINE_P2_ON_MAC.sh` | in tree |
| `APPLY_CONTINUOUS_INVENT_P3_ON_MAC.sh` | in tree |
| `APPLY_FX_RATE_JOB1_ON_MAC.sh` | in tree |
| `APPLY_HINT_CHROME_FLASH_TOGGLE_ON_MAC.sh` | in tree |
| `APPLY_INVENT_FAMILIES_ARC3_ON_MAC.sh` | in tree |
| `APPLY_MARKUP_WHT_JOB2_ON_MAC.sh` | in tree |
| `APPLY_REPORT_LAYOUT_SCRUB_JOB3_ON_MAC.sh` | in tree |
| `0001-feat-ingenium-any-customization-p0.patch` | in tree |
| `0001-feat-ingenium-atlas-elite-p4.patch` | in tree |
| `0001-feat-ingenium-build-spine-p2.patch` | in tree |
| `0001-feat-ingenium-continuous-invent-p3.patch` | in tree |
| `0001-feat-ingenium-first-try-generate-repair.patch` | in tree |
| `0001-feat-ingenium-fx-rate-job1.patch` | in tree |
| `0001-feat-ingenium-generate-spray-grammar.patch` | in tree |
| `0001-feat-ingenium-install-grammar-o2m-preview.patch` | in tree |
| `0001-feat-ingenium-invent-families-arc3.patch` | in tree |
| `0001-feat-ingenium-markup-wht-job2.patch` | in tree |
| `0001-feat-ingenium-prefer-host-fullapp-noun.patch` | in tree |
| `0001-feat-ingenium-report-layout-scrub-job3.patch` | in tree |
| `0001-feat-ingenium-state-title-identity-spray.patch` | in tree |

## Processes (left running)

This session started none. None were stopped.

| process | purpose | action |
|---|---|---|
| `ollama serve` pid 967, `127.0.0.1:11434` | local model server | leave running |
| `pnpm exec next dev --turbopack --port 3002` pid 23184 (next-server pid 23197) | web app dev server | leave running |
| `uvicorn app.main:app --host 127.0.0.1 --port 8001` pid 98117 / 98118, no `--reload` | API dev server | leave running |
| Docker `odoo-custom-odoo` (`odoo:19`) `:8069` | Odoo 19 sandbox | leave running |
| Docker `odoo-custom-odoo18` (`odoo:18`) `:8070` | Odoo 18 sandbox | leave running |
| Docker `odoo-custom-odoo17` (`odoo:17`) `:8071` | Odoo 17 sandbox | leave running |
| Docker `odoo20` (`odoo:20`) `:8073` | Odoo 20 sandbox | leave running |
| Docker `odoo-custom-app-db` (postgres:15) `:5433` | database for the 19 stack | leave running |
| Docker `odoo20-app-db` (postgres:15) `:5436` | database for the 20 stack | leave running |
| Docker `odoo-custom-db`, `odoo-custom-db17`, `odoo-custom-db18`, `odoo20-db` | internal databases, not published on a host port | leave running |

`:8002` and `:8012` were not listening.

## /tmp backups (left in /tmp)

Worth keeping. Proposed durable folder: `docs/handoff/tmp-backups/` (not created). Needs Tope's yes before any copy.

| now | what it is | proposed durable path |
|---|---|---|
| `/tmp/designer_classic.bak/page.tsx` (directory, 3860 bytes, 2026-10-19) | old classic designer page. Handover L261 and PROGRESS: `/designer/classic` now redirects to `/designer`. May not survive a reboot. | `docs/handoff/tmp-backups/designer_classic/page.tsx` |
| `/tmp/fp_app_design.bak` (145356 bytes) | Python backup matching `fp_*.bak` | `docs/handoff/tmp-backups/fp_app_design.bak` |
| `/tmp/fp_intent_contract.bak` (53424 bytes) | Python backup matching `fp_*.bak` | `docs/handoff/tmp-backups/fp_intent_contract.bak` |
| `/tmp/no_school_casual.gold.bak` (797 bytes) | backup of the dev brief gold. The live file is `apps/api/evals/v2/dev/no_school_casual.gold.yaml`. This bak was not opened. | `docs/handoff/tmp-backups/no_school_casual.gold.bak` |

Eval outputs still in `/tmp` (PROGRESS names many more that are already gone: 3 of 32 `/tmp/...` paths in PROGRESS still exist — `designer_classic.bak`, `/tmp/gap/suite_live.py`, `/tmp/pytest_b5e.log`). Proposed home for the dev outputs only: `docs/handoff/tmp-backups/eval-outputs/`. Do not copy holdout outputs into `apps/api/evals/v2/holdout_fresh/`. Those holdout files were not opened.

Still present, dev: `eval_dev_fresh.json`, `eval_dev_fresh.json.jsonl`, `eval_dev.log`, `ag2_agent_dev.json`, `ag2_pipe_dev.json`, `fp_base_dev.json.jsonl`, `/tmp/gap/suite_live.py`, `/tmp/pytest_b5e.log`, `/tmp/pytest_full.log`.

Still present, holdout (names only): `eval_holdout.log`, `eval_holdout2.log`, `eval_holdout_fresh.json`, `eval_holdout_fresh.json.jsonl`, `eval_holdout_fresh2.json`, `eval_holdout_fresh2.json.jsonl`.

## Known bugs (handover L261)

- Dark-mode paper contrast is fixed (G9). Keep the test.
- The margins overlay for the PDF proof is deferred. The PDF viewer's page offset is unknown (touch 131).
- `/designer/classic` now redirects to `/designer`. The backup is `/tmp/designer_classic.bak` on this Mac and may not survive a reboot.
