const DEFAULT_API_ORIGIN = "http://127.0.0.1:8001";

/** Absolute API origin (SSR, downloads, explicit NEXT_PUBLIC_API_URL). */
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_ORIGIN).replace(
  /\/$/,
  "",
);

function isLoopbackOrigin(origin: string): boolean {
  try {
    const { hostname } = new URL(origin);
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
  } catch {
    return false;
  }
}

/**
 * Base URL for browser fetch calls. Loopback API URLs route through same-origin `/api/*`
 * so Next.js rewrites proxy to FastAPI (avoids CORS and extension fetch interception).
 * Remote/production NEXT_PUBLIC_API_URL still calls the API directly.
 */
export function getApiBase(): string {
  if (typeof window !== "undefined") {
    if (!process.env.NEXT_PUBLIC_API_URL || isLoopbackOrigin(API_BASE)) {
      return "";
    }
    return API_BASE;
  }
  return API_BASE;
}

export type ConfirmationRequiredDetail = {
  requires_confirmation: true;
  warning: string;
  risks: string[];
  confirm_phrase: string;
};

export class ConfirmationRequiredError extends Error {
  readonly requires_confirmation = true as const;
  readonly warning: string;
  readonly risks: string[];
  readonly confirm_phrase: string;
  readonly status: number;

  constructor(
    detail: {
      warning?: string;
      risks?: string[];
      confirm_phrase?: string;
      message?: string;
    },
    status = 403,
  ) {
    const warning =
      detail.warning ||
      detail.message ||
      "This action requires explicit confirmation.";
    super(warning);
    this.name = "ConfirmationRequiredError";
    this.warning = warning;
    this.risks = Array.isArray(detail.risks) ? detail.risks.map(String) : [];
    this.confirm_phrase = detail.confirm_phrase || "I understand the risks";
    this.status = status;
  }
}

function isConfirmationDetail(detail: unknown): detail is ConfirmationRequiredDetail {
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail as { requires_confirmation?: unknown }).requires_confirmation === true
  );
}

export class ClarificationRequiredError extends Error {
  readonly clarification: import("@/lib/studio-session").StudioClarification | null;
  readonly status = 409;

  constructor(detail: {
    message?: string;
    clarification?: import("@/lib/studio-session").StudioClarification | null;
  }) {
    super(detail.message ?? "Clarification required before generation");
    this.name = "ClarificationRequiredError";
    this.clarification = detail.clarification ?? null;
  }
}

function isClarificationRequiredDetail(
  detail: unknown,
): detail is {
  message?: string;
  clarification?: import("@/lib/studio-session").StudioClarification | null;
} {
  return (
    typeof detail === "object" &&
    detail !== null &&
    "clarification" in detail
  );
}

export class FeatureGatedError extends Error {
  featureKey: string;
  planId?: string;

  constructor(detail: { message?: string; feature_key?: string; plan_id?: string }) {
    super(detail.message ?? "Feature not available on your plan");
    this.name = "FeatureGatedError";
    this.featureKey = detail.feature_key ?? "";
    this.planId = detail.plan_id;
  }
}

export function formatDetailMessage(detail: unknown): string {
  if (typeof detail === "string") {
    const trimmed = detail.trim();
    // Bare FastAPI/proxy statusText — never useful as an App Studio banner body.
    if (/^internal server error$/i.test(trimmed)) {
      return (
        "The API returned an unexpected error. Confirm uvicorn is running on :8001 " +
        "without a stale process, hard-refresh App Studio, then try again. " +
        "If this is custom-code authoring, check Gemini quota or set AI_ASSIST=ollama."
      );
    }
    return trimmed;
  }
  if (detail == null) return "";
  if (typeof detail === "object") {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.message === "string") return obj.message;
    if (typeof obj.warning === "string") return obj.warning;
    if (typeof obj.detail === "string") return obj.detail;
    if (Array.isArray(obj.findings) && obj.findings.length) {
      return obj.findings.map(String).join("; ");
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }
  return String(detail);
}

const API_KEY_STORAGE = "odoo_custom_api_key";

export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(API_KEY_STORAGE);
}

export function setStoredApiKey(key: string | null) {
  if (typeof window === "undefined") return;
  if (!key) {
    window.localStorage.removeItem(API_KEY_STORAGE);
    return;
  }
  window.localStorage.setItem(API_KEY_STORAGE, key);
}

