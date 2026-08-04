"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { UpgradeSheet } from "@/components/billing/UpgradeSheet";

export default function E2EBillingHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const trialDays = 2;

  if (!enabled) {
    return <p>E2E harness disabled</p>;
  }

  return (
    <main className="space-y-6 p-8">
      <h1 className="text-lg font-semibold">Billing e2e harness</h1>

      <Callout variant="warning" title={`Trial ends in ${trialDays} days`} testId="trial-banner">
        Add a payment method before trial ends to keep Business features.
      </Callout>

      <div className="rounded-lg border border-border-subtle p-4" data-testid="downgrade-summary">
        <h2 className="font-semibold">Downgrade preview</h2>
        <ul className="mt-2 list-inside list-disc text-sm text-muted">
          <li>designer: true → false</li>
          <li>bulk_suite: true → false</li>
        </ul>
      </div>

      <Button variant="primary" onClick={() => setUpgradeOpen(true)} data-testid="open-upgrade">
        Open upgrade sheet
      </Button>

      <Link href="/pricing" className="text-sm text-accent underline" data-testid="pricing-link">
        Compare plans
      </Link>

      <UpgradeSheet open={upgradeOpen} onOpenChange={setUpgradeOpen} featureKey="active_projects_limit" />
    </main>
  );
}
