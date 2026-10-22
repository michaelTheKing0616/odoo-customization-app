"use client";

type IdGeneratorResultCountsProps = {
  total: number;
  changed: number;
  skipped: number;
  succeeded?: number;
  failed?: number;
  dryRun?: boolean;
  testId?: string;
};

export function IdGeneratorResultCounts({
  total,
  changed,
  skipped,
  succeeded,
  failed,
  dryRun,
  testId = "id-generator-counts",
}: IdGeneratorResultCountsProps) {
  const tiles: { label: string; value: number; tone?: "success" | "danger" | "accent" }[] = [
    { label: "Total", value: total },
    { label: "Changed", value: changed, tone: changed > 0 ? "accent" : undefined },
    { label: "Skipped", value: skipped },
  ];
  if (typeof succeeded === "number") {
    tiles.push({ label: "Succeeded", value: succeeded, tone: "success" });
  }
  if (typeof failed === "number") {
    tiles.push({ label: "Failed", value: failed, tone: failed > 0 ? "danger" : undefined });
  }

  return (
    <div className="ig-counts" data-testid={testId} data-dry-run={dryRun ? "true" : "false"}>
      {tiles.map((t) => (
        <div key={t.label} className="ig-count" data-tone={t.tone || "neutral"}>
          <span className="ig-count-label">{t.label}</span>
          <span className="ig-count-value">{t.value}</span>
        </div>
      ))}
    </div>
  );
}
