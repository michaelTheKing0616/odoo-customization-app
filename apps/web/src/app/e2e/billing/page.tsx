"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BillingDesk, type BillingActionError, type BillingView } from "@/components/billing/BillingDesk";
import { UpgradeSheet } from "@/components/billing/UpgradeSheet";
import type { BillingPlansCatalog, EntitlementsOut } from "@/lib/api";
import type { LostFeature } from "@/lib/billingScreen";
import "@/components/billing/billing-desk.css";

/**
 * UI-S-42 billing harness. Fixtures mirror the real registry in apps/api/app/entitlements.py
 * (PLAN_PRICING, FEATURE_MATRIX, DISPLAY_FEATURE_CATALOG). No invented prices.
 * /e2e/billing?state=trial|active|free|choose|past-due|internal|upgraded|portal-error|at-limit|loading|empty|error
 */

const STATES = [
  "trial",
  "active",
  "free",
  "choose",
  "past-due",
  "internal",
  "upgraded",
  "portal-error",
  "at-limit",
  "loading",
  "empty",
  "error",
] as const;
type HarnessState = (typeof STATES)[number];

const ROW = (plan: string, values: Record<string, string>) => values[plan];
const MATRIX: Record<string, Record<string, string>> = {
  connections_limit: { free_solo: "1", pro: "5", business: "5", agency: "unlimited", internal: "unlimited" },
  active_projects_limit: { free_solo: "1", pro: "3", business: "10", agency: "25", internal: "unlimited" },
  designer: { free_solo: "false", pro: "true", business: "true", agency: "true", internal: "true" },
  automations: { free_solo: "false", pro: "true", business: "true", agency: "true", internal: "true" },
  approvals: { free_solo: "false", pro: "true", business: "true", agency: "true", internal: "true" },
  module_export: { free_solo: "false", pro: "true", business: "true", agency: "true", internal: "true" },
  ai_draft: { free_solo: "false", pro: "true", business: "true", agency: "true", internal: "true" },
  bulk_suite: { free_solo: "false", pro: "false", business: "true", agency: "true", internal: "true" },
  pipelines: { free_solo: "false", pro: "false", business: "true", agency: "true", internal: "true" },
  expert: { free_solo: "false", pro: "false", business: "true", agency: "true", internal: "true" },
  dev_tools: { free_solo: "false", pro: "false", business: "true", agency: "true", internal: "true" },
  white_label: { free_solo: "false", pro: "false", business: "false", agency: "true", internal: "true" },
};

function featuresFor(plan: string): Record<string, string> {
  return Object.fromEntries(Object.entries(MATRIX).map(([k, v]) => [k, ROW(plan, v) ?? "false"]));
}

const CATALOG: BillingPlansCatalog = {
  tier_order: ["free_solo", "pro", "business", "agency"],
  display_features: [
    { key: "connections_limit", label: "Odoo connections" },
    { key: "active_projects_limit", label: "Active projects" },
    { key: "designer", label: "View designer" },
    { key: "automations", label: "Automations" },
    { key: "module_export", label: "Module export + sandbox" },
    { key: "bulk_suite", label: "Bulk suite" },
    { key: "expert", label: "Odoo Expert" },
    { key: "dev_tools", label: "Code Studio & developer tools" },
  ],
  project_pass: { display_name: "Project Pass", one_time_usd: 299 },
  plans: [
    { id: "free_solo", display_name: "Free Solo", features: featuresFor("free_solo"), monthly_usd: 0, extra_slot_monthly_usd: null },
    { id: "pro", display_name: "Pro", features: featuresFor("pro"), monthly_usd: 39, extra_slot_monthly_usd: 15 },
    { id: "business", display_name: "Business", features: featuresFor("business"), monthly_usd: 149, extra_slot_monthly_usd: 10 },
    { id: "agency", display_name: "Agency", features: featuresFor("agency"), monthly_usd: 399, extra_slot_monthly_usd: null },
  ],
};

function lostFor(plan: string): LostFeature[] {
  const from = featuresFor(plan);
  const to = featuresFor("free_solo");
  const rank = (v: string) => (v === "unlimited" ? 1e9 : v === "true" ? 1 : Number(v) || 0);
  return Object.keys(from)
    .filter((k) => rank(from[k]) > rank(to[k]))
    .map((k) => ({ feature_key: k, from: from[k], to: to[k] }));
}

