"use client";

import { BULK_STEPS, type BulkStepIndex } from "@/lib/bulkSuiteScreen";

type BulkOpRailProps = {
  step: BulkStepIndex;
};

export function BulkOpRail({ step }: BulkOpRailProps) {
  return (
    <ol className="bu-rail" data-testid="bulk-stage-rail" aria-label="Bulk Suite stages">
      {BULK_STEPS.map((label, i) => {
        const index = (i + 1) as BulkStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li
            key={label}
            className="bu-rail-step"
            data-state={state}
            data-testid={`bulk-step-${label === "Test run" ? "dry-run" : label.toLowerCase()}`}
          >
            <span className="bu-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
