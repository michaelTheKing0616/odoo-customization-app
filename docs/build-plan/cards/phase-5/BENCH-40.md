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
