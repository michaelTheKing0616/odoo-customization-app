"use client";

import { IDGEN_STEPS, type IdGenStepIndex } from "@/lib/idGeneratorScreen";

type IdGeneratorStageRailProps = {
  step: IdGenStepIndex;
};

export function IdGeneratorStageRail({ step }: IdGeneratorStageRailProps) {
  return (
    <ol className="ig-rail" data-testid="id-generator-stage-rail" aria-label="ID Generator stages">
      {IDGEN_STEPS.map((label, i) => {
        const index = (i + 1) as IdGenStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li
            key={label}
            className="ig-rail-step"
            data-state={state}
            data-testid={`id-generator-step-${label.toLowerCase()}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="ig-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
