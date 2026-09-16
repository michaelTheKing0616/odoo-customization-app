"use client";

import Link from "next/link";
import type { CapabilityMatrix, Connection } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { expertDestinationHref } from "@/lib/expert-journey";

type Props = {
  connection: Connection;
  capabilities: CapabilityMatrix | null | undefined;
  onReprobe?: () => void;
  probing?: boolean;
};

function editionLabel(edition: string | undefined): string {
  const e = (edition || "").toLowerCase();
  if (e.includes("enterprise")) return "Enterprise";
  if (e.includes("community")) return "Community";
  return edition || "Unknown edition";
}

/**
 * Human-readable capabilities postcard (UI DESIGN BOT / Build Spec delight).
 * Not an engineer dump — probe details stay in CapabilityProbePanel.
 */
export function CapabilitiesPostcard({
  connection,
  capabilities,
  onReprobe,
  probing = false,
}: Props) {
  const major = capabilities?.major;
  const version =
    capabilities?.server_version || connection.server_version || "version unknown";
  const ga = capabilities?.ga;
  const supported = capabilities?.supported?.length ?? 0;
  const unsupported = capabilities?.unsupported?.length ?? 0;
  const hosting = capabilities?.hosting_hint;
  const writeMode = connection.write_mode || "standard";

  return (
    <Card className="mt-3 p-4" data-testid="capabilities-postcard">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Capabilities postcard
          </p>
          <h2 className="mt-1 text-base font-semibold text-ink">
            {connection.name || "Connection"}
          </h2>
          <p className="mt-1 text-sm text-muted">
            {editionLabel(capabilities?.edition)}
            {major != null ? ` · Odoo ${major}` : ""}
            {` · ${version}`}
            {ga === true ? " · GA matrix match" : ga === false ? " · outside GA matrix" : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="secondary" size="sm">
            <Link href={expertDestinationHref(connection.id)}>Ask Expert</Link>
          </Button>
          {onReprobe ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={probing}
              onClick={onReprobe}
            >
              {probing ? "Probing…" : "Re-probe"}
            </Button>
          ) : null}
        </div>
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Write mode
          </dt>
          <dd className="mt-0.5 text-sm text-ink">{writeMode}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Available
          </dt>
          <dd className="mt-0.5 text-sm text-ink">
            {capabilities
              ? `${supported} feature${supported === 1 ? "" : "s"}`
              : "Probe to learn"}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Unavailable here
          </dt>
          <dd className="mt-0.5 text-sm text-ink">
            {capabilities
              ? unsupported === 0
                ? "None flagged"
                : `${unsupported} gated / version-locked`
              : "—"}
          </dd>
        </div>
      </dl>

      {hosting ? (
        <p className="mt-3 text-sm text-muted" data-testid="capabilities-postcard-hosting">
          Hosting: {hosting}
        </p>
      ) : null}

      {capabilities?.message ? (
        <p className="mt-2 text-sm text-muted" data-testid="capabilities-postcard-message">
          {capabilities.message}
        </p>
      ) : (
        <p className="mt-2 text-sm text-muted">
          Probe the connection to refresh version and feature locks. Locked features stay honest —
          we do not fake Enterprise Studio.
        </p>
      )}

      {capabilities?.unsupported && capabilities.unsupported.length > 0 ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-muted hover:text-ink">
            Why some features are locked
          </summary>
          <ul className="mt-2 space-y-1 text-sm text-muted">
            {capabilities.unsupported.slice(0, 8).map((row) => (
              <li key={row.id}>
                <span className="text-ink">{row.label}</span>
                {row.reason ? ` — ${row.reason}` : ""}
              </li>
            ))}
            {capabilities.unsupported.length > 8 ? (
              <li>+{capabilities.unsupported.length - 8} more in probe details</li>
            ) : null}
          </ul>
        </details>
      ) : null}
    </Card>
  );
}
