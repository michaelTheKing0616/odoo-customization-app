"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Plan = { id: string; display_name: string; monthly_usd: number | null };

/** Home plan chips from the same catalog as Pricing and Billing (FEATURE_AUDIT 21.1). */
export function PlanChips() {
  const [plans, setPlans] = React.useState<Plan[] | null>(null);
  React.useEffect(() => {
    api
      .billingPlans()
      .then((c) => setPlans((c?.plans ?? []) as Plan[]))
      .catch(() => setPlans([]));
  }, []);
  if (plans === null) return null;
  if (plans.length === 0) {
    return (
      <Link href="/pricing" className="rounded-full border border-border-subtle px-3 py-1">
        See plans and prices
      </Link>
    );
  }
  return (
    <>
      {plans.map((p) => (
        <span key={p.id} className="rounded-full border border-border-subtle px-3 py-1" data-testid={`home-plan-${p.id}`}>
          {p.display_name}
          {p.monthly_usd ? ` $${p.monthly_usd}/mo` : ""}
        </span>
      ))}
    </>
  );
}
