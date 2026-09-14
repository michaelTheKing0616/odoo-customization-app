"use client";

import { cn } from "@/lib/cn";
import { JOB_RUN_STEPS, jobRunStepDone } from "@/lib/job-autopilot-journey";

type JobAutopilotRunLedgerProps = {
  stages?: string[];
  currentStep?: string | null;
  compact?: boolean;
};

export function JobAutopilotRunLedger({
  stages,
  currentStep,
  compact,
}: JobAutopilotRunLedgerProps) {
  return (
    <ol
      className={cn("job-run-ledger", compact && "is-compact")}
      data-testid="job-run-ledger"
    >
      {JOB_RUN_STEPS.map((step) => {
        const done = jobRunStepDone(stages, step.id);
        const current = currentStep === step.id && !done;
        return (
          <li
            key={step.id}
            className={cn(
              "job-run-step",
              done && "is-done",
              current && "is-current",
            )}
            data-step={step.id}
          >
            <span className="job-run-step-mark" aria-hidden>
              {done ? "✓" : current ? "·" : ""}
            </span>
            <span className="job-run-step-label">{step.label}</span>
            <span className="job-run-step-state">
              {done ? "Done" : current ? "Running" : "Queued"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
