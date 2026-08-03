"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { StatusPill } from "@/components/ui/StatusPill";
import { api } from "@/lib/api";
import { useEntitlements } from "@/lib/useEntitlements";
import { useUpgrade } from "@/lib/upgrade-context";

function daysUntil(iso: string | null): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / (86400000));
}

function BillingContent() {
  const params = useSearchParams();
  const { data, refresh, loading } = useEntitlements();
  const { openUpgrade } = useUpgrade();
  const [error, setError] = useState<string | null>(null);
  const [portalBusy, setPortalBusy] = useState(false);
  const [lostFeatures, setLostFeatures] = useState<Array<{ feature_key: string; from: string; to: string }>>([]);

  const trialDays = daysUntil(data?.trial_ends_at ?? null);
  const showTrialBanner = trialDays != null && trialDays <= 3 && trialDays >= 0;

  useEffect(() => {
    if (data?.plan_id && data.plan_id !== "free_solo") {
      api.billingPlanDiff(data.plan_id, "free_solo").then((r) => setLostFeatures(r.lost_features)).catch(() => setLostFeatures([]));
    }
  }, [data?.plan_id]);

  async function openPortal() {
    setPortalBusy(true);
    setError(null);
    try {
      const res = await api.stripePortal();
      window.location.href = res.portal_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Portal unavailable");
    } finally {
      setPortalBusy(false);
    }
  }

  async function checkout(planId: string) {
    setError(null);
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
      setError(err instanceof Error ? err.message : "Checkout failed");
    }
  }

  useEffect(() => {
    if (params.get("upgraded")) refresh();
  }, [params, refresh]);

  return (
    <div className="space-y-6 p-6">
      <PageHeader title="Billing" description="Plan, seats, and invoices via Stripe customer portal." />

      {params.get("upgraded") ? (
        <Callout variant="info" title="Thanks — your plan update may take a moment to sync." />
      ) : null}

      {showTrialBanner ? (
        <Callout variant="warning" title={`Trial ends in ${trialDays} day${trialDays === 1 ? "" : "s"}`}>
          Add a payment method before trial ends to keep Business features.
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} /> : null}

      <Card className="space-y-3 p-5">
        {loading ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : data ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-lg font-semibold text-ink">{data.plan_id}</span>
              {data.plan_id === "internal" ? <StatusPill kind="experimental" /> : null}
              <span className="text-sm text-muted">({data.subscription_status})</span>
            </div>
            {data.active_project_limit != null ? (
              <p className="text-sm text-muted">
                Active projects: {data.active_projects} / {data.active_project_limit}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2 pt-2">
              <Button variant="primary" onClick={() => checkout("pro")}>
                Upgrade to Pro
              </Button>
              <Button variant="secondary" onClick={() => openUpgrade("active_projects_limit")}>
                Add project slot
              </Button>
              <Button variant="ghost" disabled={portalBusy} onClick={openPortal}>
                {portalBusy ? "Opening…" : "Manage billing"}
              </Button>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted">
            Sign in with <Link href="/login" className="text-accent underline">accounts mode</Link> to view billing.
          </p>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="font-semibold text-ink">Downgrade</h2>
        <p className="mt-2 text-sm text-muted">
          Downgrading re-gates build features (designer, automations, export). Operate tools stay available. Your
          connections and project history remain.
        </p>
        {lostFeatures.length > 0 ? (
          <ul className="mt-3 list-inside list-disc text-sm text-muted">
            {lostFeatures.slice(0, 8).map((f) => (
              <li key={f.feature_key}>
                {f.feature_key}: {f.from} → {f.to}
              </li>
            ))}
          </ul>
        ) : null}
        <Button variant="ghost" className="mt-3" onClick={openPortal}>
          Change plan in portal
        </Button>
      </Card>

      <Link href="/pricing" className="text-sm text-accent hover:underline">
        Compare plans
      </Link>
    </div>
  );
}

export default function BillingSettingsPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted">Loading billing…</div>}>
      <BillingContent />
    </Suspense>
  );
}
