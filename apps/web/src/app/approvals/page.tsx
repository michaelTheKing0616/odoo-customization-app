"use client";

import { useState } from "react";

type Plan = {
  plan_hash: string;
  goal: string;
  status: string;
  max_risk: string;
  environment: string;
  expires_at: string;
  changes: { type: string }[];
};

const EMPTY = "No plans are waiting. A change appears here only after the engine validates it.";

export default function ApprovalsPage() {
  const [connectionId, setConnectionId] = useState("");
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
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
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
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
      {loading ? <div className="motion-safe:animate-pulse h-24 rounded-md bg-muted" /> : null}
      {error ? (
        <p className="rounded-md border border-danger bg-danger/10 px-3 py-2 text-sm text-ink" role="alert">
          {error}
        </p>
      ) : null}
      {plans && plans.length === 0 ? <p className="text-sm text-muted">{EMPTY}</p> : null}
      <ul className="flex flex-col gap-3">
        {(plans ?? []).map((plan) => (
          <li key={plan.plan_hash} className="rounded-md border border-border bg-surface px-4 py-3">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-medium text-ink">{plan.goal}</h2>
              <span className="font-mono text-xs text-muted">{plan.max_risk}</span>
            </div>
            <p className="mt-1 font-mono text-xs text-muted">
              {plan.plan_hash} · {plan.status} · {plan.environment}
            </p>
            <p className="mt-2 text-sm text-ink">{plan.changes.map((change) => change.type).join(", ")}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
