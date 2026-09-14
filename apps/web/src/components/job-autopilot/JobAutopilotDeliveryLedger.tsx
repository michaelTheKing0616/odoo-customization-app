"use client";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/layout-primitives";
import type { JobAutopilotResult } from "@/lib/api";

type JobAutopilotDeliveryLedgerProps = {
  result: JobAutopilotResult;
};

export function JobAutopilotDeliveryLedger({ result }: JobAutopilotDeliveryLedgerProps) {
  const bootstrap = result.bootstrap;
  const connectors = result.connectors && !result.connectors.skipped ? result.connectors : null;
  const custom = result.custom;
  const ingest = result.ingest && !result.ingest.skipped ? result.ingest : null;
  if (!bootstrap && !connectors && !custom && !ingest) return null;

  return (
    <Card className="p-5" data-testid="job-delivery-ledger">
      <h2 className="text-lg font-semibold text-ink">Delivery</h2>
      <p className="mt-1 text-sm text-muted">
        Stock bootstrap, connectors, residual <code>x_*</code>, then data. Smoke lives on
        the scorecard.
      </p>
      <div className="mt-4 space-y-4 text-sm">
        {bootstrap ? (
          <section>
            <h3 className="text-sm font-medium text-ink">Stock bootstrap</h3>
            <p className="mt-1 text-muted">{bootstrap.message}</p>
            {bootstrap.installed.length ? (
              <p className="mt-1">Installed: {bootstrap.installed.join(", ")}</p>
            ) : null}
            {bootstrap.skipped.length ? (
              <p className="mt-1">Skipped: {bootstrap.skipped.join(", ")}</p>
            ) : null}
            {bootstrap.warnings.length ? (
              <ul className="mt-1 list-disc space-y-1 pl-5 text-amber-800">
                {bootstrap.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}
            {bootstrap.probes.length ? (
              <ul className="mt-2 space-y-1">
                {bootstrap.probes.map((p, i) => (
                  <li key={`${p.name}-${i}`} className="flex flex-wrap items-start gap-2">
                    <Badge variant={p.ok ? "success" : "warning"}>{p.name}</Badge>
                    <span className="text-xs text-muted">{p.detail}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        ) : null}
        {connectors ? (
          <section>
            <h3 className="text-sm font-medium text-ink">Connectors</h3>
            <p className="mt-1 text-muted">{connectors.message}</p>
            {connectors.ran.length ? <p className="mt-1">Ran: {connectors.ran.join(", ")}</p> : null}
            {connectors.skipped_ids?.length ? (
              <p className="mt-1">Skipped: {connectors.skipped_ids.join(", ")}</p>
            ) : null}
            {connectors.failed.length ? (
              <p className="mt-1">Gaps: {connectors.failed.join(", ")}</p>
            ) : null}
            {connectors.steps.length ? (
              <ul className="mt-2 space-y-1">
                {connectors.steps.map((p, i) => (
                  <li key={`${p.name}-${i}`} className="flex flex-wrap items-start gap-2">
                    <Badge variant={p.ok ? "success" : "warning"}>{p.name}</Badge>
                    <span className="text-xs text-muted">{p.detail}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        ) : null}
        {custom ? (
          <section>
            <h3 className="text-sm font-medium text-ink">Custom residual</h3>
            <p className="mt-1 text-muted">
              {custom.skipped
                ? custom.reason || "Skipped."
                : custom.apply_message || "Applied."}
            </p>
            {custom.fields_relaxed ? (
              <p className="mt-1">Relaxed {custom.fields_relaxed} leftover required field(s).</p>
            ) : null}
            {custom.expert_score_after != null ? (
              <p className="mt-1">
                Expert-fix {custom.expert_score_before ?? "?"} → {custom.expert_score_after}
              </p>
            ) : null}
          </section>
        ) : null}
        {ingest ? (
          <section>
            <h3 className="text-sm font-medium text-ink">Data</h3>
            <p className="mt-1 text-muted">{ingest.message}</p>
            {ingest.source_rows || ingest.loaded_rows ? (
              <p className="mt-1">
                Rows: {ingest.loaded_rows ?? 0}/{ingest.source_rows ?? 0}
                {ingest.unmatched_m2o?.length
                  ? ` · unmatched M2O ${ingest.unmatched_m2o.length}`
                  : ""}
              </p>
            ) : null}
            {ingest.gaps.length ? (
              <ul className="mt-1 list-disc pl-5 text-muted">
                {ingest.gaps.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ) : null}
      </div>
    </Card>
  );
}
