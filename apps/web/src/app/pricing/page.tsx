"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { api } from "@/lib/api";

const DISPLAY_FEATURES = [
  { key: "connections_limit", label: "Odoo connections" },
  { key: "active_projects_limit", label: "Active projects" },
  { key: "designer", label: "View designer" },
  { key: "automations", label: "Automations" },
  { key: "module_export", label: "Module export + sandbox" },
  { key: "bulk_suite", label: "Bulk suite" },
  { key: "expert", label: "Odoo Expert" },
];

const TIER_ORDER = ["free_solo", "pro", "business", "agency"];

function fmtFeature(value: string | undefined): string {
  if (!value || value === "false") return "—";
  if (value === "true") return "✓";
  if (value === "unlimited") return "Unlimited";
  return value;
}

function annualPrice(monthly: number): number {
  return monthly * 10;
}

const MONTHLY_USD: Record<string, number> = {
  free_solo: 0,
  pro: 39,
  business: 149,
  agency: 399,
};

export default function PricingPage() {
  const [annual, setAnnual] = useState(false);
  const [currency, setCurrency] = useState<"USD" | "NGN">("USD");
  const [plans, setPlans] = useState<Array<{ id: string; display_name: string; features: Record<string, string> }>>([]);

  useEffect(() => {
    api.billingPlans().then(setPlans).catch(() => setPlans([]));
  }, []);

  const ordered = TIER_ORDER.map((id) => plans.find((p) => p.id === id)).filter(Boolean) as typeof plans;

  return (
    <main className="min-h-screen bg-surface px-6 py-12">
      <div className="mx-auto max-w-6xl space-y-10">
        <PageHeader
          title="Pricing"
          description="Build features gate by plan. Operate tools — bulk, health checks, snapshots, Expert — never cost per project."
        />

        <div className="flex flex-wrap items-center gap-4">
          <div className="inline-flex rounded-lg border border-border-subtle p-1">
            <button
              type="button"
              className={`rounded-md px-3 py-1 text-sm ${!annual ? "bg-accent text-white" : "text-muted"}`}
              onClick={() => setAnnual(false)}
            >
              Monthly
            </button>
            <button
              type="button"
              className={`rounded-md px-3 py-1 text-sm ${annual ? "bg-accent text-white" : "text-muted"}`}
              onClick={() => setAnnual(true)}
            >
              Annual (2 months free)
            </button>
          </div>
          <div className="inline-flex rounded-lg border border-border-subtle p-1">
            <button
              type="button"
              className={`rounded-md px-3 py-1 text-sm ${currency === "USD" ? "bg-surface-muted" : "text-muted"}`}
              onClick={() => setCurrency("USD")}
            >
              USD (Stripe)
            </button>
            <button
              type="button"
              className={`rounded-md px-3 py-1 text-sm ${currency === "NGN" ? "bg-surface-muted" : "text-muted"}`}
              onClick={() => setCurrency("NGN")}
            >
              NGN (Paystack)
            </button>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-4">
          {ordered.map((plan) => {
            const monthly = MONTHLY_USD[plan.id] ?? 0;
            const price = annual ? annualPrice(monthly) : monthly;
            const suffix = annual ? "/yr" : "/mo";
            return (
              <Card key={plan.id} className="flex flex-col p-5">
                <h2 className="text-lg font-semibold text-ink">{plan.display_name}</h2>
                <p className="mt-2 text-2xl font-semibold text-ink">
                  {currency === "USD" ? `$${price}` : "Contact"}
                  <span className="text-sm font-normal text-muted">{monthly === 0 ? "" : suffix}</span>
                </p>
                <ul className="mt-4 flex-1 space-y-2 text-sm text-muted">
                  {DISPLAY_FEATURES.map((f) => (
                    <li key={f.key} className="flex justify-between gap-2">
                      <span>{f.label}</span>
                      <span className="text-ink">{fmtFeature(plan.features[f.key])}</span>
                    </li>
                  ))}
                </ul>
                <Button variant={plan.id === "pro" ? "primary" : "secondary"} className="mt-4" asChild>
                  <Link href={plan.id === "free_solo" ? "/signup" : "/settings/billing"}>
                    {plan.id === "free_solo" ? "Start free" : "Upgrade"}
                  </Link>
                </Button>
              </Card>
            );
          })}
        </div>

        <Card className="p-6">
          <h2 className="text-lg font-semibold text-ink">Project Pass — $299 one-time</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            Just need one app built? One active project with Pro-level build features for 60 days — often less than a
            short consultant engagement for a single workflow. After 60 days the project stays readable; upgrade anytime
            to keep editing.
          </p>
          <Button variant="secondary" className="mt-4" asChild>
            <Link href="/settings/billing?pass=1">Get Project Pass</Link>
          </Button>
        </Card>

        <section className="space-y-3 text-sm text-muted">
          <h2 className="text-md font-semibold text-ink">FAQ</h2>
          <p>
            <strong className="text-ink">Draft Studio / AI</strong> — runs on your machine via Ollama (or compatible
            API). We do not host models.
          </p>
          <p>
            <strong className="text-ink">Odoo Online</strong> — works where Community RPC allows; some automations need
            modules your plan may not include on Online.
          </p>
          <p>
            <strong className="text-ink">Cancel anytime</strong> — downgrade re-gates build features; your data stays.
          </p>
        </section>

        <footer className="text-sm text-muted">
          <Link href="/terms" className="hover:text-ink">
            Terms
          </Link>
          {" · "}
          <Link href="/privacy" className="hover:text-ink">
            Privacy
          </Link>
        </footer>
      </div>
    </main>
  );
}
