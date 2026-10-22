"use client";

import type { BulkBlastRadius as Blast } from "@/lib/bulkSuiteScreen";
import { sanitizeBulkCopy } from "@/lib/bulkSuiteScreen";

type BulkBlastRadiusProps = {
  blast: Blast;
  testId?: string;
};

/** Honest blast radius before Run. Never invents counts. */
export function BulkBlastRadius({ blast, testId = "bulk-blast-radius" }: BulkBlastRadiusProps) {
  return (
    <div
      className="bu-blast"
      data-tone={blast.tone}
      data-known={blast.known ? "true" : "false"}
      data-testid={testId}
      role="status"
      aria-live="polite"
    >
      <p className="bu-blast-label" data-testid={`${testId}-label`}>
        {sanitizeBulkCopy(blast.label)}
      </p>
      <p className="bu-blast-detail" data-testid={`${testId}-detail`}>
        {sanitizeBulkCopy(blast.detail)}
      </p>
    </div>
  );
}
