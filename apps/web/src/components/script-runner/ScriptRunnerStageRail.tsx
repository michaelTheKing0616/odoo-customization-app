"use client";

import { SCRIPT_RUNNER_STEPS, type ScriptRunnerStepIndex } from "@/lib/scriptRunnerScreen";

type ScriptRunnerStageRailProps = {
  step: ScriptRunnerStepIndex;
};

export function ScriptRunnerStageRail({ step }: ScriptRunnerStageRailProps) {
  return (
    <ol className="sr-rail" data-testid="script-runner-stage-rail" aria-label="Script Runner stages">
      {SCRIPT_RUNNER_STEPS.map((label, i) => {
        const index = (i + 1) as ScriptRunnerStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li
            key={label}
            className="sr-rail-step"
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
            data-testid={`script-runner-step-${label.toLowerCase()}`}
          >
            <span className="sr-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
