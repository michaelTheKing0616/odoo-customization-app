# syntax=docker/dockerfile:1
# Build context: repository root (see docker/docker-compose.deploy.yml).

FROM node:20-bookworm-slim AS deps

WORKDIR /workspace

RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json

RUN pnpm install --frozen-lockfile --filter @odoo-custom/web

FROM node:20-bookworm-slim AS builder

WORKDIR /workspace

RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

COPY --from=deps /workspace/node_modules ./node_modules
COPY --from=deps /workspace/apps/web/node_modules ./apps/web/node_modules
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web ./apps/web

ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN pnpm --filter @odoo-custom/web build

FROM node:20-bookworm-slim AS runner

WORKDIR /workspace

RUN groupadd --gid 10001 webgroup \
    && useradd --uid 10001 --gid webgroup --create-home webuser

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

COPY --from=builder --chown=webuser:webgroup /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=webuser:webgroup /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=webuser:webgroup /workspace/apps/web/public ./apps/web/public

USER webuser

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
