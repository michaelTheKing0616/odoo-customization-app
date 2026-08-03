"use client";

import { StatusPill } from "@/components/ui/StatusPill";
import { useEntitlements } from "@/lib/useEntitlements";

export function WorkspacePlanBadge() {
  const { data } = useEntitlements();
  if (!data) return null;
  if (data.plan_id === "internal") {
    return <StatusPill kind="experimental" />;
  }
  if (data.subscription_status === "trialing") {
    return (
      <span className="rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-xs text-accent">
        Trial · {data.plan_id}
      </span>
    );
  }
  return (
    <span className="rounded-full border border-border-subtle px-2 py-0.5 text-xs text-muted">
      {data.plan_id}
    </span>
  );
}