export const CONNECTION_READ_TIMEOUT_MS = 45_000;
export const ODOO_RPC_READ_TIMEOUT_MS = 45_000;

type ApiRequestInit = RequestInit & { timeoutMs?: number };

function isFetchUnreachableError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  if (err.name === "AbortError" || err.name === "TimeoutError") return true;
  if (err instanceof TypeError) return true;
  return /failed to fetch|networkerror|network request failed|load failed|aborted|timed out|timeout/i.test(
    err.message,
  );
}

export async function fetchApi(path: string, init?: ApiRequestInit): Promise<Response> {
  const base = getApiBase();
  const url = `${base}${path}`;
  const storedKey = getStoredApiKey();
  const headers: Record<string, string> = {
    ...(storedKey ? { Authorization: `Bearer ${storedKey}` } : {}),
  };
  const { timeoutMs, ...fetchInit } = init ?? {};
  if (fetchInit.body && !(fetchInit.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  let controller: AbortController | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let onExternalAbort: (() => void) | undefined;

  if (timeoutMs != null && timeoutMs > 0) {
    controller = new AbortController();
    timeout = setTimeout(() => {
      controller?.abort(new DOMException("Request timed out", "TimeoutError"));
    }, timeoutMs);
    onExternalAbort = () => controller?.abort();
    fetchInit.signal?.addEventListener("abort", onExternalAbort);
  }

  try {
    return await fetch(url, {
      credentials: "include",
      ...fetchInit,
      ...(controller ? { signal: controller.signal } : {}),
      headers: {
        ...headers,
        ...(fetchInit.headers ?? {}),
      },
    });
  } catch (err) {
    const isAbort =
      err instanceof Error &&
      (err.name === "AbortError" ||
        err.name === "TimeoutError" ||
        /aborted|timed out|timeout/i.test(err.message));
    if (isFetchUnreachableError(err)) {
      const target =
        base || (typeof window !== "undefined" ? window.location.origin : DEFAULT_API_ORIGIN);
      throw new Error(
        isAbort
          ? `Timed out reaching the API${base ? ` at ${target}` : ""}. ` +
              `Start the API (uvicorn on port 8001, or deploy API on 8000) and restart the web dev server ` +
              `(Next /api proxy → API_PROXY_TARGET, default http://127.0.0.1:8001).`
          : `Cannot reach the API${base ? ` at ${target}` : ""}. ` +
              `Start the API (uvicorn on port 8001, or deploy API on 8000) and restart the web dev server ` +
              `(Next /api proxy → API_PROXY_TARGET, default http://127.0.0.1:8001). ` +
              `If a browser extension wraps fetch, try incognito or disable it.`,
      );
    }
    throw err;
  } finally {
    if (timeout) clearTimeout(timeout);
    if (onExternalAbort) fetchInit.signal?.removeEventListener("abort", onExternalAbort);
  }
}

export async function request<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const res = await fetchApi(path, init);
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail !== undefined ? body.detail : body;
    } catch {
      /* ignore */
    }
    if (isConfirmationDetail(detail)) {
      throw new ConfirmationRequiredError(detail, res.status);
    }
    if (res.status === 409 && isClarificationRequiredDetail(detail)) {
      throw new ClarificationRequiredError(detail);
    }
    if (
      typeof detail === "object" &&
      detail !== null &&
      (detail as { error?: string }).error === "feature_gated"
    ) {
      throw new FeatureGatedError(detail as { message?: string; feature_key?: string; plan_id?: string });
    }
    throw Object.assign(
      new Error(
        res.status === 404
          ? `${formatDetailMessage(detail) || "Not Found"} (${(init?.method || "GET").toUpperCase()} ${path})`
          : formatDetailMessage(detail) || `Request failed (${res.status})`,
      ),
      { status: res.status, detail },
    );
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export async function requestForm<T>(path: string, form: FormData, timeoutMs?: number): Promise<T> {
  const res = await fetchApi(path, {
    method: "POST",
    body: form,
    timeoutMs,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    if (isConfirmationDetail(detail)) {
      throw new ConfirmationRequiredError(
        detail as ConfirmationRequiredDetail,
        res.status,
      );
    }
    throw new Error(formatDetailMessage(detail) || `HTTP ${res.status}`);
  }
  return data as T;
}
