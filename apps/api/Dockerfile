# syntax=docker/dockerfile:1
# Build context: repository root (see docker/docker-compose.deploy.yml).

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/odoo-client/pyproject.toml packages/odoo-client/pyproject.toml
COPY packages/module-generator/pyproject.toml packages/module-generator/pyproject.toml
COPY packages/odoo-client packages/odoo-client
COPY packages/module-generator packages/module-generator
COPY apps/api apps/api

RUN uv sync --project apps/api --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl docker.io \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --create-home appuser

WORKDIR /workspace

COPY --from=builder /workspace/.venv /workspace/.venv
COPY --from=builder /workspace/apps/api /workspace/apps/api
COPY --from=builder /workspace/packages /workspace/packages
COPY docker/docker-compose.sandbox.yml docker/docker-compose.sandbox.yml
RUN mkdir -p docker/sandbox-addons \
    && chown -R appuser:appgroup /workspace

ENV PATH="/workspace/.venv/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace/apps/api

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
