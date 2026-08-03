"use client";

import { useEffect, useState } from "react";
import { api, ProtectedTier } from "@/lib/api";
import { ProtectedTierBadge } from "@/components/ProtectedTierBadge";

export function ModelTierInline({
  connectionId,
  model,
  className,
}: {
  connectionId: string;
  model: string;
  className?: string;
}) {
  const [tier, setTier] = useState<ProtectedTier | null>(null);

  useEffect(() => {
    const m = model.trim();
    if (!m || !connectionId) {
      setTier(null);
      return;
    }
    let cancelled = false;
    api.modelTier(connectionId, m).then((r) => {
      if (!cancelled) setTier(r.tier);
    }).catch(() => {
      if (!cancelled) setTier(null);
    });
    return () => {
      cancelled = true;
    };
  }, [connectionId, model]);

  return <ProtectedTierBadge tier={tier} className={className} />;
}
