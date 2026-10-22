"use client";

import { POWER_OPS_STEPS, type PowerOpsStepIndex } from "@/lib/powerOpsScreen";

type PowerOpsStageRailProps = {
  step: PowerOpsStepIndex;
};

export function PowerOpsStageRail({ step }: PowerOpsStageRailProps) {
  return (
    <ol className="po-rail" data-testid="power-ops-stage-rail" aria-label="Power Ops stages">
      {POWER_OPS_STEPS.map((label, i) => {
        const index = (i + 1) as PowerOpsStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li
            key={label}
            className="po-rail-step"
            data-state={state}
            data-testid={`power-ops-step-${label === "Test run" ? "dry-run" : label.toLowerCase()}`}
          >
            <span className="po-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
