"use client";

import { FLEET_STEPS, type FleetStepIndex } from "@/lib/fleetCommandScreen";

type FleetStageRailProps = {
  step: FleetStepIndex;
};

export function FleetStageRail({ step }: FleetStageRailProps) {
  return (
    <ol className="fc-rail" data-testid="fleet-stage-rail" aria-label="Fleet stages">
      {FLEET_STEPS.map((label, i) => {
        const index = (i + 1) as FleetStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        const slug = label.toLowerCase().replace(/\s+/g, "-");
        return (
          <li
            key={label}
            className="fc-rail-step"
            data-state={state}
            data-testid={`fleet-step-${slug}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="fc-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
