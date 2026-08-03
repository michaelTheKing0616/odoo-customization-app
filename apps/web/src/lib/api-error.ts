"use client";

export function formatApiError(err: unknown, fallback = "Request failed"): string {
  return err instanceof Error ? err.message : fallback;
}

/** Set inline error state and optionally surface a toast with Expert diagnose action. */
export function reportApiError(
  err: unknown,
  setError?: (message: string | null) => void,
  options?: { fallback?: string; toast?: boolean },
): string {
  const message = formatApiError(err, options?.fallback);
  setError?.(message);
  if (options?.toast && typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("app:api-error", { detail: { message } }),
    );
  }
  return message;
}
