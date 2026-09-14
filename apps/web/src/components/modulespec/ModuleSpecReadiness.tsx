"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { cn } from "@/lib/cn";
import type { ValidateLiveResult } from "@/lib/api";
import {
  liveItemTone,
  liveValidationHeadline,
  type LocalReadinessReport,
} from "@/lib/modulespec-journey";

const TONE: Record<string, { variant: "success" | "warning" | "danger" | "info" | "default"; label: string }> = {
  pass: { variant: "success", label: "Pass" },
  warn: { variant: "warning", label: "Review" },
  fail: { variant: "danger", label: "Block" },
  skip: { variant: "info", label: "Skip" },
};

type ModuleSpecReadinessProps = {
  report: LocalReadinessReport;
  live?: ValidateLiveResult | null;
  validating?: boolean;
  canValidate?: boolean;
  validateBlocked?: string | null;
  onValidate: () => void;
};

export function ModuleSpecReadiness({
  report,
  live,
  validating,
  canValidate,
  validateBlocked,
  onValidate,
}: ModuleSpecReadinessProps) {
  const liveHeadline = liveValidationHeadline(live ?? null);
  return (
    <Card className="p-5" data-testid="modulespec-readiness">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Validation and readiness</h2>
          <p className="mt-1 text-sm text-muted" data-testid="modulespec-readiness-headline">
            {report.headline}
          </p>
          <p className="mt-1 text-sm text-muted" data-testid="modulespec-readiness-body">
            {report.body}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={!canValidate || validating}
          loading={validating}
          title={validateBlocked ?? undefined}
          onClick={onValidate}
          data-testid="modulespec-validate"
        >
          Validate on this Odoo
        </Button>
      </div>
      <ul className="ms-readiness-grid mt-4" data-testid="modulespec-readiness-items">
        {report.items.map((item) => {
          const tone = TONE[item.status] ?? TONE.warn;
          return (
            <li
              key={item.id}
              className={cn("ms-readiness-item", `is-${item.status}`)}
              data-readiness={item.id}
            >
              <Badge variant={tone.variant}>{tone.label}</Badge>
              <div>
                <p className="text-sm font-medium text-ink">{item.label}</p>
                <p className="mt-0.5 text-xs text-muted">{item.message}</p>
              </div>
            </li>
          );
        })}
      </ul>
      {liveHeadline ? (
        <div className="mt-4" data-testid="modulespec-live-validate">
          <p className="text-sm font-medium text-ink">{liveHeadline}</p>
          {live?.message ? <p className="mt-1 text-xs text-muted">{live.message}</p> : null}
          {live?.items?.length ? (
            <ul className="mt-2 space-y-1 text-xs text-muted">
              {live.items.slice(0, 12).map((item) => (
                <li key={item.item_id} data-live-status={liveItemTone(item.status)}>
                  {item.category}: {item.message}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
