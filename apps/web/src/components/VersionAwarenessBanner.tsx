"use client";

import type { CapabilityMatrix } from "@/lib/api";
import { isEnterpriseEdition, isExperimentalMajor } from "@/lib/capabilities";

type Props = {
  capabilities: CapabilityMatrix | null | undefined;
  /** Extra note for surfaces with known caveats (menus/reports on ≤17). */
  caveat?: string | null;
  className?: string;
};

/**
 * Compact experimental + Enterprise banners for connection-scoped builder pages.
 * Prefer this over per-page copy so messaging stays consistent.
 */
export function VersionAwarenessBanner({
  capabilities,
  caveat = null,
  className = "",
}: Props) {
  if (!capabilities) {
    return (
      <p className={`mt-3 text-sm text-[#e8d09f] ${className}`}>
        Version capabilities unknown — open Connect / Browse and re-probe before
        relying on advanced actions.
      </p>
    );
  }

  return (
    <div className={`mt-3 space-y-2 ${className}`}>
      {isExperimentalMajor(capabilities) && (
        <p className="text-sm text-[#e8d09f]">
          Connected to Odoo {capabilities.major} (experimental). Some actions may be
          unavailable — expand the capability panel on Connect / Browse for details.
        </p>
      )}
      {isEnterpriseEdition(capabilities) && (
        <p className="text-sm text-[#e8d09f]">
          Enterprise edition detected. Public ORM only — Studio /{" "}
          <code className="text-xs">web_studio</code> source is never used.
        </p>
      )}
      {caveat && <p className="text-sm text-[#c9b896]">{caveat}</p>}
    </div>
  );
}
