# TRUST-6 — mutation coverage floor + settings-matrix execution

Use when shipping trust/safety work or adding settings-gated code paths.

## Coverage gate

- Mutation-relevant modules listed in `apps/api/mutation_coverage_floors.json`.
- CI job `trust-mutation-coverage` runs `tests/mutation_coverage_tests.txt` then
  `scripts/check_mutation_coverage.py`.
- **HIGH floor (85%)** — safety gate, mutation lock, RPC resilience, bulk executor/transitions.
- **MEDIUM floor (50% today, target 70%)** — spec apply, snapshots, bulk submodules, PCM, AI pipeline, power ops recipes.
- A module below its floor **fails CI**. Do not lower floors without a card note + follow-up issue.

## Settings-matrix rule

> A config-gated code path counts as tested **only if** a test executes it under that config.

Required matrix dimensions (extend `tests/test_trust6_settings_matrix.py` when adding gates):

| Setting | Values to execute |
| --- | --- |
| `AUTH_MODE` | off, api_key |
| `write_mode` | observer, standard, production (RPC block matrix) |
| `AI_PIPELINE_MODE` | staged (via `run_staged_pipeline`) |
| `AI_THINKING` | off, on, auto |
| `AI_SELF_CONSISTENCY` | off, on |
| schema-in-format | probe true/false via `llm_routing_status` |

Use `monkeypatch.setattr(settings, ...)` — never assume env defaults prove a branch ran.

## Error-path rule

Each mutating service needs ≥1 unit test where RPC/validation throws mid-operation and the
resulting state/report is asserted. Extend `tests/test_trust6_error_paths.py` (pairs with TRUST-5 chaos).

## Before marking TRUST-6 done

1. `uv run pytest tests/test_trust6*.py -q`
2. `uv run pytest $(cat tests/mutation_coverage_tests.txt) --cov=app --cov-report=json:.mutation_coverage.json -q`
3. `uv run python scripts/check_mutation_coverage.py .mutation_coverage.json`
