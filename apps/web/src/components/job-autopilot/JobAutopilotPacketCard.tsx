"use client";

import { Card } from "@/components/ui/layout-primitives";
import type { JobPacket } from "@/lib/api";
import { isStockOnlyPacket } from "@/lib/job-autopilot-journey";

type JobAutopilotPacketCardProps = {
  packet: JobPacket;
  connectionKind?: string | null;
  sandbox?: boolean;
};

export function JobAutopilotPacketCard({
  packet,
  connectionKind,
  sandbox,
}: JobAutopilotPacketCardProps) {
  const stockOnly = isStockOnlyPacket(packet);
  return (
    <Card className="p-5" data-testid="job-packet-card">
      <h2 className="text-lg font-semibold text-ink">Job packet</h2>
      <p className="mt-1 text-sm text-muted">
        Stock-first plan. Custom <code>x_*</code> is residual only. This is not a ModuleSpec.
      </p>
      {packet.structured_brief ? (
        <pre
          className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-surface-muted p-3 text-xs text-ink"
          data-testid="job-structured-brief"
        >
          {packet.structured_brief}
        </pre>
      ) : null}
      <dl className="job-packet-facts mt-4">
        <div>
          <dt>Domain</dt>
          <dd>
            {packet.domain_label}
            {packet.country_code ? ` · ${packet.country_code}` : ""}
            {packet.currency ? ` · ${packet.currency}` : ""}
            {packet.l10n_module ? ` · ${packet.l10n_module}` : ""}
          </dd>
        </div>
        <div>
          <dt>Stock apps</dt>
          <dd>{packet.stock_apps.join(", ") || "None named"}</dd>
        </div>
        <div>
          <dt>Connectors</dt>
          <dd>{packet.connectors?.length ? packet.connectors.join(" → ") : "None detected"}</dd>
        </div>
        <div>
          <dt>Custom residual</dt>
          <dd>
            {stockOnly
              ? "None — stock and data only"
              : packet.custom_residuals.map((r) => `${r.model} (${r.key})`).join(", ")}
          </dd>
        </div>
        {packet.data_files.length ? (
          <div>
            <dt>Files</dt>
            <dd>{packet.data_files.map((f) => `${f.filename}→${f.doc_type}`).join(", ")}</dd>
          </div>
        ) : null}
        {packet.grounding?.length ? (
          <div>
            <dt>Client-doc grounding</dt>
            <dd>{packet.grounding.length} chunk(s)</dd>
          </div>
        ) : null}
      </dl>
      {connectionKind ? (
        <p className="mt-3 text-xs text-muted">
          Connection: {connectionKind}
          {sandbox ? " · unattended sandbox" : " · run will need confirm"}
        </p>
      ) : null}
      {packet.decision_record.length ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted">
          {packet.decision_record.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
