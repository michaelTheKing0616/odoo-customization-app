/**
 * Same-origin FastAPI proxy — works in dev (Turbopack), `next start`, and Docker
 * standalone where `next.config` rewrites may not apply.
 *
 * Long Autopilot / Expert jobs do not send HTTP headers until they finish.
 * Node's global `fetch` (undici) still applies a ~5 minute headersTimeout, which
 * surfaces as TypeError "fetch failed" — not our AbortController 504. Use
 * node:http so the wait matches resolveUpstreamTimeoutMs.
 */
import http from "node:http";
import https from "node:https";
import { Readable } from "node:stream";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
/** Seconds — App Router / `next start` kill switch. Dev is unbounded. */
export const maxDuration = 800;

const API_PROXY_TARGET = (process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8001").replace(
  /\/$/,
  "",
);

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
]);

const DEFAULT_UPSTREAM_TIMEOUT_MS = 12_000;
/** ir.model search_read of the full stock catalog routinely exceeds the 12s default. */
const ODOO_RPC_UPSTREAM_TIMEOUT_MS = Number.parseInt(
  process.env.ODOO_RPC_UPSTREAM_TIMEOUT_MS ?? "45000",
  10,
);
/** Allow ~2× Expert LLM budget (reasoning retry) + RPC/retrieval headroom — see EXPERT_LLM_TIMEOUT_S. */
const LONG_UPSTREAM_TIMEOUT_MS = Number.parseInt(
  process.env.EXPERT_UPSTREAM_TIMEOUT_MS ?? "660000",
  10,
);

/** Expert + draft review + ingest + AI jobs can exceed the default 12s dev proxy budget. */
function resolveUpstreamTimeoutMs(path: string): number {
  if (path.startsWith("expert/")) {
    return LONG_UPSTREAM_TIMEOUT_MS;
  }
  if (path.includes("/ingest/")) {
    return LONG_UPSTREAM_TIMEOUT_MS;
  }
  if (path.startsWith("jobs/") && path.endsWith("/artifact")) {
    return 120_000;
  }
  if (path.startsWith("jobs/")) {
    return 20_000;
  }
  if (path.startsWith("ai/")) {
    return LONG_UPSTREAM_TIMEOUT_MS;
  }
  if (path.includes("module-spec")) {
    return LONG_UPSTREAM_TIMEOUT_MS;
  }
  if (path.includes("job-autopilot")) {
    return LONG_UPSTREAM_TIMEOUT_MS;
  }
  if (
    path.includes("/modules/install-community") ||
    path.includes("option-a/reverify") ||
    path.endsWith("/reverify-authoring")
  ) {
    return 300_000;
  }
  if (
    /(?:^|\/)connections\/[^/]+\/reuse-catalog(?:\/|$)/.test(path) ||
    /(?:^|\/)connections\/[^/]+\/models(?:\/|$)/.test(path) ||
    /(?:^|\/)connections\/[^/]+\/modules(?:\/|$)/.test(path)
  ) {
    return ODOO_RPC_UPSTREAM_TIMEOUT_MS;
  }
  return DEFAULT_UPSTREAM_TIMEOUT_MS;
}

function isUpstreamTimeout(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const cause = err.cause instanceof Error ? err.cause : undefined;
  const blob = `${err.name} ${err.message} ${cause?.name ?? ""} ${cause?.message ?? ""}`;
  return (
    err.name === "AbortError" ||
    err.name === "TimeoutError" ||
    /timed out|timeout|UND_ERR_HEADERS_TIMEOUT|UND_ERR_BODY_TIMEOUT/i.test(blob)
  );
}

function upstreamErrorDetail(err: unknown): string {
  if (!(err instanceof Error)) return "Upstream API request failed";
  const cause = err.cause instanceof Error ? err.cause.message : "";
  return cause ? `${err.message} (${cause})` : err.message;
}

function proxyViaNodeHttp(opts: {
  target: URL;
  method: string;
  headers: Headers;
  body?: ArrayBuffer;
  timeoutMs: number;
}): Promise<Response> {
  const { target, method, headers, body, timeoutMs } = opts;
  const headerRecord: Record<string, string> = {};
  headers.forEach((value, key) => {
    headerRecord[key] = value;
  });
  headerRecord.host = target.host;
  headerRecord.connection = "close";
  if (body) {
    headerRecord["content-length"] = String(body.byteLength);
  }

  const requestFn = target.protocol === "https:" ? https.request : http.request;
  return new Promise((resolve, reject) => {
    const req = requestFn(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port || (target.protocol === "https:" ? 443 : 80),
        path: `${target.pathname}${target.search}`,
        method,
        headers: headerRecord,
      },
      (res) => {
        const responseHeaders = new Headers();
        for (const [key, value] of Object.entries(res.headers)) {
          if (value === undefined || HOP_BY_HOP.has(key.toLowerCase())) continue;
          if (Array.isArray(value)) {
            for (const item of value) responseHeaders.append(key, item);
          } else {
            responseHeaders.set(key, value);
          }
        }
        resolve(
          new Response(Readable.toWeb(res) as ReadableStream, {
            status: res.statusCode ?? 502,
            statusText: res.statusMessage,
            headers: responseHeaders,
          }),
        );
      },
    );
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`Upstream API timed out after ${timeoutMs / 1000}s`));
    });
    req.on("error", reject);
    if (body) req.write(Buffer.from(body));
    req.end();
  });
}

function isTransientUpstream(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const cause = err.cause instanceof Error ? err.cause : undefined;
  const blob = `${err.name} ${err.message} ${cause?.name ?? ""} ${cause?.message ?? ""}`;
  return /econnreset|econnrefused|socket hang up|epipe|empty response/i.test(blob);
}

async function proxyRequest(
  request: NextRequest,
  pathSegments: string[],
  retried = false,
): Promise<NextResponse> {
  const path = pathSegments.join("/");
  const target = new URL(`/api/${path}`, API_PROXY_TARGET);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const method = request.method;
  const hasBody = method !== "GET" && method !== "HEAD";
  let body: ArrayBuffer | undefined;
  if (hasBody) {
    body = await request.arrayBuffer();
  }

  const timeoutMs = resolveUpstreamTimeoutMs(path);

  let upstream: Response;
  try {
    upstream = await proxyViaNodeHttp({
      target,
      method,
      headers,
      body: hasBody ? body : undefined,
      timeoutMs,
    });
  } catch (err) {
    const timedOut = isUpstreamTimeout(err);
    const retryJobs =
      !retried &&
      request.method === "GET" &&
      path.startsWith("jobs/") &&
      isTransientUpstream(err);
    if (retryJobs) {
      await new Promise((resolve) => setTimeout(resolve, 400));
      return proxyRequest(request, pathSegments, true);
    }
    return NextResponse.json(
      {
        detail: timedOut
          ? `Timed out reaching API at ${API_PROXY_TARGET} (${timeoutMs / 1000}s). Start uvicorn on port 8001.`
          : `Cannot reach API at ${API_PROXY_TARGET}: ${upstreamErrorDetail(err)}`,
      },
      { status: timedOut ? 504 : 502 },
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      responseHeaders.set(key, value);
    }
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

type RouteCtx = { params: Promise<{ path: string[] }> };

async function handler(request: NextRequest, ctx: RouteCtx): Promise<NextResponse> {
  const { path } = await ctx.params;
  return proxyRequest(request, path ?? []);
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const HEAD = handler;
export const OPTIONS = handler;
