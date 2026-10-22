"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { BillingDesk, type BillingActionError, type BillingView } from "@/components/billing/BillingDesk";
import { UpgradeSheet } from "@/components/billing/UpgradeSheet";
import { Skeleton } from "@/components/ui/layout-primitives";
import { api, type BillingPlansCatalog } from "@/lib/api";
import type { LostFeature } from "@/lib/billingScreen";
import { useEntitlements } from "@/lib/useEntitlements";
import "@/components/billing/billing-desk.css";

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

function BillingContent() {
  const params = useSearchParams();
  const { data, refresh, loading, error: planError, signedOut } = useEntitlements();
  const [catalog, setCatalog] = useState<BillingPlansCatalog | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [lostFeatures, setLostFeatures] = useState<LostFeature[]>([]);
  const [actionError, setActionError] = useState<BillingActionError | null>(null);
  const [portalBusy, setPortalBusy] = useState<"plan" | "billing" | null>(null);
  const [checkoutBusy, setCheckoutBusy] = useState<string | null>(null);
  const [slotSheetOpen, setSlotSheetOpen] = useState(false);

  // List prices are public; a failure leaves money as "Unavailable" rather than guessed.
  useEffect(() => {
    let live = true;
    Promise.resolve()
      .then(() => api.billingPlans())
      .then((c) => live && setCatalog(c ?? null))
      .catch(() => live && setCatalog(null))
      .finally(() => live && setCatalogLoading(false));
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    const planId = data?.plan_id;
    if (!planId || planId === "free_solo" || planId === "internal") {
      setLostFeatures([]);
      return;
    }
    let live = true;
    Promise.resolve()
      .then(() => api.billingPlanDiff(planId, "free_solo"))
      .then((r) => live && setLostFeatures(r?.lost_features ?? []))
      .catch(() => live && setLostFeatures([]));
    return () => {
      live = false;
    };
  }, [data?.plan_id]);

  const upgraded = Boolean(params.get("upgraded"));
  const slots = Boolean(params.get("slots"));
  useEffect(() => {
    if (upgraded || slots) void refresh();
  }, [upgraded, slots, refresh]);

  const openPortal = useCallback(async (source: "plan" | "billing") => {
    setPortalBusy(source);
    setActionError(null);
    try {
      const res = await api.stripePortal();
      window.location.href = res.portal_url;
    } catch (err) {
      setActionError({ context: "portal", source, message: errorMessage(err, "Portal unavailable") });
    } finally {
      setPortalBusy(null);
    }
  }, []);

  const checkout = useCallback(async (planId: string) => {
    setCheckoutBusy(planId);
    setActionError(null);
    try {
      const origin = window.location.origin;
      const res = await api.stripeCheckout({
        plan_id: planId,
        seat_quantity: 1,
        success_url: `${origin}/settings/billing?upgraded=1`,
        cancel_url: `${origin}/settings/billing`,
      });
      if (res.checkout_url) window.location.href = res.checkout_url;
    } catch (err) {
      setActionError({ context: "checkout", source: "plan", message: errorMessage(err, "Checkout failed") });
    } finally {
      setCheckoutBusy(null);
    }
  }, []);

  const view: BillingView = loading ? "loading" : data ? "ready" : planError && !signedOut ? "error" : "empty";

  return (
    <>
      <BillingDesk
        view={view}
        data={data}
        catalog={catalog}
        catalogLoading={catalogLoading}
        lostFeatures={lostFeatures}
        loadError={planError}
        returned={{ upgraded, slots }}
        actionError={actionError}
        portalBusy={portalBusy}
        checkoutBusy={checkoutBusy}
        onManagePlan={() => void openPortal("plan")}
        onManageBilling={() => void openPortal("billing")}
        onCheckout={(id) => void checkout(id)}
        onAddSlot={() => setSlotSheetOpen(true)}
        onRetry={() => void refresh()}
        onRefresh={() => void refresh()}
        onDismissError={() => setActionError(null)}
      />
      <UpgradeSheet open={slotSheetOpen} onOpenChange={setSlotSheetOpen} featureKey="active_projects_limit" />
    </>
  );
}

export default function BillingSettingsPage() {
  return (
    <Suspense
      fallback={
        <div className="billing-desk" role="status" data-testid="billing-page-loading">
          <span className="sr-only">Loading billing.</span>
          <div className="bd-skel-stack" aria-hidden>
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      }
    >
      <BillingContent />
    </Suspense>
  );
}
