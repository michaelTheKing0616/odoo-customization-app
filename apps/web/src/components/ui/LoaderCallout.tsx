"use client";

import { useCallback, useEffect, useState } from "react";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { formatFetchError } from "@/lib/format-fetch-error";

type LoaderProps<T> = {
  load: () => Promise<T>;
  children: (data: T) => React.ReactNode;
  className?: string;
  testId?: string;
};

/** Fetch wrapper with COPY_GUIDE error callout + retry. */
export function LoaderCallout<T>({ load, children, className, testId }: LoaderProps<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await load();
      setData(result);
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Request failed";
      setError(formatFetchError(raw));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    void run();
  }, [run, nonce]);

  return (
    <div className={className} data-testid={testId}>
      {loading ? <p className="text-xs text-muted">Loading…</p> : null}
      {error ? (
        <ErrorNotice
          message={error}
          showDiagnose={false}
          onRetry={() => setNonce((n) => n + 1)}
          className="mt-2"
        />
      ) : null}
      {!loading && !error && data !== null ? children(data) : null}
    </div>
  );
}
