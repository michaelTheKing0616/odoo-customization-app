"use client";

import { useState } from "react";

type Result = { ok: boolean; tier: string; error?: string; direction?: string; entities?: number };

export default function ContractStudioPage() {
  const [odooId, setOdooId] = useState("");
  const [thirdId, setThirdId] = useState("");
  const [direction, setDirection] = useState("inbound");
  const [conflict, setConflict] = useState("");
  const [money, setMoney] = useState(true);
  const [moneyPolicy, setMoneyPolicy] = useState("odoo_wins");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function validate(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    const contract: Record<string, unknown> = {
      odoo_connection_id: odooId,
      third_party_connection_id: thirdId,
      direction,
      webhook_signature_required: true,
      entities: [
        {
          name: "orders",
          money,
          money_policy: money ? moneyPolicy : null,
        },
      ],
    };
    if (direction === "two_way") {
      contract.conflict_resolution = conflict || null;
    }
    try {
      const response = await fetch("/api/bridge/contracts/validate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ contract }),
      });
      if (!response.ok) {
        setError("Validation could not be completed. Check the connection and try again.");
        setResult(null);
        return;
      }
      setResult((await response.json()) as Result);
    } catch {
      setError("Validation could not be completed. Check the connection and try again.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-lg font-semibold text-ink">Contract Studio</h1>
        <p className="text-sm text-muted">Tier I checks the contract. Secrets stay on the connection.</p>
      </header>
      <form className="flex flex-col gap-4" onSubmit={(event) => void validate(event)}>
        <label className="flex flex-col gap-1 text-sm text-ink">
          Odoo connection
          <input className="rounded-md border border-border bg-surface px-3 py-2" value={odooId} onChange={(e) => setOdooId(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink">
          Third-party connection
          <input className="rounded-md border border-border bg-surface px-3 py-2" value={thirdId} onChange={(e) => setThirdId(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink">
          Direction
          <select className="rounded-md border border-border bg-surface px-3 py-2" value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="inbound">Inbound</option>
            <option value="outbound">Outbound</option>
            <option value="two_way">Two-way</option>
          </select>
        </label>
        {direction === "two_way" ? (
          <label className="flex flex-col gap-1 text-sm text-ink">
            Conflict resolution
            <select className="rounded-md border border-border bg-surface px-3 py-2" value={conflict} onChange={(e) => setConflict(e.target.value)} required>
              <option value="">Choose</option>
              <option value="odoo_wins">Odoo wins</option>
              <option value="remote_wins">Remote wins</option>
              <option value="manual">Manual</option>
            </select>
          </label>
        ) : null}
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={money} onChange={(e) => setMoney(e.target.checked)} />
          Orders carry money
        </label>
        {money ? (
          <label className="flex flex-col gap-1 text-sm text-ink">
            Money policy
            <select className="rounded-md border border-border bg-surface px-3 py-2" value={moneyPolicy} onChange={(e) => setMoneyPolicy(e.target.value)}>
              <option value="odoo_wins">Odoo wins</option>
              <option value="remote_wins">Remote wins</option>
              <option value="manual">Manual</option>
            </select>
          </label>
        ) : null}
        <button type="submit" className="rounded-md bg-accent px-3 py-2 text-sm text-on-accent">
          Validate tier I
        </button>
      </form>
      {loading ? <div className="motion-safe:animate-pulse h-16 rounded-md bg-muted" /> : null}
      {error ? (
        <p className="rounded-md border border-danger px-3 py-2 text-sm text-ink" role="alert">
          {error}
        </p>
      ) : null}
      {result ? (
        <p className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink" role="status">
          {result.ok ? `Tier ${result.tier} passed for ${result.direction}.` : result.error}
        </p>
      ) : null}
    </main>
  );
}
