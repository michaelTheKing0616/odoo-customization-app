/**
 * Same-origin FastAPI proxy — works in dev (Turbopack), `next start`, and Docker
 * standalone where `next.config` rewrites may not apply.
 */
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

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

async function proxyRequest(
  request: NextRequest,
  pathSegments: string[],
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

  const upstreamTimeoutMs = 12_000;
  const controller = new AbortController();
  const timeout = setTimeout(() => {
    controller.abort(new DOMException("Upstream API timed out", "TimeoutError"));
  }, upstreamTimeoutMs);

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: hasBody ? body : undefined,
      redirect: "manual",
      signal: controller.signal,
    });
  } catch (err) {
    const timedOut =
      controller.signal.aborted ||
      (err instanceof Error &&
        (err.name === "AbortError" ||
          err.name === "TimeoutError" ||
          /timed out|timeout/i.test(err.message)));
    const detail =
      err instanceof Error ? err.message : "Upstream API request failed";
    return NextResponse.json(
      {
        detail: timedOut
          ? `Timed out reaching API at ${API_PROXY_TARGET} (${upstreamTimeoutMs / 1000}s). Start uvicorn on port 8001.`
          : `Cannot reach API at ${API_PROXY_TARGET}: ${detail}`,
      },
      { status: timedOut ? 504 : 502 },
    );
  } finally {
    clearTimeout(timeout);
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
