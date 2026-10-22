"use client";

import * as React from "react";
import { Button } from "@/components/ui/Button";
import { request } from "@/lib/api/client";

type Info = { company: string; customers: number; products: number; allowed: boolean; why_not: string | null };

/** Touch 126: load a believable Lagos sample company. Shown only on ingenium_* or test-copy databases. */
export function SampleCompanyCard({ connectionId }: { connectionId: string }) {
  const [info, setInfo] = React.useState<Info | null>(null);
  const [state, setState] = React.useState<"idle" | "confirm" | "loading" | "done" | "error">("idle");
  const [msg, setMsg] = React.useState("");
  React.useEffect(() => {
    request<Info>(`/api/connections/${connectionId}/sample-company`).then(setInfo, () => setInfo(null));
  }, [connectionId]);
  if (!info?.allowed) return null;
  const load = async () => {
    setState("loading");
    try {
      const r = await request<{ created: Record<string, number> }>(`/api/connections/${connectionId}/sample-company`, { method: "POST" });
      setMsg(`Added ${r.created["res.partner"] ?? 0} customers and ${r.created["product.template"] ?? 0} products.`);
      setState("done");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Couldn't load the sample company.");
      setState("error");
    }
  };
  return (
    <section className="mt-6 rounded-md border border-border-subtle p-4" data-testid="sample-company">
      <h2 className="text-sm font-semibold text-ink">Try it with a sample company</h2>
      <p className="mt-1 text-sm text-muted">{`${info.company}, a Lagos furniture maker: ${info.customers} customers and ${info.products} products in naira with 7.5% VAT. Only for test databases.`}</p>
      <div className="mt-3 flex items-center gap-2">
        {state === "confirm" ? (
          <>
            <Button size="sm" variant="primary" onClick={() => void load()} data-testid="sample-company-confirm">Yes, add the sample records</Button>
            <Button size="sm" variant="ghost" onClick={() => setState("idle")}>Cancel</Button>
          </>
        ) : (
          <Button size="sm" variant="secondary" disabled={state === "loading" || state === "done"} loading={state === "loading"} onClick={() => setState("confirm")} data-testid="sample-company-load">Load sample company</Button>
        )}
        <span role="status" className="text-sm text-muted">{msg}</span>
      </div>
    </section>
  );
}
