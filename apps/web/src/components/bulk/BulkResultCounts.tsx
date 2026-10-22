"use client";

import { RollingNumber } from "@/components/ui/craft";

type BulkResultCountsProps = {
  total: number;
  succeeded: number;
  failed: number;
  dryRun?: boolean;
  testId?: string;
};

export function BulkResultCounts({
  total,
  succeeded,
  failed,
  dryRun = false,
  testId = "bulk-result-counts",
}: BulkResultCountsProps) {
  const cells: Array<{ key: string; label: string; value: number; tone?: "danger" | "success" }> = [
    {
      key: "total",
      label: "Total",
      value: total,
    },
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
      className="bu-counts"
      data-testid={testId}
      data-dry-run={dryRun ? "true" : "false"}
      aria-label={dryRun ? "Test run counts" : "Run counts"}
    >
      {cells.map((c) => (
        <div key={c.key} className="bu-count" data-tone={c.tone} data-testid={`${testId}-${c.key}`}>
          <span className="bu-count-label">{c.label}</span>
          <span className="bu-count-value"><RollingNumber value={c.value} /></span>
        </div>
      ))}
    </div>
  );
}
