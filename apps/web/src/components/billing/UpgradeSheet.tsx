"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Sheet } from "@/components/ui/Sheet";
import { api } from "@/lib/api";
import { useEntitlements } from "@/lib/useEntitlements";

const FEATURE_LABELS: Record<string, string> = {
  bulk_suite: "Bulk suite",
  designer: "View designer",
  expert: "Odoo Expert",
  automations: "Automations",
  active_projects_limit: "Active project slots",
  connections_limit: "Odoo connections",
  module_export: "Module export",
  ai_draft: "Draft Studio (AI)",
};

type UpgradeSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  featureKey?: string;
};

export function UpgradeSheet({ open, onOpenChange, featureKey }: UpgradeSheetProps) {
  const { data: entitlements } = useEntitlements();
  const [plans, setPlans] = useState<Array<{ id: string; display_name: string; features: Record<string, string> }>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api
      .billingPlans()
      .then(setPlans)
      .catch(() => setPlans([]));
  }, [open]);

  const featureLabel = featureKey ? FEATURE_LABELS[featureKey] ?? featureKey : "this feature";
  const currentPlan = entitlements?.plan_id ?? "free_solo";

  async function checkout(planId: string) {
    setBusy(true);
    setError(null);
    try {
      const origin = window.location.origin;
      const res = await api.stripeCheckout({
        plan_id: planId,
        seat_quantity: 1,
        success_url: `${origin}/settings/billing?upgraded=1`,
        cancel_url: `${origin}/pricing`,
      });
      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed");
    } finally {
      setBusy(false);
    }
  }

  const suggested = plans.find((p) => {
    if (!featureKey) return p.id === "pro";
    const val = p.features[featureKey];
    return val === "true" || val === "unlimited";
  });

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title="Upgrade your plan"
      description={`Unlock ${featureLabel}. Operate tools (bulk, health checks, snapshots) stay available on every plan.`}
      testId="upgrade-sheet"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {entitlements ? (
          <Callout variant="info" title="Current plan">
            {entitlements.plan_id}
            {entitlements.active_project_limit != null
              ? ` · ${entitlements.active_projects}/${entitlements.active_project_limit} active projects`
              : null}
          </Callout>
        ) : null}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        {suggested ? (
          <div className="rounded-lg border border-border-subtle p-4">
            <p className="font-semibold text-ink">{suggested.display_name}</p>
            <p className="mt-1 text-sm text-muted">Includes {featureLabel} and related build features.</p>
            <Button
              className="mt-3"
              variant="primary"
              disabled={busy || suggested.id === currentPlan}
              onClick={() => checkout(suggested.id)}
            >
              {busy ? "Redirecting…" : `Upgrade to ${suggested.display_name}`}
            </Button>
          </div>
        ) : null}

        <div className="space-y-2 text-sm text-muted">
          <p>Need just one project built? Consider the Project Pass ($299 one-time).</p>
          <p>Add extra active-project slots on Pro ($15/mo) or Business ($10/mo) without changing tier.</p>
        </div>

        <Button variant="secondary" asChild>
          <Link href="/pricing">Compare all plans</Link>
        </Button>
      </div>
    </Sheet>
  );
}
