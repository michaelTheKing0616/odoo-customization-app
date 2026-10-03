# BL04 — Report-only lint slots

## Python (apps/api)

- **Dev deps:** `ruff>=0.11`, `mypy>=1.15` in `[project.optional-dependencies] dev`.
- **Config:** `[tool.ruff]` (`target-version = "py312"`) and `[tool.mypy]` in `apps/api/pyproject.toml` — not enforced repo-wide.
- **Local command:** from repo root or `apps/api`:

  ```bash
  apps/api/scripts/lint_new_modules.sh
  ```

  Lints `app/request_id.py` and `app/logging_config.py` when present; **exit 0** if neither file exists.

- **CI:** `api-unit` job runs `uv run ruff check app/request_id.py` only when that file exists (`continue-on-error: true`). No whole-api mypy.

## Web TypeScript

- **Script:** `pnpm --filter @odoo-custom/web typecheck` → `tsc --noEmit`.
- **CI:** not required (pre-existing errors).
- **Baseline (2026-10-02):** `tsc --noEmit` reported **13** error lines (`error TS*`).
