"use client";

import { CONFIG_STEPS, type ConfigStepIndex } from "@/lib/configScreen";

type ConfigStageRailProps = {
  step: ConfigStepIndex;
};

export function ConfigStageRail({ step }: ConfigStageRailProps) {
  return (
    <ol className="cfg-rail" data-testid="config-stage-rail" aria-label="Config stages">
      {CONFIG_STEPS.map((label, i) => {
        const index = (i + 1) as ConfigStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li
            key={label}
            className="cfg-rail-step"
            data-state={state}
            data-testid={`config-step-${label === "Test run" ? "dry-run" : label.toLowerCase()}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="cfg-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
