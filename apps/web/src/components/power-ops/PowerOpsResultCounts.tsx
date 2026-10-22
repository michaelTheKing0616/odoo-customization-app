"use client";

import { RollingNumber } from "@/components/ui/craft";

type PowerOpsResultCountsProps = {
  processed: number;
  succeeded: number;
  failed: number;
  dryRun?: boolean;
  testId?: string;
};

export function PowerOpsResultCounts({
  processed,
  succeeded,
  failed,
  dryRun = false,
  testId = "power-ops-result-counts",
}: PowerOpsResultCountsProps) {
  const cells: Array<{ key: string; label: string; value: number; tone?: "danger" | "success" }> = [
    { key: "processed", label: dryRun ? "Would process" : "Processed", value: processed },
    {
      key: "succeeded",
      label: dryRun ? "Would succeed" : "Succeeded",
      value: succeeded,
      tone: succeeded > 0 ? "success" : undefined,
    },
    {
      key: "failed",
      label: dryRun ? "Would fail" : "Failed",
      value: failed,
      tone: failed > 0 ? "danger" : undefined,
    },
  ];

  return (
    <div
      className="po-counts"
      data-testid={testId}
      data-dry-run={dryRun ? "true" : "false"}
      aria-label={dryRun ? "Test run counts" : "Run counts"}
    >
      {cells.map((c) => (
        <div key={c.key} className="po-count" data-tone={c.tone} data-testid={`${testId}-${c.key}`}>
          <span className="po-count-label">{c.label}</span>
          <span className="po-count-value"><RollingNumber value={c.value} /></span>
        </div>
      ))}
    </div>
  );
}
