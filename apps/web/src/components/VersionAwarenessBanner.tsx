"use client";

import type { CapabilityMatrix } from "@/lib/api";
import { isEnterpriseEdition, isExperimentalMajor } from "@/lib/capabilities";
import { Callout } from "@/components/ui/Callout";

type Props = {
  capabilities: CapabilityMatrix | null | undefined;
  /** Extra note for surfaces with known caveats (menus/reports on ≤17). */
  caveat?: string | null;
  className?: string;
};

/**
 * Compact experimental + Enterprise banners for connection-scoped builder pages.
 */
export function VersionAwarenessBanner({
  capabilities,
  caveat = null,
  className = "",
}: Props) {
  if (!capabilities) {
    return (
      <Callout variant="warning" title="Capabilities unknown" className={className}>
        Version capabilities unknown — open Connect and re-probe before relying on advanced
        actions.
      </Callout>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {isExperimentalMajor(capabilities) && (
        <Callout variant="warning" title={`Odoo ${capabilities.major} is experimental`}>
          Some actions may be unavailable — expand the capability panel on Connect for details.
        </Callout>
      )}
      {isEnterpriseEdition(capabilities) && (
        <Callout variant="info" title="Enterprise edition detected">
          Public ORM only — Studio / <code className="text-xs">web_studio</code> source is never
          used.
        </Callout>
      )}
      {caveat ? (
        <Callout variant="warning" title="Version caveat">
          {caveat}
        </Callout>
      ) : null}
    </div>
  );
}
