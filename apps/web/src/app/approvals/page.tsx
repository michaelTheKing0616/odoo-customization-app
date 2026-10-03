"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { ListLayout, ListLayoutItem } from "@/components/ui/motion";

type Plan = {
  plan_hash: string;
  goal: string;
  status: string;
  max_risk: string;
  environment: string;
  expires_at: string;
  changes: { type: string }[];
};

export default function ApprovalsPage() {
  const [connectionId, setConnectionId] = useState("");
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [inboxHydrated, setInboxHydrated] = useState(false);

  async function load() {
    setLoading(true);
    setInboxHydrated(false);
    setError(null);
    try {
      const response = await fetch(`/api/inbox/plans?connection_id=${encodeURIComponent(connectionId)}`);
      if (response.status === 404) {
        setPlans([]);
        return;
      }
      if (!response.ok) {
        setError("The inbox could not be loaded. Check the connection id and try again.");
        setPlans(null);
        return;
      }
      const body = (await response.json()) as { plans: Plan[] };
      setPlans(body.plans);
    } catch {
      setError("The inbox could not be loaded. Check the connection and try again.");
      setPlans(null);
    } finally {
      setLoading(false);
      setInboxHydrated(true);
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10" data-testid="approvals-inbox-page">
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-ink">Approval inbox</h1>
        <p className="text-sm text-muted">
          Approve the plan fingerprint the engine produced. A card for another client is not listed.
        </p>
      </header>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void load();
        }}
      >
        <label className="flex min-w-64 flex-1 flex-col gap-1 text-sm text-ink">
          Connection
          <input
            className="rounded-md border border-border bg-surface px-3 py-2 text-ink"
            value={connectionId}
            onChange={(event) => setConnectionId(event.target.value)}
            required
          />
        </label>
        <button type="submit" className="rounded-md bg-accent px-3 py-2 text-sm text-on-accent">
          Show plans
        </button>
      </form>
      {loading ? (
        <div className="space-y-2" data-testid="approvals-inbox-loading">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}
      {error ? (
        <p className="rounded-md border border-danger bg-danger/10 px-3 py-2 text-sm text-ink" role="alert">
          {error}
        </p>
      ) : null}
      {inboxHydrated && plans && plans.length === 0 ? (
        <EmptyState
          title="No plans waiting for approval"
          description="Validated engine plans for this connection id will appear here after you run a gated change."
          action={
            <Button type="button" variant="secondary" size="sm" onClick={() => void load()}>
              Refresh inbox
            </Button>
          }
        />
      ) : null}
      <ListLayout stagger={false} className="flex flex-col gap-3">
        {(plans ?? []).map((plan, index) => (
          <ListLayoutItem
            key={plan.plan_hash}
            index={index}
            className="rounded-md border border-border bg-surface px-4 py-3"
          >
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-medium text-ink">{plan.goal}</h2>
              <span className="font-mono text-xs text-muted">{plan.max_risk}</span>
            </div>
            <p className="mt-1 font-mono text-xs text-muted">
              {plan.plan_hash} · {plan.status} · {plan.environment}
            </p>
            <p className="mt-2 text-sm text-ink">{plan.changes.map((change) => change.type).join(", ")}</p>
          </ListLayoutItem>
        ))}
      </ListLayout>
    </main>
  );
}
