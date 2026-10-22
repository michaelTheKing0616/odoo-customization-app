"use client";

import { useCallback, useEffect, useState } from "react";
import { api, EntitlementsOut } from "@/lib/api";

export function useEntitlements() {
  const [data, setData] = useState<EntitlementsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signedOut, setSignedOut] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSignedOut(false);
    try {
      setData(await api.billingEntitlements());
    } catch (err) {
      setData(null);
      const message = err instanceof Error ? err.message : "Failed to load entitlements";
      const status = (err as { status?: number } | null)?.status;
      setSignedOut(
        status === 401 || status === 403 || (status === 400 && /workspace/i.test(message)),
      );
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function hasFeature(key: string): boolean {
    if (!data) return true;
    const val = data.features[key];
    return val === "true" || val === "unlimited";
  }

  return { data, error, signedOut, loading, refresh, hasFeature };
}
