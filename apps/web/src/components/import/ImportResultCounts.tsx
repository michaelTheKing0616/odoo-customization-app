"use client";

import { RollingNumber } from "@/components/ui/craft";

import type { ImportCountStrip } from "@/lib/importScreen";

type ImportResultCountsProps = {
  strip: ImportCountStrip;
  testId?: string;
};

export function ImportResultCounts({ strip, testId = "import-result-counts" }: ImportResultCountsProps) {
  const cells: Array<{ key: string; label: string; value: number; tone?: "danger" | "success" }> = [
    {
      key: "created",
      label: "Create",
      value: strip.created,
      tone: strip.created > 0 ? "success" : undefined,
    },
    {
      key: "updated",
      label: "Update",
      value: strip.updated,
      tone: strip.updated > 0 ? "success" : undefined,
    },
    {
      key: "skipped",
      label: "Skip",
      value: strip.skipped,
    },
    {
      key: "failed",
      label: "Error",
      value: strip.failed,
      tone: strip.failed > 0 ? "danger" : undefined,
    },
  ];

  return (
    <div
      className="im-counts"
      data-testid={testId}
      data-dry-run={strip.dryRun ? "true" : "false"}
      aria-label={strip.dryRun ? "Test run counts" : "Commit counts"}
    >
      {cells.map((c) => (
        <div key={c.key} className="im-count" data-tone={c.tone} data-testid={`${testId}-${c.key}`}>
          <span className="im-count-label">{c.label}</span>
          <span className="im-count-value"><RollingNumber value={c.value} /></span>
        </div>
      ))}
    </div>
  );
}
