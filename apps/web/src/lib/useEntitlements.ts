"use client";

import { useCallback, useEffect, useState } from "react";
import { api, EntitlementsOut } from "@/lib/api";

export function useEntitlements() {
  const [data, setData] = useState<EntitlementsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.billingEntitlements());
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Failed to load entitlements");
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

  return { data, error, loading, refresh, hasFeature };
}
