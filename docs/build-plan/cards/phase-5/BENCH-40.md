# BENCH-40 — Bots tier/refusal bench

Source: derived from `~/.ingenium_nf/agent_runs/debate/RESOLUTION.md` item 3 (no prior card file).
Code: `apps/api/evals/bots/` (`bench40.py`, `make_bench40.py`, `dev.json`, sealed `holdout.json`,
`seal_manifest.json`, `candidates.jsonl`); tests `apps/api/tests/test_nf_bench40.py`.

- 40 industry-neutral tasks; 10 (25%) are tier-boundary: not-built-yet (T3, marked
  `until_capability: 3` so the expectation flips to ok when the registry flips), approval-required
  (uninstall), needs-step, needs-edition, not-in-version (incl. Odoo 19 version delta), unknown.
- Split at creation by sha256(task id) (24 dev / 16 holdout). Holdout is sealed like INV-16:
  `load("holdout")` needs `EVAL_UNSEAL=yes` and a matching `seal_manifest.json` sha256.
- Loop-fed tasks: `append_candidate` (append-only queue) -> `promote(id, reviewer=, expect=)`
  into the split their id hashes to; holdout promotion also needs `EVAL_UNSEAL=yes` and reseals.
- Offline on versioncaps data (17, 20; 19 for delta tasks). Live runner: stub, skipped
  without `ODOO_LIVE=1`.
- Reuses the evals/v2 sealing convention (`EVAL_UNSEAL`); the v2 brief harness is HTTP App Studio
  scoring and does not fit tier grading, so this is a small grader, not a second harness.

## Review fixes (after c2649849)
- `installed` per version = owner apps closed over real `depends` + `auto_install` (country-bound
  l10n excluded) from `evals/bots/module_deps.json`, dumped from the odoo:17..20 images' manifests.
- Expectations re-derived from real Odoo; holdout rebuilt once with `EVAL_UNSEAL=yes` and recorded
  in `seal_manifest.json` history. Default versions 17, 18, 19, 20.
- 12 boundary tasks (30%): 2 per refusal grade, one in dev and one in holdout.
- `seal(reviewer)` needs `EVAL_UNSEAL=yes` and a reviewer and appends {old, new, reviewer, at}.
  `promote` copies only whitelisted keys, and `until_capability` comes only from the reviewer.
  Candidate ids must match `^b40-[0-9a-z-]+$`, duplicates are rejected and promotion needs one
  unique match. Multi-part tasks carry fields/module_hint per part.
