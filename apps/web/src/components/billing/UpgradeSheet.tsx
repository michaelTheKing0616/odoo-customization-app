"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Sheet } from "@/components/ui/Sheet";
import { api, type BillingPlanRow } from "@/lib/api";
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
  const [plans, setPlans] = useState<BillingPlanRow[]>([]);
  const [slotAddonUsd, setSlotAddonUsd] = useState<number | null>(null);
  const [slotQty, setSlotQty] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api
      .billingPlans()
      .then((catalog) => {
        setPlans(catalog.plans);
        const current = catalog.plans.find((p) => p.id === (entitlements?.plan_id ?? "free_solo"));
        setSlotAddonUsd(current?.extra_slot_monthly_usd ?? null);
      })
      .catch(() => setPlans([]));
  }, [open, entitlements?.plan_id]);

  const featureLabel = featureKey ? FEATURE_LABELS[featureKey] ?? featureKey : "this feature";
  const currentPlan = entitlements?.plan_id ?? "free_solo";
  const isSlotLimit = featureKey === "active_projects_limit";

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

  async function checkoutExtraSlots() {
    setBusy(true);
    setError(null);
    try {
      const origin = window.location.origin;
      const res = await api.stripeExtraSlotsCheckout({
        slot_quantity: slotQty,
        success_url: `${origin}/settings/billing?slots=1`,
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
            {entitlements.extra_project_slots > 0 ? ` · +${entitlements.extra_project_slots} purchased slots` : null}
          </Callout>
        ) : null}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        {isSlotLimit && slotAddonUsd != null ? (
          <div className="rounded-lg border border-border-subtle p-4" data-testid="extra-slots-panel">
            <p className="font-semibold text-ink">Add active-project slots</p>
            <p className="mt-1 text-sm text-muted">
              ${slotAddonUsd}/mo per slot on your current plan — no tier change required.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <label className="text-sm text-muted" htmlFor="slot-qty">
                Quantity
              </label>
              <input
                id="slot-qty"
                type="number"
                min={1}
                max={20}
                value={slotQty}
                onChange={(e) => setSlotQty(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                className="w-16 rounded border border-border-subtle px-2 py-1 text-sm"
              />
            </div>
            <Button className="mt-3" variant="primary" disabled={busy} onClick={checkoutExtraSlots}>
              {busy ? "Redirecting…" : `Add ${slotQty} slot${slotQty === 1 ? "" : "s"}`}
            </Button>
          </div>
        ) : null}

        {suggested && !isSlotLimit ? (
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

        {isSlotLimit && suggested && suggested.id !== currentPlan ? (
          <div className="rounded-lg border border-border-subtle p-4">
            <p className="font-semibold text-ink">Or upgrade tier</p>
            <p className="mt-1 text-sm text-muted">
              {suggested.display_name} includes more base slots and {featureLabel}.
            </p>
            <Button className="mt-3" variant="secondary" disabled={busy} onClick={() => checkout(suggested.id)}>
              Upgrade to {suggested.display_name}
            </Button>
          </div>
        ) : null}

        <div className="space-y-2 text-sm text-muted">
          <p>Need just one project built? See Project Pass on the pricing page.</p>
        </div>

        <Button variant="secondary" asChild>
          <Link href="/pricing">Compare all plans</Link>
        </Button>
      </div>
    </Sheet>
  );
}
