"use client";

type CronNextRunPreviewProps = {
  value: string;
  zoneLabel: string;
  testId?: string;
  caption?: string;
};

export function CronNextRunPreview({
  value,
  zoneLabel,
  testId = "cron-next-run-preview",
  caption = "Next run preview",
}: CronNextRunPreviewProps) {
  return (
    <div className="cr-next-run" data-testid={testId}>
      <span className="cr-next-run-label">{caption}</span>
      <span className="cr-next-run-value" data-testid={`${testId}-value`}>
        {value}
      </span>
      <span className="cr-next-run-zone" data-testid={`${testId}-zone`}>
        {zoneLabel}
      </span>
    </div>
  );
}