const DAY = 86_400_000;

function fixture(state: HarnessState, now: number): {
  view: BillingView;
  data: EntitlementsOut | null;
  actionError?: BillingActionError | null;
  returned?: { upgraded?: boolean; slots?: boolean };
  chooser?: boolean;
  loadError?: string;
} {
  const iso = (days: number) => new Date(now + days * DAY).toISOString();
  const base = (plan: string, over: Partial<EntitlementsOut> = {}): EntitlementsOut => ({
    workspace_id: "ws_7f3a9c",
    plan_id: plan,
    subscription_status: "active",
    features: featuresFor(plan),
    extra_project_slots: 0,
    active_projects: 1,
    active_project_limit: Number(featuresFor(plan).active_projects_limit) || null,
    trial_ends_at: null,
    current_period_end: null,
    ...over,
  });
  switch (state) {
    case "trial":
      return {
        view: "ready",
        data: base("business", { subscription_status: "trialing", trial_ends_at: iso(2), active_projects: 4 }),
      };
    case "active":
      return {
        view: "ready",
        data: base("pro", {
          extra_project_slots: 2,
          active_project_limit: 5,
          active_projects: 3,
          current_period_end: iso(24),
        }),
      };
    case "free":
      return { view: "ready", data: base("free_solo", { active_projects: 0 }) };
    case "choose":
      return { view: "ready", data: base("free_solo", { active_projects: 1 }), chooser: true };
    case "past-due":
      return {
        view: "ready",
        data: base("business", { subscription_status: "past_due", active_projects: 6, current_period_end: iso(-3) }),
      };
    case "internal":
      return {
        view: "ready",
        data: base("internal", { workspace_id: "local-dev", active_projects: 0, active_project_limit: null }),
      };
    case "upgraded":
      return {
        view: "ready",
        data: base("pro", { active_projects: 2, current_period_end: iso(30) }),
        returned: { upgraded: true },
      };
    case "portal-error":
      return {
        view: "ready",
        data: base("business", { subscription_status: "trialing", trial_ends_at: iso(9), active_projects: 2 }),
        actionError: { context: "portal", source: "billing", message: "No billing customer on file" },
      };
    case "at-limit":
      return {
        view: "ready",
        data: base("pro", { active_projects: 3, active_project_limit: 3, current_period_end: iso(11) }),
      };
    case "loading":
      return { view: "loading", data: null };
    case "empty":
      return { view: "empty", data: null };
    case "error":
      return { view: "error", data: null, loadError: "Request failed (500)" };
  }
}

function BillingHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const params = useSearchParams();
  const raw = params.get("state") || "trial";
  const state = (STATES.includes(raw as HarnessState) ? raw : "trial") as HarnessState;
  const [now] = useState(() => Date.now());
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [busy, setBusy] = useState<"plan" | "billing" | null>(null);
  const [checkoutBusy, setCheckoutBusy] = useState<string | null>(null);
  const fx = fixture(state, now);
  const [actionError, setActionError] = useState<BillingActionError | null>(fx.actionError ?? null);

  if (!enabled) {
    return <p>E2E harness disabled</p>;
  }

  return (
    <div className="bd-harness" data-harness-state={state}>
      <BillingDesk
        key={state}
        view={fx.view}
        data={fx.data}
        catalog={fx.view === "loading" ? null : CATALOG}
        lostFeatures={fx.data ? lostFor(fx.data.plan_id) : []}
        loadError={fx.loadError}
        returned={fx.returned}
        actionError={actionError}
        portalBusy={busy}
        checkoutBusy={checkoutBusy}
        defaultChooserOpen={fx.chooser}
        now={now}
        onManagePlan={() => setBusy("plan")}
        onManageBilling={() => setBusy("billing")}
        onCheckout={(id) => setCheckoutBusy(id)}
        onAddSlot={() => setUpgradeOpen(true)}
        onDismissError={() => setActionError(null)}
      />
      <UpgradeSheet open={upgradeOpen} onOpenChange={setUpgradeOpen} featureKey="active_projects_limit" />
    </div>
  );
}

export default function E2EBillingHarnessPage() {
  return (
    <Suspense fallback={null}>
      <BillingHarnessInner />
    </Suspense>
  );
}
